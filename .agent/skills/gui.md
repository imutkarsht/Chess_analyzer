# Skill: GUI & Frontend

## Purpose
The PyQt6 desktop interface. Covers theming, widget architecture, signal/slot wiring, threading patterns, and board rendering.

---

## Relevant Files
| File | Role |
|---|---|
| `src/gui/main_window.py` | Central hub: owns all views, wires signals |
| `src/gui/styles.py` | `Styles` class: dark theme, color constants, stylesheet generators |
| `src/gui/board/board_widget.py` | Interactive chessboard with SVG pieces |
| `src/gui/board/eval_bar.py` | Vertical evaluation bar |
| `src/gui/analysis/analysis_panel.py` | Right panel: graph + AI summary |
| `src/gui/analysis/move_list_panel.py` | Move list with live engine |
| `src/gui/analysis/analysis_worker.py` | QThread for full game analysis |
| `src/gui/analysis/live_analysis.py` | QThread for live engine lines |
| `src/gui/components/graph_widget.py` | Matplotlib evaluation graph |
| `src/gui/components/sidebar.py` | Navigation sidebar |
| `src/gui/views/history_view.py` | Game history page |
| `src/gui/views/metrics_view.py` | Stats dashboard |
| `src/gui/views/settings_view.py` | Settings page |
| `src/gui/dialogs/load_game_dialog.py` | Unified game loader dialog |
| `src/gui/dialogs/update_dialog.py` | Update download & install dialog |

---

## Architecture

### Page Structure (QStackedWidget)
```
Index 0: Analysis page   — board + move list + analysis panel
Index 1: History page    — HistoryView
Index 2: Metrics page    — MetricsWidget
Index 3: Settings page   — SettingsView
```
Sidebar emits `page_changed(int)` → `MainWindow.switch_page()`.

### Threading Pattern
All engine/API/AI work runs in `QThread` subclasses. Signals used:
- `progress(int, int)` — analysis progress (current, total)
- `finished(result)` — done with data
- `error(str)` — failure message

Workers are stored as instance variables to prevent garbage collection.

**Always disconnect signals before re-assigning workers** or before calling `quit()`/`wait()` to avoid `RuntimeError: wrapped C++ object has been deleted`.

### Signal/Slot Conventions
```python
# Wire once (in __init__ or setup_ui):
self.move_list_panel.move_selected.connect(self.on_move_selected)

# Disconnect before re-connecting across game loads:
try:
    self.analysis_panel.graph_widget.move_clicked.disconnect(self.on_move_selected)
except (RuntimeError, TypeError):
    pass
self.analysis_panel.graph_widget.move_clicked.connect(self.on_move_selected)
```

---

## Theming System (`Styles`)

All colors are class variables on `Styles`. Never use hardcoded hex colors in widget files.

### Key Color Constants
| Constant | Use |
|---|---|
| `COLOR_BACKGROUND` | Main window background (`#1A1A1D`) |
| `COLOR_SURFACE` | Cards, panels (`#252529`) |
| `COLOR_SURFACE_LIGHT` | Hover states (`#2E2E33`) |
| `COLOR_TEXT_PRIMARY` | Main text (`#E4E4E7`) |
| `COLOR_TEXT_SECONDARY` | Muted text (`#9CA3AF`) |
| `COLOR_ACCENT` | Dynamic accent (default `#FF9500`) |
| `COLOR_BORDER` | Borders (`#3E3E45`) |
| `COLOR_BRILLIANT/BEST/BLUNDER/…` | Move classification colors |

### Style Generators (call in widget __init__)
```python
Styles.get_theme()            # Global stylesheet for setStyleSheet()
Styles.get_button_style()     # Primary accent button
Styles.get_control_button_style()  # Secondary surface button
Styles.get_input_style()      # QLineEdit
Styles.get_combobox_style()   # QComboBox
Styles.get_group_box_style()  # Settings sections
Styles.get_card_style()       # Hoverable card frames
Styles.get_class_color(classification)  # Hex for move badge
Styles.get_board_colors(theme_name)     # {dark, light} board colors
```

### Accent Color
```python
Styles.set_accent_color("#FF9500")  # Updates COLOR_ACCENT and COLOR_ACCENT_SUBTLE
# Then call MainWindow.refresh_theme() to propagate to all widgets
```

---

## Board Widget
- Renders chess position using SVG piece images from `assets/pieces/<theme>/`
- Drag-and-drop for interactive moves (browsing mode)
- Last move highlighted with `COLOR_BOARD_HIGHLIGHT` (#F7EC74)
- `board_widget.load_game(game_analysis)` — loads all moves
- `board_widget.current_move_index` — tracks current position
- Navigate with `board_widget.go_to_move(index)`

---

## Important GUI Patterns

### Creating Buttons (use helper, not raw QPushButton)
```python
from src.gui.utils.gui_utils import create_button
btn = create_button("Label", style="primary", on_click=handler, icon_name="fa5s.play")
# style: "primary" (accent) | "secondary" (surface)
```

### Loading Overlay
```python
self.loading_overlay = LoadingOverlay(self)
self.loading_overlay.resize(self.size())
self.loading_overlay.show()   # Block UI during work
self.loading_overlay.hide()   # After work done
```

### Status Bar Updates
```python
self._set_status("Game loaded", kind="success")
# kinds: "idle" | "info" | "success" | "warning" | "error" | "progress"
self._set_engine_state("calculating")  # "offline" | "ready" | "calculating"
```

### Keyboard Shortcuts
Defined in `MainWindow._setup_shortcuts()`:
- `Ctrl+O` — load game
- `Ctrl+V` — paste PGN (smart: only triggers on non-input-focused window)
- `Ctrl+A` — analyze game
- Arrow keys — navigate moves

---

## Common Pitfalls
- **QLabel `border-radius` in QStatusBar doesn't render** — use colored text only, not background pills.
- **Multiple signal connections**: Connecting the same slot to a signal multiple times (e.g., on each game load) fires it multiple times. Always disconnect before reconnecting.
- **Worker garbage collection**: Assign workers to `self.worker = Worker(...)` — local variables get GC'd before the thread finishes.
- **QThread cleanup on close**: `MainWindow.closeEvent()` manually stops all workers. If you add a new QThread-owning widget, add cleanup there.
- **Theme refresh**: Calling `setStyleSheet()` on the main window propagates to children, but some widgets cache styles or use custom `paintEvent`. Call `refresh_styles()` on those widgets too (see `MainWindow.refresh_theme()`).
- **Splitter sizes**: Set `splitter.setSizes([250, 630, 320])` after adding all children, not before.
- **`QFont::setPointSize <= 0` warning**: Suppressed in `qt_message_handler` in `main.py` — do not remove this filter.

---

## Extension Guidelines
- **New page**: Add a new widget to `self.stack` and a button to `Sidebar`. Update `switch_page()` if the page needs a refresh on activation.
- **New dialog**: Subclass `QDialog`. Add to `src/gui/dialogs/__init__.py` exports.
- **New setting**: Add to `SettingsView`, emit `settings_changed` signal, connect in `MainWindow`. Persist via `config_manager.set()`.
- **New move classification**: Add color to `Styles`, add icon to `assets/`, update `move_cell_widget.py` icon map.
