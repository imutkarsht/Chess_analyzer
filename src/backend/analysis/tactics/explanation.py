"""Turn deterministic move evidence into a compact coaching claim sheet.

The LLM is deliberately kept out of chess reasoning: this module selects the
few facts that actually explain a move, then the offline renderer and the LLM
prompt consume the same claims. Keeping selection here makes the explanation
specific, testable, and useful with no network.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.constants import PROBLEM_CLASSIFICATIONS, SACRIFICIAL_CLASSIFICATIONS

if TYPE_CHECKING:
    from src.backend.analysis.tactics.insight import MoveInsight


@dataclass(frozen=True)
class ExplanationPlan:
    """The minimum set of claims needed to explain one move."""

    kind: str
    verdict: str
    evidence: tuple[str, ...]
    line: str
    better: str
    lesson: str
    confidence: str = "high"


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------


def _prefix(move_number: int, side: str) -> str:
    return f"{move_number}{'.' if side == 'white' else '...'}"


def _move_ref(insight: MoveInsight, san: str) -> str:
    return f"{_prefix(insight.move_number, insight.side)}{san}"


def _wp(value: float | None) -> str:
    return "?" if value is None else f"{value * 100:.0f}%"


def _piece(piece: dict[str, Any] | None) -> str:
    if not piece:
        return "material"
    return f"{piece.get('piece_name', 'piece')} on {piece.get('square', '?')}"


def _biggest(pieces: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not pieces:
        return None
    return max(pieces, key=lambda item: item.get("enemy_see_gain", 0))


def _key_capture(insight: MoveInsight) -> dict[str, Any] | None:
    """The largest piece the player wins inside the stored main line."""
    player = insight.side
    captures = [item for item in insight.main_line_captures if item.get("by") == player]
    if not captures:
        return None
    return max(captures, key=lambda item: item.get("value_cp", 0))


def _alternative_claim(insight: MoveInsight, *, only_when_large: bool = False) -> str | None:
    if not insight.second_best_move_san:
        return None
    if only_when_large and (
        insight.alternative_gap_wp is None or insight.alternative_gap_wp < 0.10
    ):
        return None
    move = _move_ref(insight, insight.second_best_move_san)
    if insight.second_best_eval:
        return f"The second-best move, {move}, was {insight.second_best_eval}."
    return f"The second-best move was {move}."


def _sacrifice_goal(insight: MoveInsight) -> str:
    if insight.line_ends_in_mate or insight.forced_mate:
        return "force mate"
    delta = insight.line_material_delta_cp
    capture = _key_capture(insight)
    if capture and delta is not None and delta >= 500:
        value = capture.get("value_cp", 0)
        if value >= 900:
            return "win the queen"
        if value >= 500:
            return "win a rook"
        if value >= 300:
            return "win a piece"
    if insight.gives_check:
        return "expose the king"
    if delta is not None and delta >= 100:
        return "win material"
    if insight.already_winning:
        return "convert the attack"
    return "keep the initiative"


def _lesson(insight: MoveInsight) -> str:
    if insight.missed_mate:
        return "When you have a forced mate, scan every check before choosing a move."
    if (
        insight.is_actual_sacrifice
        and insight.classification in SACRIFICIAL_CLASSIFICATIONS
    ):
        return (
            "A sacrifice is only strong when the follow-up is forcing; calculate "
            "the checks before giving material."
        )
    if insight.is_only_move:
        return "When only one move works, identify the opponent's threat before moving."
    if insight.allowed_motifs:
        motif = insight.allowed_motifs[0]
        if motif == "fork":
            return "Before moving, check whether the opponent can fork two of your pieces."
        if motif == "pin":
            return "Before moving, check whether an opponent piece can pin you to the king or queen."
        if motif == "skewer":
            return "Before moving, check whether an opponent piece can skewer two of your pieces."
        if motif == "discovered_attack":
            return "Before moving, check what an opponent slider will see once your piece moves."
        if motif == "back_rank":
            return "Before moving, give your king an escape square on the back rank."
    if insight.new_hung_pieces:
        return "After your move, ask which of your pieces is no longer defended."
    return ""


# ---------------------------------------------------------------------------
# Plan builders by move type
# ---------------------------------------------------------------------------


def _missed_mate_plan(insight: MoveInsight) -> ExplanationPlan:
    best = f"{_move_ref(insight, insight.best_move_san)}" if insight.best_move_san else "the mating move"
    evidence: list[str] = []
    if insight.best_line_text:
        evidence.append(f"The mating line was {insight.best_line_text}.")
    if insight.player_mate_before:
        evidence.append(f"You had mate in {insight.player_mate_before} before this move.")
    return ExplanationPlan(
        kind="missed_mate",
        verdict=f"You had a forced mate: {best} kept the win, but {insight.numbered_san} let it go.",
        evidence=tuple(evidence),
        line=insight.best_line_text or insight.main_line_text,
        better=f"Better was {best}.",
        lesson=_lesson(insight),
    )


def _sacrifice_plan(insight: MoveInsight) -> ExplanationPlan:
    offered = insight.offered_piece or _biggest(insight.new_hung_pieces)
    goal = _sacrifice_goal(insight)
    evidence: list[str] = []
    if insight.is_only_move:
        evidence.append("It is the only move that keeps the advantage.")
        alt = _alternative_claim(insight, only_when_large=True)
        if alt:
            evidence.append(alt)
    if insight.main_line_text:
        evidence.append(f"The main line runs {insight.main_line_text}.")
    capture = _key_capture(insight)
    delta = insight.line_material_delta_cp
    if capture and delta is not None and delta >= 500:
        evidence.append(
            f"The point is {capture['san']}, winning the {capture['piece_name']}."
        )
    if insight.already_winning:
        evidence.append(
            "You were already winning, so this is a forcing way to convert rather than a rescue."
        )
    if not evidence:
        evidence.append(f"The evaluation stays at {insight.eval_after} after the sacrifice.")
    return ExplanationPlan(
        kind="sacrifice",
        verdict=(
            f"{insight.numbered_san} is a sound sacrifice: you offer "
            f"{_piece(offered)} to {goal}."
        ),
        evidence=tuple(evidence),
        line=insight.main_line_text,
        better="",
        lesson=_lesson(insight),
    )


def _error_plan(insight: MoveInsight) -> ExplanationPlan:
    new_hung = _biggest(insight.new_hung_pieces)
    mate_in = insight.mate_threat_in
    drop = insight.wp_before - insight.wp_after

    if mate_in is not None:
        verdict = f"{insight.numbered_san} allows the opponent to force mate in {mate_in}."
    elif new_hung is not None:
        verdict = (
            f"{insight.numbered_san} allows the opponent to win your "
            f"{_piece(new_hung)}."
        )
    elif insight.material_loss_cp:
        verdict = (
            f"{insight.numbered_san} allows the opponent to win about "
            f"{insight.material_loss_cp / 100:.1f} pawns."
        )
    elif insight.refutation_san:
        verdict = f"{insight.numbered_san} allows {insight.refutation_text}."
    else:
        verdict = f"{insight.numbered_san} gives the opponent the initiative."

    evidence: list[str] = []
    if insight.created_threats:
        threat = _biggest(insight.created_threats)
        evidence.append(
            f"It does create a threat on {_piece(threat)}, but the opponent's reply is stronger."
        )
    if new_hung is not None:
        state = "undefended" if new_hung.get("is_undefended") else "under-defended"
        evidence.append(f"Your {_piece(new_hung)} is newly {state}.")
    if insight.refutation_text:
        evidence.append(f"The punishment line runs {insight.refutation_text}.")
    if insight.allowed_motifs:
        evidence.append(
            "That line creates a " + ", ".join(insight.allowed_motifs) + "."
        )
    if drop >= 0.03:
        evidence.append(
            f"Your winning chances fell from {_wp(insight.wp_before)} to "
            f"{_wp(insight.wp_after)}."
        )
    if not evidence:
        evidence.append("No reliable continuation was stored for this position.")

    better = ""
    if insight.best_move_san:
        better = f"Better was {_move_ref(insight, insight.best_move_san)}"
        if insight.best_line_text:
            better += f": {insight.best_line_text}."
        else:
            better += "."

    return ExplanationPlan(
        kind="error",
        verdict=verdict,
        evidence=tuple(evidence),
        line=insight.refutation_text or insight.main_line_text,
        better=better,
        lesson=_lesson(insight),
    )


def _only_move_plan(insight: MoveInsight) -> ExplanationPlan:
    evidence: list[str] = []
    if insight.main_line_text:
        evidence.append(f"The main line runs {insight.main_line_text}.")
    alt = _alternative_claim(insight, only_when_large=True)
    if alt:
        evidence.append(alt)
    return ExplanationPlan(
        kind="only_move",
        verdict=f"{insight.numbered_san} is the only move that keeps the position.",
        evidence=tuple(evidence),
        line=insight.main_line_text,
        better="",
        lesson=_lesson(insight),
    )


def _brilliant_plan(insight: MoveInsight) -> ExplanationPlan:
    evidence: list[str] = []
    if insight.main_line_text:
        evidence.append(f"The main line runs {insight.main_line_text}.")
    if insight.created_threats:
        threat = _biggest(insight.created_threats)
        evidence.append(f"It creates a threat on {_piece(threat)}.")
    if insight.is_only_move:
        evidence.append("It is the only move that keeps the advantage.")
    if not evidence:
        evidence.append(f"It keeps the evaluation at {insight.eval_after}.")
    return ExplanationPlan(
        kind="brilliant",
        verdict=f"{insight.numbered_san} is a strong move that keeps the initiative.",
        evidence=tuple(evidence),
        line=insight.main_line_text,
        better="",
        lesson=_lesson(insight),
    )


def _sound_plan(insight: MoveInsight) -> ExplanationPlan:
    if insight.is_double_check:
        verdict = f"{insight.numbered_san} is a double check, so the king must move."
    elif insight.gives_check:
        verdict = f"{insight.numbered_san} keeps the king under pressure with check."
    elif insight.is_capture and insight.captured_piece_name:
        verdict = f"{insight.numbered_san} wins the {insight.captured_piece_name}."
    elif insight.created_threats:
        threat = _biggest(insight.created_threats)
        verdict = f"{insight.numbered_san} creates a threat on {_piece(threat)}."
    elif insight.played_motifs:
        verdict = (
            f"{insight.numbered_san} is a strong move that uses a "
            f"{insight.played_motifs[0].replace('_', ' ')}."
        )
    else:
        verdict = f"{insight.numbered_san} keeps the best evaluation ({insight.eval_after})."

    evidence: list[str] = []
    if insight.main_line_text:
        evidence.append(f"The main line runs {insight.main_line_text}.")
    capture = _key_capture(insight)
    if capture and capture["san"] != insight.san:
        evidence.append(
            f"The line includes {capture['san']}, winning the {capture['piece_name']}."
        )
    alt = _alternative_claim(insight, only_when_large=True)
    if alt:
        evidence.append(alt)
    return ExplanationPlan(
        kind="sound",
        verdict=verdict,
        evidence=tuple(evidence),
        line=insight.main_line_text,
        better="",
        lesson=_lesson(insight),
    )


def _book_plan(insight: MoveInsight) -> ExplanationPlan:
    opening = " ".join(part for part in (insight.eco, insight.opening_name) if part)
    verdict = f"{insight.numbered_san} is a book move"
    verdict += f" from the {opening}." if opening else "."
    evidence = (
        (f"The main line runs {insight.main_line_text}.",)
        if insight.main_line_text
        else ()
    )
    return ExplanationPlan(
        kind="book",
        verdict=verdict,
        evidence=evidence,
        line=insight.main_line_text,
        better="",
        lesson="",
    )


def build_explanation_plan(insight: MoveInsight) -> ExplanationPlan:
    """Select the dominant story for one move."""
    if insight.missed_mate:
        return _missed_mate_plan(insight)
    if insight.is_actual_sacrifice and insight.classification in SACRIFICIAL_CLASSIFICATIONS:
        return _sacrifice_plan(insight)
    if insight.classification in PROBLEM_CLASSIFICATIONS:
        return _error_plan(insight)
    if insight.is_only_move or insight.classification == "Great":
        return _only_move_plan(insight)
    if insight.classification == "Book":
        return _book_plan(insight)
    if insight.classification == "Brilliant":
        return _brilliant_plan(insight)
    return _sound_plan(insight)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def format_plan_offline(plan: ExplanationPlan) -> str:
    """Deterministic coaching note used when no LLM is available."""
    is_error = plan.kind in {"error", "missed_mate"}
    sections: list[tuple[str, str]] = [
        (
            "WHAT WENT WRONG" if is_error else "WHY IT WORKS",
            plan.verdict,
        )
    ]
    if plan.evidence:
        sections.append(
            (
                "THE PUNISHMENT" if is_error else "THE IDEA",
                " ".join(plan.evidence),
            )
        )
    if plan.better:
        sections.append(("BETTER", plan.better))
    if plan.lesson:
        sections.append(("PATTERN", plan.lesson))
    return "\n\n".join(f"{label}\n{text}" for label, text in sections)


def format_plan_for_llm(plan: ExplanationPlan) -> str:
    """Claim sheet handed to the LLM for natural-language rewriting."""
    lines = [
        "CLAIM SHEET - single move",
        "",
        f"VERDICT: {plan.verdict}",
        "EVIDENCE:",
    ]
    if plan.evidence:
        lines.extend(f"- {claim}" for claim in plan.evidence)
    else:
        lines.append("- No additional evidence was stored.")
    lines += [
        f"MAIN LINE: {plan.line or '(no reliable continuation stored)'}",
        f"BETTER: {plan.better or '(not applicable)'}",
        f"PATTERN: {plan.lesson or '(no general pattern needed)'}",
        f"CONFIDENCE: {plan.confidence}",
    ]
    return "\n".join(lines)
