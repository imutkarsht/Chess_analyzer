"""
Mathematical utility functions for Chess Analyzer win probability and move accuracy calculations.
"""
import math
from typing import Optional, List

def get_win_probability(cp: Optional[int], mate: Optional[int]) -> float:
    """
    Calculates win probability from centipawns or mate score.
    Returns value between 0.0 and 1.0.
    """
    if mate is not None:
        # Mate in X
        if mate > 0:
            return 1.0
        elif mate < 0:
            return 0.0
        else:
            return 0.0

    if cp is None:
        return 0.5
        
    try:
        multiplier = -0.00368208 * cp
        # If multiplier is too large/small, exp will overflow/underflow
        if multiplier > 40: 
            return 0.0 
        if multiplier < -40: 
            return 1.0 
            
        win_percent = 50 + 50 * (2 / (1 + math.exp(multiplier)) - 1)
        return win_percent / 100.0
    except OverflowError:
        return 1.0 if cp > 0 else 0.0

def calculate_move_accuracy(win_prob_before: float, win_prob_after: float) -> float:
    """
    Calculates accuracy of a single move.
    Based on Lichess formula but with stricter decay to match Chess.com better.
    """
    wp_before = win_prob_before * 100.0
    wp_after = win_prob_after * 100.0
    
    diff = wp_before - wp_after
    if diff <= 0:
        return 100.0  # Improvement or equal = perfect accuracy
    
    # Higher decay constant (0.06 vs Lichess 0.04354) to penalize WPL more
    # and bring accuracy closer to Chess.com's scale
    raw = 103.1668 * math.exp(-0.06 * diff) - 3.1669
    
    return max(0.0, min(100.0, raw))

def get_cp(cp: Optional[int], mate: Optional[int]) -> int:
    """Convert score to centipawns, capping mate values."""
    if mate is not None:
        return 2000 if mate > 0 else -2000
    return cp if cp is not None else 0

def calculate_volatility_weights(win_percents: List[float], window_size: int) -> List[float]:
    """
    Calculates volatility weights based on sliding window standard deviation.
    Higher volatility = higher weight (more important positions).
    """
    if len(win_percents) < window_size:
        return [1.0] * len(win_percents)
    
    # Create windows - pad the beginning with copies of the first window
    wp_values = [wp * 100 for wp in win_percents]  # Convert to percentage
    
    windows = []
    # Pad beginning
    first_window = wp_values[:window_size] if len(wp_values) >= window_size else wp_values
    for _ in range(min(window_size - 1, len(wp_values))):
        windows.append(first_window)
    
    # Sliding windows
    for i in range(len(wp_values) - window_size + 1):
        windows.append(wp_values[i:i + window_size])
    
    # Ensure we have exactly the right number of windows
    windows = windows[:len(win_percents)]
    
    # Calculate standard deviation for each window as the weight
    weights = []
    for window in windows:
        weight_val = std_dev(window)
        # Clamp weight between 0.5 and 12 (as per Lichess source)
        weight = max(0.5, min(12.0, weight_val))
        weights.append(weight)
    
    return weights

def weighted_mean(values: List[float], weights: List[float]) -> float:
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
    
    weighted_sum = sum(v * w for v, w in zip(values, weights))
    return weighted_sum / total_weight

def harmonic_mean(values: List[float]) -> float:
    """Calculates harmonic mean, handling zeros gracefully."""
    if not values:
        return 0.0
    
    # Filter out zeros/negatives to avoid division errors
    positive_values = [v for v in values if v > 0]
    if not positive_values:
        return 0.0
    
    reciprocal_sum = sum(1.0 / v for v in positive_values)
    return len(positive_values) / reciprocal_sum

def std_dev(values: List[float]) -> float:
    """Calculates standard deviation."""
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)
