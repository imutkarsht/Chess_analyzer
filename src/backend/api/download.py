# SPDX-License-Identifier: GPL-3.0-only
"""Shared streaming download helper for updates and engine binaries."""

from __future__ import annotations

from collections.abc import Callable

import requests


class DownloadCancelled(RuntimeError):
    """Raised when the caller asks a streaming download to stop."""


def download_to_file(
    url: str,
    dest_path: str,
    *,
    progress: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    chunk_size: int = 64 * 1024,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
) -> int:
    """Stream ``url`` into ``dest_path`` and return the downloaded byte count.

    ``progress`` receives ``(downloaded, total)`` only when the server reports a
    content length. ``should_cancel`` is checked before each chunk and once
    more after the stream ends.
    """
    response = requests.get(url, headers=headers, stream=True, timeout=timeout)
    try:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if should_cancel is not None and should_cancel():
                    raise DownloadCancelled("Download cancelled by user")
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if progress is not None and total:
                    progress(downloaded, total)
    finally:
        response.close()

    if should_cancel is not None and should_cancel():
        raise DownloadCancelled("Download cancelled by user")
    return downloaded
