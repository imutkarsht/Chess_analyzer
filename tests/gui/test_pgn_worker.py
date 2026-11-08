"""Background PGN indexing worker behaviour."""

from src.gui.dialogs.load_game.pgn_worker import PgnIndexWorker


def test_worker_indexes_file_synchronously(qapp, tmp_path):
    path = tmp_path / "games.pgn"
    path.write_text(
        '[Event "One"]\n[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n'
        "1. e4 e5 1-0",
        encoding="utf-8",
    )

    worker = PgnIndexWorker(path=str(path))
    results = []
    worker.completed.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert results[0].games[0].white == "A"
