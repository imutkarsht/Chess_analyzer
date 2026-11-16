"""Data-maintenance actions must not run under a live or paused batch."""

from types import SimpleNamespace

from src.backend.models.analysis_batch import BATCH_COMPLETED, BATCH_PAUSED, BATCH_RUNNING
from src.gui.components.feedback.toast import ToastManager
from src.gui.views.settings.storage_actions import analysis_is_running, ensure_idle


def _window(**overrides):
    values = {"worker": None, "_batch_worker": None, "analysis_coordinator": None}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_batch_blocks_data_maintenance_until_finished(monkeypatch):
    warnings = []
    monkeypatch.setattr(
        ToastManager, "warning", lambda *_args, **_kwargs: warnings.append(True)
    )

    idle = _window()
    assert analysis_is_running(idle) is False
    assert ensure_idle(idle) is True

    for state in (BATCH_RUNNING, BATCH_PAUSED):
        window = _window(
            analysis_coordinator=SimpleNamespace(batch_state=state)
        )
        assert analysis_is_running(window) is True
        assert ensure_idle(window) is False

    assert analysis_is_running(
        _window(_batch_worker=SimpleNamespace())
    ) is True
    assert analysis_is_running(
        _window(analysis_coordinator=SimpleNamespace(batch_state=BATCH_COMPLETED))
    ) is False
    assert warnings
