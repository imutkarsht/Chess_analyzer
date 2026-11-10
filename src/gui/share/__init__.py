# SPDX-License-Identifier: GPL-3.0-only
"""Shareable game report rendering and export."""

from .report_card import ShareReportRenderer
from .share_report_dialog import ShareReportDialog

__all__ = ["ShareReportDialog", "ShareReportRenderer"]
