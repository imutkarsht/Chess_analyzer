"""Tests for win probability, accuracy, and aggregation math."""

import pytest

from src.backend.analysis.math_utils import (
    MIN_MOVE_ACCURACY,
    aggregate_accuracy,
    apply_accuracy_floor,
    calculate_move_accuracy,
    calculate_volatility_weights,
    get_cp,
    get_win_probability,
    harmonic_mean,
    std_dev,
    weighted_mean,
)


def test_win_probability_maps_centipawns_and_mate():
    assert abs(get_win_probability(0, None) - 0.5) < 0.01
    assert get_win_probability(500, None) > 0.85
    assert get_win_probability(-500, None) < 0.15
    assert get_win_probability(None, 1) == 1.0
    assert get_win_probability(None, -1) == 0.0
    assert get_win_probability(None, 0) == 0.0
    assert get_win_probability(None, None) == 0.5


@pytest.mark.parametrize(("cp", "expected"), [(50_000, 1.0), (-50_000, 0.0)])
def test_win_probability_handles_extreme_scores(cp, expected):
    assert get_win_probability(cp, None) == expected


def test_calculate_move_accuracy_bounds():
    assert calculate_move_accuracy(0.5, 0.5) == 100.0
    assert calculate_move_accuracy(0.5, 0.6) == 100.0
    assert 85.0 < calculate_move_accuracy(0.6, 0.58) <= 100.0
    assert calculate_move_accuracy(0.8, 0.2) < 20.0
    assert calculate_move_accuracy(1.0, 0.0) == 0.0


def test_apply_accuracy_floor_protects_blunders():
    assert apply_accuracy_floor(0.0) == MIN_MOVE_ACCURACY
    assert apply_accuracy_floor(99.5) == 99.5


@pytest.mark.parametrize(
    ("cp", "mate", "expected"),
    [(None, None, 0), (120, None, 120), (None, 4, 2000), (None, -3, -2000)],
)
def test_get_cp_caps_mate_scores(cp, mate, expected):
    assert get_cp(cp, mate) == expected


def test_volatility_weights_short_sequence_is_neutral():
    assert calculate_volatility_weights([0.5, 0.6], window_size=8) == [1.0, 1.0]


def test_volatility_weights_emphasise_swings():
    flat = calculate_volatility_weights([0.5] * 12, window_size=8)
    volatile = calculate_volatility_weights(
        [0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9],
        window_size=8,
    )

    assert all(weight == 0.5 for weight in flat)
    assert max(volatile) > max(flat)
    assert all(0.5 <= weight <= 12.0 for weight in volatile)


def test_volatility_weights_stay_aligned_with_moves():
    for length in (0, 1, 7, 20):
        win_percents = [0.5 + 0.01 * (i % 7) for i in range(length)]
        assert len(calculate_volatility_weights(win_percents, window_size=8)) == length


def test_volatility_weights_ignore_which_side_is_ahead():
    """Weights describe position sharpness, not who is winning."""
    sequence = [0.2, 0.5, 0.3, 0.8, 0.6, 0.9, 0.4, 0.7, 0.55, 0.65, 0.45, 0.75]
    mirrored = [1.0 - value for value in sequence]

    weights = calculate_volatility_weights(sequence, window_size=4)
    mirror_weights = calculate_volatility_weights(mirrored, window_size=4)

    assert weights == pytest.approx(mirror_weights)


def test_move_accuracy_never_improves_as_more_win_probability_is_lost():
    scores = [calculate_move_accuracy(0.8, after) for after in (0.8, 0.75, 0.7, 0.5, 0.3, 0.0)]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 100.0


def test_aggregate_accuracy_blends_weighted_and_harmonic_means():
    accuracies = [100.0, 90.0, 55.0, 30.0, 85.0, 95.0, 70.0, 60.0, 99.0, 80.0]
    win_percents = [0.5, 0.55, 0.6, 0.45, 0.5, 0.7, 0.65, 0.4, 0.8, 0.75]

    # Pins the blended score; drift here means game and phase accuracy moved.
    assert aggregate_accuracy(accuracies, win_percents) == pytest.approx(71.579339, abs=1e-5)
    assert aggregate_accuracy([], []) == 0.0


def test_weighted_mean_averages_by_weight():
    assert weighted_mean([10.0, 20.0], [1.0, 3.0]) == 17.5
    assert weighted_mean([], []) == 0.0


def test_weighted_mean_zero_weights_fall_back_to_arithmetic():
    assert weighted_mean([10.0, 20.0], [0.0, 0.0]) == 15.0


def test_weighted_mean_truncates_mismatched_lengths():
    assert weighted_mean([10.0, 20.0, 999.0], [1.0, 1.0]) == 15.0


def test_harmonic_mean_ignores_non_positive_values():
    assert harmonic_mean([]) == 0.0
    assert harmonic_mean([0.0, -5.0]) == 0.0
    assert harmonic_mean([100.0, 0.0, 50.0]) == pytest.approx(200.0 / 3.0)


def test_std_dev_of_known_sequence():
    assert std_dev([5.0]) == 0.0
    assert std_dev([2, 4, 4, 4, 5, 5, 7, 9]) == 2.0
