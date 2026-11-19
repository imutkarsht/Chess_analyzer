"""Helpers shared by the Data & Storage cards.

Kept out of the widgets so the reset/restore paths used by three different
cards cannot drift apart.
"""

import chess

from src.backend.models.analysis_batch import BATCH_PAUSED, BATCH_RUNNING
from src.gui.components.feedback.toast import ToastManager
from src.utils.logger import logger

__all__ = [
    "analysis_is_running",
    "close_analyzer_cache",
    "ensure_idle",
    "refresh_after_data_change",
    "reset_analysis_workspace",
]


def analysis_is_running(window) -> bool:
    worker = getattr(window, "worker", None)
    if worker is not None and worker.isRunning():
        return True
    if getattr(window, "_batch_worker", None) is not None:
        return True
    coordinator = getattr(window, "analysis_coordinator", None)
    return bool(
        coordinator is not None
        and coordinator.batch_state in (BATCH_RUNNING, BATCH_PAUSED)
    )


def ensure_idle(window) -> bool:
    """Refuse data operations while a game analysis owns the engine and cache."""
    if not analysis_is_running(window):
        return True

    ToastManager.warning(
        window,
        "Finish or cancel the current analysis or batch before changing local data.",
    )
    return False


def close_analyzer_cache(window) -> None:
    """Release the analyzer's long-lived cache connection.

    VACUUM and restore need exclusive access; ``AnalysisCache`` reconnects
    lazily on the next read, so closing it here is safe.
    """
    analyzer = getattr(window, "analyzer", None)
    cache = getattr(analyzer, "cache", None)
    if cache is not None and hasattr(cache, "close"):
        try:
            cache.close()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"Could not close analyzer cache: {e}")


def reset_analysis_workspace(window) -> None:
    """Return the Analyze page to its landing state after the data is gone.

    Without this, a wiped game would stay visible on the board and in the move
    list even though it no longer exists in the database.
    """
    window.current_game = None
    if hasattr(window, "games"):
        # The parsed-but-not-yet-analyzed list belongs to the deleted library.
        window.games = []

    move_list = getattr(window, "move_list_panel", None)
    if move_list is not None:
        move_list.clear()

    analysis_panel = getattr(window, "analysis_panel", None)
    if analysis_panel is not None:
        analysis_panel.set_game(None)

    board = getattr(window, "board_widget", None)
    if board is not None:
        board.load_fen(chess.STARTING_FEN)
        if hasattr(board, "set_eval_bar_visible"):
            board.set_eval_bar_visible(False)

    if hasattr(window, "_update_analysis_view_mode"):
        window._update_analysis_view_mode(False)


def refresh_after_data_change(window) -> None:
    """Reload every view that reads the database after a reset or restore."""
    timer = getattr(window, "_batch_eta_timer", None)
    if timer is not None:
        timer.stop()
    coordinator = getattr(window, "analysis_coordinator", None)
    if coordinator is not None:
        coordinator.reset()
    if hasattr(window, "_set_batch_snapshot"):
        window._set_batch_snapshot(None)
    cache = getattr(window, "_batch_up_next_cache", None)
    if cache is not None:
        cache.clear()

    history_view = getattr(window, "history_view", None)
    if history_view is not None:
        if hasattr(history_view, "hide_batch_queue"):
            history_view.hide_batch_queue()
        history_view.load_history()

    metrics_view = getattr(window, "metrics_view", None)
    if metrics_view is not None:
        # refresh([]) silently keeps the old dashboard: force a rebuild.
        metrics_view.refresh(force=True)

    reset_analysis_workspace(window)
