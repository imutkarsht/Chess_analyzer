# SPDX-License-Identifier: GPL-3.0-only
"""Shareable report card rendering and export behavior."""

from __future__ import annotations

import chess
import pytest
from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QFont, QFontMetrics, QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog

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
        eco="C20" if include_metadata else None,
        opening="King's Pawn Game" if include_metadata else None,
        termination_mode="resignation" if include_metadata else None,
        termination_description="Alice won by resignation" if include_metadata else None,
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

    paused = _game()
    paused.summary["analysis_status"] = "paused"
    assert not ShareReportRenderer.can_render(paused)


def test_markdown_summary_includes_game_facts_and_classifications():
    markdown = ShareReportRenderer.markdown_summary(_game())

    assert "# Game Report: Alice vs Bob" in markdown
    assert "**Result:** White wins" in markdown
    assert "White 95.0%; Black 87.2%" in markdown
    assert "- Best: White 1, Black 0" in markdown
    assert "- **Opening:** C20 · King's Pawn Game" in markdown
    assert "- **Result:** White wins · by resignation" in markdown
    assert "- **Time control:** 10:00 + 5s" in markdown
    assert "Chess Analyzer Pro v" in markdown
    assert "Free, open-source offline Stockfish desktop analyzer" in markdown
    assert "https://chessanalyzer.xyz" in markdown


@pytest.mark.parametrize(
    ("time_control", "expected"),
    [
        ("600+5", "10:00 + 5s"),
        ("180+2", "3:00 + 2s"),
        ("60", "1:00"),
        ("40/7200:3600", "40 moves / 2:00:00 then 1:00:00"),
    ],
)
def test_report_formats_time_control_as_minutes_and_seconds(time_control, expected):
    game = _game()
    game.metadata.time_control = time_control

    markdown = ShareReportRenderer.markdown_summary(game)

    assert f"- **Time control:** {expected}" in markdown


def test_report_termination_subline_fits_without_eliding(qapp, monkeypatch):
    original_draw_text = ShareReportRenderer._draw_text
    rendered = []

    def capture_text(painter, rect, text, *args, **kwargs):
        rendered.append((str(text), rect))
        original_draw_text(painter, rect, text, *args, **kwargs)

    monkeypatch.setattr(
        ShareReportRenderer, "_draw_text", staticmethod(capture_text)
    )
    ShareReportRenderer.render(_game())

    termination = next(
        (text, rect) for text, rect in rendered if text == "WHITE WINS · BY RESIGNATION"
    )
    details = next(text for text, _rect in rendered if text.startswith("DATE  "))
    font = QFont()
    font.setPixelSize(11)
    font.setWeight(QFont.Weight.DemiBold)
    assert QFontMetrics(font).horizontalAdvance(termination[0]) <= termination[1].width()
    assert "TIME CONTROL  10:00 + 5s" in details
    assert "1 MOVE" in details


def test_report_handles_malformed_final_position_data(qapp):
    game = _game()
    game.metadata.last_fen = "not a FEN"
    game.metadata.starting_fen = "also not a FEN"
    game.moves[-1].uci = None

    image = ShareReportRenderer.render(game)
    assert not image.isNull()


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
        assert panel.share_report_button.accessibleName() == "Share Report"
        assert panel.share_report_button.height() == 34

        panel.current_game = _game()
        panel.current_game.summary["analysis_status"] = "paused"
        panel.refresh()
        assert not panel.share_report_button.isEnabled()

        panel.current_game = _game()
        for move in panel.current_game.moves:
            move.classification = ""
        panel.refresh()
        assert not panel.share_report_button.isEnabled()
    finally:
        panel.deleteLater()


def test_panel_surfaces_report_render_failures(qapp, monkeypatch):
    panel = AnalysisPanel()
    errors = []

    def fail_to_construct(*_args, **_kwargs):
        raise ValueError("invalid report data")

    monkeypatch.setattr(
        "src.gui.analysis.analysis_panel.ShareReportDialog", fail_to_construct
    )
    monkeypatch.setattr(
        ToastManager, "error", lambda _widget, message: errors.append(message)
    )
    try:
        panel.current_game = _game()
        panel.open_share_report()
        assert errors == ["Could not render the game report."]
    finally:
        panel.deleteLater()


def test_dialog_preview_and_clipboard_exports(qapp, monkeypatch):
    monkeypatch.setattr(ToastManager, "success", lambda *_args, **_kwargs: None)
    clipboard = QApplication.clipboard()
    if clipboard is None or clipboard.mimeData() is None:
        pytest.skip("System clipboard is unavailable.")
    original = _clipboard_snapshot(clipboard)
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
        _restore_clipboard(clipboard, original)


def test_enter_activates_close_without_copying_image(qapp):
    dialog = ShareReportDialog(_game())
    copy_clicks = []
    close_clicks = []
    try:
        assert dialog.close_button.isDefault()
        assert not dialog.copy_image_button.autoDefault()
        assert not dialog.save_png_button.autoDefault()
        assert not dialog.copy_markdown_button.autoDefault()
        dialog.copy_image_button.clicked.connect(lambda: copy_clicks.append(True))
        dialog.close_button.clicked.connect(lambda: close_clicks.append(True))

        dialog.show()
        QTest.keyClick(dialog, Qt.Key.Key_Return)

        assert dialog.result() == QDialog.DialogCode.Accepted
        assert not copy_clicks
        assert close_clicks == [True]
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


def _clipboard_snapshot(clipboard) -> QMimeData:
    source = clipboard.mimeData()
    snapshot = QMimeData()
    if source.hasImage():
        snapshot.setImageData(source.imageData())
    for mime_type in source.formats():
        if mime_type not in {"application/x-qt-image", "text/plain"}:
            snapshot.setData(mime_type, source.data(mime_type))
    if source.hasText():
        snapshot.setText(source.text())
    return snapshot


def _restore_clipboard(clipboard, snapshot: QMimeData) -> None:
    if snapshot.formats() or snapshot.hasImage() or snapshot.hasText():
        clipboard.setMimeData(snapshot)
    else:
        clipboard.clear()
