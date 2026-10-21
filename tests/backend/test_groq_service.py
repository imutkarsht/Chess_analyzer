from unittest.mock import MagicMock

import pytest

from src.backend.services.groq_service import GroqService, validate_explanation
from src.constants import PROVIDERS

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeProfile:
    """Mimics the dict-like profile object that ConfigManager.get_active_profile
    returns. The service code only ever calls .get() on it, so this is the
    minimum surface we need."""

    def __init__(self, **kwargs):
        self._data = dict(kwargs)

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def fake_config(monkeypatch):
    """Replace ConfigManager() inside groq_service with a stub that returns a
    profile we control per-test."""
    profiles = {}

    def _set(profile):
        profiles["current"] = profile

    def _factory():
        cfg = MagicMock()
        cfg.get_active_profile.return_value = profiles.get(
            "current", _FakeProfile(provider="groq", api_key="", model="")
        )
        return cfg

    monkeypatch.setattr("src.backend.services.groq_service.ConfigManager", _factory)
    _set(_FakeProfile())  # default: empty profile
    return _set


# ---------------------------------------------------------------------------
# Core service: configuration → client lifecycle
# ---------------------------------------------------------------------------


class TestGroqService:
    """Tests for the openai.OpenAI-based GroqService.

    The earlier iteration of this file exercised a pre-rewrite API
    (groq.Groq + load_dotenv) that no longer exists in the module.
    Those tests are replaced here with coverage of the current
    provider/profile architecture.
    """

    def test_constructs_with_no_profile_does_not_crash(self, fake_config):
        """Constructing the service with a fully empty profile is a no-op:
        the client stays None and no exception escapes."""
        fake_config(_FakeProfile())
        service = GroqService()
        assert service.client is None

    def test_placeholder_key_does_not_create_client(self, fake_config):
        """A 'gsk_…' README placeholder must not be turned into a client."""
        fake_config(
            _FakeProfile(
                provider="groq",
                api_key="<YOUR_GROQ_KEY_HERE>",
                model="llama-3.3-70b-versatile",
            )
        )
        service = GroqService()
        assert service.client is None

    def test_placeholder_xxx_does_not_create_client(self, fake_config):
        fake_config(
            _FakeProfile(
                provider="groq",
                api_key="XXXXXXXX",
                model="llama-3.3-70b-versatile",
            )
        )
        service = GroqService()
        assert service.client is None

    def test_valid_groq_profile_creates_client(self, fake_config, monkeypatch):
        """A real-looking key produces an OpenAI client with the right args."""
        fake_config(
            _FakeProfile(
                provider="groq",
                api_key="gsk_real_key",
                model="llama-3.3-70b-versatile",
            )
        )
        captured = {}

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service.client is not None
        assert captured["api_key"] == "gsk_real_key"
        assert captured["base_url"] == PROVIDERS["groq"]["base_url"]

    def test_lmstudio_does_not_require_a_key(self, fake_config, monkeypatch):
        """LM Studio is local: the client must be built even without a key."""
        fake_config(_FakeProfile(provider="lmstudio", api_key="", model=""))
        captured = {}

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service.client is not None
        assert captured["base_url"] == PROVIDERS["lmstudio"]["base_url"]

    def test_unknown_provider_falls_back_to_custom(self, fake_config, monkeypatch):
        """An unknown provider name is preserved case-insensitively as 'custom'."""
        fake_config(
            _FakeProfile(
                provider="MyLocalLLM",
                api_key="abc",
                model="custom-model",
                base_url="http://example.com/v1/",
            )
        )
        captured = {}

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service._provider == "custom"
        # Trailing slash + /chat/completions must be stripped before use.
        assert captured["base_url"] == "http://example.com/v1"

    def test_groq_env_fallback_used_when_profile_key_empty(self, fake_config, monkeypatch):
        """If the profile has no Groq key, the GROQ_API_KEY env var is honoured."""
        fake_config(_FakeProfile(provider="groq", api_key="", model="llama"))
        monkeypatch.setenv("GROQ_API_KEY", "env-groq-key")
        captured = {}

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service.client is not None
        assert captured["api_key"] == "env-groq-key"

    def test_openai_profile_creates_client(self, fake_config, monkeypatch):
        """A valid OpenAI profile produces an OpenAI client with the right preset url."""
        fake_config(
            _FakeProfile(
                provider="openai",
                api_key="sk-proj-key123",
                model="gpt-4o-mini",
            )
        )
        captured = {}

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service.client is not None
        assert captured["api_key"] == "sk-proj-key123"
        assert captured["base_url"] == PROVIDERS["openai"]["base_url"]

    def test_openai_env_fallback_used_when_profile_key_empty(self, fake_config, monkeypatch):
        """If the profile has no OpenAI key, the OPENAI_API_KEY env var is honoured."""
        fake_config(_FakeProfile(provider="openai", api_key="", model="gpt-4o"))
        monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
        captured = {}

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service.client is not None
        assert captured["api_key"] == "env-openai-key"

    def test_configure_replaces_client(self, fake_config, monkeypatch):
        """configure() must rebuild the client with the new settings."""
        fake_config(_FakeProfile(provider="groq", api_key="first", model="m1"))
        captured = []

        class _FakeOpenAI:
            def __init__(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", _FakeOpenAI)
        service = GroqService()
        assert service.client is not None
        service.configure(provider="groq", api_key="second", model="m2", base_url="")
        assert len(captured) == 2
        assert captured[-1]["api_key"] == "second"

    def test_generate_summary_without_client_returns_error(self, fake_config):
        """Calling generate_summary before any client is configured returns
        the user-visible error string, never raises."""
        fake_config(_FakeProfile())  # nothing configured
        service = GroqService()
        out = service.generate_summary("1. e4 e5", "analysis")
        assert "not configured" in out.lower()

    def test_generate_coach_insights_without_client_returns_error(self, fake_config):
        fake_config(_FakeProfile())
        service = GroqService()
        out = service.generate_coach_insights("stats")
        assert "not configured" in out.lower()

    def test_generate_summary_truncates_huge_pgn(self, fake_config, monkeypatch):
        """A 50k-char PGN must be truncated to ~10k chars before being sent."""
        fake_config(_FakeProfile(provider="groq", api_key="k", model="m"))
        sent = {}

        class _FakeChoice:
            def __init__(self, content):
                self.message = MagicMock(content=content)

        class _FakeCompletion:
            def __init__(self):
                self.choices = [_FakeChoice("Game Comment: ok\n\nSummary:\nshort summary")]

        class _FakeChatCompletions:
            def create(self, **kwargs):
                sent.update(kwargs)
                return _FakeCompletion()

        class _FakeClient:
            def __init__(self):
                self.chat = MagicMock()
                self.chat.completions = _FakeChatCompletions()

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", lambda **kw: _FakeClient())
        service = GroqService()
        huge_pgn = "1. " + ("e4 " * 20_000)
        service.generate_summary(huge_pgn, "analysis")
        # The first user message contains the PGN; it must be < 11000 chars.
        user_msg = sent["messages"][-1]["content"]
        assert "truncated" in user_msg
        assert len(user_msg) < 11_000

    def test_generate_summary_happy_path(self, fake_config, monkeypatch):
        fake_config(_FakeProfile(provider="groq", api_key="k", model="m"))
        sent = {}

        class _FakeChoice:
            def __init__(self, content):
                self.message = MagicMock(content=content)

        class _FakeCompletion:
            def __init__(self):
                self.choices = [_FakeChoice("Game Comment: Sharp\n\nSummary:\nfun game")]

        class _FakeChatCompletions:
            def create(self, **kwargs):
                sent.update(kwargs)
                return _FakeCompletion()

        class _FakeClient:
            def __init__(self):
                self.chat = MagicMock()
                self.chat.completions = _FakeChatCompletions()

        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", lambda **kw: _FakeClient())
        service = GroqService()
        out = service.generate_summary("1. e4 e5", "analysis")
        assert "Sharp" in out
        assert sent["model"] == "m"
        assert "1. e4 e5" in sent["messages"][-1]["content"]


# ---------------------------------------------------------------------------
# _is_placeholder_key — secret template detection
# ---------------------------------------------------------------------------


class TestIsPlaceholderKey:
    """Unit tests for the placeholder secret detection.

    These cover the patterns the previous implementation missed and the
    ones it already handled, so the detection logic is regression-safe.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "   ",  # whitespace only
            "${GROQ_API_KEY}",  # docker / shell substitution
            "${input:openai_key}",  # 1Password CLI
            "${{ secrets.GROQ_API_KEY }}",  # GitHub Actions
            "<YOUR_KEY_HERE>",  # README placeholder
            "<your-api-key>",  # README placeholder, lower case
            "<YOUR_GROQ_KEY_HERE>",  # README placeholder, specific
            "XXXXXXXX",  # redaction artifact
            "xxxx",  # short redaction artifact
        ],
    )
    def test_placeholder_patterns_are_detected(self, value):
        assert GroqService._is_placeholder_key(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "gsk_real-looking-key-1234",
            "sk-abc123def456",
            "AIzaSyA-real-google-key",
        ],
    )
    def test_real_keys_are_not_flagged(self, value):
        assert GroqService._is_placeholder_key(value) is False


# ---------------------------------------------------------------------------
# Move explanations: explain_move, _chat hardening, validate_explanation
# ---------------------------------------------------------------------------


def _completion(text: str):
    choice = MagicMock()
    choice.message = MagicMock(content=text)
    completion = MagicMock()
    completion.choices = [choice]
    return completion


class _CapturingClient:
    """Minimal OpenAI-compatible client that records every request."""

    def __init__(self, reply: str = "ok", fail_first: str | None = None):
        self.calls: list[dict] = []
        self.with_options_calls: list[dict] = []
        self._reply = reply
        self._fail_first = fail_first
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if outer._fail_first and len(outer.calls) == 1:
                    raise RuntimeError(outer._fail_first)
                return _completion(outer._reply)

        self.chat = MagicMock()
        self.chat.completions = _Completions()

    def with_options(self, **kwargs):
        self.with_options_calls.append(kwargs)
        return self


@pytest.fixture
def configured_service(fake_config, monkeypatch):
    """Factory: build a GroqService backed by a capturing client."""

    def _make(reply: str = "ok", fail_first: str | None = None):
        fake_config(_FakeProfile(provider="groq", api_key="k", model="openai/gpt-oss-120b"))
        client = _CapturingClient(reply=reply, fail_first=fail_first)
        monkeypatch.setattr("src.backend.services.groq_service.OpenAI", lambda **kw: client)
        return GroqService(), client

    return _make


FACTS = "FACT SHEET - single move\n\n- Played: 5...Bxd1 (black)\n- Classification: Blunder"


class TestExplainMove:
    def test_facts_are_sent_verbatim_with_coach_system_prompt(self, configured_service):
        service, client = configured_service("You lost the rook.")
        out = service.explain_move(FACTS, "Blunder")

        assert out == "You lost the rook."
        sent = client.calls[0]
        assert sent["messages"][-1] == {"role": "user", "content": FACTS}
        system = sent["messages"][0]
        assert system["role"] == "system"
        assert "Never name a move" in system["content"]
        assert "classified as Blunder" in system["content"]

    def test_request_is_bounded_and_unretried(self, configured_service):
        service, client = configured_service()
        service.explain_move(FACTS, "Blunder")

        sent = client.calls[0]
        assert sent["timeout"] == 20.0
        assert sent["max_tokens"] == 1024
        assert sent["temperature"] == 0.3
        assert sent["reasoning_effort"] == "low"
        # retries are a client-level option, applied via with_options
        assert client.with_options_calls == [{"max_retries": 0}]
        assert "max_retries" not in sent


class TestChatHardening:
    def test_reasoning_effort_is_dropped_when_provider_rejects_it(self, configured_service):
        service, client = configured_service(
            "plain answer", fail_first="Unknown parameter: reasoning_effort"
        )

        out = service._chat("hi", reasoning_effort="low")

        assert out == "plain answer"
        assert len(client.calls) == 2
        assert client.calls[0]["reasoning_effort"] == "low"
        assert "reasoning_effort" not in client.calls[1]

    def test_unrelated_failure_is_reported_not_retried(self, configured_service):
        service, client = configured_service(fail_first="connection reset")

        out = service._chat("hi")

        assert out.startswith("Error [RuntimeError]")
        assert len(client.calls) == 1


# ---------------------------------------------------------------------------
# validate_explanation — the hallucination guard (D5)
# ---------------------------------------------------------------------------

ALLOWED_SAN = {"Bxd1", "Nxe5", "Bxf7", "O-O", "O-O-O", "e8=Q", "Qxf7"}
ALLOWED_SQUARES = {"d1", "f7", "e5", "e8", "g1"}


class TestValidateExplanation:
    def test_grounded_reply_passes(self):
        reply = (
            "You grabbed the queen on d1 with Bxd1, but that allows the opponent to play "
            "Bxf7. Nxe5 was the move that kept your advantage."
        )
        valid, offending = validate_explanation(reply, ALLOWED_SAN, ALLOWED_SQUARES)
        assert valid is True
        assert offending == []

    @pytest.mark.parametrize(
        ("reply", "expected"),
        [
            # an invented move
            ("You should have played Qh5 instead of Bxd1.", "Qh5"),
            # an invented square
            ("The rook on a8 was the problem, not Bxd1.", "a8"),
            # an invented pawn move that is not a fact square
            ("Simply push d5 and Bxd1 is fine.", "d5"),
        ],
    )
    def test_invented_tokens_are_rejected(self, reply, expected):
        valid, offending = validate_explanation(reply, ALLOWED_SAN, ALLOWED_SQUARES)
        assert valid is False
        assert expected in offending

    @pytest.mark.parametrize(
        "reply",
        [
            "Bxd1 loses because Bxf7+ is coming.",
            "After Bxd1 the reply Bxf7# wins the game.",
            "O-O would have been safer than Bxd1, and O-O-O also works.",
            "Promoting with e8=Q beats Bxd1 here.",
        ],
    )
    def test_check_mate_castling_and_promotion_tokens_are_understood(self, reply):
        """Suffixes (#, +) and castling/promotion SAN must normalise correctly."""
        valid, offending = validate_explanation(reply, ALLOWED_SAN, ALLOWED_SQUARES)
        assert valid is True, f"unexpectedly rejected: {offending}"

    @pytest.mark.parametrize("reply", ["", "   ", "Error [Timeout]: request timed out"])
    def test_empty_or_error_replies_are_invalid(self, reply):
        assert validate_explanation(reply, ALLOWED_SAN, ALLOWED_SQUARES) == (False, [])
