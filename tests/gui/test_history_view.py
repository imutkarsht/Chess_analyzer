"""
Tests for HistoryView, GameImportWorker, and CSV export/import fidelity.
"""

import csv
import io

import chess
import chess.pgn
import pytest
from PyQt6.QtWidgets import QLabel, QPushButton

from src.backend.storage.game_history import GAME_CSV_COLUMNS, GameHistoryManager
from src.backend.storage.game_query import (
    ANALYSIS_ANALYZED,
    ANALYSIS_PAUSED,
    ANALYSIS_UNANALYZED,
    OWNERSHIP_MINE,
    OWNERSHIP_OTHER,
    GameQuery,
)
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.board import MiniBoardWidget
from src.gui.components.lists.game_list_item_widget import GameListItemWidget
from src.gui.views.history_view import (
    AnnotatedPGNExportWorker,
    GameImportWorker,
    HistoryView,
)


def test_annotated_pgn_export_worker_exports_history_off_thread(tmp_path, qtbot):
    manager = GameHistoryManager(str(tmp_path / "export.db"))
    board = chess.Board()
    move = board.parse_san("e4")
    game = GameAnalysis(
        game_id="exported-game",
        metadata=GameMetadata(white="Alice", black="Bob", headers={}),
        moves=[
            MoveAnalysis(
                move_number=1,
                ply=0,
                san="e4",
                uci=move.uci(),
                fen_before=board.fen(),
                classification="Brilliant",
                eval_after_cp=25,
            )
        ],
        pgn_content='[Event "Export"]\n[White "Alice"]\n[Black "Bob"]\n[Result "*"]\n\n1. e4 *',
    )
    manager.save_game(game, game.pgn_content)
    output = tmp_path / "history.pgn"
    worker = AnnotatedPGNExportWorker(manager, str(output))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        with qtbot.waitSignal(worker.exported, timeout=5000) as result:
            worker.start()

    assert result.args == [1, 0]
    exported = output.read_text(encoding="utf-8")
    parsed = chess.pgn.read_game(io.StringIO(exported))
    assert parsed is not None
    assert parsed.variation(0).nags == {3}
    assert "[%eval +0.25]" in parsed.variation(0).comment


def test_history_export_buttons_preserve_csv_and_export_annotated_pgn(
    tmp_path, qtbot, qapp, monkeypatch
):
    from PyQt6.QtWidgets import QFileDialog

    from src.gui.components.feedback.toast import ToastManager

    manager = GameHistoryManager(str(tmp_path / "history-export.db"))
    board = chess.Board()
    move = board.parse_san("e4")
    game = GameAnalysis(
        game_id="history-export",
        metadata=GameMetadata(white="Alice", black="Bob", headers={}),
        moves=[
            MoveAnalysis(
                move_number=1,
                ply=0,
                san="e4",
                uci=move.uci(),
                fen_before=board.fen(),
                classification="Brilliant",
                eval_after_cp=25,
            )
        ],
        pgn_content=(
            '[Event "Export"]\n[White "Alice"]\n[Black "Bob"]\n[Result "*"]\n\n1. e4 *'
        ),
    )
    manager.save_game(game, game.pgn_content)
    manager.save_games_bulk(
        [
            {
                "id": "unfiltered-game",
                "white": "Bob",
                "black": "Carol",
                "event": "Other",
                "result": "*",
                "pgn": '[Event "Other"]\n[Result "*"]\n\n1. d4 *',
            }
        ]
    )

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.filter_bar.search_input.setText("alice")
    csv_path = tmp_path / "games.csv"
    pgn_path = tmp_path / "history-export.pgn"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda _parent, title, *_args: (
            (str(csv_path), "CSV Files (*.csv)")
            if title == "Export Games"
            else (str(pgn_path.with_suffix("")), "PGN Files (*.pgn)")
        ),
    )
    monkeypatch.setattr(ToastManager, "success", lambda *_args: None)
    monkeypatch.setattr(
        ToastManager, "loading", lambda *_args, **_kwargs: _StubToast()
    )

    view.export_csv_action.trigger()

    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        assert reader.fieldnames == GAME_CSV_COLUMNS
        assert [row["id"] for row in reader] == ["history-export"]

    workers = []
    monkeypatch.setattr(AnnotatedPGNExportWorker, "start", lambda worker: workers.append(worker))
    view.export_pgn_action.trigger()
    assert len(workers) == 1
    worker = workers[0]
    assert not view.btn_export.isEnabled()
    assert not view.btn_cancel_export.isHidden()

    worker.run()
    worker.finished.emit()

    assert view.btn_export.isEnabled()
    assert view.btn_cancel_export.isHidden()
    exported = pgn_path.read_text(encoding="utf-8")
    parsed = chess.pgn.read_game(io.StringIO(exported))
    assert parsed is not None
    assert parsed.headers["White"] == "Alice"
    assert parsed.variation(0).nags == {3}
    assert "[%eval +0.25]" in parsed.variation(0).comment
    assert view._current_query().search == "alice"
    assert view.btn_export.text() == "Export"
    assert view.export_pgn_action.text() == "Export Annotated PGN"


