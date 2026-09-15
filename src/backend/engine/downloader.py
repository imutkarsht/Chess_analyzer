import sys
import os
import re
import tarfile
import zipfile
import tempfile
import shutil
import stat
import subprocess
from typing import Optional, Callable, Iterable
from dataclasses import dataclass

import requests

from src.utils.logger import logger


GITHUB_API = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"
GITHUB_RELEASE_BY_TAG = (
    "https://api.github.com/repos/official-stockfish/Stockfish/releases/tags/{tag}"
)
GITHUB_RELEASE_DOWNLOAD = (
    "https://github.com/official-stockfish/Stockfish/releases/download/{tag}/{asset}"
)

# Known-good fallback release. If the *latest* release ever ships assets that
# the token matcher cannot recognise, we still have a tag whose naming we know
# how to resolve. Bump this deliberately when validating a new release.
PINNED_RELEASE_TAG = "sf_17"

_USER_AGENT = "ChessAnalyzerPro/StockfishDownloader (+https://github.com/imutkarsht/Chess_analyzer)"

# Canonical asset name per platform, used for display/tests only. Selection
# never depends on these strings — see select_assets().
PLATFORM_ASSETS: dict[tuple[str, str], str] = {
    ("darwin", "arm64"):  "stockfish-macos-universal.tar.gz",
    ("darwin", "x86_64"): "stockfish-macos-universal.tar.gz",
    ("win32",  "x86_64"): "stockfish-windows-x86-64-universal.zip",
    ("win32",  "arm64"):  "stockfish-windows-arm64-universal.zip",
    ("linux",  "x86_64"): "stockfish-linux-x86-64-universal.tar.gz",
    ("linux",  "arm64"):  "stockfish-linux-arm64-universal.tar.gz",
    ("linux",  "riscv64"): "stockfish-linux-riscv64-universal.tar.gz",
}

_ARCH_ALIASES = {
    "x86_64": "x86_64", "x86-64": "x86_64", "amd64": "x86_64", "x64": "x86_64",
    "arm64": "arm64", "aarch64": "arm64", "armv8": "arm64", "armv9": "arm64",
    "arm64e": "arm64",
    "riscv64": "riscv64",
    "armv7": "armv7", "armv7l": "armv7", "armhf": "armv7", "armel": "armv7",
    "i386": "x86_32", "i686": "x86_32", "x86": "x86_32", "x86_32": "x86_32",
    "x86-32": "x86_32",
    # Recognised but unsupported architectures. Mapped to a distinct value so
    # they are skipped cleanly instead of being mistaken for "unknown/generic".
    "ppc64le": "ppc64le", "ppc64": "ppc64le",
    "s390x": "s390x",
    "loongarch64": "loongarch64", "loongarch": "loongarch64",
}

_OS_ALIASES = {
    "linux": "linux", "ubuntu": "linux", "debian": "linux",
    "fedora": "linux", "centos": "linux", "rhel": "linux", "rocky": "linux",
    "alpine": "linux", "opensuse": "linux", "suse": "linux",
    "macos": "darwin", "osx": "darwin", "darwin": "darwin",
    "apple": "darwin", "mac": "darwin",
    "windows": "win32", "win": "win32", "win32": "win32", "win64": "win32",
}

# Preferred archive containers, best first. Used only as a tie-breaker.
_CONTAINER_RANK = {
    ".tar.gz": 3, ".tgz": 3, ".zip": 3,
    ".tar.xz": 2, ".tar.bz2": 2, ".tbz2": 2, ".txz": 2,
    ".tar.zst": 2, ".tzst": 2, ".tar.lz4": 2, ".tar.lz": 2,
    ".tar": 1,
}


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def _normalize_arch(machine: Optional[str]) -> Optional[str]:
    """Map a raw ``platform.machine()`` value to a canonical arch token."""
    if not machine:
        return None
    return _ARCH_ALIASES.get(machine.strip().lower())


