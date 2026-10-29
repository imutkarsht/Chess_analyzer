"""
Central registry for the main window's keyboard shortcuts.

Every QShortcut is owned here so bindings can be swapped at runtime (presets)
and listed for the cheat-sheet in Settings and the F1 help dialog.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from PyQt6 import sip
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget

from src.constants import DEFAULT_SHORTCUT_PRESET, SHORTCUT_PRESETS
from src.gui.components.controls.input import TEXT_INPUT_TYPES
from src.utils.logger import logger

KeyInput = str | Iterable[str]

_TEXT_INPUTS = TEXT_INPUT_TYPES


@dataclass
class ShortcutAction:
    """A named action and the QShortcuts currently backing it."""

    action_id: str
    description: str
    category: str
    default_keys: tuple[str, ...]
    callback: Callable[[], None]
    keys: list[str] = field(default_factory=list, init=False)
    shortcuts: list[QShortcut] = field(default_factory=list, init=False, repr=False)


class ShortcutManager(QObject):
    """Owns every QShortcut attached to ``window``.

    Single-key shortcuts that also type text (letters, digits, Space) are
    switched off while an editable text field has focus, so typing "Fabiano"
    in a username box never flips the board or jumps between pages.
    """

    #: Emitted after the active bindings change (preset switch).
    bindings_changed = pyqtSignal()

    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window
        self._actions: dict[str, ShortcutAction] = {}
        self._overrides: dict[str, list[str]] = {}
        self.preset = DEFAULT_SHORTCUT_PRESET
        self._typing = False
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)
            self._typing = self._is_text_input(QApplication.focusWidget())

    def register(
        self,
        action_id: str,
        description: str,
        default_keys: KeyInput,
        callback: Callable[[], None],
        category: str = "General",
    ) -> ShortcutAction:
        """Register an action and bind its keys immediately.

        ``default_keys`` is a single key (``"Ctrl+O"``) or several
        (``("Down", "Home")``); every key triggers the same callback.
        """
        if action_id in self._actions:
            raise ValueError(f"Shortcut action already registered: {action_id!r}")

        defaults = tuple(self._normalize(default_keys))
        action = ShortcutAction(action_id, description, category, defaults, callback)
        action.keys = list(self._overrides.get(action_id, defaults))
        self._actions[action_id] = action

        self._warn_on_conflicts(action)
        self._bind(action)
        return action

    def apply_preset(self, name: str) -> None:
        """Switch to a named preset from ``SHORTCUT_PRESETS``.

        Unknown names (e.g. a hand-edited config.json) fall back to the
        default preset instead of leaving the user with no bindings.
        """
        if name not in SHORTCUT_PRESETS:
            logger.warning(f"ShortcutManager: unknown preset {name!r}, using default")
            name = DEFAULT_SHORTCUT_PRESET
        self.preset = name
        self.apply_overrides(SHORTCUT_PRESETS[name])

    def apply_overrides(self, overrides: Mapping[str, KeyInput]) -> None:
        """Rebind actions from ``{action_id: keys}``.

        Actions not named in ``overrides`` go back to their defaults, so the
        result depends only on ``overrides``. Unknown ids are ignored.
        """
        self._overrides = {k: self._normalize(v) for k, v in overrides.items()}
        for action in self._actions.values():
            action.keys = list(self._overrides.get(action.action_id, action.default_keys))
            self._bind(action)
        # Defaults were already checked at registration; only overrides can add a clash.
        for action_id in self._overrides.keys() & self._actions.keys():
            self._warn_on_conflicts(self._actions[action_id])
        self.bindings_changed.emit()

    def get_bindings(self) -> list[dict]:
        """Return the active bindings in registration order.

        Each entry: ``{"id", "description", "category", "keys"}`` where
        ``keys`` are human-readable key strings.
        """
        return [
            {
                "id": a.action_id,
                "description": a.description,
                "category": a.category,
                "keys": [self._display(k) for k in a.keys],
            }
            for a in self._actions.values()
        ]

    def keys_for(self, action_id: str) -> list[str]:
        return list(self._require(action_id).keys)

    def trigger(self, action_id: str) -> None:
        """Run an action's callback directly (used by tests)."""
        self._require(action_id).callback()

    def _require(self, action_id: str) -> ShortcutAction:
        try:
            return self._actions[action_id]
        except KeyError:
            raise KeyError(f"Unknown shortcut action: {action_id!r}") from None

    def _bind(self, action: ShortcutAction) -> None:
        """(Re)create the QShortcut objects for one action."""
        self._unbind(action)
        for key in action.keys:
            seq = QKeySequence(key)
            if seq.isEmpty():
                logger.warning(
                    f"ShortcutManager: ignoring invalid key {key!r} for {action.action_id!r}"
                )
                continue
            shortcut = QShortcut(seq, self._window)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.setEnabled(not (self._typing and self._types_text(seq)))
            shortcut.activated.connect(action.callback)
            action.shortcuts.append(shortcut)

    @staticmethod
    def _unbind(action: ShortcutAction) -> None:
        for shortcut in action.shortcuts:
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
        action.shortcuts.clear()

    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        typing = self._is_text_input(new)
        if typing == self._typing:
            return
        self._typing = typing
        for action in self._actions.values():
            for shortcut in action.shortcuts:
                if not sip.isdeleted(shortcut) and self._types_text(shortcut.key()):
                    shortcut.setEnabled(not typing)

    @staticmethod
    def _is_text_input(widget: QWidget | None) -> bool:
        return isinstance(widget, _TEXT_INPUTS) and not widget.isReadOnly()

    @staticmethod
    def _types_text(seq: QKeySequence) -> bool:
        """True for a single unmodified printable key (letters, digits, Space)."""
        if seq.count() != 1:
            return False
        combo = seq[0]
        printable = 0x20 <= combo.key().value <= 0x7E  # Key_Space .. Key_AsciiTilde
        return printable and combo.keyboardModifiers() == Qt.KeyboardModifier.NoModifier

    def _warn_on_conflicts(self, action: ShortcutAction) -> None:
        """Log (but don't block) when two actions claim the same key.

        Qt treats a duplicate as ambiguous and fires neither action, so this
        is worth surfacing even though registration still succeeds.
        """
        wanted = {self._canonical(k) for k in action.keys}
        for other in self._actions.values():
            if other is action:
                continue
            clash = wanted & {self._canonical(k) for k in other.keys}
            if clash:
                logger.warning(
                    f"ShortcutManager: {action.action_id!r} conflicts with "
                    f"{other.action_id!r} on {sorted(clash)}"
                )

    @staticmethod
    def _normalize(keys: KeyInput) -> list[str]:
        if isinstance(keys, str):
            return [keys]
        return [k for k in keys if k]

    @staticmethod
    def _canonical(key: str) -> str:
        return QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)

    @staticmethod
    def _display(key: str) -> str:
        return QKeySequence(key).toString(QKeySequence.SequenceFormat.NativeText) or key