def test_annotated_pgn_export_skips_corrupt_games_and_preserves_raw_pgn(tmp_path):
    class _Rows:
        def count_games(self, _query):
            return 2

        def iter_games_for_export(self, _query, _batch_size):
            yield {
                "id": "raw",
                "pgn": '[Event "Raw"]\n[Result "*"]\n\n1. e4 *',
                "moves_json": "[]",
                "move_count": 1,
            }
            yield {
                "id": "corrupt",
                "pgn": "not a PGN",
                "moves_json": "[]",
                "move_count": None,
            }

    output = tmp_path / "filtered.pgn"
    worker = AnnotatedPGNExportWorker(_Rows(), str(output), GameQuery(search="raw"))
    exported = []
    progress = []
    worker.exported.connect(lambda count, skipped: exported.append((count, skipped)))
    worker.progress.connect(lambda done, total: progress.append((done, total)))

    worker.run()

    assert exported == [(1, 1)]
    assert progress[-1] == (2, 2)
    assert output.read_text(encoding="utf-8") == (
        '[Event "Raw"]\n[Result "*"]\n\n1. e4 *\n'
    )
    assert not list(tmp_path.glob("*.tmp"))


def test_annotated_pgn_export_cancellation_removes_temporary_output(
    tmp_path, monkeypatch
):
    class _Rows:
        def count_games(self, _query):
            return 2

        def iter_games_for_export(self, _query, _batch_size):
            for game_id in ("first", "second"):
                yield {
                    "id": game_id,
                    "pgn": '[Event "Raw"]\n[Result "*"]\n\n1. e4 *',
                    "moves_json": "[]",
                    "move_count": 1,
                }

    output = tmp_path / "cancelled.pgn"
    worker = AnnotatedPGNExportWorker(_Rows(), str(output))
    cancelled = []
    worker.cancelled.connect(lambda count, skipped: cancelled.append((count, skipped)))
    monkeypatch.setattr(AnnotatedPGNExportWorker, "_YIELD_EVERY", 1)
    monkeypatch.setattr(
        "src.gui.views.history_view.time.sleep", lambda _seconds: worker.request_cancel()
    )

    worker.run()

    assert cancelled == [(1, 0)]
    assert not output.exists()
    assert not list(tmp_path.glob(".*.tmp"))


class _StubToast:
    def update(self, *_args, **_kwargs):
        pass

    def set_progress(self, _value):
        pass


def test_game_import_worker_execution(tmp_path, qtbot):
    """Test that GameImportWorker parses CSV in background and bulk saves without error."""
    db_path = str(tmp_path / "test_import.db")
    manager = GameHistoryManager(db_path)

    # Pre-insert one game to test duplicate skipping
    meta_pre = GameMetadata(
        white="Pre", black="Existing", result="1-0", date="2024.01.01", event="Pre", headers={}
    )
    manager.save_game(
        GameAnalysis(game_id="pre_1", metadata=meta_pre, moves=[], pgn_content="pre"), "pre"
    )

    # Create CSV file with 3 rows: 1 duplicate, 2 new
    csv_file = tmp_path / "games_to_import.csv"
    fieldnames = GAME_CSV_COLUMNS
    rows = [
        {
            "id": "pre_1",
            "white": "Pre",
            "black": "Existing",
            "result": "1-0",
            "date": "2024.01.01",
            "event": "Pre",
            "speed_category": "Rapid",
            "pgn": "pre",
            "timestamp": "100.0",
        },
        {
            "id": "new_1",
            "white": "Magnus",
            "black": "Nakamura",
            "result": "1-0",
            "date": "2024.02.01",
            "event": "Speed",
            "speed_category": "Blitz",
            "pgn": "1. e4 e5 1-0",
            "timestamp": "200.0",
        },
        {
            "id": "new_2",
            "white": "Gukesh",
            "black": "Ding",
            "result": "1/2-1/2",
            "date": "2024.03.01",
            "event": "Candidates",
            "speed_category": "Classical",
            "pgn": "1. d4 d5 1/2-1/2",
            "timestamp": "300.0",
        },
    ]

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    worker = GameImportWorker(manager, str(csv_file))

    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()

    imported_cnt, skipped_cnt = blocker.args
    assert imported_cnt == 2
    assert skipped_cnt == 1

    # Verify both games exist in DB with preserved timestamps
    assert manager.game_exists("new_1")
    assert manager.game_exists("new_2")
    g1 = manager.get_game("new_1")
    assert g1["timestamp"] == 200.0
    assert g1["speed_category"] == "Blitz"


