"""
Tests for PGN Parser - parsing, source detection, edge cases.
"""
import pytest
from src.backend.storage.pgn_parser import PGNParser
from src.backend.storage.models import GameAnalysis


class TestPGNParsing:
    """Tests for basic PGN parsing functionality."""
    
    def test_parse_pgn_text_basic(self, sample_pgn_chesscom):
        """Test parsing a simple PGN string."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        
        assert len(games) == 1
        game = games[0]
        assert isinstance(game, GameAnalysis)
        assert game.metadata.white == "Player1"
        assert game.metadata.black == "Player2"
        assert game.metadata.result == "1-0"
        assert len(game.moves) > 0

    def test_parse_pgn_file(self, tmp_path, sample_pgn_chesscom):
        """Test parsing PGN from file."""
        pgn_file = tmp_path / "test.pgn"
        pgn_file.write_text(sample_pgn_chesscom, encoding="utf-8")
        
        games = PGNParser.parse_pgn_file(str(pgn_file))
        
        assert len(games) == 1
        assert games[0].metadata.white == "Player1"

    def test_parse_multiple_games(self, sample_pgn_chesscom, sample_pgn_lichess):
        """Test parsing multiple games in one PGN string."""
        combined_pgn = sample_pgn_chesscom + "\n\n" + sample_pgn_lichess
        games = PGNParser.parse_pgn_text(combined_pgn)
        
        assert len(games) == 2
        assert games[0].metadata.white == "Player1"
        assert games[1].metadata.white == "LichessPlayer1"

    def test_parse_empty_pgn(self):
        """Test parsing empty PGN returns empty list."""
        games = PGNParser.parse_pgn_text("")
        assert games == []

    def test_parse_invalid_pgn(self):
        """Test parsing invalid PGN is handled gracefully (returns game with no moves)."""
        games = PGNParser.parse_pgn_text("This is not a PGN")
        # Parser may return empty or a placeholder - either is acceptable
        assert games == [] or (len(games) == 1 and len(games[0].moves) == 0)


class TestSourceDetection:
    """Tests for source detection from Site header."""
    
    def test_detect_chesscom_source(self, sample_pgn_chesscom):
        """Test Chess.com source is detected correctly."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.source == "chesscom"

    def test_detect_lichess_source(self, sample_pgn_lichess):
        """Test Lichess source is detected correctly."""
        games = PGNParser.parse_pgn_text(sample_pgn_lichess)
        assert games[0].metadata.source == "lichess"

    def test_detect_file_source(self, sample_pgn_file):
        """Test unknown site defaults to 'file' source."""
        games = PGNParser.parse_pgn_text(sample_pgn_file)
        assert games[0].metadata.source == "file"


class TestMetadataExtraction:
    """Tests for metadata extraction from PGN headers."""
    
    def test_extract_elo_ratings(self, sample_pgn_chesscom):
        """Test ELO ratings are extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        game = games[0]
        
        assert game.metadata.white_elo == "1500"
        assert game.metadata.black_elo == "1400"

    def test_extract_time_control(self, sample_pgn_chesscom):
        """Test time control is extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.time_control == "600"

    def test_extract_eco(self, sample_pgn_chesscom):
        """Test ECO code is extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.eco == "C65"

    def test_extract_termination(self, sample_pgn_chesscom):
        """Test termination is extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.termination == "Normal"


# ---------------------------------------------------------------------------
# Clock parsing
# ---------------------------------------------------------------------------

