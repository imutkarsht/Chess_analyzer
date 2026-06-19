"""
Platform-aware in-app updater for Chess Analyzer Pro.

Flow per platform
-----------------
Windows  → Download Setup.exe to %TEMP%
           → Launch with /VERYSILENT /NORESTART /CLOSEAPPLICATIONS
           → Inno Setup closes & replaces the app, then relaunches it
           → We call QApplication.quit()

macOS    → Download .dmg to ~/Downloads  (no silent mount — Gatekeeper)
           → Strip quarantine xattr so the first open isn't blocked
           → Open the DMG in Finder so the user drags to Applications
           → We call QApplication.quit()

Linux    → Download .AppImage to /tmp
           → Write a tiny shell script that waits for our PID to exit,
             moves the new AppImage into the old one's place, and relaunches
           → Launch that script detached
           → We call QApplication.quit()
"""

import os
import sys
import stat
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.logger import logger

# ---------------------------------------------------------------------------
# Platform constant
# ---------------------------------------------------------------------------
PLATFORM: str = sys.platform   # "win32" | "darwin" | "linux" | …


# ---------------------------------------------------------------------------
# Download worker
# ---------------------------------------------------------------------------
class DownloadWorker(QThread):
    """Downloads a URL to a local file in a background thread.

    Signals
    -------
    progress(int)   0–100 percent complete
    finished(str)   absolute local path of the downloaded file
    error(str)      human-readable error message
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url: str, dest_path: str, parent=None):
        super().__init__(parent)
        self.url       = url
        self.dest_path = dest_path
        self._cancelled = False

    def cancel(self):
        """Signal the worker to abort (best-effort — urllib doesn't stream-cancel)."""
        self._cancelled = True

    def run(self):
        try:
            def _reporthook(block_num: int, block_size: int, total_size: int):
                if self._cancelled:
                    raise RuntimeError("Download cancelled by user")
                if total_size > 0:
                    pct = min(100, int(block_num * block_size * 100 / total_size))
                    self.progress.emit(pct)

            logger.info(f"Downloading update: {self.url} → {self.dest_path}")
            urllib.request.urlretrieve(self.url, self.dest_path, reporthook=_reporthook)
            self.progress.emit(100)
            logger.info("Download complete")
            self.finished.emit(self.dest_path)

        except Exception as exc:
            if not self._cancelled:
                logger.error(f"Download failed: {exc}")
            # Clean up partial file
            try:
                if os.path.exists(self.dest_path):
                    os.remove(self.dest_path)
            except OSError:
                pass
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Destination path helpers
# ---------------------------------------------------------------------------
def _filename_from_url(url: str) -> str:
    """Extract the bare filename from a download URL."""
    return os.path.basename(urlparse(url).path) or "ChessAnalyzerPro-update"


def get_download_destination(url: str) -> str:
    """Return the full local path where the installer should be saved."""
    filename = _filename_from_url(url)
    if PLATFORM == "darwin":
        # Place in ~/Downloads — visible to the user, survives temp cleanup
        dl = Path.home() / "Downloads"
        dl.mkdir(parents=True, exist_ok=True)
        return str(dl / filename)
    else:
        return os.path.join(tempfile.gettempdir(), filename)


# ---------------------------------------------------------------------------
# Install / relaunch
# ---------------------------------------------------------------------------
def install_and_quit(local_path: str, quit_app_fn) -> None:
    """
    Execute the platform-specific install action, then call quit_app_fn().

    Parameters
    ----------
    local_path   : path to the downloaded installer file
    quit_app_fn  : callable that gracefully exits the Qt application
                   (e.g. ``QApplication.instance().quit``)
    """
    try:
        if PLATFORM == "win32":
            _install_windows(local_path)
        elif PLATFORM == "darwin":
            _install_macos(local_path)
        else:
            _install_linux(local_path)
    except Exception as exc:
        logger.error(f"Install step failed: {exc}")
        raise
    finally:
        quit_app_fn()


# ── Windows ─────────────────────────────────────────────────────────────────

def _install_windows(exe_path: str) -> None:
    """
    Launch the Inno Setup installer with silent flags.

    /VERYSILENT        – no wizard UI
    /NORESTART         – suppress the "please restart" prompt
    /CLOSEAPPLICATIONS – installer closes any running instance for us
    /RESTARTAPPLICATIONS – installer relaunches the app after install
    """
    logger.info(f"Windows: launching installer silently: {exe_path}")
    # DETACHED_PROCESS and CREATE_NEW_PROCESS_GROUP are Windows-only subprocess flags.
    _DETACHED   = getattr(subprocess, "DETACHED_PROCESS",        0x00000008)
    _NEW_PG     = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    subprocess.Popen(
        [
            exe_path,
            "/VERYSILENT",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
        ],
        # Detach so the installer outlives our process
        creationflags=_DETACHED | _NEW_PG,
        close_fds=True,
    )


# ── macOS ────────────────────────────────────────────────────────────────────

def _install_macos(dmg_path: str) -> None:
    """
    Remove quarantine from the downloaded DMG, then open it.

    Opening a .dmg mounts the disk image and shows the Finder window
    with the drag-to-Applications shortcut — exactly the normal install UX.
    The user drags, ejects, and reopens the app themselves.
    """
    logger.info(f"macOS: stripping quarantine and opening DMG: {dmg_path}")

    # Remove the com.apple.quarantine xattr so Gatekeeper won't block the open
    try:
        subprocess.run(
            ["xattr", "-rd", "com.apple.quarantine", dmg_path],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass  # xattr not available — rare, but non-fatal

    # open(1) mounts the DMG and brings up the Finder window
    subprocess.Popen(["open", dmg_path])


# ── Linux ────────────────────────────────────────────────────────────────────

def _install_linux(new_appimage_path: str) -> None:
    """
    Hot-swap the running AppImage with the new one via a detached shell script.

    When running as an AppImage, the $APPIMAGE environment variable is set by
    the AppImage runtime and points to the original .AppImage file on disk.
    We use that as the replacement target.

    If the app is NOT running from an AppImage (e.g. running from source during
    development), we fall back to sys.executable — which replaces the Python
    binary itself, so we skip the relaunch step in that case.
    """
    current = os.environ.get("APPIMAGE")
    running_as_appimage = bool(current)
    if not running_as_appimage:
        current = sys.executable

    logger.info(
        f"Linux: swapping AppImage "
        f"{'(AppImage runtime)' if running_as_appimage else '(bare executable — dev mode)'}"
        f"\n  old: {current}\n  new: {new_appimage_path}"
    )

    # Ensure the new file is executable before we swap
    new_mode = os.stat(new_appimage_path).st_mode
    os.chmod(new_appimage_path, new_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    pid = os.getpid()
    script_path = os.path.join(tempfile.gettempdir(), "chess_analyzer_updater.sh")

    if running_as_appimage:
        relaunch_cmd = f'exec "{current}"'
    else:
        # Dev mode: just log that the swap happened; don't relaunch a raw interpreter
        relaunch_cmd = (
            f'echo "[updater] swap complete; '
            f'relaunch {current} manually (dev mode)"'
        )

    script = f"""\
#!/usr/bin/env bash
# Chess Analyzer Pro — AppImage hot-swap script
# Generated at runtime; safe to delete after execution.

set -euo pipefail

TARGET="{current}"
NEW_APPIMAGE="{new_appimage_path}"
PID={pid}

# Wait for the running app to exit (max 30 s)
WAITED=0
while kill -0 "$PID" 2>/dev/null; do
    sleep 0.5
    WAITED=$((WAITED + 1))
    if [ "$WAITED" -ge 60 ]; then
        echo "[updater] Timed out waiting for PID $PID to exit" >&2
        exit 1
    fi
done

# Atomic swap: move new over old
mv -f "$NEW_APPIMAGE" "$TARGET"
chmod +x "$TARGET"

echo "[updater] AppImage updated successfully."

# Relaunch
{relaunch_cmd}
"""

    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, 0o755)

    subprocess.Popen(
        ["bash", script_path],
        start_new_session=True,   # detach from our process group
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
