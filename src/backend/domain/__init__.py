# SPDX-License-Identifier: GPL-3.0-only
"""Backend domain rules shared by storage and presentation layers."""

from src.backend.domain.termination import detect_termination

__all__ = ["detect_termination"]