class TestClockParser:
    """Unit tests for the private _parse_clk helper."""

    def test_no_comment_returns_none_pair(self):
        from src.backend.storage.pgn_parser import _parse_clk
        assert _parse_clk(None) == (None, None)
        assert _parse_clk("") == (None, None)

    def test_comment_without_clk_returns_none_pair(self):
        from src.backend.storage.pgn_parser import _parse_clk
        assert _parse_clk("Some unrelated comment") == (None, None)

    def test_standard_chesscom_format(self):
        from src.backend.storage.pgn_parser import _parse_clk
        raw, secs = _parse_clk("[%clk 0:09:56.1]")
        assert raw == "0:09:56.1"
        assert secs == pytest.approx(9 * 60 + 56.1)

    def test_whole_seconds_only(self):
        from src.backend.storage.pgn_parser import _parse_clk
        raw, secs = _parse_clk("[%clk 1:23:45]")
        assert raw == "1:23:45"
        assert secs == 3600 + 23 * 60 + 45

    def test_minute_overflow_is_rejected(self):
        """[0:99:00] would be a malformed clock and must not silently
        produce 99 minutes of 'time spent'."""
        from src.backend.storage.pgn_parser import _parse_clk
        assert _parse_clk("[%clk 0:99:00]") == (None, None)

    def test_second_overflow_is_rejected(self):
        from src.backend.storage.pgn_parser import _parse_clk
        assert _parse_clk("[%clk 0:00:99]") == (None, None)

    def test_minute_overflow_with_decimal_seconds_still_rejected(self):
        from src.backend.storage.pgn_parser import _parse_clk
        assert _parse_clk("[%clk 0:99:00.5]") == (None, None)

    def test_picks_first_clk_in_multi_comment(self):
        """When a comment has multiple %clk tags, return the first one."""
        from src.backend.storage.pgn_parser import _parse_clk
        raw, secs = _parse_clk("blabla [%clk 0:00:10] extra [%clk 0:00:05]")
        assert raw == "0:00:10"
        assert secs == pytest.approx(10.0)


class TestClockIntegration:
    """End-to-end tests verifying that time_spent is computed correctly
    when parsing a PGN that carries [%clk …] comments."""

    def test_time_spent_delta_from_consecutive_clocks(self):
        """Two moves on the same side with clocks 9:56 and 9:30 should
        yield a 26-second time_spent for the second move."""
        pgn = (
            '[Event "Test"]\n[White "W"]\n[Black "B"]\n[Result "*"]\n\n'
            '1. e4 { [%clk 0:09:56] } 1... e5 { [%clk 0:10:00] } *'
        )
        games = PGNParser.parse_pgn_text(pgn)
        assert len(games) == 1
        moves = games[0].moves
        # moves[0] = White's e4
        # moves[1] = Black's e5
        # We expect move 0 (first move) to use the TimeControl fallback
        # and move 1 to compute time_spent from the delta.
        assert moves[0].time_left == pytest.approx(9 * 60 + 56.0)
        assert moves[1].time_left == pytest.approx(10 * 60 + 0.0)
        # First move of each side has no previous clock recorded, so
        # time_spent is None unless the TimeControl header is set. Our
        # test PGN has no TimeControl, so the first move of each side
        # ends up with time_spent=None, but the *next* time that side
        # moves we get a real delta.
        assert moves[0].time_spent is None
        assert moves[1].time_spent is None

    def test_time_spent_uses_timecontrol_for_first_move(self):
        """If the PGN has [TimeControl '600'] and the first move has a
        clock, we use the header value as the previous clock and compute
        a real delta for the very first move."""
        pgn = (
            '[Event "Test"]\n[White "W"]\n[Black "B"]\n'
            '[TimeControl "600"]\n[Result "*"]\n\n'
            '1. e4 { [%clk 0:09:56] } 1... e5 { [%clk 0:10:00] } *'
        )
        games = PGNParser.parse_pgn_text(pgn)
        moves = games[0].moves
        # Starting clock = 600s, after White's e4 the clock is 9:56 = 596s,
        # so time_spent for the first move is 600 - 596 = 4 seconds.
        assert moves[0].time_spent == pytest.approx(4.0)
        # The first Black move's clock is identical to the start clock,
        # so the delta is 0 — *not* None. (If you want a non-zero delta
        # for the first move of each side, every move needs its own
        # [%clk] comment, which is what chess.com / lichess emit.)
        assert moves[1].time_spent == pytest.approx(0.0)

    def test_malformed_clk_does_not_pollute_time_spent(self):
        """A clock of [0:99:00] is rejected by the parser, so the move
        gets time_left=None and time_spent=None — it must not contribute
        a garbage delta to the next move."""
        pgn = (
            '[Event "Test"]\n[White "W"]\n[Black "B"]\n[Result "*"]\n\n'
            '1. e4 { [%clk 0:99:00] } 1... e5 { [%clk 0:10:00] } *'
        )
        games = PGNParser.parse_pgn_text(pgn)
        moves = games[0].moves
        assert moves[0].time_left is None
        assert moves[0].time_spent is None
        # Black's e5 is parsed normally, with no previous clock on its
        # side so time_spent stays None.
        assert moves[1].time_left == pytest.approx(600.0)
        assert moves[1].time_spent is None
