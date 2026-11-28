"""Stable metadata for the sortable Performance Dashboard cards.

Only chart/AI cards are sortable; the five summary statistic cards are pinned
to the top of the dashboard. Keys are persisted in config, so they must remain
stable even if the display labels change.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardCardSpec:
    key: str
    title: str
    description: str
    icon: str


SORTABLE_CARDS: tuple[DashboardCardSpec, ...] = (
    DashboardCardSpec(
        "accuracy_trend",
        "Accuracy Trend",
        "Accuracy across recent games",
        "chart-line",
    ),
    DashboardCardSpec(
        "phase_performance",
        "Phase Performance",
        "Opening, middlegame, and endgame accuracy",
        "layer-group",
    ),
    DashboardCardSpec(
        "ending_distribution",
        "Ending Distribution",
        "How games finish",
        "flag-checkered",
    ),
    DashboardCardSpec(
        "move_quality",
        "Move Quality Distribution",
        "Classification mix across all moves",
        "star-half-alt",
    ),
    DashboardCardSpec(
        "time_management",
        "Time Management",
        "Clock usage and time pressure",
        "clock",
    ),
    DashboardCardSpec(
        "hanging_pieces",
        "Hanging Pieces",
        "Recurring material errors",
        "exclamation-triangle",
    ),
    DashboardCardSpec(
        "tactical_themes",
        "Tactical Themes",
        "Motifs behind your mistakes",
        "bolt",
    ),
    DashboardCardSpec(
        "advantage_conversion",
        "Advantage Conversion",
        "Converting winning positions",
        "chess-queen",
    ),
    DashboardCardSpec(
        "brilliancy_hall",
        "Brilliancy Hall",
        "Your best tactical finds",
        "gem",
    ),
    DashboardCardSpec(
        "openings",
        "Openings",
        "Results by opening",
        "book-open",
    ),
    DashboardCardSpec(
        "ai_coach",
        "AI Coach",
        "Generated coaching insights",
        "robot",
    ),
)

SORTABLE_BY_KEY = {spec.key: spec for spec in SORTABLE_CARDS}
DEFAULT_CARD_ORDER: tuple[str, ...] = tuple(spec.key for spec in SORTABLE_CARDS)


def normalise_card_order(stored: object) -> list[str]:
    """Return a complete, unique order using the known sortable cards.

    Unknown and duplicate keys are dropped; cards added in a future release are
    appended in registry order so saved preferences never hide a new card.
    """
    if not isinstance(stored, (list, tuple)):
        return list(DEFAULT_CARD_ORDER)

    order = [
        key
        for key in stored
        if isinstance(key, str) and key in SORTABLE_BY_KEY
    ]
    deduped = list(dict.fromkeys(order))
    deduped.extend(key for key in DEFAULT_CARD_ORDER if key not in deduped)
    return deduped
