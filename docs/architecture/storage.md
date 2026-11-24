# Storage

SQLite is the system of record for games, analysis, batches, and caches. JSON
settings and OS-keychain credentials sit outside it. The database lives in the
OS user-data directory, never in the repository.

---

## Rules

- Repositories persist data. Domain services compute classifications, tactics,
  and termination.
- `GAME_COLUMNS` is the single column specification. DDL, INSERT statements, and
  row dictionaries derive from it.
- `db_connection.py` owns connections, pragmas, commits, and rollbacks.
- Models own their serialisation through `to_dict()` and `from_dict()`.
- `GameHistoryManager` is the facade over focused repositories.
- `AnalysisBatchRepo` stores the queue intent and outcome; the game row is the
  source of truth.
- `analysis_status` is a denormalised column so History can filter by status
  without parsing summary JSON.

## History and paging

`HistoryView` builds a `GameQuery` from the filter bar. `GamesRepo` applies the
filters in SQL and returns one page. After rendering, an idle timer prefetches
the next page. `PaginationBar` and `GameListWidget` share the paging state.

Bulk selection lives in `HistoryView`; search or filter changes clear it, while
paging and sorting preserve it.

## Termination

`detect_termination()` checks, in order:

1. physical board state,
2. explicit PGN termination headers,
3. zero-clock fallbacks,
4. the game result.

PGN `Opening` and `ECO` headers are the canonical opening source. API and local
book values only fill missing metadata. History rows use the recomputed
termination description so they agree with the analysis panel.

`compute_clock_times()` infers `0:00` for the side to move at a terminal
`timeout` or `timeout_insufficient` position, because PGNs omit the flag-fall
clock. `metrics/termination.py` only projects the canonical mode into the
dashboard's Checkmate/Resignation/Time/Abandon/Draw buckets.

## Migrations

`migrations.py` owns schema creation, versioning, backfills, and indexes. Add a
column through a migration, update `GAME_COLUMNS`, and keep call sites free of
schema-version branches.

## Key modules

| Module | Purpose |
| --- | --- |
| `db_connection.py` | Connection context manager and performance pragmas |
| `schema_constants.py` | Column specs and shared SQL |
| `migrations.py` | Schema creation, versioning, backfills, indexes |
| `models.py` | Domain dataclasses and serialisation |
| `games_repo.py` | Game persistence, querying, hydration, export iteration |
| `game_query.py` | Declarative history queries and filters |
| `game_history.py` | Storage facade over games, caches, and the batch queue |
| `analysis_batch_repo.py` | Persisted batch queue, outcomes, elapsed time, reorder |
| `pgn_parser.py` | PGN parsing, header indexing, and move-less records |
| `annotated_pgn.py` | Annotated PGN export with move-identity checks |
| `backup.py` | Validated backup and restore with a safety copy |
| `cache.py` | Position-level analysis cache |
