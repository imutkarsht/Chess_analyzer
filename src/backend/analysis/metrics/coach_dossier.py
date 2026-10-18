"""
Coach dossier generation module for AI Chess Coach prompt formatting.
Translates statistical aggregations into a high-signal text dossier.
"""

from __future__ import annotations

import math
from typing import Any


def _header_section(stats: dict[str, Any]) -> list[str]:
    total = stats.get("total", 0)
    win_rate = stats.get("win_rate", 0.0)
    wins = stats.get("wins", 0)
    draws = stats.get("draws", 0)
    losses = stats.get("losses", 0)
    avg_accuracy = stats.get("avg_accuracy", 0.0)
    clean_games_pct = stats.get("clean_games_pct", 0.0)
    clean_games = stats.get("clean_games", 0)

    return [
        f"=== STUDENT CHESS PERFORMANCE DOSSIER (Sample: {total} games) ===",
        f"Overall Win Rate: {win_rate:.1f}% ({wins}W / {draws}D / {losses}L)",
        (
            f"Average Accuracy: {avg_accuracy:.1f}% | "
            f"Clean Games: {clean_games_pct:.1f}% ({clean_games} games without blunders)"
        ),
    ]


def _phase_section(stats: dict[str, Any]) -> list[str]:
    phases = stats.get("phase_stats", {})
    accs = phases.get("accuracies", {})
    blunds = phases.get("blunders", {})
    return [
        "\nPhase Accuracies & Blunder Distribution:",
        f"- Opening: {accs.get('opening', 0.0):.1f}% accuracy | {blunds.get('opening', 0)} blunders",
        (
            f"- Middlegame: {accs.get('middlegame', 0.0):.1f}% accuracy | "
            f"{blunds.get('middlegame', 0)} blunders"
        ),
        f"- Endgame: {accs.get('endgame', 0.0):.1f}% accuracy | {blunds.get('endgame', 0)} blunders",
    ]


def _advantage_section(stats: dict[str, Any]) -> list[str]:
    adv = stats.get("advantage_stats", {})
    hwa = adv.get("had_winning_advantage", 0)
    hlp = adv.get("had_losing_position", 0)
    lines = ["\nAdvantage Conversion & Fighting Spirit:"]

    if hwa > 0:
        lines.append(
            f"- Decisive Lead (+3.0+ pawns) Conversion: {adv.get('conversion_rate', 0.0):.1f}% "
            f"({adv.get('converted_advantage', 0)} wins out of {hwa} games ahead)"
        )
        lines.append(
            f"- Squandered Leads: {adv.get('thrown_losses', 0)} losses, "
            f"{adv.get('squandered_draws', 0)} draws from winning positions"
        )
    else:
        lines.append("- Decisive Leads (+3.0+): None achieved in this sample.")

    if hlp > 0:
        lines.append(
            f"- Deficit (-3.0- pawns) Comeback Rate: {adv.get('comeback_rate', 0.0):.1f}% "
            f"({adv.get('comeback_wins', 0)} wins, {adv.get('comeback_draws', 0)} draws out of {hlp} games behind)"
        )
    else:
        lines.append("- Decisive Deficits (-3.0-): None conceded in this sample.")

    return lines


def _tactics_section(stats: dict[str, Any]) -> list[str]:
    hanging = stats.get("hanging_stats", {})
    by_p = hanging.get("by_piece", {})
    tactics = stats.get("tactical_themes", {})
    top_motifs = sorted(tactics.items(), key=lambda x: x[1], reverse=True)
    motifs_str = ", ".join(f"{k}: {v}" for k, v in top_motifs if v > 0)
    brills = len(stats.get("brilliancies", []))

    return [
        "\nTactical Profile & Board Awareness:",
        (
            f"- Undefended Pieces Dropped: {hanging.get('total_hung', 0)} "
            f"(P: {by_p.get('pawn', 0)}, "
            f"N: {by_p.get('knight', 0)}, "
            f"B: {by_p.get('bishop', 0)}, "
            f"R: {by_p.get('rook', 0)}, "
            f"Q: {by_p.get('queen', 0)})"
        ),
        (
            f"- Opponent Hanging Pieces Punished: {hanging.get('opponent_hanging_captured', 0)} captured "
            f"vs {hanging.get('opponent_hanging_missed', 0)} missed opportunities"
        ),
        f"- Tactical Motifs Executed: {motifs_str if motifs_str else 'None detected'}",
        f"- Brilliant Moves (!!): {brills}",
    ]


