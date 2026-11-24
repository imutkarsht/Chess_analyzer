# Runtime flows

Each flow follows the same path: user action -> controller -> worker -> backend
-> signal -> UI.

For the layer rules behind these flows, see [ARCHITECTURE.md](../../ARCHITECTURE.md).

---

## Full game analysis

1. `GameLoadingController.load_game()` accepts a `GameAnalysis` and hands it to
   the analysis page.
2. `AnalysisController.start_analysis()` starts `AnalysisWorker`.
3. `Analyzer.analyze_game()` drives `EngineManager`, reads and writes the
   analysis cache, and converts scores to White's perspective in
   `_process_analysis_results()`.
4. Signals update the board, move list, evaluation graph, result tabs, and
   status bar.
5. The engine is stopped in `finally`; a fresh analysis restarts it.

## Batch analysis

1. History bulk mode pins `GameQuery(batchable_only=True)` and keeps a selection
   set of game IDs.
2. `BatchController` creates a persisted batch and starts one
   `BatchAnalysisWorker`.
3. `BatchAnalysisRunner` walks the queue sequentially and calls the existing
   `Analyzer.analyze_game()` once per game.
4. Queue items store intent and outcome; the game row remains the source of
   truth.
5. `AnalysisCoordinator` blocks conflicting single analyses and pauses live
   sessions while a batch runs.
6. Recovery and resume reconcile from stored analysis status and continue from
   the first unfinished ply.

## Import

1. `LoadGameDialog` hosts the source panels.
2. `ApiWorker` fetches online games; `PgnIndexWorker` indexes PGN headers and
   dropped files off the UI thread.
3. PGN indexing stores header summaries and offsets; it does not fully parse
   every game just to render the picker.
4. One result opens Analysis. A multi-game result becomes a `GameBatch` in the
   History-hosted `GameImportView`.
5. Selected games are parsed and saved as unanalyzed history rows; existing
   analyzed rows are preserved.
6. CSV import and annotated PGN export use dedicated workers.

## AI coaching

1. `CoachCardWidget` requests an explanation for the current move.
2. `ExplainMoveWorker` builds deterministic evidence from
   `backend/analysis/tactics/insight.py`.
3. `backend/analysis/tactics/explanation.py` selects the dominant story and
   emits an `ExplanationPlan` claim sheet.
4. `GroqService` rewrites the claim sheet; the reply is validated against the
   allowed moves and squares.
5. On failure or no network, the deterministic claim text is used.
6. Full-game summaries use `backend/analysis/game_report.py` and are cached and
   persisted with the game.

## Live engine

1. `LiveEngineSession` owns one Stockfish process and the current FEN.
2. `LiveAnalysisWorker` and session signals feed `EngineLinesWidget`.
3. `StatusBarMixin` mirrors the live session state in the status bar.
4. `MainWindow.closeEvent()` shuts down every session.

## Variations

1. A board move, engine-line click, or "show best move" enters `VariationMode`.
2. `VariationMode` mutates the FEN-keyed tree in
   `backend/analysis/variation_tree.py`.
3. `VariationGraph` renders branches; `MoveListPanel` shows saved-tree badges.
4. The tree survives leaving and re-entering variation mode for the session.

---

## Where the code starts

| Flow | Entry points |
| --- | --- |
| Full analysis | `src/gui/app/analysis_controller.py`, `src/workers/analysis/analysis_worker.py`, `src/backend/analysis/analyzer.py` |
| Batch | `src/gui/app/batch_controller.py`, `src/backend/analysis/batch.py`, `src/workers/analysis/batch_analysis_worker.py` |
| Import | `src/gui/dialogs/load_game_dialog.py`, `src/workers/imports/`, `src/gui/import_workspace/` |
| AI coaching | `src/gui/analysis/coach/`, `src/workers/analysis/coach_worker.py`, `src/backend/services/groq_service.py` |
| Live engine | `src/gui/engine_lines/session.py`, `src/gui/engine_lines/widget.py` |
| Variations | `src/gui/analysis/variation/mode.py`, `src/backend/analysis/variation_tree.py` |
