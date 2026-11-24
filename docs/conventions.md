# Conventions

Patterns and rules for changing the codebase. For layer edges, see
[ARCHITECTURE.md](../ARCHITECTURE.md). For hard rules and commands, see
[AGENTS.md](../AGENTS.md).

---

## Core patterns

| Pattern | Rule |
| --- | --- |
| Qt-free backend | No PyQt6 or `src.gui` imports in `backend`, `utils`, or `config`. Qt work belongs in `src/workers/`. |
| Component facade | Import shared widgets from `src.gui.components`, never from a subpackage. |
| Shared controls | Do not construct raw `QPushButton`, `QLineEdit`, `QComboBox`, `QCheckBox`, `QProgressBar`, or `QListWidget`, and do not use `QLabel` for plain text. |
| No button factories | Construct `Button` directly with a variant and size. |
| Theme properties | Static looks live in `theme_template.qss` via object names and dynamic properties. |
| Canvas refresh | Only canvas and data-driven widgets keep `refresh_styles()`. |
| Settings schema | Defaults, types, and validation live in `settings_schema.py`; read through typed `ConfigManager` properties. |
| Off-thread work | `QThread` subclasses live in `src/workers/` and communicate with signals. |
| Worker lifetime | Cancel, disconnect, and delete workers on close. |
| Domain before storage | Repositories persist; domain services compute. |
| DB context | Connections, pragmas, commits, and rollbacks go through `db_connection.py`. |
| Single column spec | `GAME_COLUMNS` drives DDL, INSERTs, and row dictionaries. |
| Model serialisation | `to_dict()` and `from_dict()` live on the model. |
| Symmetric sides | Iterate over `("white", "black")` instead of copying White and Black blocks. |
| Paged data | Page plus idle prefetch; do not load the whole history at once. |
| Offline fallback | Provide deterministic text or cached data when the network is unavailable. |
| Debounce and throttle | Coalesce high-frequency UI work. |
| Shared sessions | One live-engine session per surface. |
| Claim-first coaching | Deterministic facts select the story; the LLM only rewrites it. |
| Toast-driven tasks | Long work shows loading, then success or error. |
| Layered errors | `logger` for diagnostics, toast or dialog for users. |

## Naming

- Modules are `snake_case`; Qt classes are `PascalCase` with a role suffix:
  `Card`, `Panel`, `Widget`, `Dialog`, `View`, or `Mixin`.
- One primary class per module; helpers stay private with a leading underscore.
- Pages live in `views/`, reusable pieces in `components/`, and page-specific
  sub-widgets next to their page.
- Compatibility shims stay for import stability. Add new code to the real
  module, not the shim.

## Components and settings

- Use the shared component facade for every control.
- Dashboard cards use `MetricCard.new_content()`, `clear_content()`, and
  `show_empty()`, plus the shared `EmptyState`, `StatusBadge`,
  `SegmentedControl`, `PaginationBar`, `LegendList`, `MiniBar`, and
  `SegmentedBar`.
- Add settings to `src/config/settings_schema.py` with a default, type,
  validation, and `apply="live"` when appropriate.
- Add a typed `ConfigManager` property when widgets or backend code read a
  value directly. Raw key access belongs in `SettingsBinder`, migrations, and
  secret or profile storage.
- Settings cards live in `src/gui/views/settings/` and use `SettingsForm` and
  `SettingsBinder`.
- Credentials go through `SecretStore`, never plaintext JSON.
- Runtime-registered choice values must be declared with
  `register_choice_values(key, values)`. Theme bundles do this automatically.

Theme rules and guardrails live in
[architecture/gui.md](architecture/gui.md#theming).

## Shared utility homes

Extend the canonical module before adding a private helper.

| Concern | Canonical module |
| --- | --- |
| Clock, eval, count, bytes, percent, duration | `src/utils/format_utils.py` |
| Time-control parsing, formatting, classification | `src/utils/time_control.py` |
| Display dates and cache ages | `src/utils/date_utils.py` |
| Error-text detection, initials, country flags | `src/utils/text_utils.py` |
| FEN keys, canonical FEN, Chess960 detection | `src/backend/analysis/chess_utils.py` |
| LLM clock-data summaries | `src/backend/analysis/metrics/time_stats.py` |
| PGN headers and mainline metadata | `src/backend/storage/pgn_metadata.py` |
| Cache timestamps and TTLs | `src/backend/storage/cache_time.py` |
| DB connections, read-only access, row counts | `src/backend/storage/db_connection.py` |
| Tactics summary enrichment | `src/backend/analysis/tactics/enrichment.py` |
| Streaming downloads and GitHub releases | `src/backend/api/download.py`, `src/backend/api/github_releases.py` |
| GUI asset and icon paths | `src/gui/utils/assets.py` |
| External URLs and local paths | `src/gui/utils/links.py` |
| Result labels and tones | `src/gui/utils/result_ui.py` |
| Layout clearing | `src/gui/utils/layout.py` |
| Themed dialogs and launchers | `src/gui/components/dialogs.py` |
| Motif metadata and classification tones | `src/gui/tactics_meta.py` |
| Lazy metric sub-view rendering | `src/gui/views/metrics/lazy_view.py` |
| Board SVG primitives | `src/gui/board/svg_board.py` |
