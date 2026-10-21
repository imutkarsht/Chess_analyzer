"""Move-list selection: checkmate ends the game, so alternatives are not shown."""

import chess

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
    mocker.patch("src.gui.analysis.move_list_panel.LiveAnalysisWorker")
    panel = MoveListPanel()
    qtbot.addWidget(panel)
    return panel


def test_checkmate_shows_only_the_mating_line(qtbot, mocker):
    mating = _line(["d6e7"], "28. Qxe7#", "M1")
    alternative = _line(["h1h2"], "28. Rh1 Qxh1+ 29. Rxh1", "2.82")
    panel = _panel(qtbot, mocker)
    panel.set_game(_game(mating, alternative))
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))
    panel.engine_lines_enabled = True

    panel.select_move(0)

    assert emitted == [([mating], True, chess.STARTING_FEN)]
    # A finished game must not start another engine search.
    assert panel.analysis_timer.isActive() is False
    assert panel.live_worker.set_position.call_args.args[0] is None

    # Toggling engine lines off must not bring the alternative back.
    panel.set_engine_lines_enabled(False)
    assert emitted[-1][0] == [mating]


def test_checkmate_prefers_the_line_starting_with_the_played_move(qtbot, mocker):
    other = _line(["a2a3"], "28. a3 Qxh1+", "2.82")
    mating = _line(["d6e7"], "28. Qxe7#", "M1")
    panel = _panel(qtbot, mocker)
    panel.set_game(_game(other, mating))
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))

    panel.select_move(0)

    assert emitted[0][0] == [mating]


def test_non_checkmate_keeps_all_engine_lines(qtbot, mocker):
    first = _line(["d6e7"], "28. Qxe7", "2.82")
    second = _line(["h1h2"], "28. Rh1", "2.10")
    panel = _panel(qtbot, mocker)
    panel.set_game(_game(first, second, san="Qxe7"))
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))

    panel.select_move(0)

    assert emitted[0][0] == [first, second]


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

    assert emitted == [([reply, alternative], False, after_e4)]

    # Live analysis must target the same position the board shows.
    panel.engine_lines_enabled = True
    panel.start_live_analysis()
    assert panel.live_worker.set_position.call_args.args[0] == after_e4