def get_current_platform() -> tuple[str, str]:
    """Return ``(system, arch)`` suitable for asset selection.

    ``system`` is one of ``darwin``/``win32``/``linux`` and ``arch`` is a
    canonical token (``x86_64``, ``arm64``, ``riscv64``, ``armv7``,
    ``x86_32``).
    """
    system_map = {"darwin": "darwin", "win32": "win32", "linux": "linux"}
    system = system_map.get(sys.platform)
    if system is None:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")

    if system == "win32":
        arch = _normalize_arch(os.environ.get("PROCESSOR_ARCHITECTURE", "")) or "x86_64"
    else:
        import platform
        arch = _normalize_arch(platform.machine())
        if arch is None:
            arch = "arm64" if system == "darwin" else "x86_64"
    return system, arch


def get_expected_asset_name() -> str:
    """Return the canonical Stockfish asset name for the current platform.

    This is a human-readable hint only; downloads are resolved dynamically via
    :func:`select_assets` so upstream renames do not break the app.
    """
    platform_key = get_current_platform()
    asset_name = PLATFORM_ASSETS.get(platform_key)
    if asset_name is None:
        raise RuntimeError(
            f"No Stockfish asset defined for platform {platform_key}. "
            f"Supported: {list(PLATFORM_ASSETS.keys())}"
        )
    return asset_name


# ---------------------------------------------------------------------------
# Release fetching
# ---------------------------------------------------------------------------

