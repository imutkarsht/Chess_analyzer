"""Helpers shared by the Data & Storage cards.

Kept out of the widgets so the reset/restore paths used by three different
cards cannot drift apart.
"""

import chess

from src.utils.logger import logger


def format_bytes(size: int) -> str:
    """Human-readable size with one decimal, e.g. ``42.6 MB``."""
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def format_count(count: int) -> str:
    return f"{int(count):,}"


def analysis_is_running(window) -> bool:
    worker = getattr(window, "worker", None)
    return bool(worker is not None and worker.isRunning())


def ensure_idle(window) -> bool:
    """Refuse data operations while a game analysis owns the engine and cache."""
    if not analysis_is_running(window):
        return True
    from src.gui.main_window import MainWindow

    MainWindow.toast_from_widget(
        window,
        "Stop the current analysis before changing local data.",
        "warning",
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
    history_view = getattr(window, "history_view", None)
    if history_view is not None:
        history_view.load_history()

    metrics_view = getattr(window, "metrics_view", None)
    if metrics_view is not None:
        # refresh([]) silently keeps the old dashboard: force a rebuild.
        metrics_view.refresh(force=True)

    reset_analysis_workspace(window)
