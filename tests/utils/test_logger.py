import logging
from unittest.mock import patch

from src.utils.logger import (
    SensitiveDataFilter,
    get_default_log_level,
    setup_logging,
)


def test_sensitive_data_filter_tokens():
    """Verify SensitiveDataFilter redacts known token patterns."""
    text_openai = "Connecting with sk-proj-1234567890abcdef12345678"
    assert SensitiveDataFilter.sanitize(text_openai) == "Connecting with [REDACTED]"

    text_groq = "Groq initialized: gsk_abcdef123456789012345678"
    assert SensitiveDataFilter.sanitize(text_groq) == "Groq initialized: [REDACTED]"

    text_lichess = "Lichess user with lip_abcdefghijklmnop"
    assert SensitiveDataFilter.sanitize(text_lichess) == "Lichess user with [REDACTED]"

    text_bearer = "Authorization: Bearer mysecrettoken123456789"
    assert SensitiveDataFilter.sanitize(text_bearer) == "Authorization: Bearer [REDACTED]"


def test_sensitive_data_filter_key_values():
    """Verify SensitiveDataFilter redacts key-value credential pairs."""
    text_kv1 = "config token: secretpassword123"
    assert "secretpassword123" not in SensitiveDataFilter.sanitize(text_kv1)
    assert "[REDACTED]" in SensitiveDataFilter.sanitize(text_kv1)

    text_kv2 = 'User logged in api_key="my_long_secret_api_key"'
    assert "my_long_secret_api_key" not in SensitiveDataFilter.sanitize(text_kv2)
    assert "[REDACTED]" in SensitiveDataFilter.sanitize(text_kv2)


def test_sensitive_data_filter_record():
    """Verify SensitiveDataFilter sanitizes LogRecord message and arguments."""
    flt = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Login with gsk_abcdef123456789012345678 and user %s",
        args=("sk-proj-1234567890abcdef12345678",),
        exc_info=None,
    )
    assert flt.filter(record) is True
    assert "gsk_" not in record.msg
    assert "[REDACTED]" in record.msg
    assert "sk-" not in record.args[0]
    assert record.args[0] == "[REDACTED]"


def test_get_default_log_level(monkeypatch):
    """Verify environment variable controls log level."""
    monkeypatch.delenv("CHESS_ANALYZER_LOG_LEVEL", raising=False)
    assert get_default_log_level() == logging.INFO

    monkeypatch.setenv("CHESS_ANALYZER_LOG_LEVEL", "DEBUG")
    assert get_default_log_level() == logging.DEBUG

    monkeypatch.setenv("CHESS_ANALYZER_LOG_LEVEL", "warning")
    assert get_default_log_level() == logging.WARNING

    monkeypatch.setenv("CHESS_ANALYZER_LOG_LEVEL", "INVALID_VAL")
    assert get_default_log_level() == logging.INFO


def test_setup_logging_handlers_and_rotation(tmp_path):
    """Verify setup_logging creates file handler and writes session header."""
    test_logger = logging.getLogger("TestChessAnalyzer")
    test_logger.handlers.clear()

    with patch("src.utils.logger.logging.getLogger", return_value=test_logger):
        with patch("src.utils.path_utils.get_user_data_dir", return_value=str(tmp_path)):
            # Reset session header state
            import src.utils.logger as log_mod
            log_mod._SESSION_HEADER_LOGGED = False

            lg = setup_logging(custom_level=logging.DEBUG)
            assert len(lg.handlers) >= 2

            log_file = tmp_path / "chess_analyzer.log"
            assert log_file.exists()

            with open(log_file, encoding="utf-8") as f:
                content = f.read()
            assert "Session Started" in content

            # Test idempotency (calling setup_logging again does not add duplicate handlers)
            initial_count = len(lg.handlers)
            setup_logging()
            assert len(lg.handlers) == initial_count
