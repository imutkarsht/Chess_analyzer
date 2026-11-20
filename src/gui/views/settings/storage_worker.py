"""Backward-compatible alias for the generic background task worker."""

from src.workers.settings import BackgroundTaskWorker

StorageTaskWorker = BackgroundTaskWorker

__all__ = ["StorageTaskWorker"]
