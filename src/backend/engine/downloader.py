import sys
import os
import tarfile
import zipfile
import tempfile
import shutil
import stat
from typing import Optional, Callable
from dataclasses import dataclass

import requests


GITHUB_API = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"

PLATFORM_ASSETS: dict[tuple[str, str], str] = {
    ("darwin", "arm64"):  "stockfish-macos-universal.tar.gz",
    ("darwin", "x86_64"): "stockfish-macos-universal.tar.gz",
    ("win32",  "x86_64"): "stockfish-windows-x86-64-universal.zip",
    ("linux",  "x86_64"): "stockfish-linux-x86-64-universal.tar.gz",
}


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int


def get_current_platform() -> tuple[str, str]:
    """Return (system, machine) tuple suitable for PLATFORM_ASSETS lookup."""
    system_map = {"darwin": "darwin", "win32": "win32", "linux": "linux"}
    system = system_map.get(sys.platform)
    if system is None:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
    machine = "x86_64"
    if system == "darwin" and sys.platform == "darwin":
        import platform
        machine = platform.machine()
        if machine == "arm64":
            machine = "arm64"
        else:
            machine = "x86_64"
    elif system == "linux":
        import platform
        machine = platform.machine()
    return system, machine


def get_expected_asset_name() -> str:
    """Return the expected Stockfish release asset name for the current platform."""
    platform_key = get_current_platform()
    asset_name = PLATFORM_ASSETS.get(platform_key)
    if asset_name is None:
        raise RuntimeError(
            f"No Stockfish asset defined for platform {platform_key}. "
            f"Supported: {list(PLATFORM_ASSETS.keys())}"
        )
    return asset_name


def get_official_releases() -> list[ReleaseAsset]:
    """Fetch the latest Stockfish release from GitHub and return its assets."""
    resp = requests.get(GITHUB_API, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    assets = []
    for asset in data.get("assets", []):
        assets.append(ReleaseAsset(
            name=asset["name"],
            url=asset["browser_download_url"],
            size=asset["size"],
        ))
    return assets


def get_download_url(releases: list[ReleaseAsset], target_asset: str) -> Optional[str]:
    """Find the download URL for the given asset name in the release list."""
    for asset in releases:
        if asset.name == target_asset:
            return asset.url
    return None


def download_and_extract(
    url: str,
    dest_dir: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Download a Stockfish archive and extract the binary.

    Args:
        url: Direct download URL for the archive.
        dest_dir: Directory to extract into.
        progress_callback: Optional callback(bytes_downloaded, total_bytes).

    Returns:
        Absolute path to the extracted Stockfish binary.
    """
    os.makedirs(dest_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".download") as tmp:
        tmp_path = tmp.name

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)

        if url.endswith(".zip"):
            return _extract_zip(tmp_path, dest_dir)
        else:
            return _extract_tar(tmp_path, dest_dir)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _extract_zip(archive_path: str, dest_dir: str) -> str:
    """Extract a .zip archive and return the path to the Stockfish binary."""
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(dest_dir)

    return _find_binary(dest_dir)


def _extract_tar(archive_path: str, dest_dir: str) -> str:
    """Extract a .tar.gz archive and return the path to the Stockfish binary."""
    with tarfile.open(archive_path, "r:gz") as tf:
        tf.extractall(dest_dir)

    return _find_binary(dest_dir)


def _find_binary(search_dir: str) -> str:
    """Find the Stockfish binary inside an extracted directory.

    Searches recursively for a file named 'stockfish' (or 'stockfish.exe' on Windows).
    """
    target = "stockfish.exe" if sys.platform == "win32" else "stockfish"
    for root, _dirs, files in os.walk(search_dir):
        for f in files:
            if f == target:
                path = os.path.join(root, f)
                _make_executable(path)
                return path
    raise FileNotFoundError(
        f"Could not find '{target}' in extracted contents under {search_dir}"
    )


def _make_executable(path: str) -> None:
    """Ensure the binary is executable (no-op on Windows)."""
    if sys.platform != "win32":
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
