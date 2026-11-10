# SPDX-License-Identifier: GPL-3.0-only
"""Shareable report card rendering and export behavior."""

from __future__ import annotations

import chess
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.analysis.analysis_panel import AnalysisPanel
from src.gui.components.feedback.toast import ToastManager
from src.gui.share import ShareReportDialog, ShareReportRenderer


def _game(*, include_metadata: bool = True) -> GameAnalysis:
    board = chess.Board()
    moves = []
    for ply, san in enumerate(("e4", "e5"), start=0):
        move = board.parse_san(san)
        fen_before = board.fen()
        board.push(move)
        moves.append(
            MoveAnalysis(
                move_number=ply // 2 + 1,
                ply=ply,
                san=san,
                uci=move.uci(),
                fen_before=fen_before,
                classification="Best" if ply == 0 else "Good",
                eval_after_cp=25 if ply == 0 else 10,
            )
        )
    metadata = GameMetadata(
        white="Alice" if include_metadata else "?",
        black="Bob" if include_metadata else "?",
        white_elo="1600" if include_metadata else None,
        black_elo="1500" if include_metadata else None,
        date="2025.01.02" if include_metadata else "?",
        result="1-0",
        time_control="600+5" if include_metadata else None,
        last_fen=board.fen() if include_metadata else None,
    )
    return GameAnalysis(
        game_id="share-report",
        metadata=metadata,
        moves=moves,
        summary={
            "white": {"accuracy": 95.0, "acpl": 12.5, "Best": 1},
            "black": {"accuracy": 87.2, "acpl": 34, "Good": 1},
        },
    )


def test_report_card_is_fixed_size_opaque_and_handles_missing_metadata(qapp):
    image = ShareReportRenderer.render(_game(include_metadata=False))

    assert image.size().width() == 1200
    assert image.size().height() == 675
    assert image.format() == QImage.Format.Format_ARGB32_Premultiplied
    assert image.pixelColor(0, 0).alpha() == 255
    assert not image.isNull()


def test_report_requires_analyzed_data():
    game = _game()
    for move in game.moves:
        move.classification = ""

    assert not ShareReportRenderer.can_render(None)
    assert not ShareReportRenderer.can_render(
        GameAnalysis(game_id="empty", metadata=GameMetadata())
    )
    assert not ShareReportRenderer.can_render(game)


def test_markdown_summary_includes_game_facts_and_classifications():
    markdown = ShareReportRenderer.markdown_summary(_game())

    assert "# Game Report: Alice vs Bob" in markdown
    assert "**Result:** White wins" in markdown
    assert "White 95.0%; Black 87.2%" in markdown
    assert "- Best: White 1, Black 0" in markdown
    assert "https://chessanalyzer.xyz" in markdown


def test_analysis_panel_share_action_tracks_analysis_availability(qapp):
    panel = AnalysisPanel()
    try:
        assert not panel.share_report_button.isEnabled()

        panel.current_game = GameAnalysis(game_id="unanalysed", metadata=GameMetadata())
        panel.refresh()
        assert not panel.share_report_button.isEnabled()

        panel.current_game = _game()
        panel.refresh()
        assert panel.share_report_button.isEnabled()

        panel.current_game = _game()
        for move in panel.current_game.moves:
            move.classification = ""
        panel.refresh()
        assert not panel.share_report_button.isEnabled()
    finally:
        panel.deleteLater()


def test_dialog_preview_and_clipboard_exports(qapp, monkeypatch):
    monkeypatch.setattr(ToastManager, "success", lambda *_args, **_kwargs: None)
    dialog = ShareReportDialog(_game())
    try:
        assert not dialog.preview_label.pixmap().isNull()

        dialog.copy_image_button.click()
        mime_data = QApplication.clipboard().mimeData()
        assert mime_data.hasImage()
        assert mime_data.hasFormat("image/png")
        assert bytes(mime_data.data("image/png")).startswith(b"\x89PNG")

        dialog.copy_markdown_button.click()
        assert "# Game Report: Alice vs Bob" in QApplication.clipboard().text()
    finally:
        dialog.close()


def test_dialog_saves_png_and_adds_extension(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ToastManager, "success", lambda *_args, **_kwargs: None)
    target = tmp_path / "report.jpg"
    monkeypatch.setattr(
        "src.gui.share.share_report_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "PNG image (*.png)"),
    )
    dialog = ShareReportDialog(_game())
    try:
        dialog.save_png_button.click()
        saved = tmp_path / "report.png"
        image = QImage(str(saved))
        assert image.size().width() == 1200
        assert image.size().height() == 675
    finally:
        dialog.close()


def test_dialog_reports_png_save_errors(qapp, monkeypatch, tmp_path):
    errors = []
    monkeypatch.setattr(
        "src.gui.share.share_report_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "report.png"), "PNG image (*.png)"),
    )
    monkeypatch.setattr(ToastManager, "error", lambda _widget, message: errors.append(message))
    monkeypatch.setattr(QImage, "save", lambda *_args, **_kwargs: False)
    dialog = ShareReportDialog(_game())
    try:
        dialog.save_png()
        assert errors and "Could not save report image" in errors[0]
    finally:
        dialog.close()
