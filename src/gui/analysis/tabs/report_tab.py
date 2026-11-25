# SPDX-License-Identifier: GPL-3.0-only
"""Report tab: game outcome, accuracy gauges, classification table, export/share."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.backend.domain.termination import detect_termination
from src.backend.storage.annotated_pgn import AnnotatedPGNExporter
from src.constants import CLASSIFICATION_ORDER
from src.gui.components import (
    Button,
    ButtonVariant,
    CircularAccuracyWidget,
    IconLabel,
    Label,
    RichTextLabel,
    TextRole,
    TextTone,
    ToastManager,
)
from src.gui.resources import ResourceManager
from src.gui.share import ShareReportDialog, ShareReportRenderer
from src.gui.styles import Styles
from src.gui.tactics_meta import classification_tone
from src.gui.utils.layout import clear_layout
from src.utils.logger import logger


class ReportTab(QWidget):
    """Deterministic post-game report built from the analyzer's own findings."""

    def __init__(self) -> None:
        super().__init__()
        Styles.apply_transparent(self, borderless=False)
        self.resource_manager = ResourceManager()
        self.current_game = None

        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        self.report_card = QFrame()
        self.report_card.setObjectName("ReportCard")
        tab_layout.addWidget(self.report_card)

        self.report_layout = QVBoxLayout(self.report_card)
        self.report_layout.setContentsMargins(12, 12, 12, 12)
        self.report_layout.setSpacing(10)

        result_header = QHBoxLayout()
        result_header.setSpacing(6)
        self.result_banner_lbl = RichTextLabel("-", role=TextRole.BODY)
        result_header.addWidget(self.result_banner_lbl, stretch=1)
        self.btn_export_pgn = Button(
            "",
            variant=ButtonVariant.OUTLINED,
            size="md",
            icon="fa5s.file-export",
            icon_position="only",
            tooltip="Analyze this game before exporting an annotated PGN",
        )
        self.btn_export_pgn.setAccessibleName("Export Annotated PGN")
        self.btn_export_pgn.setEnabled(False)
        self.btn_export_pgn.clicked.connect(self.export_annotated_pgn)
        result_header.addWidget(self.btn_export_pgn)
        self.share_report_button = Button(
            "",
            variant=ButtonVariant.OUTLINED,
            size="md",
            icon="fa5s.share-alt",
            icon_position="only",
            tooltip="Analyze this game before sharing a report",
        )
        self.share_report_button.setAccessibleName("Share Report")
        self.share_report_button.setEnabled(False)
        self.share_report_button.clicked.connect(self.open_share_report)
        result_header.addWidget(self.share_report_button)
        self.report_layout.addLayout(result_header)

        # 1. Top Section: Hero Outcome Header
        self.hero_card = QFrame()
        Styles.apply_transparent(self.hero_card)
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(2)

        self.opening_label = Label("-", role=TextRole.CAPTION, weight=600, wrap=True)
        hero_layout.addWidget(self.opening_label)

        self.details_label = Label("-", role=TextRole.MICRO, tone=TextTone.MUTED)
        hero_layout.addWidget(self.details_label)

        self.report_layout.addWidget(self.hero_card)

        # Subtle divider 1
        self.div1 = QFrame()
        self.div1.setObjectName("ReportDivider")
        self.div1.setFrameShape(QFrame.Shape.HLine)
        self.report_layout.addWidget(self.div1)

        # 2. Accuracy Gauges (Side by side White & Black)
        self.accuracy_frame = QFrame()
        Styles.apply_transparent(self.accuracy_frame)
        self.accuracy_layout = QHBoxLayout(self.accuracy_frame)
        self.accuracy_layout.setContentsMargins(0, 4, 0, 4)
        self.accuracy_layout.setSpacing(16)

        self.w_circular_acc = CircularAccuracyWidget(side="White", accuracy=0.0, acpl=None)
        self.b_circular_acc = CircularAccuracyWidget(side="Black", accuracy=0.0, acpl=None)
        self.accuracy_layout.addWidget(self.w_circular_acc)
        self.accuracy_layout.addWidget(self.b_circular_acc)

        self.report_layout.addWidget(self.accuracy_frame)

        # Subtle divider 2
        self.div2 = QFrame()
        self.div2.setFrameShape(QFrame.Shape.HLine)
        self.div2.setObjectName("ReportDivider")
        self.report_layout.addWidget(self.div2)

        # 3. Move Quality Classification Table
        self.stats_frame = QFrame()
        Styles.apply_transparent(self.stats_frame)
        self.stats_layout = QGridLayout(self.stats_frame)
        self.stats_layout.setSpacing(4)
        self.stats_layout.setContentsMargins(0, 4, 0, 4)
        self.report_layout.addWidget(self.stats_frame)

        # Subtle divider 3
        self.div3 = QFrame()
        self.div3.setFrameShape(QFrame.Shape.HLine)
        self.div3.setObjectName("ReportDivider")
        self.report_layout.addWidget(self.div3)

        # Keep the Report tab top-aligned: the classification table is last.
        self.report_layout.addStretch()

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def render(self, game, user_side: str | None) -> None:
        """Update every report field for the game currently loaded."""
        self.current_game = game
        self._update_share_report_button()

        if not game:
            self.btn_export_pgn.setEnabled(False)
            self.btn_export_pgn.setToolTip(
                "Load and analyze a game before exporting an annotated PGN"
            )
            return

        has_annotations = self._has_move_analysis()
        self.btn_export_pgn.setEnabled(has_annotations)
        self.btn_export_pgn.setToolTip(
            "Export analyzed moves and engine variations"
            if has_annotations
            else "Analyze this game before exporting an annotated PGN"
        )

        self.update_summary(game.summary)

        meta = game.metadata
        w_name = meta.white or "White"
        b_name = meta.black or "Black"

        _term_mode, term_desc = detect_termination(
            headers={
                "Result": meta.result,
                "White": w_name,
                "Black": b_name,
                "Termination": meta.termination or "",
            },
            moves=getattr(game, "moves", []) or [],
            starting_fen=meta.starting_fen,
        )

        res_color = self._get_result_color(meta, user_side)
        self.result_banner_lbl.setText(
            f"<span style='color: {res_color}; font-weight: 800; font-size: 13px;'>{meta.result}</span> &nbsp;<span style='color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 500;'>{term_desc}</span>"
        )

        opening = meta.opening or "Unknown Opening"
        self.opening_label.setText(opening)

        speed_cat = getattr(meta, "speed_category", "")
        moves = getattr(game, "moves", None) or []
        num_moves = (len(moves) + 1) // 2 if moves else 0

        details_parts = []
        if speed_cat:
            details_parts.append(speed_cat)
        if num_moves:
            details_parts.append(f"{num_moves} moves")

        if details_parts:
            self.details_label.setText("  •  ".join(details_parts))
            self.details_label.setVisible(True)
        else:
            self.details_label.setVisible(False)

    def update_summary(self, summary) -> None:
        clear_layout(self.stats_layout)

        if not summary or "white" not in summary:
            self.w_circular_acc.set_data(0.0, None)
            self.b_circular_acc.set_data(0.0, None)
            return

        w_acc = summary["white"].get("accuracy", 0.0)
        b_acc = summary["black"].get("accuracy", 0.0)
        w_acpl = summary["white"].get("acpl", None)
        b_acpl = summary["black"].get("acpl", None)

        self.w_circular_acc.set_data(w_acc, w_acpl)
        self.b_circular_acc.set_data(b_acc, b_acpl)

        # Stats Grid Header
        self.stats_layout.addWidget(QWidget(), 0, 0)
        lbl_w = Label("White", role=TextRole.BODY_LARGE, weight=700)
        lbl_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_layout.addWidget(lbl_w, 0, 1)

        self.stats_layout.addWidget(QWidget(), 0, 2)

        lbl_b = Label("Black", role=TextRole.BODY_LARGE, weight=700)
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_layout.addWidget(lbl_b, 0, 3)

        for i, type_name in enumerate(CLASSIFICATION_ORDER):
            color = Styles.get_class_color(type_name)
            bg_tint = f"{color}15"

            # Create row container widget for subtle background tint
            row_frame = QFrame()
            row_frame.setStyleSheet(f"background-color: {bg_tint}; border-radius: 4px;")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(6, 2, 6, 2)

            lbl_type = Label(
                type_name,
                role=TextRole.CAPTION,
                weight=700,
                tone=classification_tone(type_name),
            )
            self.stats_layout.addWidget(lbl_type, i + 1, 0)

            val_w = summary["white"].get(type_name, 0)
            lbl_val_w = Label(
                str(val_w),
                role=TextRole.BODY,
                weight=700,
                tone=classification_tone(type_name),
            )
            lbl_val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(lbl_val_w, i + 1, 1)

            icon_label = IconLabel(
                self.resource_manager.get_icon(type_name),
                size=20,
                fallback="-",
            )
            self.stats_layout.addWidget(icon_label, i + 1, 2)

            val_b = summary["black"].get(type_name, 0)
            lbl_val_b = Label(
                str(val_b),
                role=TextRole.BODY,
                weight=700,
                tone=classification_tone(type_name),
            )
            lbl_val_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(lbl_val_b, i + 1, 3)

    def export_annotated_pgn(self) -> None:
        if self.current_game is None:
            return

        try:
            from PyQt6.QtWidgets import QFileDialog

            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Export Annotated PGN",
                "game.pgn",
                "PGN Files (*.pgn)",
            )
            if not file_name:
                return
            if not Path(file_name).suffix:
                file_name = f"{file_name}.pgn"

            pgn = AnnotatedPGNExporter.export_game(self.current_game)
            with Path(file_name).open("w", encoding="utf-8", newline="\n") as output:
                output.write(pgn)
            ToastManager.success(self, "Annotated PGN exported.")
        except Exception as e:
            logger.error("Annotated PGN export failed: %s", e, exc_info=True)
            ToastManager.error(self, f"Export failed: {e}")

    def open_share_report(self) -> None:
        if not ShareReportRenderer.can_render(self.current_game):
            return
        try:
            dialog = ShareReportDialog(self.current_game, self)
        except Exception as error:
            logger.error(
                "Could not render shareable game report: %s", error, exc_info=True
            )
            ToastManager.error(self, "Could not render the game report.")
            return
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    # ------------------------------------------------------------------
    # Helpers / lifecycle
    # ------------------------------------------------------------------

    def _update_share_report_button(self) -> None:
        can_share = ShareReportRenderer.can_render(self.current_game)
        self.share_report_button.setEnabled(can_share)
        self.share_report_button.setToolTip(
            "Open the shareable game report"
            if can_share
            else "Analyze this game before sharing a report"
        )

    def _has_move_analysis(self) -> bool:
        """Whether the current game has analysis data worth exporting."""
        for move in getattr(self.current_game, "moves", []) or []:
            if (
                move.classification
                or move.eval_after_cp is not None
                or move.eval_after_mate is not None
                or move.pv
                or move.multi_pvs
            ):
                return True
        return False

    @staticmethod
    def _get_result_color(meta, user_side: str | None) -> str:
        if meta.result == "1-0":
            return Styles.COLOR_BLUNDER if user_side == "black" else Styles.COLOR_BEST
        if meta.result == "0-1":
            return Styles.COLOR_BLUNDER if user_side == "white" else Styles.COLOR_BEST

        return Styles.COLOR_TEXT_PRIMARY

    def refresh_styles(self) -> None:
        """Re-render data-driven content; card/divider chrome is global."""
        self.w_circular_acc.refresh_styles()
        self.b_circular_acc.refresh_styles()

        if self.current_game:
            self.update_summary(self.current_game.summary)


__all__ = ["ReportTab"]