def _fetch_assets(api_url: str) -> list[ReleaseAsset]:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"}
    resp = requests.get(api_url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    assets = []
    for asset in data.get("assets", []):
        assets.append(ReleaseAsset(
            name=asset["name"],
            url=asset["browser_download_url"],
            size=asset.get("size", 0),
        ))
    return assets


def get_official_releases() -> list[ReleaseAsset]:
    """Fetch the latest Stockfish release from GitHub and return its assets."""
    return _fetch_assets(GITHUB_API)


def get_releases_for_tag(tag: str) -> list[ReleaseAsset]:
    """Fetch assets for a specific release tag (used as a pinned fallback)."""
    return _fetch_assets(GITHUB_RELEASE_BY_TAG.format(tag=tag))


# ---------------------------------------------------------------------------
# Asset selection (token based, rename-proof)
# ---------------------------------------------------------------------------

def _tokenize(name: str) -> list[str]:
    return [t for t in re.split(r"[-_.]+", name.lower()) if t]


def _asset_os(name: str) -> Optional[str]:
    if "android" in name.lower():
        return "android"
    for token in _tokenize(name):
        if token in _OS_ALIASES:
            return _OS_ALIASES[token]
    return None


def _asset_arch(name: str) -> Optional[str]:
    """Best-effort architecture detection from an asset filename."""
    tokens = _tokenize(name)
    joined = "-".join(tokens)

    # Multi-token patterns first (x86 + 64, apple + silicon).
    if ("x86" in tokens and "64" in tokens) or "x86-64" in joined:
        return "x86_64"
    if "x86" in tokens and "32" in tokens:
        return "x86_32"
    if ("apple" in tokens and "silicon" in tokens) or "m1" in tokens:
        return "arm64"

    for token in tokens:
        arch = _ARCH_ALIASES.get(token)
        if arch:
            return arch
    return None


def _container_rank(name: str) -> int:
    lower = name.lower()
    for suffix, rank in _CONTAINER_RANK.items():
        if lower.endswith(suffix):
            return rank
    return 0


def _score_asset(asset: ReleaseAsset, system: str, arch: str) -> Optional[tuple[int, int]]:
    """Return a sort key for ``asset`` on the given platform, or None to skip.

    Key is ``(arch_rank, container_rank)``; higher is better. Assets for a
    different OS (or Android) are skipped entirely.
    """
    asset_os = _asset_os(asset.name)
    if asset_os != system:
        return None

    # Architecture must be a confident match. An explicit, recognised arch that
    # differs from ours is a hard no; an *unknown* arch token is treated as
    # suspicious (rather than generic) so we never grab a wrong-arch binary.
    # The only arch-ambiguous name we trust is an explicit "universal" build.
    asset_arch = _asset_arch(asset.name)
    if asset_arch == arch:
        arch_rank = 3
    elif asset_arch is None and "universal" in asset.name.lower():
        arch_rank = 2
    else:
        return None

    container_rank = _container_rank(asset.name)
    if container_rank == 0:
        return None
    return (arch_rank, container_rank)


def select_assets(releases: Iterable[ReleaseAsset]) -> list[ReleaseAsset]:
    """Return all compatible assets for the current platform, best first.

    Matching is based on filename *tokens* (OS + architecture + container), so
    both the current ``stockfish-linux-x86-64-universal.tar.gz`` naming and the
    legacy ``stockfish-ubuntu-x86-64-avx2.tar`` naming resolve correctly.
    """
    system, arch = get_current_platform()
    scored: list[tuple[tuple[int, int], int, ReleaseAsset]] = []
    for order, asset in enumerate(releases):
        key = _score_asset(asset, system, arch)
        if key is not None:
            # Negate order so earlier API entries win ties under reverse sort.
            scored.append((key, -order, asset))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [asset for _key, _order, asset in scored]


def select_asset(releases: Iterable[ReleaseAsset]) -> Optional[ReleaseAsset]:
    """Return the single best asset for the current platform, or None."""
    assets = select_assets(releases)
    return assets[0] if assets else None


def get_download_url(releases: list[ReleaseAsset], target_asset: str = "") -> Optional[str]:
    """Find a download URL in ``releases``.

    An exact name match wins (back-compat); otherwise fall back to token-based
    platform selection so renamed assets still resolve.
    """
    if target_asset:
        for asset in releases:
            if asset.name == target_asset:
                return asset.url
    best = select_asset(releases)
    return best.url if best else None


def get_download_candidates(releases: Optional[list[ReleaseAsset]] = None) -> list[str]:
    """Return ranked download URLs, falling back to a pinned known-good tag.

    Order:
      1. Best assets from the latest release.
      2. Best assets from :data:`PINNED_RELEASE_TAG` (if the latest is
         unrecognisable or the API call fails).
    """
    urls: list[str] = []

    if releases is None:
        try:
            releases = get_official_releases()
        except Exception as e:
            logger.warning("Failed to fetch latest Stockfish release: %s", e)
            releases = []

    urls.extend(a.url for a in select_assets(releases))

    if not urls:
        logger.info("No match in latest release; trying pinned tag %s", PINNED_RELEASE_TAG)
        try:
            pinned = get_releases_for_tag(PINNED_RELEASE_TAG)
            urls.extend(a.url for a in select_assets(pinned))
        except Exception as e:
            logger.warning("Failed to fetch pinned Stockfish release: %s", e)

    return urls


# ---------------------------------------------------------------------------
# Download + extraction
# ---------------------------------------------------------------------------

def download_and_extract(
    url: str,
    dest_dir: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    validate: bool = True,
    fallback_urls: Optional[list[str]] = None,
) -> str:
    """Download a Stockfish archive, extract it, and return the binary path.

    Args:
        url: Primary direct download URL for the archive.
        dest_dir: Directory to place the final ``stockfish`` binary in.
        progress_callback: Optional callback(bytes_downloaded, total_bytes).
        validate: If True, run a UCI handshake before declaring success.
        fallback_urls: Additional URLs tried in order if ``url`` fails.

    Returns:
        Absolute path to the extracted Stockfish binary.
    """
    os.makedirs(dest_dir, exist_ok=True)
    urls = [url] + [u for u in (fallback_urls or []) if u and u != url]

    errors: list[str] = []
    for candidate in urls:
        try:
            return _download_one(candidate, dest_dir, progress_callback, validate)
        except Exception as e:  # try the next candidate
            logger.warning("Stockfish download attempt failed (%s): %s", candidate, e)
            errors.append(f"{candidate}: {e}")

    raise RuntimeError(
        "Failed to download Stockfish. Attempts:\n  " + "\n  ".join(errors)
    )


def _download_one(
    url: str,
    dest_dir: str,
    progress_callback: Optional[Callable[[int, int], None]],
    validate: bool,
) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".download") as tmp:
        tmp_path = tmp.name
    staging = tempfile.mkdtemp(prefix="stockfish_extract_")

    try:
        headers = {"User-Agent": _USER_AGENT}
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
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

        _extract_archive(tmp_path, staging)
        binary = _find_binary(staging)
        _make_executable(binary)

        if validate and not probe_engine_binary(binary):
            raise RuntimeError(
                f"Extracted binary at {binary} failed the UCI handshake"
            )

        final_path = os.path.join(dest_dir, _binary_filename())
        shutil.move(binary, final_path)
        return final_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        shutil.rmtree(staging, ignore_errors=True)


