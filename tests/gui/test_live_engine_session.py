"""LiveEngineSession: sequencing, pause/resume, and stable line rendering."""

from src.backend.analysis.engine_line import EngineLine
from src.gui.engine_lines import LiveEngineSession

FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _session(mocker):
    worker_cls = mocker.patch("src.gui.engine_lines.session.LiveAnalysisWorker")
    session = LiveEngineSession("/fake/stockfish", throttle_ms=0)
    worker = worker_cls.return_value
    worker.isRunning.return_value = False

    slots = {}
    for name in ("info_ready", "thinking_started", "thinking_stopped", "error"):
        getattr(worker, name).connect.side_effect = (
            lambda slot, key=name: slots.__setitem__(key, slot)
        )
    return session, worker, slots


def test_request_starts_the_engine_lazily_with_a_sequence(mocker):
    session, worker, _slots = _session(mocker)
    worker.start.assert_not_called()

    session.request(FEN)

    worker.start.assert_called_once()
    assert worker.set_position.call_args.args == (FEN, 1)
    assert session.state == "thinking"


def test_results_from_a_previous_position_are_dropped(mocker):
    session, _worker, slots = _session(mocker)
    emitted = []
    session.lines_changed.connect(emitted.append)
    session.request(FEN)
    stale = EngineLine(rank=1, cp=30, pv_uci=("e7e5",))

    slots["info_ready"]({"seq": 99, "line": stale})
    assert emitted == []

    slots["info_ready"]({"seq": 1, "line": stale})
    assert emitted[-1] == [stale]


def test_clearing_invalidates_in_flight_results(mocker):
    session, worker, slots = _session(mocker)
    emitted = []
    session.lines_changed.connect(emitted.append)
    session.request(FEN)
    line = EngineLine(rank=1, cp=30, pv_uci=("e7e5",))
    slots["info_ready"]({"seq": 1, "line": line})

    session.clear()

    assert emitted[-1] == []
    # A late batch for the cleared position must not resurrect the lines.
    slots["info_ready"]({"seq": 1, "line": line})
    assert emitted[-1] == []
    assert worker.set_position.call_args.args[0] is None


def test_a_truncated_update_keeps_the_longer_pv(mocker):
    session, _worker, slots = _session(mocker)
    emitted = []
    session.lines_changed.connect(emitted.append)
    session.request(FEN)
    long_line = EngineLine(
        rank=1, depth=16, cp=57, pv_uci=("g1f3", "g8f6", "f1c4"), pv_san="2. Nf3 Nf6 3. Bc4"
    )
    short_line = EngineLine(rank=1, depth=17, cp=104, pv_uci=("g1f3", "g8f6"))

    slots["info_ready"]({"seq": 1, "line": long_line})
    slots["info_ready"]({"seq": 1, "line": short_line})

    last = emitted[-1][0]
    assert last.pv_uci == long_line.pv_uci
    assert last.cp == 104


def test_enabling_after_a_pause_dispatches_the_pending_position(mocker):
    session, worker, _slots = _session(mocker)
    session.pause()
    session.request(FEN)
    worker.set_position.assert_not_called()

    # The Explorer unchecks/rechecks "Engine Lines" while the page is visible
    # and then asks for the position the board currently shows.
    session.set_enabled(True)
    session.request(FEN)

    assert worker.set_position.call_args.args[0] == FEN
    assert session.state == "thinking"


def test_unchanged_lines_are_not_re_emitted(mocker):
    session, _worker, slots = _session(mocker)
    emitted = []
    session.lines_changed.connect(emitted.append)
    session.request(FEN)
    line = EngineLine(rank=1, depth=17, cp=104, pv_uci=("e7e5",))

    slots["info_ready"]({"seq": 1, "line": line})
    slots["info_ready"]({"seq": 1, "line": line})

    assert len(emitted) == 1
