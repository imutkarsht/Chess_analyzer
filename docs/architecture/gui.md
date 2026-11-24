# GUI

The GUI is a PyQt6 presentation layer. Widgets render state and dispatch user
actions; workflows live in controllers, and background work lives in
`src/workers/`.

---

## Composition

- `MainWindow` builds the layout, constructs controllers, connects their
  signals, and keeps the QWidget drag/drop hooks.
- `src/gui/app/` owns workflows: single-game analysis, batch analysis, and game
  loading.
- `src/gui/main_window/` contains focused mixins for navigation, variations,
  theming, the status bar, the tour, and updates.
- `src/gui/views/` contains pages and their page-specific sub-widgets.
- `src/gui/analysis/` contains the analysis workspace: tabs, move list, coach,
  variations, and captured pieces.
- `src/gui/components/` contains the shared component library. Import from the
  package facade, never from a subpackage at a call site.

## Components

Use the shared controls for every UI control: `Button`, `Checkbox`, `Input`,
`TextArea`, `Select`, `PathField`, `RadioChoice`, `SliderCounter`,
`ProgressBar`, `Tabs`, `DatePicker`, `ListView`, `Toast`, `PaginationBar`,
`EmptyState`, `StatusBadge`, `SegmentedControl`, `MiniBar`, and `SegmentedBar`.

Construct `Button` directly with a variant and size. Do not reintroduce
`create_button` or `create_icon_button` factories.

Documented exceptions are board swatches, theme cards, star rating, variation
graph nodes, the move-cell variation badge, pixmap labels, the toast hairline
progress bar, and the domain-specific move table.

Guardrails: `tests/gui/test_button.py` and `tests/gui/test_input.py`.

## Theming

`src/gui/theme/theme_template.qss` is the single source of truth for static
chrome. Widgets publish dynamic properties such as `btnVariant`, `inputSize`,
`checkboxVariant`, `settingsCard`, `cellState`, `selected`, and `compact`.
Only canvas and data-driven widgets keep `refresh_styles()`.

`ThemeManager.set_mode()`, `set_accent()`, and `set_bundle()` apply the global
stylesheet before emitting their signals. `ThemeMixin.refresh_theme()` must not
apply it again; it refreshes the palette, canvas widgets, and the visible page.
Hidden pages flush when navigation makes them visible.

Rules:

- Never use declaration-only stylesheets such as a bare `background` rule. They
  apply to every descendant and override the app stylesheet.
- Never add a universal `QWidget` background rule.
- Never style descendant `QWidget`s from an ancestor rule.
- Never hardcode hex colours in widget files. Use `Styles.COLOR_*` and
  `Styles.apply_transparent()`.
- Stateful looks are dynamic properties followed by `unpolish()` and `polish()`
  on that widget.
- Instance-specific values that QSS cannot express stay in a small
  selector-scoped sheet, never a bare declaration.

Guardrails: `tests/architecture/test_theme_guardrails.py` and
`tests/architecture/test_theme_tokens.py`.

A new theme is one `ThemeBundle` in `src/gui/theme/bundles/`, registered in
`src/gui/theme/__init__.py`. The appearance picker discovers it automatically.
Do not add theme-specific branches to `ThemeManager.set_mode()`.

## Board and live engine

- `Board` is the single configurable board used across Analysis, Explorer, and
  shared previews. Wheel navigation is opt-in through `BoardConfig`.
- `MiniBoardWidget` and `render_mini_board_pixmap()` share one cached renderer
  for import tables, history cards, and drill-down rows.
- `LiveEngineSession` owns one Stockfish process per surface. `EngineLinesWidget`
  renders its output, and `MainWindow.closeEvent()` shuts every session down.

## UI contracts

- The status bar shows only the engine-ready pill when idle. The separator and
  status label appear for real progress, warning, or error messages.
- New installs use `DEFAULT_BOARD_THEME` from `src/constants.py`. Keep fallbacks
  wired to that constant, never a literal theme name.
