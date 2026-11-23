# SPDX-License-Identifier: GPL-3.0-only
"""MainWindow access to the persisted batch-queue controller."""

from __future__ import annotations

from src.gui.app.batch_controller import BatchController


class BatchAnalysisMixin:
    """Expose the batch controller to window composition."""

    @property
    def batch_controller(self) -> BatchController:
        controller = getattr(self, "_batch_controller", None)
        if controller is None:
            controller = BatchController()
            controller.attach(self)
            self._batch_controller = controller
        return controller
