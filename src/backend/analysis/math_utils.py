"""Win-probability, move-accuracy, and aggregation math.

A move is judged by how far it moved the player's win probability: small drops
are harmless, large drops are blunders. Because a flat average hides blunders
while a harmonic mean over-reacts to a single one, a game score blends both,
with positions weighted by how volatile they were.

The metric follows the win-probability-loss approach popularised by online
chess platforms (see ``CREDITS.md``); this implementation is original.
"""

import math
import statistics

from src.constants import MIN_MOVE_ACCURACY

# Slope of the logistic mapping a centipawn score to a win probability. A
# one-pawn edge lands near 59%, a queen edge near 96%.
_WIN_PROB_SLOPE = 0.00368208

# Exponential curve turning a win-probability-loss percentage into a per-move
# accuracy. Decay is tuned so a full point swing scores near zero while a
# minor slip still scores highly.
_ACCURACY_CURVE_SCALE = 103.1668
_ACCURACY_CURVE_DECAY = 0.06
_ACCURACY_CURVE_OFFSET = 3.1669

# Volatility weights are clamped so neither a dead-flat stretch nor a chaotic
# one can dominate the game average.
_MIN_VOLATILITY_WEIGHT = 0.5
_MAX_VOLATILITY_WEIGHT = 12.0


def apply_accuracy_floor(accuracy: float) -> float:
    """Clamp a per-move accuracy to MIN_MOVE_ACCURACY."""
    return max(accuracy, MIN_MOVE_ACCURACY)


def get_win_probability(cp: int | None, mate: int | None) -> float:
    """
    Win probability (0.0-1.0) for the side the score favours.

    ``cp`` and ``mate`` are White-perspective scores: positive means White is
    better, so the result is the chance White wins (and ``1 - result`` is
    Black's).
    """
    if mate is not None:
        return 1.0 if mate > 0 else 0.0

    if cp is None:
        return 0.5

    exponent = -_WIN_PROB_SLOPE * cp
    # Outside this range exp() is numerically indistinguishable from 0/inf and
    # the logistic has already saturated.
    if exponent > 40:
        return 0.0
    if exponent < -40:
        return 1.0
    return 1.0 / (1.0 + math.exp(exponent))


def calculate_move_accuracy(win_prob_before: float, win_prob_after: float) -> float:
    """
    Accuracy (0-100) for one move, from the mover's win-probability drop.

    Both inputs are from the mover's point of view: improving or holding the
    evaluation scores a perfect 100, and the score decays as the drop grows.
    """
    loss = (win_prob_before - win_prob_after) * 100.0
    if loss <= 0:
        return 100.0

    raw = _ACCURACY_CURVE_SCALE * math.exp(-_ACCURACY_CURVE_DECAY * loss) - _ACCURACY_CURVE_OFFSET
    return min(100.0, max(0.0, raw))


def get_cp(cp: int | None, mate: int | None) -> int:
    """Convert score to centipawns, capping mate values."""
    if mate is not None:
        return 2000 if mate > 0 else -2000
    return cp if cp is not None else 0


def calculate_volatility_weights(win_percents: list[float], window_size: int) -> list[float]:
    """Weight each move by how volatile the position around it was.

    Sharp positions reveal more about a player's strength than quiet ones, so
    each move is weighted by the standard deviation of the win percentage over
    a trailing window of ``window_size`` moves. Moves before the first full
    window exists share the opening window's weight, which keeps the weight
    list aligned one-to-one with the move list.

    Returns ``1.0`` for every move when there are fewer moves than a window.
    """
    if not win_percents:
        return []
    if len(win_percents) < window_size:
        return [1.0] * len(win_percents)

    window_size = max(1, window_size)
    percents = [wp * 100.0 for wp in win_percents]

    opening_weight = _clamp_weight(std_dev(percents[:window_size]))
    weights = [opening_weight] * (window_size - 1)
    last_start = len(percents) - window_size
    weights.extend(
        _clamp_weight(std_dev(percents[start : start + window_size]))
        for start in range(last_start + 1)
    )
    return weights


def _clamp_weight(weight: float) -> float:
    return min(_MAX_VOLATILITY_WEIGHT, max(_MIN_VOLATILITY_WEIGHT, weight))


def aggregate_accuracy(accuracies: list[float], win_percents: list[float]) -> float:
    """Combine per-move accuracies into one score for a game or a phase.

    The result is the mean of a volatility-weighted average and a harmonic
    mean. Per-move values are floored first: without that floor a single
    blunder drags the harmonic mean towards zero and makes a solid game look
    catastrophic.
    """
    if not accuracies:
        return 0.0
    if len(accuracies) == 1:
        return accuracies[0]

    floored = [apply_accuracy_floor(accuracy) for accuracy in accuracies]
    window_size = max(2, min(8, len(floored) // 10))
    weights = calculate_volatility_weights(win_percents, window_size)

    weighted = weighted_mean(floored, weights)
    harmonic = harmonic_mean(floored)
    return (weighted + harmonic) / 2.0


def weighted_mean(values: list[float], weights: list[float]) -> float:
    """Calculates weighted arithmetic mean."""
    if not values or not weights:
        return 0.0

    # Ensure same length
    min_len = min(len(values), len(weights))
    values = values[:min_len]
    weights = weights[:min_len]

    total_weight = sum(weights)
    if total_weight == 0:
        return sum(values) / len(values) if values else 0.0

    weighted_sum = sum(v * w for v, w in zip(values, weights, strict=True))
    return weighted_sum / total_weight


def harmonic_mean(values: list[float]) -> float:
    """Calculates harmonic mean, handling zeros gracefully."""
    if not values:
        return 0.0

    # Filter out zeros/negatives to avoid division errors
    positive_values = [v for v in values if v > 0]
    if not positive_values:
        return 0.0

    reciprocal_sum = sum(1.0 / v for v in positive_values)
    return len(positive_values) / reciprocal_sum


def std_dev(values: list[float]) -> float:
    """Calculates population standard deviation."""
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)
