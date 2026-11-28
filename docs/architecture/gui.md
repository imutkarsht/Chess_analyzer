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
`EmptyState`, `StatusBadge`, `SegmentedControl`, `MiniBar`, `SegmentedBar`,
`Icon`, `IconLabel`, and `ElidedLabel`.

Construct `Button` directly with a variant and size. Do not reintroduce
`create_button` or `create_icon_button` factories.

### Tooltips

`TooltipManager` owns one custom popup for the whole app: inverted surface,
painted caret, shadow, fade-and-zoom, screen-edge clamping, keyboard focus,
item-view tooltips, tab tooltips, and disabled reasons. It is installed once
in `main.py`; existing `setToolTip` calls are routed through it.

Use the semantic `Tooltip` factories from `src.gui.components` for new copy.
Copy rules live in [conventions.md](../conventions.md#tooltips). Use
`ElidedLabel` instead of adding a label tooltip by hand, and rely on
`Button`'s tooltip-to-accessible-name default for icon-only controls.

Documented exceptions are board swatches, theme cards, star rating, variation
graph nodes, the move-cell variation badge, pixmap labels, the toast hairline
progress bar, and the domain-specific move table.

Guardrails: `tests/gui/test_button.py` and `tests/gui/test_input.py`.

### Icons

`src/gui/icons/` is the only module that imports `qtawesome`. It owns
`IconSpec`, `IconVariant`, icon packs, `IconStyleManager`, and the resolver.
The `Icon` widget lives in `src/gui/components/display/icon.py` and is exported
through the component facade.

- Use semantic keys (`play`, `history`, `close`) or asset paths. Do not pass
  `fa5s.*` / `fa6s.*` names from call sites.
- `IconSpec` carries key, variant, size, tone, colour, and fallback.
- Variants are pack-defined: `solid` and `outline`. Font Awesome provides the
  solid pack; Phosphor provides the outline pack. The resolver falls back to
  the pack default and then the default pack when a glyph is unavailable.
- QtAwesome glyphs resolve to cached 1x/2x raster `QIcon`s so Qt never invokes
  QtAwesome's Python icon engine during a paint event. SVG and asset paths keep
  Qt's vector icon engine.
- `IconStyleManager.set_pack()` re-resolves every subscribed icon. The
  `icon_style` Appearance setting selects `Solid (Font Awesome)` or
  `Outline (Phosphor)`.
- Brand glyphs and content artwork (logos, board pieces, previews, charts) are
  explicit exceptions; they may use asset helpers directly.

Guardrail: `tests/architecture/test_icon_guardrails.py` rejects direct
`qtawesome` imports, raw font names, and raw `QIcon` / `setIcon` use outside
the allowed content exceptions.

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

Accent tint is a modifier, not a bundle: `tint_enabled` rebuilds the active
Light or Dark palette from the live accent in `bundles/tinted.py`.

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
