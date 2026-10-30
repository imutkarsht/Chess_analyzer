"""Behavioural tests for the centralized toast component."""

import pytest
from PyQt6.QtWidgets import QWidget

from src.gui.components.feedback.toast import (
    ToastManager,
    ToastPosition,
    ToastVariant,
    coerce_position,
    coerce_variant,
)
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.palette import LIGHT


@pytest.fixture(autouse=True)
def reset_toast_state():
    saved_defaults = ToastManager.defaults()
    yield
    ToastManager.clear()
    ToastManager._defaults = saved_defaults


@pytest.fixture
def window(qtbot):
    win = QWidget()
    win.resize(900, 600)
    qtbot.addWidget(win)
    win.show()
    return win


def _host(window):
    return ToastManager._host_for(window)


def test_variants_have_their_own_durations_and_legacy_alias(window):
    assert coerce_variant("warn") is ToastVariant.WARNING
    assert ToastManager.success(window, "ok").toast.duration == 3000
    assert ToastManager.info(window, "note").toast.duration == 3500
    assert ToastManager.warning(window, "careful").toast.duration == 4500
    assert ToastManager.error(window, "broken").toast.duration == 6000

    loading = ToastManager.loading(window, "working").toast
    assert loading.duration == 0
    assert loading.is_loading
    assert loading.is_counting_down is False


def test_loading_handle_turns_into_success_in_place(window):
    handle = ToastManager.loading(window, "Importing games…")
    toast = handle.toast

    handle.update("Imported: 412, Skipped: 3", variant="success")

    assert handle.toast is toast
    assert toast.variant is ToastVariant.SUCCESS
    assert toast.message == "Imported: 412, Skipped: 3"
    assert toast.duration == 3000
    assert toast.is_counting_down is True
    assert len(ToastManager.active_toasts(window)) == 1


def test_stack_limit_retires_the_oldest_toast(window):
    ToastManager.configure(max_visible=2)

    ToastManager.success(window, "first")
    ToastManager.success(window, "second")
    ToastManager.success(window, "third")

    messages = [toast.message for toast in ToastManager.active_toasts(window)]
    assert messages == ["second", "third"]


def test_duplicate_messages_refresh_instead_of_stacking(window):
    ToastManager.success(window, "Saved")
    ToastManager.success(window, "Saved")
    assert len(ToastManager.active_toasts(window)) == 1

    ToastManager.error(window, "Saved")
    assert len(ToastManager.active_toasts(window)) == 2


def test_close_button_starts_the_dismiss_animation(window):
    toast = ToastManager.info(window, "Dismiss me").toast

    toast._close_button.click()

    assert toast.is_dismissing is True
    assert toast.is_counting_down is False


def test_hover_pauses_and_resumes_the_dismiss_timer(window):
    toast = ToastManager.success(window, "Hover me").toast
    assert toast.is_counting_down is True

    toast.enterEvent(None)
    assert toast.is_counting_down is False

    toast.leaveEvent(None)
    assert toast.is_counting_down is True


@pytest.mark.parametrize("position", list(ToastPosition))
def test_position_is_configurable(window, position):
    ToastManager.configure(position=position)
    ToastManager.success(window, f"at {position.value}")

    host = _host(window)
    bottom = position in (
        ToastPosition.BOTTOM_LEFT,
        ToastPosition.BOTTOM_CENTER,
        ToastPosition.BOTTOM_RIGHT,
    )
    assert host.y() == (600 - host.height() - 12 if bottom else 12)

    if position in (ToastPosition.TOP_RIGHT, ToastPosition.BOTTOM_RIGHT):
        assert host.x() == 900 - host.width() - 12
    elif position in (ToastPosition.TOP_LEFT, ToastPosition.BOTTOM_LEFT):
        assert host.x() == 12
    else:
        assert host.x() == (900 - host.width()) // 2


def test_position_aliases_are_accepted():
    assert coerce_position("top-right") is ToastPosition.TOP_RIGHT
    assert coerce_position("bottomleft") is ToastPosition.BOTTOM_LEFT
    with pytest.raises(ValueError):
        coerce_position("middle")


def test_custom_options_apply(window):
    clicked = []
    handle = ToastManager.error(
        window,
        "Export failed",
        title="Could not export",
        min_width=320,
        max_width=380,
        radius=10,
        font_size=15,
        action=("Retry", lambda: clicked.append(True)),
        show_progress=True,
    )
    toast = handle.toast

    assert toast.width() <= 380 + 16
    assert toast._title_label.isVisible() is True
    assert toast._action_button.isVisible() is True

    toast._action_button.click()
    assert clicked == [True]

    toast.set_progress(0.5)
    assert toast._progress.value() == 500


def test_icons_are_monochrome_except_for_errors():
    assert Styles.get_toast_icon_color("success") == Styles.COLOR_TEXT_PRIMARY
    assert Styles.get_toast_icon_color("warning") == Styles.COLOR_TEXT_PRIMARY
    assert Styles.get_toast_icon_color("error") == Styles.COLOR_BLUNDER
    assert (
        Styles.get_toast_icon_color("success", semantic=True)
        == Styles.COLOR_ENGINE_READY
    )


def test_theme_change_restyles_live_toasts(window, monkeypatch):
    toast = ToastManager.success(window, "Theme me").toast
    dark_sheet = toast._surface.styleSheet()
    assert Styles.COLOR_SURFACE in dark_sheet

    monkeypatch.setattr(ThemeManager, "palette", classmethod(lambda cls: LIGHT))
    toast._on_theme_changed()

    light_sheet = toast._surface.styleSheet()
    assert light_sheet != dark_sheet
    assert LIGHT.surface in light_sheet


def test_unknown_options_and_variants_are_rejected(window):
    with pytest.raises(TypeError):
        ToastManager.success(window, "Nope", glow=True)
    with pytest.raises(ValueError):
        ToastManager.show(window, "Nope", "celebrate")
