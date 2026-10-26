"""Tests for analysis lifecycle, caching, and final-position evaluation paths."""

import json
import threading

import chess
import chess.engine
import pytest

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis


def _analyzer(mocker):
    manager = EngineManager("dummy_path")
    analyzer = Analyzer(manager)
    mocker.patch.object(manager, "stop_engine")
    return analyzer


def _game(moves, pgn_content=""):
    return GameAnalysis(
        game_id="paths",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=moves,
        pgn_content=pgn_content,
    )


def _move(fen=chess.STARTING_FEN, uci="e2e4", **kwargs):
    return MoveAnalysis(
        move_number=kwargs.pop("move_number", 1),
        ply=kwargs.pop("ply", 1),
        san=kwargs.pop("san", "e4"),
        uci=uci,
        fen_before=fen,
        **kwargs,
    )


class TestAnalysisLifecycle:
    def test_interrupted_error_saves_paused_state(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.history_manager = mocker.Mock()
        mocker.patch.object(analyzer, "_analyze_positions", side_effect=InterruptedError)
        game = _game([_move()], pgn_content="1. e4 *")

        with pytest.raises(InterruptedError):
            analyzer.analyze_game(game)

        assert game.summary["analysis_status"] == "paused"
        analyzer.history_manager.save_game.assert_called_once()
        analyzer.engine_manager.stop_engine.assert_called_once()

    def test_cancel_before_loop_preserves_partial_results(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.history_manager = mocker.Mock()
        mocker.patch.object(analyzer.engine_manager, "start_engine")
        mocker.patch.object(analyzer, "_get_position_analysis")
        cancel_token = threading.Event()
        cancel_token.set()
        game = _game([_move()], pgn_content="1. e4 *")

        analyzer.analyze_game(game, cancel_token=cancel_token)

        analyzer._get_position_analysis.assert_not_called()
        assert game.summary["analysis_status"] == "paused"
        analyzer.history_manager.save_game.assert_called_once()

    def test_engine_failure_during_cancel_is_not_reraised(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.history_manager = mocker.Mock()
        cancel_token = threading.Event()
        mocker.patch.object(analyzer.engine_manager, "start_engine")

        def cancel_engine(*_args):
            cancel_token.set()
            raise RuntimeError("engine killed")

        mocker.patch.object(
            analyzer, "_get_position_analysis", side_effect=cancel_engine
        )
        game = _game([_move()], pgn_content="1. e4 *")

        analyzer.analyze_game(game, cancel_token=cancel_token)

        assert game.summary["analysis_status"] == "paused"
        analyzer.engine_manager.stop_engine.assert_called_once()

    def test_cancel_sets_event_and_reaches_engine(self, mocker):
        analyzer = _analyzer(mocker)
        cancel_engine = mocker.patch.object(
            analyzer.engine_manager, "cancel_current_analysis"
        )

        analyzer.cancel()
        assert cancel_engine.call_count == 1

        analyzer._cancel_event = threading.Event()
        analyzer.cancel()

        assert analyzer._cancel_event.is_set()
        assert cancel_engine.call_count == 2

    def test_close_swallows_cleanup_failures(self, mocker):
        analyzer = _analyzer(mocker)
        for attribute in ("cache", "_opening_db", "polyglot_book"):
            resource = getattr(analyzer, attribute)
            mocker.patch.object(resource, "close", side_effect=RuntimeError("broken"))

        analyzer.close()

    def test_context_manager_closes_on_exit(self, mocker):
        analyzer = _analyzer(mocker)
        close = mocker.patch.object(analyzer, "close")

        with analyzer as entered:
            assert entered is analyzer

        close.assert_called_once()


def test_resume_false_clears_previous_analysis(mocker):
    analyzer = _analyzer(mocker)
    mocker.patch.object(analyzer, "_get_position_analysis", return_value=[])
    mocker.patch.object(analyzer, "_analyze_final_position", return_value=None)
    mocker.patch.object(analyzer, "_classify_and_calculate_stats")
    mocker.patch.object(analyzer, "_calculate_final_accuracy")
    mocker.patch.object(analyzer, "_log_classification_summary")
    mocker.patch.object(analyzer.engine_manager, "start_engine")
    move = _move(eval_before_cp=99, eval_after_cp=99, classification="Blunder")
    game = _game([move])

    analyzer._analyze_positions(game, resume=False)

    assert move.eval_before_cp is None
    assert move.eval_after_cp is None
    assert move.classification == ""
    assert game.summary == {}


class TestPositionAnalysisCache:
    def test_valid_cached_json_skips_engine(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.cache = mocker.Mock()
        analyzer.config = {"use_cache": True, "depth": 18, "multi_pv": 1, "time_per_move": 1}
        analyzer.cache.get_analysis.return_value = json.dumps(
            [{"pv": ["e2e4"], "cp": 25, "depth": 12}]
        )
        analyze = mocker.patch.object(analyzer.engine_manager, "analyze_position")

        result = analyzer._get_position_analysis(chess.Board(), _move())

        assert result == [{"pv": ["e2e4"], "cp": 25, "depth": 12}]
        analyze.assert_not_called()

    @pytest.mark.parametrize(
        ("cached", "expected"),
        [
            ({"pv": ["e2e4"], "cp": 10}, [{"pv": ["e2e4"], "cp": 10}]),
            ([{"pv": ["d2d4"]}], [{"pv": ["d2d4"]}]),
        ],
    )
    def test_cached_dict_or_list_is_normalized(self, mocker, cached, expected):
        analyzer = _analyzer(mocker)
        analyzer.cache = mocker.Mock()
        analyzer.config = {"use_cache": True, "depth": 18, "multi_pv": 1, "time_per_move": 1}
        analyzer.cache.get_analysis.return_value = cached

        assert analyzer._get_position_analysis(chess.Board(), _move()) == expected

    def test_corrupt_cached_json_falls_back_to_engine(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.cache = mocker.Mock()
        analyzer.config = {"use_cache": True, "depth": 18, "multi_pv": 1, "time_per_move": 1}
        analyzer.cache.get_analysis.return_value = "{not json"
        engine_info = [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE),
                "pv": [chess.Move.from_uci("e2e4")],
                "depth": 14,
            }
        ]
        mocker.patch.object(
            analyzer.engine_manager, "analyze_position", return_value=engine_info
        )

        assert analyzer._get_position_analysis(chess.Board(), _move()) == engine_info
        analyzer.cache.save_analysis.assert_called_once()
        cached_payload = analyzer.cache.save_analysis.call_args.args[2]
        assert cached_payload == [{"cp": 30, "pv": ["e2e4"], "depth": 14}]

    def test_engine_list_is_wrapped_and_non_dicts_are_not_cached(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.cache = mocker.Mock()
        analyzer.config = {"use_cache": True, "depth": 18, "multi_pv": 1, "time_per_move": 1}
        analyzer.cache.get_analysis.return_value = None
        engine_info = [{"pv": [], "depth": 12}, "junk"]
        mocker.patch.object(
            analyzer.engine_manager, "analyze_position", return_value=engine_info
        )

        result = analyzer._get_position_analysis(chess.Board(), _move())

        assert result == engine_info
        assert analyzer.cache.save_analysis.call_args.args[2] == [
            {"pv": [], "depth": 12}
        ]


class TestFinalPosition:
    def test_no_moves_returns_none(self, mocker):
        analyzer = _analyzer(mocker)

        assert analyzer._analyze_final_position(_game([]), chess.Board()) is None

    def test_checkmate_returns_mate_for_losing_side(self, mocker):
        analyzer = _analyzer(mocker)
        moves = []
        board = chess.Board()
        for number, san in [(1, "f3"), (1, "e5"), (2, "g4"), (2, "Qh4#")]:
            moves.append(
                _move(
                    fen=board.fen(),
                    uci=board.parse_san(san).uci(),
                    san=san,
                    move_number=number,
                    ply=len(moves) + 1,
                )
            )
            board.push_san(san)

        score = analyzer._analyze_final_position(_game(moves), chess.Board())

        assert score.is_mate()
        assert score.relative.mate() == -1

    def test_stalemate_returns_draw_score(self, mocker):
        analyzer = _analyzer(mocker)
        stalemate_before = "k7/8/2K5/8/8/8/8/1R6 w - - 0 1"
        move = _move(fen=stalemate_before, uci="b1b7", san="Rb7")
        board = chess.Board(stalemate_before)
        board.push_uci("b1b7")
        assert board.is_stalemate()

        score = analyzer._analyze_final_position(_game([move]), chess.Board())

        assert score.relative.score() == 0

    def test_other_game_over_returns_draw_score(self, mocker):
        analyzer = _analyzer(mocker)
        move = _move()
        mocker.patch.object(
            chess.Board, "is_game_over", return_value=True
        )
        mocker.patch.object(chess.Board, "is_checkmate", return_value=False)

        score = analyzer._analyze_final_position(_game([move]), chess.Board())

        assert score.relative.score() == 0

    def test_engine_score_is_returned_for_unfinished_game(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.config = {"depth": 18, "multi_pv": 1, "time_per_move": 1}
        expected = chess.engine.PovScore(chess.engine.Cp(42), chess.BLACK)
        mocker.patch.object(
            analyzer.engine_manager,
            "analyze_position",
            return_value=[{"score": expected}],
        )

        assert analyzer._analyze_final_position(_game([_move()]), chess.Board()) is expected

    def test_empty_engine_result_returns_none(self, mocker):
        analyzer = _analyzer(mocker)
        analyzer.config = {"depth": 18, "multi_pv": 1, "time_per_move": 1}
        mocker.patch.object(
            analyzer.engine_manager, "analyze_position", return_value=[]
        )

        assert analyzer._analyze_final_position(_game([_move()]), chess.Board()) is None


class TestNextEval:
    def _game(self, moves):
        return _game(moves)

    def test_uses_next_move_eval_before(self, mocker):
        analyzer = _analyzer(mocker)
        first = _move()
        second = _move(eval_before_cp=15, eval_before_mate=None)
        second.fen_before = (
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        )

        assert analyzer._get_next_eval(self._game([first, second]), 0, None, None) == (15, None)

    def test_falls_back_to_current_eval_after(self, mocker):
        analyzer = _analyzer(mocker)
        first = _move(eval_after_cp=-20)
        second = _move()

        assert analyzer._get_next_eval(self._game([first, second]), 0, None, None) == (-20, None)

    def test_falls_back_to_current_eval_before(self, mocker):
        analyzer = _analyzer(mocker)
        first = _move(eval_before_cp=10)
        second = _move()

        assert analyzer._get_next_eval(self._game([first, second]), 0, None, None) == (10, None)

    @pytest.mark.parametrize(
        ("final_score", "expected"),
        [
            (chess.engine.PovScore(chess.engine.Cp(80), chess.BLACK), (-80, None)),
            (chess.engine.PovScore(chess.engine.Mate(3), chess.BLACK), (None, -3)),
        ],
    )
    def test_final_score_is_flipped_to_white_perspective(
        self, mocker, final_score, expected
    ):
        analyzer = _analyzer(mocker)

        # e4 leaves Black to move, so a Black-relative score must be negated.
        assert analyzer._get_next_eval(self._game([_move()]), 0, final_score, None) == expected

    def test_missing_final_score_returns_none(self, mocker):
        analyzer = _analyzer(mocker)

        assert analyzer._get_next_eval(self._game([_move()]), 0, None, None) == (None, None)
