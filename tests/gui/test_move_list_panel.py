"""Move-list selection: White-perspective lines for the position on the board."""

import chess
import pytest

from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.analysis.move_list_panel import MoveListPanel


def _line(pv: list[str], san: str, score: str, depth: int = 26) -> dict:
    return {"pv": pv, "pv_san": san, "score_value": score, "depth": depth}


def _game(*lines: dict, san: str = "Qxe7#") -> GameAnalysis:
    metadata = GameMetadata(white="W", black="B", result="1-0")
    move = MoveAnalysis(
        move_number=28,
        ply=55,
        san=san,
        uci="d6e7",
        fen_before=chess.STARTING_FEN,
        eval_before_mate=1 if san.endswith("#") else None,
        multi_pvs=list(lines),
    )
    return GameAnalysis(game_id="mate", metadata=metadata, moves=[move], pgn_content="")


def _panel(qtbot, mocker) -> MoveListPanel:
    mocker.patch("src.gui.analysis.move_list_panel.LiveEngineSession")
    panel = MoveListPanel()
    qtbot.addWidget(panel)
    return panel


def _timed_game() -> GameAnalysis:
    moves = [
        MoveAnalysis(1, i + 1, san, uci, chess.STARTING_FEN, time_spent=2.0)
        for i, (san, uci) in enumerate(
            [("e4", "e2e4"), ("e5", "e7e5"), ("Nf3", "g1f3"), ("Nc6", "b8c6")]
        )
    ]
    return GameAnalysis(
        game_id="timed",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=moves,
        pgn_content="",
    )


@pytest.mark.parametrize(
    ("panel_width", "expect_time"),
    [(280, True), (220, False)],
)
def test_think_time_stays_inline_at_default_pane_width(
    qtbot, mocker, panel_width, expect_time
):
    """The allowed splitter width must not force users to expand for clocks."""
    panel = _panel(qtbot, mocker)
    panel.resize(panel_width, 500)
    panel.set_game(_timed_game())
    panel.show()
    qtbot.wait(10)

    panel._update_compact_mode()

    assert all(w._compact != expect_time for w in panel._move_widgets.values())


def test_time_gap_grows_when_pane_is_stretched(qtbot, mocker):
    """Extra column width belongs between the SAN and the clock, not as dead space."""
    panel = _panel(qtbot, mocker)
    panel.set_game(_timed_game())
    panel.show()

    panel.resize(280, 500)
    qtbot.wait(10)
    panel._update_compact_mode()
    cell = panel._move_widgets[0]
    narrow_time_x = cell._time_label.x()

    panel.resize(420, 500)
    qtbot.wait(10)
    wide_time_x = cell._time_label.x()

    assert wide_time_x > narrow_time_x


def test_checkmate_shows_only_the_mating_line(qtbot, mocker):
    mating = _line(["d6e7"], "28. Qxe7#", "M1")
    alternative = _line(["h1h2"], "28. Rh1 Qxh1+ 29. Rxh1", "2.82")
    panel = _panel(qtbot, mocker)
    panel.set_game(_game(mating, alternative))
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))
    panel.engine_lines_enabled = True

    panel.select_move(0)

    lines, fen = emitted[0]
    assert fen == chess.STARTING_FEN
    assert [line.first_move for line in lines] == ["d6e7"]
    assert lines[0].score_text == "M1"
    # A finished game must not start another engine search.
    panel.session.request.assert_not_called()

    # Toggling engine lines off must not bring the alternative back.
    panel.set_engine_lines_enabled(False)
    assert [line.first_move for line in emitted[-1][0]] == ["d6e7"]


def test_checkmate_prefers_the_line_starting_with_the_played_move(qtbot, mocker):
    other = _line(["a2a3"], "28. a3 Qxh1+", "2.82")
    mating = _line(["d6e7"], "28. Qxe7#", "M1")
    panel = _panel(qtbot, mocker)
    panel.set_game(_game(other, mating))
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))

    panel.select_move(0)

    assert [line.first_move for line in emitted[0][0]] == ["d6e7"]


def test_final_non_checkmate_move_analyses_the_position_after_it(qtbot, mocker):
    """The last move has no cached successor, so the live engine takes over."""
    after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    moves = [
        MoveAnalysis(
            1,
            1,
            "e4",
            "e2e4",
            chess.STARTING_FEN,
            multi_pvs=[_line(["d2d4"], "1. d4", "0.30")],
        )
    ]
    game = GameAnalysis(
        game_id="final",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=moves,
        pgn_content="",
    )
    panel = _panel(qtbot, mocker)
    panel.set_game(game)
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))
    panel.engine_lines_enabled = True

    panel.select_move(0)

    lines, fen = emitted[0]
    # The pre-move lines belong to a position the board no longer shows.
    assert lines == []
    assert fen == after_e4
    assert panel.session.request.call_args.args[0] == after_e4


def test_selected_move_shows_lines_from_the_next_position(qtbot, mocker):
    """The board holds the position after the move, so the PV must start there."""
    after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    reply = _line(["e7e5"], "1... e5", "0.20")
    alternative = _line(["c7c5"], "1... c5", "0.10")
    moves = [
        MoveAnalysis(1, 1, "e4", "e2e4", chess.STARTING_FEN),
        MoveAnalysis(1, 2, "e5", "e7e5", after_e4, multi_pvs=[reply, alternative]),
    ]
    game = GameAnalysis(
        game_id="opening",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=moves,
        pgn_content="",
    )
    panel = _panel(qtbot, mocker)
    panel.set_game(game)
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))

    panel.select_move(0)

    lines, fen = emitted[0]
    assert fen == after_e4
    # Black is to move, so the stored +0.20 becomes -0.20 for White.
    assert [(line.first_move, line.cp) for line in lines] == [("e7e5", -20), ("c7c5", -10)]
