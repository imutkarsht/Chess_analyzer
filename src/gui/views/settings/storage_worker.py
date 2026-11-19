"""Backward-compatible alias for the generic background task worker."""

from src.gui.views.settings.background_worker import BackgroundTaskWorker

StorageTaskWorker = BackgroundTaskWorker

__all__ = ["StorageTaskWorker"]
