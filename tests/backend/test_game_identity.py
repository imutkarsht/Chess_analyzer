"""Normalized identity keys used by the import workspace."""

from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.game_identity import game_identity_key, normalize_date
from src.backend.storage.pgn_parser import PGNParser


def test_identity_key_normalizes_dates_and_player_names():
    assert normalize_date("2024-05-06") == "2024.05.06"
    assert normalize_date("2024/05/06") == "2024.05.06"
    assert game_identity_key(
        "2024-05-06", " Alice ", "BOB", "1-0"
    ) == ("2024.05.06", "alice", "bob", "1-0")


def test_history_returns_normalized_identity_keys(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "history.db"))
    pgn = (
        '[Event "One"]\n[Site "https://lichess.org/aaaaaaaa"]\n'
        '[Date "2024.05.06"]\n[White "Alice"]\n[Black "Bob"]\n'
        '[Result "1-0"]\n\n1. e4 e5 1-0'
    )
    game = PGNParser.parse_pgn_text(pgn)[0]
    manager.save_game(game, game.pgn_content)

    keys = manager.get_game_identity_keys()

    assert ("2024.05.06", "alice", "bob", "1-0") in keys
