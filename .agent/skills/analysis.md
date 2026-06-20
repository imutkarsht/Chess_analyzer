# Skill: Chess Analysis Engine

## Purpose
Manages Stockfish UCI integration, position evaluation, move classification, and game accuracy calculation. This is the core computational subsystem.

---

## Relevant Files
| File | Role |
|---|---|
| `src/backend/analysis/engine.py` | `EngineManager` — Stockfish lifecycle |
| `src/backend/analysis/analyzer.py` | `Analyzer` — full game analysis orchestrator |
| `src/backend/analysis/move_classifier.py` | `classify_move()` — Brilliant/Best/Blunder/etc. |
| `src/backend/analysis/math_utils.py` | Win probability, accuracy, volatility weights |
| `src/backend/analysis/book.py` | `BookManager` — opening name lookup |
| `src/backend/storage/cache.py` | `AnalysisCache` — depth-aware SQLite cache |

---

## Important APIs

### EngineManager
```python
em = EngineManager(engine_path: str, config_manager=None)
em.start_engine()                          # Must call before analyze_position()
em.stop_engine()                           # Called in Analyzer.analyze_game() finally block
em.analyze_position(board, time_limit, depth, multi_pv)  # Returns InfoDict or list
em.apply_settings(threads, hash_mb)        # Hot-applies to running engine
em.set_chess960_mode(enabled: bool)        # Before Chess960 analysis
```

### Analyzer
```python
analyzer = Analyzer(engine_manager)
analyzer.analyze_game(game_analysis, callback=None)
# callback(current_move_index: int, total_moves: int)
```

### classify_move
```python
classify_move(move: MoveAnalysis, wpl: float, side: str, multi_pvs: List[Dict])
# Modifies move.classification and move.explanation in-place
# wpl = Win Probability Loss (0.0–1.0)
# side = "white" or "black"
```

### math_utils
```python
get_win_probability(cp: Optional[int], mate: Optional[int]) -> float  # 0.0–1.0
calculate_move_accuracy(wp_before: float, wp_after: float) -> float   # 0–100
get_cp(cp, mate) -> int   # Converts to centipawns (mate = ±2000)
calculate_volatility_weights(win_percents, window_size) -> List[float]
weighted_mean(values, weights) -> float
harmonic_mean(values) -> float
```

---

## Key Assumptions
- Engine must be **started before** and **stopped after** each analysis. `analyze_game()` handles this in its try/finally.
- `EngineManager.analyze_position()` returns either a single `chess.engine.InfoDict` or a `list` of them (for multi-PV). Always normalize to list.
- Score from engine is **relative to side-to-move**. Flip sign for Black's turn before storing.
- Cache key = `SHA256(fen + "|multipv:" + str(multi_pv))`. Depth is stored separately as a quality guard.

---

## Move Classification Priority (in order)
1. Delivered checkmate → **Best**
2. Position after is ≥99% winning → **Best**
3. Move matches engine's top choice:
   - Multi-PV gap >40% + position improved + not already winning → **Brilliant**
   - Multi-PV gap >15% → **Great**
   - Otherwise → **Best**
4. Had forced mate, lost it → **Miss**
5. Was >80% winning, dropped to <60% → **Miss**
6. Was >70% winning, WPL >20% → **Miss**
7. WPL thresholds: ≥20% → **Blunder**, ≥10% → **Mistake**, ≥5% → **Inaccuracy**, ≥2% → **Good**, <2% → **Excellent**

---

## Accuracy Algorithm (Lichess-Derived)
```
Per-move accuracy = 103.1668 * exp(-0.05 * win_percent_loss) - 3.1669
Minimums: book/checkmate/mating moves = 100%, Best/Great moves ≥ 80%, all moves ≥ 10%
Final accuracy = avg(volatility_weighted_mean, harmonic_mean) of per-move accuracies
```

---

## Common Pitfalls
- **Forgetting to flip score for Black**: After `analyze_position()`, if `not is_white_turn`, negate `cp` and `mate` before storing.
- **Final position score**: The last move's `eval_after` needs special handling — the board must be advanced past the last move before calling the engine again.
- **Cache invalidation**: Changing `multi_pv` generates a different cache key. Changing depth does not (it only updates if new depth > cached depth).
- **Chess960 castling**: Set `UCI_Chess960` mode before analysis. FEN-based detection is needed when Variant header is absent.
- **Engine not started**: `analyze_position()` raises `RuntimeError` if engine is not running. `start_engine()` is safe to call redundantly (guarded by `if not self.engine`).

---

## Testing Approach
- `tests/backend/` — unit tests for `Analyzer`, `PGNParser`, `AnalysisCache`
- Use `pytest-mock` to mock `EngineManager.analyze_position()` — avoid requiring a real Stockfish binary in CI.
- Test `classify_move()` in isolation by constructing `MoveAnalysis` objects with known `win_chance_before/after` and `uci/best_move` fields.

---

## Extension Guidelines
- To add a new classification tier (e.g., "Excellent+"), add it to `classify_move()` priority chain, add a color in `Styles`, and add count tracking in `summary_counts` in `Analyzer._analyze_positions()`.
- To support a new engine (e.g., Leela), subclass or replace `EngineManager`. The UCI protocol is standardized — the main risk is option naming differences.
