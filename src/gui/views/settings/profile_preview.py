"""Public player-profile preview for the Integrations settings cards.

The preview is cache-first: TTL-fresh rows render instantly without a network
call, stale rows are shown while a refresh is attempted, and a failed refresh
falls back to the cached row so the page still works offline.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from urllib.parse import quote

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.backend.api.base_api import ApiStatus
from src.backend.api.chess_com_api import ChessComAPI
from src.backend.api.lichess_api import LichessAPI
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.profile_cache_repo import CachedProfile
from src.gui.components import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.utils.logger import logger

from .background_worker import BackgroundTaskWorker

AVATAR_SIZE = 56
ACTIVE_PROFILE_WORKERS: set[BackgroundTaskWorker] = set()
_PLATFORM_LABELS = {"chesscom": "Chess.com", "lichess": "Lichess"}
_PROFILE_URLS = {
    "chesscom": "https://www.chess.com/member/{username}",
    "lichess": "https://lichess.org/@/{username}",
}
_RATING_LABELS = {
    "chesscom": {
        "bullet": "Bullet",
        "blitz": "Blitz",
        "rapid": "Rapid",
        "classical": "Daily",
        "puzzle": "Puzzles",
    },
    "lichess": {
        "bullet": "Bullet",
        "blitz": "Blitz",
        "rapid": "Rapid",
        "classical": "Classical",
        "puzzle": "Puzzles",
    },
}


@dataclass(frozen=True)
class ProfileLoad:
    """Result of a cache-first profile load."""

    status: ApiStatus
    username: str
    profile: dict | None = None
    fetched_at: float = 0.0
    from_cache: bool = False
    is_stale: bool = False
    avatar_bytes: bytes | None = None
    avatar_mime: str | None = None


def platform_label(platform: str) -> str:
    return _PLATFORM_LABELS.get(platform, platform.title())


def _from_cache(status: ApiStatus, cached: CachedProfile, username: str) -> ProfileLoad:
    return ProfileLoad(
        status=status,
        username=username,
        profile=cached.profile,
        fetched_at=cached.fetched_at,
        from_cache=True,
        is_stale=cached.is_stale,
        avatar_bytes=cached.avatar_bytes,
        avatar_mime=cached.avatar_mime,
    )


def load_profile(
    platform: str,
    username: str,
    *,
    force: bool = False,
    history: GameHistoryManager | None = None,
) -> ProfileLoad:
    """Load a profile cache-first, refreshing only when the TTL has elapsed."""
    username = (username or "").strip()
    if not username:
        return ProfileLoad("not_found", username)

    history = history or GameHistoryManager()
    cached = history.get_cached_profile(platform, username)
    if cached is not None and not cached.is_stale and not force:
        return _from_cache("ok", cached, username)

    try:
        if platform == "chesscom":
            result = ChessComAPI.get_user_profile_result(username)
        else:
            result = LichessAPI().get_user_profile_result(username)
    except Exception as e:
        logger.warning("Profile fetch failed for %s/%s: %s", platform, username, e)
        if cached is not None:
            return _from_cache("error", cached, username)
        return ProfileLoad("error", username)

    if result.status == "ok" and result.profile:
        fetched_at = time.time()
        try:
            history.save_cached_profile(
                platform,
                username,
                result.profile,
                avatar_bytes=result.avatar_bytes,
                avatar_mime=result.avatar_mime,
                avatar_url=result.profile.get("avatar"),
            )
        except Exception as e:
            # A cache write failure must not hide a perfectly good profile.
            logger.warning("Could not cache profile for %s/%s: %s", platform, username, e)

        return ProfileLoad(
            status="ok",
            username=username,
            profile=result.profile,
            fetched_at=fetched_at,
            avatar_bytes=result.avatar_bytes or (cached.avatar_bytes if cached else None),
            avatar_mime=result.avatar_mime or (cached.avatar_mime if cached else None),
        )

    if cached is not None:
        # Keep the last known profile visible; the card labels it as offline.
        return _from_cache(result.status, cached, username)
    return ProfileLoad(result.status, username)


def format_cache_age(fetched_at: float, now: float | None = None) -> str:
    """Human-readable age for a profile snapshot."""
    if not fetched_at:
        return ""
    now = time.time() if now is None else now
    seconds = max(0, now - fetched_at)
    if seconds < 90:
        return "just now"

    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"

    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hr ago" if hours == 1 else f"{hours} hrs ago"

    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day ago" if days == 1 else f"{days} days ago"
    return time.strftime("%d %b %Y", time.localtime(fetched_at))


def country_flag(code: str | None) -> str:
    """Turn an ISO country code into a flag emoji without shipping assets."""
    if not code or len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(char.upper()) - ord("A")) for char in code)


def initials_for(name: str) -> str:
    """Two-letter avatar fallback that tolerates underscores and dots."""
    parts = [part for part in re.split(r"[\s_.\-]+", (name or "").strip()) if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def status_message(status: ApiStatus, platform: str, username: str) -> str:
    label = platform_label(platform)
    if status == "not_found":
        return f'No {label} player found for "{username}".'
    if status == "rate_limited":
        return f"{label} is rate-limiting requests. Try again in a minute."
    if status == "unauthorized":
        return f"{label} rejected the request. Check your credentials."
    if status == "offline":
        return f"Can't reach {label}. Check your connection."
    return f"Couldn't load this {label} profile."


def _circular_avatar(data: bytes) -> QPixmap | None:
    source = QPixmap()
    if not source.loadFromData(data):
        return None

    source = source.scaled(
        AVATAR_SIZE,
        AVATAR_SIZE,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    left = max(0, (source.width() - AVATAR_SIZE) // 2)
    top = max(0, (source.height() - AVATAR_SIZE) // 2)
    cropped = source.copy(left, top, AVATAR_SIZE, AVATAR_SIZE)

    target = QPixmap(AVATAR_SIZE, AVATAR_SIZE)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(QRectF(0.5, 0.5, AVATAR_SIZE - 1, AVATAR_SIZE - 1))
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(Styles.COLOR_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # QPainter only accepts QRect/QRectF (or ints) here, not four floats.
        painter.drawEllipse(QRectF(0.5, 0.5, AVATAR_SIZE - 1, AVATAR_SIZE - 1))
    finally:
        painter.end()
    return target


class ProfilePreview(QFrame):
    """Compact, self-refreshing preview of a public chess profile."""

    def __init__(self, platform: str, parent=None):
        super().__init__(parent)
        self.platform = platform
        self._username = ""
        self._worker: BackgroundTaskWorker | None = None
        self._worker_username = ""
        self._pending: tuple[str, bool] | None = None
        self._last_load: ProfileLoad | None = None
        self._chips: list[QLabel] = []

        self.setObjectName("ProfilePreview")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self.show_idle()

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        self.avatar = QLabel()
        self.avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.hide()
        root.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        body = QWidget()
        body.setStyleSheet(Styles.get_transparent_label_style())
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(5)
        root.addWidget(body, 1)

        self._state_row = QWidget()
        self._state_row.setStyleSheet(Styles.get_transparent_label_style())
        state_layout = QHBoxLayout(self._state_row)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(10)

        self.state_label = QLabel()
        self.state_label.setWordWrap(True)
        self.state_label.setStyleSheet(
            Styles.get_secondary_label_style(size=12)
            + " "
            + Styles.get_transparent_label_style()
        )
        state_layout.addWidget(self.state_label, 1)

        self.retry_btn = Button(
            "Retry",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            on_click=self.refresh,
            parent=self,
        )
        self.retry_btn.hide()
        state_layout.addWidget(self.retry_btn)
        body_layout.addWidget(self._state_row)

        self._data_widget = QWidget()
        self._data_widget.setStyleSheet(Styles.get_transparent_label_style())
        data_layout = QVBoxLayout(self._data_widget)
        data_layout.setContentsMargins(0, 0, 0, 0)
        data_layout.setSpacing(5)
        body_layout.addWidget(self._data_widget)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)

        self.name_label = QLabel()
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        name_row.addWidget(self.name_label)

        self.title_badge = QLabel()
        self.title_badge.hide()
        name_row.addWidget(self.title_badge)

        self.country_label = QLabel()
        name_row.addWidget(self.country_label)
        name_row.addStretch(1)

        self.refresh_btn = Button(
            variant=ButtonVariant.FILLED,
            size=ButtonSize.SM,
            icon="fa5s.sync-alt",
            icon_position="only",
            tooltip="Refresh profile",
            on_click=self.refresh,
            parent=self,
        )
        name_row.addWidget(self.refresh_btn)

        self.link_label = QLabel()
        self.link_label.setOpenExternalLinks(True)
        self.link_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        name_row.addWidget(self.link_label)
        data_layout.addLayout(name_row)

        self.meta_label = QLabel()
        self.meta_label.setStyleSheet(
            Styles.get_secondary_label_style(size=11)
            + " "
            + Styles.get_transparent_label_style()
        )
        data_layout.addWidget(self.meta_label)

        self._chips_widget = QWidget()
        self._chips_widget.setStyleSheet(Styles.get_transparent_label_style())
        self._chips_layout = QHBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(0, 2, 0, 2)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch(1)
        data_layout.addWidget(self._chips_widget)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        self.record_label = QLabel()
        self.record_label.setStyleSheet(
            Styles.get_secondary_label_style(size=11)
            + " "
            + Styles.get_transparent_label_style()
        )
        footer.addWidget(self.record_label)
        footer.addStretch(1)
        self.updated_label = QLabel()
        footer.addWidget(self.updated_label)
        data_layout.addLayout(footer)

        self._data_widget.hide()
        self.setStyleSheet(self._frame_style())

    def _frame_style(self) -> str:
        return f"""
            QFrame#ProfilePreview {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
            }}
            QFrame#ProfilePreview QLabel {{
                background: transparent;
                border: none;
            }}
        """

    # -- state transitions ------------------------------------------------
    def show_idle(self) -> None:
        self._data_widget.hide()
        self.avatar.hide()
        self.retry_btn.hide()
        self._state_row.show()
        self.state_label.setStyleSheet(
            Styles.get_secondary_label_style(size=12)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.state_label.setText(
            f"Enter your {platform_label(self.platform)} username to preview "
            "your public profile."
        )

    def _show_loading(self, username: str) -> None:
        self._data_widget.hide()
        self.avatar.hide()
        self.retry_btn.hide()
        self._state_row.show()
        self.state_label.setStyleSheet(
            Styles.get_secondary_label_style(size=12)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.state_label.setText(
            f"Loading {platform_label(self.platform)} profile for \"{username}\"…"
        )

    def _show_error(self, status: ApiStatus, username: str) -> None:
        self._data_widget.hide()
        self.avatar.hide()
        self._state_row.show()
        self.retry_btn.setVisible(bool(username))
        self.state_label.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_ENGINE_BUSY}; "
            "background-color: transparent; border: none; padding: 4px 0px;"
        )
        self.state_label.setText(status_message(status, self.platform, username))

    # -- loading ----------------------------------------------------------
    def load(self, username: str, *, force: bool = False) -> None:
        username = (username or "").strip()
        self._username = username
        if not username:
            self._pending = None
            self.show_idle()
            return

        if self._worker is not None:
            self._pending = (username, force)
            self._show_loading(username)
            return
        self._start(username, force)

    def refresh(self) -> None:
        if self._username:
            self.load(self._username, force=True)
        else:
            self.show_idle()

    def _start(self, username: str, force: bool) -> None:
        self._show_loading(username)
        worker = BackgroundTaskWorker(
            lambda: load_profile(self.platform, username, force=force)
        )
        ACTIVE_PROFILE_WORKERS.add(worker)
        worker.completed.connect(self._on_loaded)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        self._worker = worker
        self._worker_username = username
        worker.start()

    def _on_loaded(self, load: object) -> None:
        if not isinstance(load, ProfileLoad):
            return
        if load.username.casefold() != self._worker_username.casefold():
            return
        if self._pending is not None:
            # A newer username is queued; showing this result would flicker
            # the previous profile over the loading state.
            return
        if load.profile:
            self._render(load)
        else:
            self._show_error(load.status, load.username)

    def _on_worker_failed(self, message: str) -> None:
        logger.warning("Profile preview worker failed: %s", message)
        if self._pending is None:
            self._show_error("error", self._worker_username)

    def _on_worker_finished(self, worker: BackgroundTaskWorker) -> None:
        ACTIVE_PROFILE_WORKERS.discard(worker)
        worker.deleteLater()
        if worker is not self._worker:
            return
        self._worker = None
        pending = self._pending
        self._pending = None
        if pending is not None:
            QTimer.singleShot(0, lambda: self._start(*pending))

    # -- rendering --------------------------------------------------------
    def _render(self, load: ProfileLoad) -> None:
        profile = load.profile or {}
        self._last_load = load

        display = profile.get("username") or load.username
        self.name_label.setText(display)
        self.name_label.setStyleSheet(
            Styles.get_label_style(
                size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True
            )
            + " "
            + Styles.get_transparent_label_style()
        )

        title = profile.get("title")
        if title:
            self.title_badge.setText(title)
            self.title_badge.setStyleSheet(
                Styles.get_eval_badge_style(
                    Styles.COLOR_ACCENT_SUBTLE, Styles.COLOR_ACCENT
                )
            )
            self.title_badge.show()
        else:
            self.title_badge.hide()

        flag = country_flag(profile.get("country"))
        self.country_label.setText(flag)
        self.country_label.setToolTip(profile.get("country") or "")
        self.country_label.setVisible(bool(flag))

        total = int(profile.get("total_games") or 0)
        meta = f"@{display}"
        if total:
            meta += f" · {total:,} games"
        self.meta_label.setText(meta)

        self._render_chips(profile)
        self._render_record(profile, total)
        self._render_updated(load)
        self._render_link(profile, load.username)
        self._render_avatar(load, display)

        self._state_row.hide()
        self._data_widget.show()
        self.avatar.show()
        self._refresh_button_style()

    def _render_chips(self, profile: dict) -> None:
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._chips = []

        labels = _RATING_LABELS.get(self.platform, {})
        for key in ("bullet", "blitz", "rapid", "classical", "puzzle"):
            perf = profile.get(key) or {}
            rating = perf.get("rating")
            if not rating:
                continue
            chip = QLabel(f"{labels.get(key, key.title())} {rating}")
            chip.setStyleSheet(Styles.get_badge_style(size=11))
            peak = perf.get("peak")
            if peak and peak != rating:
                chip.setToolTip(f"Peak: {peak}")
            self._chips_layout.addWidget(chip)
            self._chips.append(chip)
        self._chips_layout.addStretch(1)
        self._chips_widget.setVisible(bool(self._chips))

    def _render_record(self, profile: dict, total: int) -> None:
        record = profile.get("record") or {}
        if not total:
            self.record_label.setText("No rated games played yet")
            return
        wins = int(record.get("win") or 0)
        draws = int(record.get("draw") or 0)
        losses = int(record.get("loss") or 0)
        win_rate = profile.get("win_rate")
        if win_rate is None:
            win_rate = (wins / total * 100) if total else 0.0
        self.record_label.setText(
            f"{wins:,}W · {draws:,}D · {losses:,}L · {float(win_rate):.1f}% win rate"
        )

    def _render_updated(self, load: ProfileLoad) -> None:
        age = format_cache_age(load.fetched_at)
        if load.status != "ok":
            self.updated_label.setText(
                f"Offline · cached {age}" if age else "Offline"
            )
            color = Styles.COLOR_ENGINE_BUSY
        elif load.from_cache:
            self.updated_label.setText(f"Cached {age}" if age else "Cached")
            color = Styles.COLOR_TEXT_MUTED
        else:
            self.updated_label.setText("Updated just now")
            color = Styles.COLOR_TEXT_MUTED
        self.updated_label.setStyleSheet(
            f"font-size: 10px; color: {color}; background: transparent; border: none;"
        )

    def _render_link(self, profile: dict, username: str) -> None:
        url = profile.get("url") or ""
        if not str(url).startswith("https://"):
            url = _PROFILE_URLS.get(self.platform, "").format(
                username=quote(username, safe="")
            )
        if not url:
            self.link_label.clear()
            return
        safe_url = html.escape(str(url), quote=True)
        self.link_label.setText(
            f'<a href="{safe_url}" style="color: {Styles.COLOR_ACCENT}; '
            'text-decoration: none;">View profile ↗</a>'
        )
        self.link_label.setStyleSheet(
            "font-size: 11px; background: transparent; border: none;"
        )

    def _render_avatar(self, load: ProfileLoad, display: str) -> None:
        pixmap = _circular_avatar(load.avatar_bytes) if load.avatar_bytes else None
        if pixmap is not None:
            self.avatar.setPixmap(pixmap)
            self.avatar.setText("")
            self.avatar.setStyleSheet(
                "background: transparent; border: none; padding: 0px;"
            )
            return

        self.avatar.setPixmap(QPixmap())
        self.avatar.setText(initials_for(display))
        self.avatar.setStyleSheet(f"""
            QLabel {{
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
                color: {Styles.COLOR_ACCENT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: {AVATAR_SIZE // 2}px;
                font-size: 18px;
                font-weight: 700;
            }}
        """)

    def _refresh_button_style(self) -> None:
        self.refresh_btn.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet(self._frame_style())
        self.state_label.setStyleSheet(
            Styles.get_secondary_label_style(size=12)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.meta_label.setStyleSheet(
            Styles.get_secondary_label_style(size=11)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.record_label.setStyleSheet(
            Styles.get_secondary_label_style(size=11)
            + " "
            + Styles.get_transparent_label_style()
        )
        self.retry_btn.refresh_styles()
        self._refresh_button_style()
        if self._last_load and self._data_widget.isVisible():
            self._render(self._last_load)