def _extract_archive(archive_path: str, dest_dir: str) -> None:
    """Extract a zip or tar archive, detecting the container by content."""
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
        return
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tf:
            try:
                tf.extractall(dest_dir, filter="data")
            except TypeError:
                # Python < 3.12 has no extraction filter.
                tf.extractall(dest_dir)
        return
    raise RuntimeError(f"Unrecognised archive format: {archive_path}")


def _binary_filename() -> str:
    return "stockfish.exe" if sys.platform == "win32" else "stockfish"


def _find_binary(search_dir: str) -> str:
    """Find the Stockfish binary inside an extracted directory tree.

    Prefers a binary matching the current architecture, then any regular
    ``stockfish*`` file (``.exe`` on Windows). Directories are ignored.
    """
    is_windows = sys.platform == "win32"
    _system, arch = get_current_platform()

    candidates: list[tuple[int, str]] = []
    for root, _dirs, files in os.walk(search_dir):
        for f in files:
            lower = f.lower()
            if not lower.startswith("stockfish"):
                continue
            if is_windows and not lower.endswith(".exe"):
                continue
            if not is_windows and lower.endswith(".exe"):
                continue
            path = os.path.join(root, f)
            if not os.path.isfile(path):
                continue
            file_arch = _asset_arch(f)
            rank = 2 if file_arch == arch else (1 if file_arch is None else 0)
            candidates.append((rank, path))

    if not candidates:
        raise FileNotFoundError(
            f"Could not find a Stockfish binary in extracted contents under {search_dir}"
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def probe_engine_binary(path: str, timeout: int = 10) -> bool:
    """Return True if ``path`` behaves like a working UCI engine.

    Runs the binary and sends ``uci``/``quit``, expecting a ``uciok`` reply (or
    the Stockfish banner) on stdout/stderr.
    """
    try:
        proc = subprocess.run(
            [path],
            input=b"uci\nquit\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("Engine probe failed for %s: %s", path, e)
        return False

    output = (proc.stdout or b"") + (proc.stderr or b"")
    lowered = output.lower()
    return b"uciok" in lowered or b"stockfish" in lowered


def _make_executable(path: str) -> None:
    """Ensure the binary is executable and remove macOS quarantine (no-op on Windows)."""
    if sys.platform != "win32":
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    ["xattr", "-d", "com.apple.quarantine", path],
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Distro package-manager fallback
# ---------------------------------------------------------------------------

_PACKAGE_MANAGERS = [
    ("apt-get", ["apt-get", "install", "-y", "stockfish"]),
    ("dnf", ["dnf", "install", "-y", "stockfish"]),
    ("pacman", ["pacman", "-S", "--noconfirm", "stockfish"]),
    ("zypper", ["zypper", "--non-interactive", "install", "stockfish"]),
    ("apk", ["apk", "add", "stockfish"]),
]


def try_package_manager_install() -> Optional[str]:
    """Best-effort Stockfish install via the system package manager.

    Returns the resolved binary path on success, else None. Never raises and
    never prompts (each invocation is non-interactive). Requires the process to
    already have sufficient privileges (e.g. running as root); otherwise it is
    skipped gracefully.
    """
    env = dict(os.environ)
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    for name, cmd in _PACKAGE_MANAGERS:
        if shutil.which(name) is None:
            continue
        try:
            logger.info("Attempting Stockfish install via %s", name)
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180, env=env
            )
            if result.returncode != 0:
                logger.warning("%s install failed: %s", name, result.stderr)
                continue
        except Exception as e:
            logger.warning("%s install crashed: %s", name, e)
            continue

        resolved = shutil.which("stockfish")
        if resolved and probe_engine_binary(resolved):
            return resolved
    return None
