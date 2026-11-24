# Tactics pipeline

Tactics are deterministic. Engine lines and played moves confirm every fact
before it reaches headline statistics. AI coaching only rewrites those facts.

---

## Pipeline

1. `build_contexts()` parses SAN/UCI, boards, clocks, evaluations, and mate
   distances once per game.
2. `detect_candidates()` proposes facts from legal moves, legal-capture SEE,
   escape analysis, and the focused motif detectors.
3. `confirm_facts()` promotes a fact only when the engine line or played reply
   demonstrates it.
4. `resolve_losses()` attributes material loss one reply ahead and separates
   immediate losses from punished losses.
5. `recorders.py` and `state.py` accumulate phase accuracy, clocks, roles,
   losses, and drill-down details.
6. `build_game_tactics_report()` projects the result into the per-game Tactics
   tab.

The same facts feed the offline coach text and the LLM prompt.

## Guardrails

- Never count probable facts in headline statistics.
- Suppress missed tactics on sound, book, and mating moves.
- Sacrifices require the engine-approved move and report net material given.
- Absolute pins always count; relative pins need a tactical consequence.
- Skewers must survive interposition and show a vacate-then-capture line.
- Morphy and Boden mates require real mating geometry.
- Keep the strict trapped-piece rule; broader bad-escape rules confirmed poorly
  on game data.
- `TACTICS_VERSION` is a development cache epoch. When the tactic schema
  changes, clear local tactics summaries instead of accumulating version bumps.

## AI coaching

1. `insight.py` builds the played motifs, newly hanging pieces, created threats,
   numbered main and punishment lines, line captures, second-best comparisons,
   and move mechanics.
2. `explanation.py` selects the dominant story and emits an `ExplanationPlan`
   claim sheet.
3. `GroqService` rewrites the claim sheet. The reply must cite a concrete move
   from the supplied lines and is validated against the allowed SAN and squares.
4. On failure or no network, the deterministic claim text is used.
5. Full-game summaries use `game_report.py`; the claim sheets are persisted with
   the game.

Never send raw game data to an LLM without the fact sheet, and never render an
unvalidated reply.

## Key modules

| Module | Purpose |
| --- | --- |
| `contexts.py` | Parse every ply once into an immutable context |
| `motifs/` | Focused detectors for forks, pins, skewers, discoveries, losses, sacrifices, promotions, and mate patterns |
| `facts.py` | Fact model, merge rules, and serialisation |
| `validation.py` | Engine and game confirmation |
| `attribution.py` | One-reply-ahead loss attribution and deduplication |
| `piece_safety.py`, `see.py` | Legal-capture safety, escape analysis, and SEE |
| `state.py`, `recorders.py` | Per-game accumulation and drill-down details |
| `report.py` | Qt-free projection into the Tactics tab |
| `insight.py`, `explanation.py` | Coach facts and explanation plans |
| `enrichment.py` | Tactics summary enrichment |
