"""Explorer authentication gate and token-authenticated worker behaviour."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.constants import LICHESS_EXPLORER_URL
from src.gui.views.explorer import ExplorerView, LichessExplorerWorker


@pytest.fixture(autouse=True)
def _no_env_token(monkeypatch):
    """Keep the LICHESS_TOKEN fallback from leaking into gate assertions."""
    monkeypatch.delenv("LICHESS_TOKEN", raising=False)


class _Config:
    def __init__(self, enabled: bool = True, token: str = "lip_test"):
        self.enabled = enabled
        self.token = token

    def get(self, key, default=None):
        if key == "lichess_explorer_enabled":
            return self.enabled
        if key == "lichess_token":
            return self.token
        return default


def _gate(config, offline_until: float = 0.0) -> bool:
    view = SimpleNamespace(
        config_manager=config, _explorer_offline_until=offline_until
    )
    view._explorer_enabled = lambda: ExplorerView._explorer_enabled(view)
    return ExplorerView._online_explorer_allowed(view)


def test_online_explorer_gate_requires_token_and_allows_traffic():
    """Token, toggle, and cooldown all gate live explorer traffic."""
    assert _gate(_Config()) is True
    assert _gate(_Config(token="")) is False
    assert _gate(_Config(token="   ")) is False
    assert _gate(_Config(enabled=False)) is False
    assert _gate(_Config(), offline_until=time.time() + 60) is False


def test_cached_explorer_renders_without_a_token(qapp):
    history = MagicMock()
    history.get_explorer_cache.return_value = '{"moves": [{"san": "e4"}]}'
    view = SimpleNamespace(
        chk_cache=SimpleNamespace(isChecked=lambda: True),
        _history=lambda: history,
        on_lichess_explorer_finished=MagicMock(),
    )

    assert ExplorerView._render_cached_explorer(view, "startpos") is True
    view.on_lichess_explorer_finished.assert_called_once_with(
        {"moves": [{"san": "e4"}]}
    )


def test_cached_explorer_ignores_empty_or_disabled_cache(qapp):
    history = MagicMock()
    history.get_explorer_cache.return_value = '{"moves": []}'
    view = SimpleNamespace(
        chk_cache=SimpleNamespace(isChecked=lambda: False),
        _history=lambda: history,
        on_lichess_explorer_finished=MagicMock(),
    )

    assert ExplorerView._render_cached_explorer(view, "startpos") is False
    view.chk_cache.isChecked = lambda: True
    assert ExplorerView._render_cached_explorer(view, "startpos") is False
    view.on_lichess_explorer_finished.assert_not_called()


def test_explorer_worker_fetches_with_bearer_token(qapp, mock_requests):
    response = mock_requests.return_value
    response.status_code = 200
    response.json.return_value = {"moves": [{"san": "e4"}]}
    history = MagicMock()
    history.get_explorer_cache.return_value = None

    worker = LichessExplorerWorker("startpos", True, history, token="lip_abc")
    loaded = []
    worker.loaded.connect(loaded.append)

    worker.run()

    assert loaded == [{"moves": [{"san": "e4"}]}]
    kwargs = mock_requests.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer lip_abc"
    assert mock_requests.call_args.args[0].startswith(
        f"{LICHESS_EXPLORER_URL}?fen="
    )
    history.save_explorer_cache.assert_called_once()


def test_explorer_worker_serves_cache_before_requiring_a_token(qapp, mock_requests):
    history = MagicMock()
    history.get_explorer_cache.return_value = '{"moves": [{"san": "d4"}]}'

    worker = LichessExplorerWorker("startpos", True, history, token="")
    loaded = []
    worker.loaded.connect(loaded.append)

    worker.run()

    assert loaded == [{"moves": [{"san": "d4"}]}]
    mock_requests.assert_not_called()


def test_explorer_worker_rejects_a_missing_token(qapp, mock_requests):
    history = MagicMock()
    history.get_explorer_cache.return_value = None

    worker = LichessExplorerWorker("startpos", False, history, token="")
    errors = []
    worker.error.connect(errors.append)

    worker.run()

    assert errors == ["unauthorized"]
    mock_requests.assert_not_called()


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(401, "unauthorized"), (403, "unauthorized"), (429, "rate_limited")],
)
def test_explorer_worker_classifies_auth_and_rate_limit_errors(
    qapp, mock_requests, status_code, expected
):
    mock_requests.return_value.status_code = status_code
    history = MagicMock()
    history.get_explorer_cache.return_value = None

    worker = LichessExplorerWorker("startpos", False, history, token="lip_abc")
    errors = []
    worker.error.connect(errors.append)

    worker.run()

    assert errors == [expected]
