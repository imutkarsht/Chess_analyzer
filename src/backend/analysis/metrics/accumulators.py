"""
Statistical accumulators and aggregation logic for chess games.
Modular sub-accumulators maintain state and produce the final metrics output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    ADVANTAGE_DRILLS,
    ADVANTAGE_KEYS,
    COLORS,
    DRAW_BUCKETS,
    MOTIF_NAMES,
    NON_DRAW_TERM_TYPES,
    PHASES,
    PIECE_NAMES,
    QUALITY_NAMES,
    QUALITY_PACE_KEYS,
    TERM_TYPES,
)
from .models import GameRecord


def pct(num: float | int, denom: float | int) -> float:
    """Calculate percentage, safely returning 0.0 when denominator is zero."""
    return (num / denom * 100.0) if denom else 0.0


@dataclass
class ColorStats:
    """Statistics for a specific player color (White or Black)."""

    wins: int = 0
    draws: int = 0
    losses: int = 0
    total: int = 0
    total_acc: float = 0.0
    acc_count: int = 0
    blunders: int = 0
    pieces_hung: int = 0

    def to_dict(self) -> dict[str, Any]:
        avg_acc = (self.total_acc / self.acc_count) if self.acc_count > 0 else 0.0
        return {
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "total": self.total,
            "total_acc": self.total_acc,
            "acc_count": self.acc_count,
            "blunders": self.blunders,
            "pieces_hung": self.pieces_hung,
            "avg_accuracy": avg_acc,
        }


@dataclass
class FormatStats:
    """Statistics for a specific speed category/format."""

    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    acc_sum: float = 0.0
    acc_count: int = 0
    time_losses: int = 0
    total_time_spent: float = 0.0
    timed_moves: int = 0

    def to_dict(self, name: str) -> dict[str, Any]:
        return {
            "name": name,
            "games": self.games,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "win_rate": pct(self.wins, self.games),
            "avg_accuracy": (self.acc_sum / self.acc_count) if self.acc_count > 0 else 0.0,
            "time_losses": self.time_losses,
            "avg_move_time": (
                (self.total_time_spent / self.timed_moves) if self.timed_moves > 0 else 0.0
            ),
            "timed_moves": self.timed_moves,
        }


@dataclass
class OpeningStats:
    """Detailed statistics for an opening family."""

    name: str
    eco: str = ""
    total: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    as_white: int = 0
    as_black: int = 0
    white_wins: int = 0
    black_wins: int = 0
    total_acc: float = 0.0
    acc_count: int = 0
    variations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "eco": self.eco,
            "total": self.total,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "as_white": self.as_white,
            "as_black": self.as_black,
            "white_wins": self.white_wins,
            "black_wins": self.black_wins,
            "total_acc": self.total_acc,
            "acc_count": self.acc_count,
            "variations": list(self.variations),
            "win_rate": pct(self.wins, self.total),
            "avg_acc": (self.total_acc / self.acc_count) if self.acc_count > 0 else 0.0,
        }


@dataclass
class ClockStats:
    """Clock, move timing, and time trouble statistics."""

    total_timed_moves: int = 0
    total_time_spent: float = 0.0
    phase_time: dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in PHASES})
    phase_moves: dict[str, int] = field(default_factory=lambda: {p: 0 for p in PHASES})
    quality_time: dict[str, float] = field(
        default_factory=lambda: {k: 0.0 for k in QUALITY_PACE_KEYS}
    )
    quality_moves: dict[str, int] = field(default_factory=lambda: {k: 0 for k in QUALITY_PACE_KEYS})
    normal_moves: int = 0
    normal_blunders: int = 0
    trouble_moves: int = 0
    trouble_blunders: int = 0

    def merge(self, cm: dict[str, Any]) -> None:
        """Merge clock metrics from a game's tactical analysis."""
        self.total_timed_moves += cm.get("total_timed_moves", 0)
        self.total_time_spent += cm.get("total_time_spent", 0.0)

        p_time = cm.get("phase_time_spent", {})
        p_moves = cm.get("phase_timed_moves", {})
        for ph in PHASES:
            self.phase_time[ph] += p_time.get(ph, 0.0)
            self.phase_moves[ph] += p_moves.get(ph, 0)

        q_time = cm.get("quality_time_spent", {})
        q_moves = cm.get("quality_timed_moves", {})
        for qk in QUALITY_PACE_KEYS:
            self.quality_time[qk] += q_time.get(qk, 0.0)
            self.quality_moves[qk] += q_moves.get(qk, 0)

        self.normal_moves += cm.get("normal_moves", 0)
        self.normal_blunders += cm.get("normal_blunders", 0)
        self.trouble_moves += cm.get("trouble_moves", 0)
        self.trouble_blunders += cm.get("trouble_blunders", 0)

    def to_dict(self, formats_final: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Produce the finalized time_stats dictionary."""
        phase_pace = {
            ph: {
                "avg_time": (
                    self.phase_time[ph] / self.phase_moves[ph] if self.phase_moves[ph] > 0 else 0.0
                ),
                "moves_count": self.phase_moves[ph],
            }
            for ph in PHASES
        }

        quality_pace = {
            qk: {
                "avg_time": (
                    self.quality_time[qk] / self.quality_moves[qk]
                    if self.quality_moves[qk] > 0
                    else 0.0
                ),
                "moves_count": self.quality_moves[qk],
            }
            for qk in QUALITY_PACE_KEYS
        }

        n_pct = pct(self.normal_blunders, self.normal_moves)
        t_pct = pct(self.trouble_blunders, self.trouble_moves)

        if n_pct > 0:
            panic_mult = t_pct / n_pct
        elif t_pct > 0:
            panic_mult = float("inf")
        else:
            panic_mult = 0.0

        return {
            "has_clock_data": self.total_timed_moves > 0,
            "total_timed_moves": self.total_timed_moves,
            "overall_avg_time": (
                (self.total_time_spent / self.total_timed_moves)
                if self.total_timed_moves > 0
                else 0.0
            ),
            "formats": formats_final,
            "phase_pace": phase_pace,
            "quality_pace": quality_pace,
            "time_trouble": {
                "normal_moves": self.normal_moves,
                "normal_blunders": self.normal_blunders,
                "normal_blunder_pct": n_pct,
                "trouble_moves": self.trouble_moves,
                "trouble_blunders": self.trouble_blunders,
                "trouble_blunder_pct": t_pct,
                "panic_multiplier": panic_mult,
                "total_time_losses": sum(f["time_losses"] for f in formats_final.values()),
            },
        }


@dataclass
class HangingStats:
    """Dropped and punished piece statistics."""

    total_hung: int = 0
    by_piece: dict[str, int] = field(default_factory=lambda: {p: 0 for p in PIECE_NAMES})
    hanging_blunders: int = 0
    opponent_hanging_captured: int = 0
    opponent_hanging_missed: int = 0
    captured_by_piece: dict[str, int] = field(default_factory=lambda: {p: 0 for p in PIECE_NAMES})

    def merge(self, h_metrics: dict[str, Any]) -> int:
        """Merge hanging piece metrics and return total pieces hung in this game."""
        hung = h_metrics.get("total_hung", 0)
        self.total_hung += hung
        self.hanging_blunders += h_metrics.get("hanging_blunders", 0)
        self.opponent_hanging_captured += h_metrics.get("opponent_hanging_captured", 0)
        self.opponent_hanging_missed += h_metrics.get("opponent_hanging_missed", 0)

        for p_type, count in h_metrics.get("by_piece", {}).items():
            if p_type in self.by_piece:
                self.by_piece[p_type] += count

        for p_type, count in h_metrics.get("captured_by_piece", {}).items():
            if p_type in self.captured_by_piece:
                self.captured_by_piece[p_type] += count

        return hung

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_hung": self.total_hung,
            "by_piece": dict(self.by_piece),
            "hanging_blunders": self.hanging_blunders,
            "opponent_hanging_captured": self.opponent_hanging_captured,
            "opponent_hanging_missed": self.opponent_hanging_missed,
            "captured_by_piece": dict(self.captured_by_piece),
        }


@dataclass
class AdvantageStats:
    """Lead conversion, squandering, and comeback statistics."""

    counts: dict[str, int] = field(default_factory=lambda: {k: 0 for k in ADVANTAGE_KEYS})

    def merge(self, adv: dict[str, Any]) -> None:
        for k in ADVANTAGE_KEYS:
            if adv.get(k):
                self.counts[k] += 1

    def to_dict(self) -> dict[str, Any]:
        hwa = self.counts["had_winning_advantage"]
        hlp = self.counts["had_losing_position"]
        out = dict(self.counts)
        out["conversion_rate"] = pct(self.counts["converted_advantage"], hwa)
        out["throw_rate"] = pct(self.counts["thrown_losses"], hwa)
        out["comeback_rate"] = pct(self.counts["comeback_drawn_or_won"], hlp)
        return out


@dataclass
class PhaseStats:
    """Phase-weighted move accuracy and blunders."""

    data: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            p: {"acc_sum": 0.0, "total_moves": 0, "blunders": 0} for p in PHASES
        }
    )

    def record(
        self,
        phase: str,
        acc_val: float | None,
        move_cnt: int,
        blunders: int,
    ) -> None:
        entry = self.data[phase]
        if acc_val is not None:
            weight = move_cnt if move_cnt > 0 else 1
            entry["acc_sum"] += acc_val * weight
            entry["total_moves"] += weight
        entry["blunders"] += blunders

    def to_dict(self) -> dict[str, Any]:
        accuracies: dict[str, float] = {}
        blunders: dict[str, int] = {}
        for phase in PHASES:
            entry = self.data[phase]
            cnt = entry["total_moves"]
            accuracies[phase] = (entry["acc_sum"] / cnt) if cnt > 0 else 0.0
            blunders[phase] = entry["blunders"]

        return {
            "accuracies": accuracies,
            "blunders": blunders,
        }


class StatsAccumulator:
    """Aggregates multiple GameRecords into comprehensive player metrics."""

    def __init__(self) -> None:
        self.total = 0
        self.wins = 0
        self.draws = 0
        self.losses = 0
        self.total_acc = 0.0
        self.acc_count = 0
        self.best_win_rating = 0
        self.clean_games = 0

        self.term_counts: dict[str, int] = {k: 0 for k in TERM_TYPES}
        self.win_term_counts: dict[str, int] = {k: 0 for k in NON_DRAW_TERM_TYPES}
        self.loss_term_counts: dict[str, int] = {k: 0 for k in NON_DRAW_TERM_TYPES}
        self.draw_term_counts: dict[str, int] = {k: 0 for k in DRAW_BUCKETS}

        self.quality_counts: dict[str, int] = {k: 0 for k in QUALITY_NAMES}
        self.accuracy_history: list[float] = []

        self.color_stats: dict[str, ColorStats] = {c: ColorStats() for c in COLORS}
        self.format_stats: dict[str, FormatStats] = {}
        self.detailed_openings: dict[str, OpeningStats] = {}

        self.clock = ClockStats()
        self.hanging = HangingStats()
        self.phase = PhaseStats()
        self.advantage = AdvantageStats()

        self.tactical_themes: dict[str, int] = {m: 0 for m in MOTIF_NAMES}
        self.brilliancies: list[dict[str, Any]] = []

        self.drill_down: dict[str, Any] = {
            "hung_pieces": {"all": [], **{p: [] for p in PIECE_NAMES}},
            "opp_captured": {"all": [], **{p: [] for p in PIECE_NAMES}},
            "tactical_themes": {m: [] for m in MOTIF_NAMES},
            "advantage": {
                "thrown_losses": [],
                "squandered_draws": [],
                "comeback_wins": [],
                "comeback_draws": [],
            },
            "blunders": [],
            "clean_games": [],
            "openings": {},
        }

    def add(self, rec: GameRecord) -> None:
        """Accumulate a single game record into the running statistics."""
        self.total += 1
        c_stat = self.color_stats[rec.user_color]
        c_stat.total += 1

        # 1. Outcomes
        if rec.is_win:
            self.wins += 1
            c_stat.wins += 1
        elif rec.is_draw:
            self.draws += 1
            c_stat.draws += 1
        elif rec.is_loss:
            self.losses += 1
            c_stat.losses += 1

        # 2. Terminations
        self.term_counts[rec.term_type] = self.term_counts.get(rec.term_type, 0) + 1
        if rec.is_draw and rec.draw_type:
            self.draw_term_counts[rec.draw_type] = self.draw_term_counts.get(rec.draw_type, 0) + 1
        elif rec.is_win and rec.term_type in self.win_term_counts:
            self.win_term_counts[rec.term_type] += 1
        elif rec.is_loss and rec.term_type in self.loss_term_counts:
            self.loss_term_counts[rec.term_type] += 1

        # 3. Formats
        if rec.speed not in self.format_stats:
            self.format_stats[rec.speed] = FormatStats()
        f_entry = self.format_stats[rec.speed]
        f_entry.games += 1
        if rec.is_win:
            f_entry.wins += 1
        elif rec.is_draw:
            f_entry.draws += 1
        elif rec.is_loss:
            f_entry.losses += 1

        term_mode_raw = (rec.raw_game.get("termination_mode") or "").strip().lower()
        term_raw = (rec.raw_game.get("termination") or "").lower()
        if rec.is_loss and (
            rec.term_type == "Time" or term_mode_raw == "timeout" or "time" in term_raw
        ):
            f_entry.time_losses += 1

        # 4. Accuracy & Move Quality
        if rec.game_acc > 0:
            self.total_acc += rec.game_acc
            self.acc_count += 1
            c_stat.total_acc += rec.game_acc
            c_stat.acc_count += 1
            self.accuracy_history.append(rec.game_acc)
            f_entry.acc_sum += rec.game_acc
            f_entry.acc_count += 1

        for qk, count in rec.quality_counts.items():
            self.quality_counts[qk] += count

        c_stat.blunders += rec.blunders_count
        if rec.blunders_count == 0:
            self.clean_games += 1
            clean_item = {
                **rec.game_meta,
                "is_game": True,
                "ply": 1,
                "move_number": 1,
                "move_display": "0 Blunders",
                "classification": "Clean Game",
                "description": (
                    f"Accuracy: {rec.game_acc:.1f}% • 0 blunders"
                    if rec.game_acc > 0
                    else "0 blunders"
                ),
                "fen_before": rec.raw_game.get("starting_fen")
                or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            }
            self.drill_down["clean_games"].append(clean_item)

        # 5. Best Win Rating
        if rec.is_win and rec.opp_elo > self.best_win_rating:
            self.best_win_rating = rec.opp_elo

        # 6. Openings
        if rec.opening:
            main_name = rec.opening.split(":")[0].split(",")[0].strip()
            var_name = rec.opening[len(main_name) :].lstrip(":,").strip()

            if main_name not in self.detailed_openings:
                self.detailed_openings[main_name] = OpeningStats(name=main_name, eco=rec.eco)
            d_op = self.detailed_openings[main_name]
            d_op.total += 1
            if not d_op.eco and rec.eco:
                d_op.eco = rec.eco

            if rec.is_win:
                d_op.wins += 1
            elif rec.is_draw:
                d_op.draws += 1
            elif rec.is_loss:
                d_op.losses += 1

            if rec.user_color == "white":
                d_op.as_white += 1
                if rec.is_win:
                    d_op.white_wins += 1
            else:
                d_op.as_black += 1
                if rec.is_win:
                    d_op.black_wins += 1

            if rec.game_acc > 0:
                d_op.total_acc += rec.game_acc
                d_op.acc_count += 1

            if var_name and var_name not in d_op.variations:
                d_op.variations.append(var_name)

            if main_name not in self.drill_down["openings"]:
                self.drill_down["openings"][main_name] = []

            opening_item = {
                **rec.game_meta,
                "is_game": True,
                "ply": 1,
                "move_number": 1,
                "move_display": rec.eco or "Opening",
                "classification": (
                    f"{rec.game_acc:.1f}% Acc" if rec.game_acc > 0 else (rec.eco or "Opening")
                ),
                "description": (
                    f"{rec.opening} • {rec.game_acc:.1f}% Acc" if rec.game_acc > 0 else rec.opening
                ),
                "fen_before": rec.raw_game.get("starting_fen")
                or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            }
            self.drill_down["openings"][main_name].append(opening_item)

        # 7. Tactics Data
        tactics = rec.tactics_data
        if not tactics:
            return

        # Clock metrics
        cm = tactics.get("clock_metrics")
        if cm:
            f_entry.total_time_spent += cm.get("total_time_spent", 0.0)
            f_entry.timed_moves += cm.get("total_timed_moves", 0)
            self.clock.merge(cm)

        # Hanging pieces
        h_metrics = tactics.get("hanging_metrics", {})
        hung_count = self.hanging.merge(h_metrics)
        c_stat.pieces_hung += hung_count

        # Phase stats
        p_acc = tactics.get("phase_accuracies", {})
        p_blund = tactics.get("phase_blunders", {})
        p_counts = tactics.get("phase_move_counts", {})
        for phase in PHASES:
            self.phase.record(
                phase=phase,
                acc_val=p_acc.get(phase),
                move_cnt=p_counts.get(phase, 0),
                blunders=p_blund.get(phase, 0),
            )

        # Advantage stats
        adv = tactics.get("advantage_metrics", {})
        self.advantage.merge(adv)

        # Tactical themes
        for motif, count in tactics.get("tactical_themes", {}).items():
            if motif in self.tactical_themes:
                self.tactical_themes[motif] += count

        # Brilliancies
        for b in tactics.get("brilliancies", []):
            self.brilliancies.append(
                {
                    **rec.game_meta,
                    "san": b.get("san"),
                    "uci": b.get("uci"),
                    "fen_before": b.get("fen_before"),
                    "ply": b.get("ply"),
                    "move_number": b.get("move_number"),
                    "classification": b.get("classification"),
                    "explanation": b.get("explanation"),
                    "opening_name": b.get("opening_name") or rec.game_meta["opening"],
                }
            )

        # Drill-Down items
        for h in tactics.get("hung_pieces_details", []):
            item = {**rec.game_meta, **h}
            self.drill_down["hung_pieces"]["all"].append(item)
            p_name = h.get("piece_name", "").lower()
            if p_name in self.drill_down["hung_pieces"]:
                self.drill_down["hung_pieces"][p_name].append(item)

        for c in tactics.get("opp_captured_details", []):
            item = {**rec.game_meta, **c}
            self.drill_down["opp_captured"]["all"].append(item)
            p_name = c.get("piece_name", "").lower()
            if p_name in self.drill_down["opp_captured"]:
                self.drill_down["opp_captured"][p_name].append(item)

        for tm in tactics.get("tactical_motifs_details", []):
            item = {**rec.game_meta, **tm}
            motif = tm.get("motif", "").lower()
            if motif in self.drill_down["tactical_themes"]:
                self.drill_down["tactical_themes"][motif].append(item)

        for b_item in tactics.get("blunders_details", []):
            self.drill_down["blunders"].append({**rec.game_meta, **b_item})

        # Advantage turning points
        for adv_key, move_key, fallback_san, fallback_class in ADVANTAGE_DRILLS:
            if adv.get(adv_key):
                mv = tactics.get(move_key)
                if mv:
                    self.drill_down["advantage"][adv_key].append({**rec.game_meta, **mv})
                else:
                    self.drill_down["advantage"][adv_key].append(
                        {**rec.game_meta, "san": fallback_san, "classification": fallback_class}
                    )

    def finalize(
        self,
        color_filter: str = "All Colors",
        format_filter: str = "All Formats",
        source_filter: str = "All Sources",
        date_filter: str = "All Time",
    ) -> dict[str, Any]:
        """Produce the complete statistical dictionary for consumers."""
        # Openings summary dicts
        openings: dict[str, int] = {}
        opening_wins: dict[str, int] = {}
        detailed_openings_dict: dict[str, dict[str, Any]] = {}
        for name, op in self.detailed_openings.items():
            openings[name] = op.total
            if op.wins > 0:
                opening_wins[name] = op.wins
            detailed_openings_dict[name] = op.to_dict()

        # Legacy-compatible quality counts (for 4-key cards)
        legacy_quality_counts = {
            "Best": (
                self.quality_counts["Best"]
                + self.quality_counts["Brilliant"]
                + self.quality_counts["Great"]
            ),
            "Inaccuracy": self.quality_counts["Inaccuracy"],
            "Mistake": self.quality_counts["Mistake"],
            "Blunder": self.quality_counts["Blunder"],
        }

        # Formats final
        formats_final = {sp: f.to_dict(sp) for sp, f in self.format_stats.items()}

        return {
            "total": self.total,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": pct(self.wins, self.total),
            "avg_accuracy": (self.total_acc / self.acc_count) if self.acc_count else 0.0,
            "best_win": str(self.best_win_rating) if self.best_win_rating > 0 else "N/A",
            "term_counts": self.term_counts,
            "win_term_counts": self.win_term_counts,
            "loss_term_counts": self.loss_term_counts,
            "draw_term_counts": self.draw_term_counts,
            "time_loss_pct": (
                pct(self.loss_term_counts["Time"], self.losses) if self.losses > 0 else 0.0
            ),
            "quality_counts": legacy_quality_counts,
            "detailed_quality_counts": self.quality_counts,
            "accuracy_history": self.accuracy_history,
            "openings": openings,
            "opening_wins": opening_wins,
            "detailed_openings": detailed_openings_dict,
            "color_stats": {c: self.color_stats[c].to_dict() for c in COLORS},
            "hanging_stats": self.hanging.to_dict(),
            "clean_games": self.clean_games,
            "clean_games_pct": pct(self.clean_games, self.total),
            "phase_stats": self.phase.to_dict(),
            "advantage_stats": self.advantage.to_dict(),
            "brilliancies": self.brilliancies,
            "tactical_themes": self.tactical_themes,
            "drill_down": self.drill_down,
            "time_stats": self.clock.to_dict(formats_final),
            "filter_applied": {
                "color": color_filter,
                "format": format_filter,
                "source": source_filter,
                "date": date_filter,
            },
        }
