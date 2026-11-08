"""Bulk import storage behaviour."""

from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.pgn_parser import PGNParser

_PGN = (
    '[Event "One"]\n[Site "https://lichess.org/aaaaaaaa"]\n'
    '[Date "2024.05.06"]\n[White "Alice"]\n[Black "Bob"]\n'
    '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0'
)


def test_unanalyzed_bulk_history_uses_detector_termination(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "history.db"))
    pgn = (
        '[Event "rated bullet game"]\n'
        '[Site "https://lichess.org/game/rr4SgLCv"]\n'
        '[Date "2026.08.23"]\n[White "RipJaw016"]\n'
        '[Black "ImutKarsht"]\n[Result "1-0"]\n'
        '[TimeControl "120+1"]\n[Termination "Time forfeit"]\n\n'
        "1. e4 e5 2. Nf3 Nc6 1-0"
    )
    stub = PGNParser.parse_game_stub(pgn)
    assert stub is not None
    assert manager.save_unanalyzed_games_bulk([stub]) == (1, 0)

    stored = manager.get_game_analysis(stub.game_id)

    assert stored is not None
    assert stored.metadata.termination == "Time forfeit"
    assert stored.metadata.termination_description == "RipJaw016 won on time"


def test_save_unanalyzed_bulk_inserts_once_and_skips_existing(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "history.db"))
    stub = PGNParser.parse_game_stub(_PGN)
    assert stub is not None

    assert manager.save_unanalyzed_games_bulk([stub]) == (1, 0)
    assert manager.save_unanalyzed_games_bulk([stub]) == (0, 1)

    stored = manager.get_game_analysis(stub.game_id)
    assert stored is not None
    assert stored.metadata.move_count == 2
    assert stored.metadata.last_fen
