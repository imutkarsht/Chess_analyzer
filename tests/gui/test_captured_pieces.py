"""Captured-piece chip caching and rebuild rules."""

import chess

from src.gui.analysis import captured as captured_module
from src.gui.analysis.captured import CapturedPiecesWidget


def _fen_after(*uci_moves: str) -> str:
    board = chess.Board()
    for uci in uci_moves:
        board.push_uci(uci)
    return board.fen()


def test_unchanged_captures_reuse_existing_chips(qapp, monkeypatch):
    widget = CapturedPiecesWidget(side="white")
    rebuilds = []
    monkeypatch.setattr(
        captured_module, "clear_layout", lambda _layout: rebuilds.append(True)
    )

    widget.update_captured(chess.STARTING_FEN)
    rebuilds.clear()
    widget.update_captured(_fen_after("e2e4", "e7e5"))

    assert rebuilds == []
    widget.deleteLater()


def test_capture_change_rebuilds_and_theme_refresh_forces_rebuild(qapp, monkeypatch):
    widget = CapturedPiecesWidget(side="white")
    rebuilds = []
    monkeypatch.setattr(
        captured_module, "clear_layout", lambda _layout: rebuilds.append(True)
    )

    widget.update_captured(chess.STARTING_FEN)
    rebuilds.clear()
    widget.update_captured(_fen_after("e2e4", "d7d5", "e4d5"))
    assert len(rebuilds) == 1

    rebuilds.clear()
    widget.refresh_styles()
    assert len(rebuilds) == 1

    widget.update_captured(None)
    assert len(rebuilds) == 2
    widget.deleteLater()
