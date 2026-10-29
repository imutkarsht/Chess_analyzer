"""Declarative game-history queries shared by the repo and the history view.

Filtering and ordering used to live in Python over a fully loaded table, which
does not scale past a few hundred games and duplicated the column names in the
UI. A single frozen query object keeps the SQL builder, the page size and the
view state in sync, and makes every filter combination unit-testable without a
database.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# Columns searched by the free-text box. Kept lowercase for LOWER(col) matching.
SEARCH_COLUMNS: tuple[str, ...] = ("white", "black", "event", "opening", "eco", "date")

RESULT_WIN = "win"
RESULT_LOSS = "loss"
RESULT_DRAW = "draw"
_RESULTS = frozenset({RESULT_WIN, RESULT_LOSS, RESULT_DRAW})

SORTS: dict[str, str] = {
    "newest": "timestamp DESC, id DESC",
    "oldest": "timestamp ASC, id DESC",
    "most_moves": "COALESCE(move_count, 0) DESC, timestamp DESC, id DESC",
    "fewest_moves": "COALESCE(move_count, 0) ASC, timestamp DESC, id DESC",
}
DEFAULT_SORT = "newest"


@dataclass(frozen=True)
class GameQuery:
    """One immutable description of "which games, in which order, which page"."""

    search: str = ""
    result: str = ""
    speed: str = ""
    source: str = ""
    sort: str = DEFAULT_SORT
    usernames: tuple[str, ...] = ()
    limit: int = 25
    offset: int = 0

    def with_offset(self, offset: int) -> GameQuery:
        return replace(self, offset=max(0, int(offset)))


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so a search for "50%" is literal."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_filters(query: GameQuery) -> tuple[str, dict[str, object]]:
    """Return the ``WHERE`` fragment (with leading space) and its parameters."""
    clauses: list[str] = []
    params: dict[str, object] = {}

    search = (query.search or "").strip().lower()
    if search:
        params["q"] = f"%{_escape_like(search)}%"
        clauses.append(
            "("
            + " OR ".join(f"LOWER({col}) LIKE :q ESCAPE '\\'" for col in SEARCH_COLUMNS)
            + ")"
        )

    if query.speed:
        clauses.append("LOWER(speed_category) = :speed")
        params["speed"] = query.speed.lower()

    if query.source:
        # Older rows can have a NULL source; they are local files.
        clauses.append("LOWER(COALESCE(source, 'file')) = :source")
        params["source"] = query.source.lower()

    result = (query.result or "").lower()
    if result in _RESULTS:
        if result == RESULT_DRAW:
            clauses.append("result = '1/2-1/2'")
        else:
            usernames = [u.strip().lower() for u in query.usernames if u and u.strip()]
            if not usernames:
                # Win/loss is user-relative; without a known username nothing matches.
                clauses.append("0")
            else:
                for index, username in enumerate(usernames):
                    params[f"user{index}"] = username
                placeholders = ", ".join(f":user{i}" for i in range(len(usernames)))
                win_sql = (
                    f"(result = '1-0' AND LOWER(white) IN ({placeholders})) "
                    f"OR (result = '0-1' AND LOWER(black) IN ({placeholders}))"
                )
                loss_sql = (
                    f"(result = '0-1' AND LOWER(white) IN ({placeholders})) "
                    f"OR (result = '1-0' AND LOWER(black) IN ({placeholders}))"
                )
                clauses.append(f"({win_sql if result == RESULT_WIN else loss_sql})")

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def build_order_by(query: GameQuery) -> str:
    """Whitelisted ORDER BY clause; never interpolates user text."""
    return SORTS.get((query.sort or "").strip().lower(), SORTS[DEFAULT_SORT])