class _HistoryConfig:
    def __init__(self, mode):
        self.mode = mode

    def get(self, key, default=None):
        if key == "history_view_mode":
            return self.mode
        return default


def test_history_view_applies_configured_default_layout(qapp, qtbot):
    view = HistoryView(_HistoryConfig("detailed"))
    qtbot.addWidget(view)

    assert view.game_list.view_mode == "detailed"
    assert view.btn_export.text() == "Export"
    assert view.export_pgn_action.text() == "Export Annotated PGN"

    view.game_list.set_view_mode("compact")
    view.apply_default_view_mode()
    assert view.game_list.view_mode == "detailed"


def test_history_view_load_history_fast_path(tmp_path, qtbot, qapp):
    """Test HistoryView load_history utilizes cached speed_category and termination_mode."""
    db_path = str(tmp_path / "test_load.db")
    manager = GameHistoryManager(db_path)

    row = {
        "id": "cached_meta_game",
        "white": "Player1",
        "black": "Player2",
        "result": "1-0",
        "date": "2024.04.01",
        "event": "Rapid Cup",
        "speed_category": "Rapid",
        "termination": "White won by resignation",
        "termination_mode": "resignation",
        "pgn": "1. e4 e5 1-0",
        "timestamp": 12345.0,
    }
    manager.save_games_bulk([row])

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    assert len(view.games) == 1
    assert view.games[0].metadata.speed_category == "Rapid"
    assert view.games[0].metadata.termination_mode == "resignation"
    assert view.games[0].metadata.termination_description == "Player1 won by resignation"


def test_custom_start_position_is_not_mislabeled_as_chess960(qtbot):
    meta = GameMetadata(
        white="A",
        black="B",
        result="1-0",
        date="2023.08.25",
        event="Live Chess",
        starting_fen=(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/2BQKBNR w Kkq - 0 1"
        ),
        headers={},
    )
    game = GameAnalysis(game_id="custom", metadata=meta, moves=[])

    widget = GameListItemWidget(game, usernames=[], view_mode="detailed")
    qtbot.addWidget(widget)
    assert not any(
        label.text() == "Chess960" for label in widget.findChildren(QLabel)
    )

    meta.chess960 = True
    widget = GameListItemWidget(game, usernames=[], view_mode="detailed")
    qtbot.addWidget(widget)
    assert any(label.text() == "Chess960" for label in widget.findChildren(QLabel))


@pytest.mark.parametrize(
    "status,expected_badge,expected_action",
    [
        ("completed", "Analyzed", "reanalyze"),
        ("paused", "Paused", "resume"),
        ("not_started", "Unanalyzed", "analyze"),
    ],
)
def test_game_list_item_action_and_badge(qtbot, status, expected_badge, expected_action):
    """Test GameListItemWidget displays appropriate badge and emits action_requested for all statuses."""
    meta = GameMetadata(
        white="Magnus", black="Hikaru", result="1-0", date="2024.01.01", event="Speed", headers={}
    )
    moves = (
        [
            MoveAnalysis(
                move_number=1,
                ply=1,
                san="e4",
                uci="e2e4",
                fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            )
        ]
        if status != "not_started"
        else []
    )
    if status == "completed":
        moves[0].eval_after_cp = 30
        summary = {"analysis_status": "completed"}
    elif status == "paused":
        summary = {"analysis_status": "paused"}
    else:
        summary = {}

    game = GameAnalysis(
        game_id="g1", metadata=meta, moves=moves, summary=summary, pgn_content="1. e4"
    )

    for mode in ("detailed", "compact"):
        widget = GameListItemWidget(game, usernames=["Magnus"], view_mode=mode)
        qtbot.addWidget(widget)

        # Verify badge text
        badges = [w.text() for w in widget.findChildren(QLabel) if expected_badge in w.text()]
        assert len(badges) >= 1

        mini_board = widget.findChild(MiniBoardWidget)
        if mode == "detailed":
            # Magnus is White here, so the card board follows the user's side.
            assert mini_board is not None
            assert mini_board.config.orientation == chess.WHITE
        else:
            assert mini_board is None

        # Verify action button tooltip and signal emission
        action_buttons = [
            btn
            for btn in widget.findChildren(QPushButton)
            if expected_action.capitalize() in btn.toolTip()
        ]
        assert len(action_buttons) == 1
        with qtbot.waitSignal(widget.action_requested, timeout=1000) as blocker:
            action_buttons[0].click()
        assert blocker.args == [game, expected_action]


