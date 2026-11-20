# SPDX-License-Identifier: GPL-3.0-only
"""Background AI coach summary generation."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.game_report import build_game_report
from src.backend.analysis.metrics.time_stats import format_time_stats_for_llm
from src.utils.logger import logger


class GenerateSummaryThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, service, game, user_side: str | None = None):
        super().__init__()
        self.service = service
        self.game = game
        self.user_side = user_side

    def run(self):
        logger.info("GenerateSummaryThread started")
        try:
            # Replay the moves onto a fresh board and export a valid PGN.
            # The previous inline string-concat produced invalid notation
            # like "b4 1. Nf6 c4 2. d5 …" because every move was prefixed
            # with its number regardless of side-to-move.

            import chess
            import chess.pgn

            is_chess960 = self.game.metadata.chess960
            if self.game.metadata.starting_fen:
                board = chess.Board(self.game.metadata.starting_fen, chess960=is_chess960)
            else:
                board = chess.Board(chess960=is_chess960)
            pgn_game = chess.pgn.Game()
            if self.game.metadata.starting_fen:
                pgn_game.headers["SetUp"] = "1"
                pgn_game.headers["FEN"] = self.game.metadata.starting_fen
            node = pgn_game
            for move in self.game.moves:
                chess_move = chess.Move.from_uci(move.uci) if move.uci else None
                if chess_move is None or chess_move not in board.legal_moves:
                    # Fall back to SAN parsing for moves without a UCI
                    try:
                        chess_move = board.parse_san(move.san)
                    except Exception as e:
                        logger.warning(
                            "Failed to parse SAN move '%s': %s", getattr(move, "san", "?"), e
                        )
                        continue
                node = node.add_variation(chess_move)
                board.push(chess_move)

            exporter = chess.pgn.StringExporter(headers=False, comments=False, variations=False)
            pgn_text = pgn_game.accept(exporter)
            if not pgn_text.strip():
                pgn_text = " ".join(m.san for m in self.game.moves)

            # Ground the narrative in the engine's own findings instead of the
            # raw ``summary`` dict, which the model would have to interpret.
            facts = build_game_report(self.game, user_side=self.user_side)
            time_stats = format_time_stats_for_llm(self.game.moves)
            summary = self.service.generate_summary(pgn_text, facts, time_stats)
            logger.info("GenerateSummaryThread completed successfully")
            self.finished.emit(summary)
        except Exception as e:
            logger.error(f"GenerateSummaryThread failed: {e}", exc_info=True)
            self.finished.emit(f"Error [{type(e).__name__}]: {e}")
