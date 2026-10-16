"""
Worker threads for metrics calculations and AI insights.
"""

from __future__ import annotations

import json
import re
import time

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.tactics import analyze_game_tactics
from src.backend.storage.pgn_parser import PGNParser
from src.utils.logger import logger


class InsightWorker(QThread):
    """Worker thread for generating AI insights."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, service, stats_text: str):
        super().__init__()
        self.service = service
        self.stats_text = stats_text

    def run(self):
        logger.info("InsightWorker: generating coach insights...")
        try:
            insight = self.service.generate_coach_insights(self.stats_text)
            logger.info("InsightWorker: coach insights generated successfully")
            self.finished.emit(insight)
        except Exception as e:
            logger.error("InsightWorker failed: %s", e, exc_info=True)
            self.error.emit(str(e))


class StatsWorker(QThread):
    """Worker thread for calculating filtered game statistics."""

    finished = pyqtSignal(dict)

    def __init__(
        self,
        games: list[dict],
        usernames: list[str],
        color_filter: str = "All Colors",
        format_filter: str = "All Formats",
        source_filter: str = "All Sources",
        date_filter: str = "All Time",
    ):
        super().__init__()
        self.games = games
        self.usernames = usernames
        self.color_filter = color_filter
        self.format_filter = format_filter
        self.source_filter = source_filter
        self.date_filter = date_filter

    def run(self):
        logger.debug(
            "StatsWorker: calculating stats for %d total games (filters: %s, %s, %s, %s)",
            len(self.games),
            self.color_filter,
            self.format_filter,
            self.source_filter,
            self.date_filter,
        )
        try:
            stats = self._calculate_stats()
            logger.debug(
                "StatsWorker: stats calculated successfully (%d games matched)",
                stats.get("total", 0),
            )
            self.finished.emit(stats)
        except Exception as e:
            logger.error("StatsWorker failed to calculate stats: %s", e, exc_info=True)
            self.finished.emit({})

    def _get_user_color(self, game: dict) -> str:
        """Returns 'white' or 'black' based on which player matches usernames."""
        white = (game.get("white") or "").lower()
        if white in [u.lower() for u in self.usernames]:
            return "white"
        return "black"

    def _matches_filters(self, game: dict, user_color: str) -> bool:
        """Determines if a game matches the user-selected filter criteria."""
        # 1. Color filter
        if self.color_filter == "White" and user_color != "white":
            return False
        if self.color_filter == "Black" and user_color != "black":
            return False

        # 2. Format / Time Control filter
        is_960 = bool(game.get("chess960", 0))
        if self.format_filter == "Freestyle (Chess960)":
            if not is_960:
                return False
        else:
            if is_960 and self.format_filter != "All Formats":
                return False

            if self.format_filter != "All Formats":
                speed = (game.get("speed_category") or "").strip()
                if not speed:
                    speed = PGNParser._detect_speed_category(
                        game.get("time_control"), game.get("event")
                    )
                if speed.lower() != self.format_filter.lower():
                    return False

        # 3. Source filter
        if self.source_filter != "All Sources":
            src = (game.get("source") or "file").lower()
            target = self.source_filter.lower()
            if "chess" in target and "lichess" not in target:
                # Targeting Chess.com (not Lichess)
                if "lichess" in src or not (
                    "chesscom" in src or "chess.com" in src or src == "chess"
                ):
                    return False
            elif "lichess" in target:
                if "lichess" not in src:
                    return False
            elif "file" in target and src not in ("file", "pgn", "local", "text"):
                return False

        # 4. Date Range filter
        if self.date_filter != "All Time":
            now = time.time()
            ts = game.get("timestamp")
            if ts:
                try:
                    ts_val = float(ts)
                    if self.date_filter == "Last 30 Days" and (now - ts_val) > 30 * 86400:
                        return False
                    if self.date_filter == "Last 90 Days" and (now - ts_val) > 90 * 86400:
                        return False
                    if (
                        self.date_filter == "This Year"
                        and time.localtime(ts_val).tm_year != time.localtime(now).tm_year
                    ):
                        return False
                except (ValueError, TypeError):
                    pass
            else:
                date_str = str(game.get("date") or "")
                # Format: YYYY.MM.DD
                match = re.match(r"^(\d{4})", date_str)
                if (
                    match
                    and self.date_filter == "This Year"
                    and int(match.group(1)) != time.localtime(now).tm_year
                ):
                    return False

        return True

    def _calculate_stats(self) -> dict:
        """Calculate comprehensive game statistics over filtered games."""
        filtered_games = []
        for g in self.games:
            user_color = self._get_user_color(g)
            if self._matches_filters(g, user_color):
                filtered_games.append((g, user_color))

        total = len(filtered_games)
        wins = draws = losses = 0
        total_acc = acc_count = best_win_rating = 0

        term_counts = {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandon": 0, "Draw": 0}
        quality_counts = {
            "Brilliant": 0,
            "Great": 0,
            "Best": 0,
            "Excellent": 0,
            "Good": 0,
            "Inaccuracy": 0,
            "Mistake": 0,
            "Blunder": 0,
            "Miss": 0,
            "Book": 0,
        }
        accuracy_history = []
        openings: dict[str, int] = {}
        opening_wins: dict[str, int] = {}

        color_stats = {
            "white": {
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "total": 0,
                "total_acc": 0.0,
                "acc_count": 0,
                "blunders": 0,
                "pieces_hung": 0,
            },
            "black": {
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "total": 0,
                "total_acc": 0.0,
                "acc_count": 0,
                "blunders": 0,
                "pieces_hung": 0,
            },
        }

        hanging_stats = {
            "total_hung": 0,
            "by_piece": {"pawn": 0, "knight": 0, "bishop": 0, "rook": 0, "queen": 0},
            "hanging_blunders": 0,
            "opponent_hanging_captured": 0,
            "opponent_hanging_missed": 0,
        }

        phase_stats = {
            "opening": {"acc_sum": 0.0, "acc_count": 0, "blunders": 0},
            "middlegame": {"acc_sum": 0.0, "acc_count": 0, "blunders": 0},
            "endgame": {"acc_sum": 0.0, "acc_count": 0, "blunders": 0},
        }

        advantage_stats = {
            "had_winning_advantage": 0,
            "converted_advantage": 0,
            "choked_advantage": 0,
            "had_losing_position": 0,
            "comeback_drawn_or_won": 0,
        }

        brilliancies: list[dict] = []

        for game, user_color in filtered_games:
            res = game.get("result", "*")
            color_stats[user_color]["total"] += 1

            # 1. Result
            is_win = False
            if res == "1-0":
                if user_color == "white":
                    wins += 1
                    is_win = True
                    color_stats["white"]["wins"] += 1
                else:
                    losses += 1
                    color_stats["black"]["losses"] += 1
            elif res == "0-1":
                if user_color == "black":
                    wins += 1
                    is_win = True
                    color_stats["black"]["wins"] += 1
                else:
                    losses += 1
                    color_stats["white"]["losses"] += 1
            else:
                draws += 1
                color_stats[user_color]["draws"] += 1

            # 2. Termination
            term = (game.get("termination") or "").lower()
            if res == "1/2-1/2":
                term_counts["Draw"] += 1
            elif "time" in term:
                term_counts["Time"] += 1
            elif "resign" in term:
                term_counts["Resignation"] += 1
            elif "abandon" in term:
                term_counts["Abandon"] += 1
            elif "mate" in term:
                term_counts["Checkmate"] += 1
            else:
                pgn = game.get("pgn", "")
                if "#" in pgn:
                    term_counts["Checkmate"] += 1
                else:
                    term_counts["Resignation"] += 1

            # 3. Accuracy & Move Quality
            game_acc = 0.0
            tactics_data = None

            if game.get("summary_json"):
                try:
                    summary = json.loads(game["summary_json"])
                    s_data = summary.get(user_color, {})

                    acc = s_data.get("accuracy", 0.0)
                    if acc > 0:
                        total_acc += acc
                        acc_count += 1
                        game_acc = acc
                        color_stats[user_color]["total_acc"] += acc
                        color_stats[user_color]["acc_count"] += 1

                    for qk in quality_counts:
                        quality_counts[qk] += s_data.get(qk, 0)

                    color_stats[user_color]["blunders"] += s_data.get("Blunder", 0)
                    tactics_data = s_data.get("tactics")
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    pass

            if game_acc > 0:
                accuracy_history.append(game_acc)

            # 4. Tactical analysis fallback if not cached in summary
            if not tactics_data and game.get("moves_json"):
                try:
                    moves_data = json.loads(game["moves_json"])
                    tactics_data = analyze_game_tactics(moves_data, user_color, res)
                except Exception:
                    pass

            # 5. Aggregate tactical and phase stats
            if tactics_data:
                h_metrics = tactics_data.get("hanging_metrics", {})
                hanging_stats["total_hung"] += h_metrics.get("total_hung", 0)
                color_stats[user_color]["pieces_hung"] += h_metrics.get("total_hung", 0)
                hanging_stats["hanging_blunders"] += h_metrics.get("hanging_blunders", 0)
                hanging_stats["opponent_hanging_captured"] += h_metrics.get(
                    "opponent_hanging_captured", 0
                )
                hanging_stats["opponent_hanging_missed"] += h_metrics.get(
                    "opponent_hanging_missed", 0
                )

                for p_type, count in h_metrics.get("by_piece", {}).items():
                    if p_type in hanging_stats["by_piece"]:
                        hanging_stats["by_piece"][p_type] += count

                # Phase stats
                p_acc = tactics_data.get("phase_accuracies", {})
                p_blund = tactics_data.get("phase_blunders", {})
                for phase in ("opening", "middlegame", "endgame"):
                    acc_val = p_acc.get(phase)
                    if acc_val is not None and acc_val > 0:
                        phase_stats[phase]["acc_sum"] += acc_val
                        phase_stats[phase]["acc_count"] += 1
                    phase_stats[phase]["blunders"] += p_blund.get(phase, 0)

                # Advantage stats
                adv = tactics_data.get("advantage_metrics", {})
                if adv.get("had_winning_advantage"):
                    advantage_stats["had_winning_advantage"] += 1
                if adv.get("converted_advantage"):
                    advantage_stats["converted_advantage"] += 1
                if adv.get("choked_advantage"):
                    advantage_stats["choked_advantage"] += 1
                if adv.get("had_losing_position"):
                    advantage_stats["had_losing_position"] += 1
                if adv.get("comeback_drawn_or_won"):
                    advantage_stats["comeback_drawn_or_won"] += 1

                # Brilliancies list
                opp_key = "black" if user_color == "white" else "white"
                opp_elo_key = "black_elo" if user_color == "white" else "white_elo"
                opp_name = game.get(opp_key, "Unknown")
                opp_rating = game.get(opp_elo_key, "")

                for b in tactics_data.get("brilliancies", []):
                    brilliancies.append(
                        {
                            "game_id": game.get("id"),
                            "opponent": opp_name,
                            "opponent_elo": opp_rating,
                            "date": game.get("date", ""),
                            "user_color": user_color,
                            "san": b.get("san"),
                            "uci": b.get("uci"),
                            "fen_before": b.get("fen_before"),
                            "ply": b.get("ply"),
                            "move_number": b.get("move_number"),
                            "classification": b.get("classification"),
                            "explanation": b.get("explanation"),
                            "opening_name": b.get("opening_name") or game.get("opening", ""),
                        }
                    )

            # 6. Best Win
            opponent_elo = 0
            if is_win:
                opp_key = "black_elo" if user_color == "white" else "white_elo"
                try:
                    opponent_elo = int(game.get(opp_key, 0))
                except (ValueError, TypeError):
                    opponent_elo = 0
            if is_win and opponent_elo > best_win_rating:
                best_win_rating = opponent_elo

            # 7. Openings
            op_name = game.get("opening")
            if not op_name:
                pgn = game.get("pgn", "")
                if 'Opening "' in pgn:
                    match = re.search(r'\[Opening "([^"]+)"\]', pgn)
                    if match:
                        op_name = match.group(1)

            if op_name:
                main_name = op_name.split(":")[0].split(",")[0].strip()
                openings[main_name] = openings.get(main_name, 0) + 1
                if is_win:
                    opening_wins[main_name] = opening_wins.get(main_name, 0) + 1

        # Calculate final phase accuracy averages
        phase_accuracies_final = {}
        for phase in ("opening", "middlegame", "endgame"):
            cnt = phase_stats[phase]["acc_count"]
            phase_accuracies_final[phase] = (
                (phase_stats[phase]["acc_sum"] / cnt) if cnt > 0 else 0.0
            )

        # Legacy-compatible quality_counts (for old cards expecting 4 keys)
        legacy_quality_counts = {
            "Best": quality_counts["Best"] + quality_counts["Brilliant"] + quality_counts["Great"],
            "Inaccuracy": quality_counts["Inaccuracy"],
            "Mistake": quality_counts["Mistake"],
            "Blunder": quality_counts["Blunder"],
        }

        # Average accuracy per color
        for col in ("white", "black"):
            c_cnt = color_stats[col]["acc_count"]
            color_stats[col]["avg_accuracy"] = (
                (color_stats[col]["total_acc"] / c_cnt) if c_cnt > 0 else 0.0
            )

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": (wins / total * 100) if total else 0.0,
            "avg_accuracy": (total_acc / acc_count) if acc_count else 0.0,
            "best_win": str(best_win_rating) if best_win_rating > 0 else "N/A",
            "term_counts": term_counts,
            "quality_counts": legacy_quality_counts,
            "detailed_quality_counts": quality_counts,
            "accuracy_history": accuracy_history,
            "openings": openings,
            "opening_wins": opening_wins,
            "color_stats": color_stats,
            "hanging_stats": hanging_stats,
            "phase_stats": {
                "accuracies": phase_accuracies_final,
                "blunders": {
                    p: phase_stats[p]["blunders"] for p in ("opening", "middlegame", "endgame")
                },
            },
            "advantage_stats": advantage_stats,
            "brilliancies": brilliancies,
            "filter_applied": {
                "color": self.color_filter,
                "format": self.format_filter,
                "source": self.source_filter,
                "date": self.date_filter,
            },
        }