def test_history_view_game_action_propagation(tmp_path, qtbot):
    """Test clicking action button on a card in HistoryView propagates game_action_requested."""
    db_path = str(tmp_path / "test_action_prop.db")
    manager = GameHistoryManager(db_path)
    meta = GameMetadata(
        white="P1", black="P2", result="1-0", date="2024.01.01", event="Test", headers={}
    )
    manager.save_game(
        GameAnalysis(
            game_id="g_paused",
            metadata=meta,
            moves=[
                MoveAnalysis(
                    move_number=1,
                    ply=1,
                    san="e4",
                    uci="e2e4",
                    fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    eval_after_cp=20,
                )
            ],
            summary={"analysis_status": "paused"},
            pgn_content="1. e4",
        ),
        "1. e4",
    )

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    card = view.game_list.list_widget.itemWidget(view.game_list.list_widget.item(0))
    resume_btn = next(btn for btn in card.findChildren(QPushButton) if "Resume" in btn.toolTip())

    with qtbot.waitSignal(view.game_action_requested, timeout=1000) as blocker:
        resume_btn.click()

    emitted_game, action = blocker.args
    assert emitted_game.game_id == "g_paused"
    assert action == "resume"


def test_history_view_analyzing_status_and_action(tmp_path, qtbot):
    """Test that a game currently being analyzed shows 'Analyzing...' badge and emits view_analysis."""
    db_path = str(tmp_path / "test_analyzing.db")
    manager = GameHistoryManager(db_path)
    meta = GameMetadata(
        white="P1", black="P2", result="1-0", date="2024.01.01", event="Test", headers={}
    )
    manager.save_game(
        GameAnalysis(
            game_id="g_analyzing",
            metadata=meta,
            moves=[],
            summary={"analysis_status": "unanalyzed"},
            pgn_content="1. e4",
        ),
        "1. e4",
    )

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.set_analyzing_game_id("g_analyzing")
    view.load_history()

    card = view.game_list.list_widget.itemWidget(view.game_list.list_widget.item(0))
    badges = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert "Analyzing..." in badges

    view_btn = next(
        btn for btn in card.findChildren(QPushButton) if "View ongoing analysis" in btn.toolTip()
    )
    assert view_btn is not None

    with qtbot.waitSignal(view.game_action_requested, timeout=1000) as blocker:
        view_btn.click()

    emitted_game, action = blocker.args
    assert emitted_game.game_id == "g_analyzing"
    assert action == "view_analysis"


def _seed_games(manager, count: int):
    manager.save_games_bulk(
        [
            {
                "id": f"page_g{i}",
                "white": "PlayerA",
                "black": f"Rival{i}",
                "result": "1-0",
                "date": "2026.10.01",
                "event": "Ranked",
                "time_control": "300+3",
                "speed_category": "Blitz",
                "source": "chesscom",
                "pgn": "1. e4 e5 2. Nf3 Nc6 1-0",
                "timestamp": 1_700_000_000 + i,
            }
            for i in range(count)
        ]
    )


def test_history_view_pages_rows_instead_of_loading_everything(tmp_path, qtbot):
    """The list renders one page, grows on demand, and export still sees the table."""
    manager = GameHistoryManager(str(tmp_path / "paged.db"))
    _seed_games(manager, 60)

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    assert view.btn_clear.text() == "Delete all games"
    assert view.game_list.total_count == 60
    # A single page is rendered, not the whole archive.
    assert 0 < len(view.game_list.games) <= view._page_size()
    assert view.game_list.title_lbl.text() == "60 games"
    assert view._page_size() == view._COMPACT_PAGE_SIZE

    view.game_list.set_view_mode("detailed")
    assert view._page_size() == view._DETAILED_PAGE_SIZE

    loaded = len(view.game_list.games)
    view.game_list.load_more_requested.emit()

    assert len(view.game_list.games) > loaded
    # Export is independent of paging and filtering.
    assert len(manager.get_all_games(limit=None)) == 60


