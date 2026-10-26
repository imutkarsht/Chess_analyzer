"""Eval-bar rendering and analysis-position replay for the board."""

import chess

from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.board import Board, EvalBarWidget


def test_eval_label_is_drawn_when_white_wins(qapp):
    """The label must stay inside the bar on the white (winning) side."""
    bar = EvalBarWidget()
    bar.resize(24, 200)
    bar.set_eval(0, 3)  # mate snaps the bar to a full white fill

    image = bar.grab().toImage()
    bottom = int(image.height() * 0.9)
    dark_pixels = sum(
        1
        for x in range(image.width())
        for y in range(bottom, image.height())
        if image.pixelColor(x, y).lightness() < 128
    )
    assert dark_pixels > 0


def test_analysis_position_renders_arrow_and_keeps_game_replay(qapp):
    """Variation rendering must not destroy the moves exit needs to restore."""
    move = MoveAnalysis(1, 1, "e4", "e2e4", chess.STARTING_FEN)
    game = GameAnalysis("id", GameMetadata(), [move], "pgn")
    widget = Board()
    widget.load_game(game)

    widget.load_analysis_position(chess.STARTING_FEN)
    widget.set_best_move("e2e4")
    widget.set_dimmed(True)

    assert widget.interactive is True
    assert widget.game_moves == game.moves

    colors = {"light": "#FFFFFF", "dark": "#000000"}
    svg = widget._generate_custom_board_svg(colors, "")
    assert b"<polygon" in svg  # best-move arrow head
    assert b'opacity="0.10"' in svg  # exploring dim

    widget.board.push_uci("e2e4")
    assert widget.undo_move() is True
    assert widget.board.fen() == chess.STARTING_FEN

    # Back to playback: the game position is restored, analysis chrome is gone.
    widget.set_best_move(None)
    widget.set_dimmed(False)
    widget.set_position(0)
    assert widget.board.peek().uci() == "e2e4"
    assert b"<polygon" not in widget._generate_custom_board_svg(colors, "")