def _clock_section(stats: dict[str, Any]) -> list[str]:
    time_s = stats.get("time_stats", {})
    if not time_s.get("has_clock_data"):
        return []

    tt = time_s.get("time_trouble", {})
    formats = time_s.get("formats", {})
    lines = [
        "\nTime Management & Clock Discipline:",
        f"- Overall Average Move Time: {time_s.get('overall_avg_time', 0.0):.1f}s",
    ]

    pp = time_s.get("phase_pace", {})
    lines.append(
        f"- Pace by Phase: Opening {pp.get('opening', {}).get('avg_time', 0.0):.1f}s | "
        f"Middlegame {pp.get('middlegame', {}).get('avg_time', 0.0):.1f}s | "
        f"Endgame {pp.get('endgame', {}).get('avg_time', 0.0):.1f}s"
    )

    for fmt_name in ("Rapid", "Classical"):
        if fmt_name in formats:
            amt = formats[fmt_name].get("avg_move_time", 0.0)
            if 0 < amt < 8.0:
                lines.append(
                    f"- CRITICAL ALERT [RUSHING IN {fmt_name.upper()}]: Student averages only {amt:.1f}s per move in {fmt_name}. "
                    f"They are playing far too fast for a longer game, blitzing out moves impulsively and finishing with substantial unused time on their clock while blundering."
                )

    qp = time_s.get("quality_pace", {})
    blunder_pace = qp.get("blunder", {}).get("avg_time", 0.0)
    if 0 < blunder_pace < 6.0:
        lines.append(
            f"- Hasty Blunders: Blunders were committed in an average of {blunder_pace:.1f}s (impulsive moves without calculating)."
        )

    panic_mult = tt.get("panic_multiplier", 1.0)
    if math.isinf(panic_mult):
        lines.append(
            "- Panic Multiplier in Time Trouble: Extreme (all blunders committed in time trouble)"
        )
    else:
        lines.append(f"- Panic Multiplier in Time Trouble: {panic_mult:.1f}x higher blunder rate")

    lines.append(f"- Losses on Time: {tt.get('total_time_losses', 0)}")
    return lines


def _openings_section(stats: dict[str, Any]) -> list[str]:
    detailed_ops = stats.get("detailed_openings", {})
    if not detailed_ops:
        return []

    lines = ["\nOpening Repertoire Highlights:"]
    sorted_ops = sorted(detailed_ops.values(), key=lambda x: x["total"], reverse=True)
    for op in sorted_ops[:5]:
        lines.append(
            f"- {op['name']} (ECO {op.get('eco', 'N/A')}): "
            f"{op['total']} games, {op['win_rate']:.1f}% win rate, {op.get('avg_acc', 0.0):.1f}% accuracy"
        )
    return lines


def build_coach_dossier(stats: dict[str, Any]) -> str:
    """
    Build a compact, high-signal performance dossier from aggregated stats
    specifically tailored for the AI Chess Coach prompt.
    """
    total = stats.get("total", 0)
    if total == 0:
        return "No analyzed games available for coaching evaluation."

    lines: list[str] = []
    lines.extend(_header_section(stats))
    lines.extend(_phase_section(stats))
    lines.extend(_advantage_section(stats))
    lines.extend(_tactics_section(stats))
    lines.extend(_clock_section(stats))
    lines.extend(_openings_section(stats))

    return "\n".join(lines)
