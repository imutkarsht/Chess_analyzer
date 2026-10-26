"""Backward-compatible alias for storage cards.

The base class is now generic because network cards use the same task runner.
"""

from .background_card import BackgroundTaskCard

StorageCard = BackgroundTaskCard

__all__ = ["StorageCard"]
