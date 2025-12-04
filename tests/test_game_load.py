import pytest
from src.backend.pgn_parser import PGNParser
from src.backend.models import GameAnalysis

SAMPLE_PGN = """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2023.10.01"]
[Round "-"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 1-0"""

def test_parse_pgn_text():
    """Test parsing PGN text."""
    games = PGNParser.parse_pgn_text(SAMPLE_PGN)
    assert len(games) == 1
    game = games[0]
    assert isinstance(game, GameAnalysis)
    assert game.metadata.white == "Player1"
    assert game.metadata.black == "Player2"
    assert game.metadata.result == "1-0"
    assert len(game.moves) > 0

def test_parse_pgn_file(tmp_path):
    """Test parsing PGN file."""
    pgn_file = tmp_path / "test.pgn"
    pgn_file.write_text(SAMPLE_PGN, encoding="utf-8")
    
    games = PGNParser.parse_pgn_file(str(pgn_file))
    assert len(games) == 1
    game = games[0]
    assert game.metadata.white == "Player1"
