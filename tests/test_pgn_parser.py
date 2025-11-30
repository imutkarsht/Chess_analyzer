import pytest
from src.backend.pgn_parser import PGNParser
import os

def test_parse_pgn_text_single_game():
    pgn_text = """
[Event "Test Game"]
[Site "Chess.com"]
[Date "2023.01.01"]
[Round "-"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 1-0
"""
    games = PGNParser.parse_pgn_text(pgn_text)
    assert len(games) == 1
    game = games[0]
    assert game.metadata.white == "Player1"
    assert game.metadata.black == "Player2"
    assert game.metadata.result == "1-0"
    assert len(game.moves) > 0
    assert game.moves[0].san == "e4"

def test_parse_pgn_text_multiple_games():
    pgn_text = """
[Event "Game 1"]
[Result "1-0"]

1. e4 e5 1-0

[Event "Game 2"]
[Result "0-1"]

1. d4 d5 0-1
"""
    games = PGNParser.parse_pgn_text(pgn_text)
    assert len(games) == 2
    assert games[0].metadata.event == "Game 1"
    assert games[1].metadata.event == "Game 2"

def test_parse_pgn_file(tmp_path):
    # Create a temporary PGN file
    d = tmp_path / "subdir"
    d.mkdir()
    p = d / "test.pgn"
    p.write_text("""
[Event "File Game"]
[White "W"]
[Black "B"]
[Result "*"]

1. e4 c5 *
""")
    
    games = PGNParser.parse_pgn_file(str(p))
    assert len(games) == 1
    assert games[0].metadata.white == "W"
