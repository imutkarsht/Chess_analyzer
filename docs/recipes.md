# Recipes

Step-by-step changes for common tasks. For patterns, see
[conventions.md](conventions.md); for layer edges, see
[ARCHITECTURE.md](../ARCHITECTURE.md).

---

## Add a page

1. Create the view in `src/gui/views/`; put sub-widgets in a matching
   subpackage.
2. Add a navigation entry in `src/gui/components/layout/sidebar.py`.
3. Add the page to `MainWindow.setup_ui()` and `switch_page()`.
4. Add a tour key if the page is part of the tour.
5. Add a `pytest-qt` test in `tests/gui/`.

## Add a setting

1. Add a `SettingSpec` to `src/config/settings_schema.py` with a default, type,
   validation, and `apply="live"` when it should apply immediately.
2. Add a typed `ConfigManager` property when code reads the value directly.
3. Add the control to the matching card in `src/gui/views/settings/` using
   `SettingsForm` and `SettingsBinder`.
4. Handle the live-apply branch in `SettingsView` and `MainWindow`.
5. Test persistence and the live branch.

## Add a shared component

1. Put it in the right `src/gui/components/<group>/` subpackage.
2. Export it from `src/gui/components/__init__.py`.
3. Generate its look from `Styles` or the QSS template; do not add static
   widget-local QSS or hex colours.
4. Restyle it on theme and accent changes if it paints data.
5. Add a `pytest-qt` test and use it through the facade.

## Add a tactic motif

1. Add the value to `TacticalTheme` in `tactics/constants.py`.
2. Add a detector under `tactics/motifs/` and register it in
   `motifs/detection.py`.
3. Add a confirmation rule in `tactics/validation.py` when the motif needs an
   engine or game sequence.
4. Add its label, icon, description, and colour to `src/gui/tactics_meta.py`.
5. Clear local tactics summaries and run the tactics regression tests and the
   full suite.

## Add an analysis feature

1. Compute the domain facts in `src/backend/analysis/`.
2. Extend `MoveAnalysis` or `GameAnalysis` with serialisation on the model.
3. If persisted, update `GAME_COLUMNS` and add a migration.
4. Surface the result through signals from `AnalysisWorker` or `Analyzer`.
5. Render it in the owning tab under `src/gui/analysis/` with existing
   components.

## Add an AI fact or provider behaviour

1. Add the deterministic fact in `tactics/insight.py` or `game_report.py`.
2. Format it in `metrics/coach_dossier.py`.
3. Validate the LLM reply against it in `GroqService`.
4. Keep the offline fallback text in sync.

## Add an import source

1. Add a client under `src/backend/api/` extending `BaseChessAPI`.
2. Add a panel under `src/gui/dialogs/load_game/` and wire it into
   `LoadGameDialog`.
3. Run requests through `ApiWorker`; normalise results to `GameInfo` or
   `GameAnalysis`.
4. Respect `import_limits.py` and cache through the storage repositories.
5. Mock the HTTP client in tests.

## Add a metrics card

1. Subclass `MetricCard` in `src/gui/views/metrics/`.
2. Register it in `card_registry.py` with a stable key.
3. Use `new_content()`, `clear_content()`, and `show_empty()` with the shared
   components.
4. Compute the numbers in `src/backend/analysis/metrics/`.
5. Add a GUI test for the card lifecycle.

## Add a test

- Backend tests go in `tests/backend/` with fake engines and HTTP clients.
- GUI tests go in `tests/gui/` with `pytest-qt`; run workers synchronously.
- Architecture guards go in `tests/architecture/`.
- Use `tmp_path`; never touch real user data.
- Do not use sleeps, Qt wait loops, or real network calls.

---

## Task index

| I want to change... | Go to |
| --- | --- |
| Controller lifecycle | `src/gui/app/controller.py` |
| Single-game analysis | `src/gui/app/analysis_controller.py` |
| Batch queue | `src/gui/app/batch_controller.py` |
| Game loading and ingestion | `src/gui/app/game_loading_controller.py` |
| Move classification thresholds | `src/backend/analysis/move_classifier.py` |
| Accuracy and win-probability maths | `src/backend/analysis/math_utils.py` |
| Engine options, path, lifecycle | `src/backend/analysis/engine.py` |
| AI coach facts and prompts | `src/backend/analysis/tactics/insight.py`, `src/backend/services/groq_service.py` |
| Coach request lifecycle | `src/gui/analysis/coach/panel.py` |
| Full-game AI summary | `src/backend/analysis/game_report.py`, `src/gui/analysis/coach/summary.py` |
| Metrics calculations | `src/backend/analysis/metrics/` |
| Metrics dashboard layout | `src/gui/views/metrics/`, `src/gui/views/metrics/card_registry.py` |
| History paging and filters | `src/gui/views/history_view.py`, `src/backend/storage/game_query.py` |
| Settings defaults | `src/config/settings_schema.py` |
| Theme and accent application | `src/gui/theme/manager.py`, `src/gui/main_window/theme_mixin.py` |
| Database schema and migrations | `src/backend/storage/schema_constants.py`, `src/backend/storage/migrations.py` |
| Backup and restore | `src/backend/storage/backup.py`, `src/gui/views/settings/backup_settings.py` |
| Shortcuts | `src/gui/utils/shortcut_manager.py` |
