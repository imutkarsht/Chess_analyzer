import logging
import logging.handlers
import os
import platform
import re
import sys

_SESSION_HEADER_LOGGED = False

class SensitiveDataFilter(logging.Filter):
    """
    Redacts sensitive API keys, tokens, and credentials from log records
    before emission to disk or console.
    """

    PATTERNS = [
        re.compile(r"sk-(?:proj-)?[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
        re.compile(r"gsk_[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
        re.compile(r"lip_[a-zA-Z0-9_\-]{16,}", re.IGNORECASE),
        re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.]{15,}\b"),
        re.compile(
            r"(?i)\b(api_key|token|access_token|secret|password|lichess_token)\s*([:=])\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (self.sanitize(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    (self.sanitize(arg) if isinstance(arg, str) else arg)
                    for arg in record.args
                )
        return True

    @classmethod
    def sanitize(cls, text: str) -> str:
        if not isinstance(text, str):
            return text
        sanitized = text
        for pattern in cls.PATTERNS:
            if pattern.groups == 3:
                sanitized = pattern.sub(r"\1\2[REDACTED]", sanitized)
            elif "Bearer" in pattern.pattern:
                sanitized = pattern.sub("Bearer [REDACTED]", sanitized)
            else:
                sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized


def get_default_log_level() -> int:
    """Resolve default log level from environment variable."""
    env_level = os.environ.get("CHESS_ANALYZER_LOG_LEVEL", "").upper().strip()
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return levels.get(env_level, logging.INFO)


def setup_logging(custom_level: int | None = None) -> logging.Logger:
    """
    Configures the global logging setup with console and rotating file handlers,
    thread identification, session demarcations, and sensitive data redaction.
    """
    global _SESSION_HEADER_LOGGED

    logger_instance = logging.getLogger("ChessAnalyzer")
    env_level = os.environ.get("CHESS_ANALYZER_LOG_LEVEL", "").strip()
    base_level = (
        custom_level
        if custom_level is not None
        else (get_default_log_level() if env_level else logging.DEBUG)
    )
    logger_instance.setLevel(base_level)

    # If handlers already configured, don't duplicate
    if logger_instance.handlers:
        return logger_instance

    # Sensitive data filter
    redactor = SensitiveDataFilter()

    # Console handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_level = get_default_log_level() if custom_level is None else custom_level
    c_handler.setLevel(c_level)
    c_handler.addFilter(redactor)
    c_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | [%(module)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    c_handler.setFormatter(c_fmt)
    logger_instance.addHandler(c_handler)

    # Rotating file handler
    try:
        from .path_utils import get_user_data_dir

        app_dir = get_user_data_dir()
        os.makedirs(app_dir, exist_ok=True)
        log_file = os.path.join(app_dir, "chess_analyzer.log")
        f_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            mode="a",
            encoding="utf-8",
        )
        f_level = get_default_log_level() if env_level else logging.DEBUG
        if custom_level is not None:
            f_level = custom_level
        f_handler.setLevel(f_level)
        f_handler.addFilter(redactor)

        f_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | [%(threadName)s] [%(name)s.%(module)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        f_handler.setFormatter(f_fmt)
        logger_instance.addHandler(f_handler)

        if not _SESSION_HEADER_LOGGED:
            try:
                from src.constants import APP_VERSION
            except Exception:
                APP_VERSION = "2.3.0"
            platform_info = f"{sys.platform} ({platform.machine()})"
            py_ver = platform.python_version()
            logger_instance.info("=" * 80)
            logger_instance.info(
                "=== Chess Analyzer Pro v%s Session Started (%s, Python %s) ===",
                APP_VERSION,
                platform_info,
                py_ver,
            )
            logger_instance.info("=" * 80)
            _SESSION_HEADER_LOGGED = True

    except Exception as e:
        sys.stderr.write(f"Failed to setup file logging: {e}\n")

    return logger_instance

# Global logger instance
logger = setup_logging()
