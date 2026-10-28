"""Data & Storage cards: formatting, reset, maintenance, and restore wiring."""

from types import SimpleNamespace

import pytest

from src.backend.storage.backup import BackupSummary, BackupValidationError
from src.backend.storage.stats import StorageStats
from src.gui.views.settings import backup_settings, danger_settings, maintenance_settings
from src.gui.views.settings.backup_settings import BackupSettings
from src.gui.views.settings.danger_settings import DangerSettings
from src.gui.views.settings.maintenance_settings import MaintenanceSettings
from src.gui.views.settings.storage_actions import format_bytes
from src.gui.views.settings.storage_settings import StorageSettings


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (1536, "1.5 KB"),
        (5 * 1024**2, "5.0 MB"),
    ],
)
def test_format_bytes(size, expected):
    assert format_bytes(size) == expected


def test_storage_card_renders_stats(qapp):
    card = StorageSettings()

    card.apply_stats(
        StorageStats(
            db_bytes=2048,
            wal_bytes=1024,
            openings_bytes=0,
            games=3,
            analyses=10,
            explanations=2,
            api_cached_games=4,
            explorer_positions=5,
        )
    )

    assert card.stat_labels["database"].text() == "3.0 KB"
    assert card.stat_labels["games"].text() == "3"
    assert card.stat_labels["analyses"].text() == "10"
    assert card.stat_labels["explanations"].text() == "2"
    assert card.stat_labels["api_cache"].text() == "4 games"
    assert card.stat_labels["explorer_cache"].text() == "5 positions"
    card.deleteLater()


class _RecordingCache:
    def __init__(self):
        self.calls = []

    def clear_cache(self):
        self.calls.append("clear_cache")
        return 7


def test_clear_cache_is_dispatched_to_a_worker(qapp, monkeypatch):
    """VACUUM must never run inside the click handler."""
    card = MaintenanceSettings()
    monkeypatch.setattr(maintenance_settings, "ensure_idle", lambda _window: True)
    monkeypatch.setattr(
        maintenance_settings, "confirm_dialog", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(maintenance_settings, "close_analyzer_cache", lambda _window: None)
    fake_cache = _RecordingCache()
    monkeypatch.setattr(maintenance_settings, "AnalysisCache", lambda: fake_cache)

    captured = {}

    def run_task(task, on_success, on_error=None, **kwargs):
        captured["task"] = task
        captured["on_success"] = on_success

    monkeypatch.setattr(card, "run_task", run_task)
    emitted = []
    card.data_changed.connect(lambda: emitted.append(True))

    card.clear_cache()

    assert fake_cache.calls == [], "the click handler must only queue the work"
    assert captured["task"]() == 7
    captured["on_success"](7)
    assert emitted == [True]
    card.deleteLater()


class _RecordingHistory:
    def __init__(self):
        self.calls = []

    def clear_all_data(self):
        self.calls.append("clear_all_data")


def test_reset_wipes_data_and_refreshes_every_view(qapp, monkeypatch):
    card = DangerSettings()
    monkeypatch.setattr(danger_settings, "ensure_idle", lambda _window: True)
    monkeypatch.setattr(
        danger_settings, "confirm_dialog", lambda *args, **kwargs: True
    )
    events = []
    monkeypatch.setattr(
        danger_settings, "close_analyzer_cache", lambda _window: events.append("closed")
    )
    fake_history = _RecordingHistory()
    monkeypatch.setattr(danger_settings, "GameHistoryManager", lambda: fake_history)
    monkeypatch.setattr(
        danger_settings,
        "refresh_after_data_change",
        lambda _window: events.append("refreshed"),
    )
    monkeypatch.setattr(
        card, "run_task", lambda task, on_success, on_error=None, **kwargs: on_success(task())
    )
    emitted = []
    card.data_changed.connect(lambda: emitted.append(True))

    card.reset_all_data()

    assert events == ["closed", "refreshed"]
    assert fake_history.calls == ["clear_all_data"]
    assert emitted == [True]
    card.deleteLater()


def test_reset_aborts_when_analysis_is_running(qapp, monkeypatch):
    card = DangerSettings()
    monkeypatch.setattr(danger_settings, "ensure_idle", lambda _window: False)
    prompted = []
    monkeypatch.setattr(
        danger_settings,
        "confirm_dialog",
        lambda *args, **kwargs: prompted.append(True) or True,
    )
    monkeypatch.setattr(
        card, "run_task", lambda *args, **kwargs: prompted.append("task")
    )

    card.reset_all_data()

    assert prompted == []
    card.deleteLater()


def _summary() -> BackupSummary:
    return BackupSummary(
        path="/tmp/backup.db",
        size_bytes=1024,
        games=2,
        analyses=3,
        explanations=4,
        schema_version=3,
        created_at=0,
    )


def test_restore_refreshes_views_after_a_valid_backup(qapp, monkeypatch):
    card = BackupSettings()
    summary = _summary()
    monkeypatch.setattr(backup_settings, "ensure_idle", lambda _window: True)
    monkeypatch.setattr(
        backup_settings,
        "QFileDialog",
        SimpleNamespace(getOpenFileName=lambda *args, **kwargs: ("/tmp/backup.db", "")),
    )
    monkeypatch.setattr(backup_settings, "inspect_backup", lambda _path: summary)
    monkeypatch.setattr(
        backup_settings, "confirm_dialog", lambda *args, **kwargs: True
    )
    events = []
    monkeypatch.setattr(
        backup_settings,
        "close_analyzer_cache",
        lambda _window: events.append("closed"),
    )
    monkeypatch.setattr(
        backup_settings,
        "restore_backup",
        lambda _path: events.append("restored") or summary,
    )
    monkeypatch.setattr(
        backup_settings,
        "refresh_after_data_change",
        lambda _window: events.append("refreshed"),
    )
    monkeypatch.setattr(
        card, "run_task", lambda task, on_success, on_error=None, **kwargs: on_success(task())
    )
    emitted = []
    card.data_changed.connect(lambda: emitted.append(True))

    card.restore_from_backup()

    assert events == ["closed", "restored", "refreshed"]
    assert emitted == [True]
    card.deleteLater()


def test_restore_rejects_an_invalid_file_before_touching_data(qapp, monkeypatch):
    card = BackupSettings()
    monkeypatch.setattr(backup_settings, "ensure_idle", lambda _window: True)
    monkeypatch.setattr(
        backup_settings,
        "QFileDialog",
        SimpleNamespace(getOpenFileName=lambda *args, **kwargs: ("/tmp/notes.db", "")),
    )

    def reject(_path):
        raise BackupValidationError("The selected file is not a SQLite database.")

    monkeypatch.setattr(backup_settings, "inspect_backup", reject)
    errors = []
    monkeypatch.setattr(card, "_report_error", errors.append)
    tasks = []
    monkeypatch.setattr(card, "run_task", lambda *args, **kwargs: tasks.append(True))

    card.restore_from_backup()

    assert errors == ["The selected file is not a SQLite database."]
    assert tasks == []
    card.deleteLater()
