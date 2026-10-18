"""
Tests for data models - GameMetadata, GameAnalysis, MoveAnalysis.
"""

from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis


class TestModels:
    """Tests for storage data models - GameMetadata, GameAnalysis, MoveAnalysis."""

    def test_model_defaults_and_attributes(self):
        """Test default values and attribute assignments across models."""
        meta = GameMetadata(
            white="Magnus",
            black="Hikaru",
            result="1/2-1/2",
            date="2023.12.01",
            event="World Championship",
            headers={"Site": "lichess.org"},
            white_elo="2800",
            source="lichess",
        )
        assert meta.source == "lichess"
        assert meta.white == "Magnus"
        assert meta.white_elo == "2800"
        assert meta.starting_fen is None

        move = MoveAnalysis(
            1, 1, "e4", "e2e4", "startfen", classification="Best", eval_before_cp=30
        )
        assert move.san == "e4"
        assert move.classification == "Best"
        assert move.eval_before_cp == 30

        game = GameAnalysis(
            game_id="test123", metadata=meta, moves=[move], pgn_content="1. e4 1/2-1/2"
        )
        assert game.game_id == "test123"
        assert len(game.moves) == 1
        assert game.summary == {}


class TestMoveAnalysisSerialization:
    """Tests for MoveAnalysis serialization and deserialization."""

    def test_to_dict_and_from_dict_roundtrip(self):
        """Test MoveAnalysis can be serialized to dict and reconstructed losslessly."""
        original = MoveAnalysis(
            move_number=3,
            ply=5,
            san="Nf3",
            uci="g1f3",
            fen_before="r1bqkbnr/pppppppp/2n5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
            eval_before_cp=40,
            eval_before_mate=None,
            best_move="g1f3",
            best_eval_cp=40,
            best_eval_mate=None,
            pv=["g1f3", "g8f6"],
            eval_after_cp=35,
            eval_after_mate=None,
            win_chance_before=0.55,
            win_chance_after=0.54,
            classification="Best",
            explanation="Natural developing move",
            multi_pvs=[{"move": "g1f3", "eval": 40}],
            is_book_move=True,
            book_move_count=2,
            book_exit_move=False,
            eco="C50",
            opening_name="Italian Game",
            candidate_continuations=["d2d4", "f1c4"],
            time_left=175.5,
            time_spent=4.5,
            raw_clk="0:02:55.5",
        )
        d = original.to_dict()
        assert isinstance(d, dict)
        assert d["san"] == "Nf3"
        assert d["time_spent"] == 4.5

        reconstructed = MoveAnalysis.from_dict(d)
        assert reconstructed.move_number == original.move_number
        assert reconstructed.ply == original.ply
        assert reconstructed.san == original.san
        assert reconstructed.uci == original.uci
        assert reconstructed.fen_before == original.fen_before
        assert reconstructed.eval_before_cp == original.eval_before_cp
        assert reconstructed.best_move == original.best_move
        assert reconstructed.classification == original.classification
        assert reconstructed.time_spent == original.time_spent
        assert reconstructed.raw_clk == original.raw_clk
        assert reconstructed.is_book_move is True
        assert reconstructed.candidate_continuations == ["d2d4", "f1c4"]

    def test_from_dict_fallback_defaults(self):
        """Test from_dict handles empty or partial dictionary with clean defaults."""
        move = MoveAnalysis.from_dict({})
        assert move.move_number == 0
        assert move.ply == 0
        assert move.san == ""
        assert move.uci == ""
        assert move.fen_before == ""
        assert move.eval_before_cp is None
        assert move.is_book_move is False
        assert move.win_chance_before == 0.5