def test_history_view_filter_resets_to_the_first_page(tmp_path, qtbot):
    manager = GameHistoryManager(str(tmp_path / "filtered.db"))
    _seed_games(manager, 12)

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    view.result_filter.set_current_index(3)  # Draws — no seeded game is a draw

    assert view.game_list.total_count == 0
    assert view.game_list.games == []
    assert (
        view.game_list.content_stack.currentWidget()
        is view.game_list.empty_widget
    )
    assert view.game_list.empty_button.text() == "Clear filters"

    view.game_list.empty_button.click()

    assert view.game_list.total_count == 12
    assert (
        view.game_list.content_stack.currentWidget()
        is view.game_list.list_widget
    )


def test_history_view_filters_analysis_status_and_ownership(tmp_path, qtbot):
    manager = GameHistoryManager(str(tmp_path / "status.db"))
    manager.save_games_bulk(
        [
            {
                "id": "completed-mine",
                "white": "PlayerA",
                "black": "X",
                "result": "1-0",
                "date": "2026.10.01",
                "summary_json": '{"analysis_status": "completed"}',
                "timestamp": 1_700_000_001,
            },
            {
                "id": "new-mine",
                "white": "PlayerA",
                "black": "Y",
                "result": "1-0",
                "date": "2026.10.02",
                "summary_json": '{"analysis_status": "not_started"}',
                "timestamp": 1_700_000_002,
            },
            {
                "id": "paused-rival",
                "white": "Rival",
                "black": "Z",
                "result": "0-1",
                "date": "2026.10.03",
                "summary_json": '{"analysis_status": "paused"}',
                "timestamp": 1_700_000_003,
            },
            {
                "id": "completed-rival",
                "white": "Neutral",
                "black": "Rival",
                "result": "0-1",
                "date": "2026.10.04",
                "summary_json": '{"analysis_status": "completed"}',
                "timestamp": 1_700_000_004,
            },
        ]
    )

    class _Prefs:
        def get(self, key, default=""):
            return "PlayerA" if key == "chesscom_username" else default

    view = HistoryView(config_manager=_Prefs())
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    assert view.game_list.total_count == 4

    view.analysis_filter.set_value(ANALYSIS_ANALYZED, emit=True)
    assert view.game_list.total_count == 2

    view.analysis_filter.set_value(ANALYSIS_UNANALYZED, emit=True)
    assert view.game_list.total_count == 1
    assert view.game_list.games[0].game_id == "new-mine"

    view.analysis_filter.set_value(ANALYSIS_PAUSED, emit=True)
    assert view.game_list.total_count == 1

    view.analysis_filter.set_value("", emit=True)
    view.ownership_filter.set_value(OWNERSHIP_MINE, emit=True)
    assert view.game_list.total_count == 2

    view.ownership_filter.set_value(OWNERSHIP_OTHER, emit=True)
    assert view.game_list.total_count == 2

    view.ownership_filter.set_value("", emit=True)
    view.analysis_filter.set_value(ANALYSIS_UNANALYZED, emit=True)
    view.ownership_filter.set_value(OWNERSHIP_MINE, emit=True)
    assert view.game_list.total_count == 1


def test_history_row_click_hydrates_the_full_game(tmp_path, qtbot):
    """List rows are light; opening one must fetch moves and pgn for that id."""
    manager = GameHistoryManager(str(tmp_path / "hydrate.db"))
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    moves = [
        MoveAnalysis(move_number=1, ply=0, san="e4", uci="e2e4", fen_before=start),
        MoveAnalysis(
            move_number=1,
            ply=1,
            san="e5",
            uci="e7e5",
            fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        ),
    ]
    manager.save_game(
        GameAnalysis(
            game_id="full",
            metadata=GameMetadata(white="A", black="B", result="1-0"),
            moves=moves,
            summary={"analysis_status": "completed"},
            pgn_content="1. e4 e5 1-0",
        ),
        "1. e4 e5 1-0",
        force_overwrite=True,
    )

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    row = view.game_list.games[0]
    assert row.moves == [] and not row.pgn_content  # light list projection

    with qtbot.waitSignal(view.game_selected, timeout=1000) as blocker:
        view.on_game_selected(row)

    opened = blocker.args[0]
    assert opened.game_id == "full"
    assert len(opened.moves) == 2
    assert opened.pgn_content


def test_history_view_prefetches_one_page_beyond_the_first(tmp_path, qtbot):
    """The next page is warmed so scrolling does not wait on the database."""
    manager = GameHistoryManager(str(tmp_path / "prefetch.db"))
    _seed_games(manager, 60)

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    first_page = view._page_size()
    assert view._offset == first_page

    view._prefetch_next_page()

    assert view._offset == first_page * 2
    # Prefetch stops after one page of headroom; scrolling takes over from here.
    view._schedule_prefetch()
    assert not view._prefetch_timer.isActive()
