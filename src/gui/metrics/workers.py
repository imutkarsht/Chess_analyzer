"""
Worker threads for metrics calculations.
"""
import json
import re
from PyQt6.QtCore import QThread, pyqtSignal


# Termination modes mapped to a small stable set used across the dashboard.
MODE_ORDER = ["Checkmate", "Resignation", "Time", "Abandonment", "Draw", "Other"]

# Time control buckets (based on base time in seconds).
TIME_CONTROL_ORDER = ["Bullet", "Blitz", "Rapid", "Classical"]

# Quality buckets shown on the Move Quality card ("Good" aggregates all positive classes).
QUALITY_ORDER = ["Good", "Inaccuracy", "Mistake", "Blunder", "Miss", "Book"]


class InsightWorker(QThread):
    """Worker thread for generating AI insights."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, service, stats_text):
        super().__init__()
        self.service = service
        self.stats_text = stats_text

    def run(self):
        try:
            insight = self.service.generate_coach_insights(self.stats_text)
            self.finished.emit(insight)
        except Exception as e:
            self.error.emit(str(e))


class StatsWorker(QThread):
    """Worker thread for calculating game statistics."""
    finished = pyqtSignal(dict)
    
    def __init__(self, games, usernames):
        super().__init__()
        self.games = games
        self.usernames = usernames
        
    def run(self):
        try:
            stats = self._calculate_stats()
            self.finished.emit(stats)
        except Exception as e:
            self.finished.emit({})
        
    def _get_user_color(self, game):
        """Returns 'white' or 'black' based on which player matches usernames."""
        white = game['white'].lower()
        if white in [u.lower() for u in self.usernames]:
            return 'white'
        return 'black'

    def _detect_termination(self, game):
        """Returns a stable termination mode using TerminationDetector."""
        try:
            from src.backend.storage.termination_detector import TerminationDetector
            from src.backend.storage.models import MoveAnalysis

            headers = {
                "Result": game.get("result", "*"),
                "White": game.get("white", ""),
                "Black": game.get("black", ""),
                "Termination": game.get("termination") or "",
            }

            moves = []
            moves_json = game.get("moves_json")
            if moves_json:
                for m in json.loads(moves_json):
                    moves.append(MoveAnalysis(
                        move_number=m.get("move_number", 0),
                        ply=m.get("ply", 0),
                        san=m.get("san", ""),
                        uci=m.get("uci", ""),
                        fen_before=m.get("fen_before", ""),
                        time_left=m.get("time_left"),
                        time_spent=m.get("time_spent"),
                        raw_clk=m.get("raw_clk"),
                    ))

            mode, _ = TerminationDetector.detect_termination(
                headers, moves,
                starting_fen=game.get("starting_fen"),
                chess960=bool(game.get("chess960")),
            )
            return mode
        except Exception:
            return "Other"

    @staticmethod
    def _normalize_termination_mode(mode):
        """Collapses detector modes into the stable dashboard buckets."""
        if mode in ("checkmate",):
            return "Checkmate"
        if mode in ("resignation",):
            return "Resignation"
        if mode in ("timeout", "timeout_insufficient", "flag"):
            return "Time"
        if mode in ("abandonment", "abandoned"):
            return "Abandonment"
        if mode in ("agreed_draw", "stalemate", "threefold_repetition",
                    "insufficient_material", "fifty_moves"):
            return "Draw"
        return "Other"

    @staticmethod
    def _time_control_bucket(time_control):
        """Categorizes a PGN TimeControl string into a stable bucket by base seconds."""
        if not time_control:
            return None
        raw = str(time_control).strip()
        if raw in ("?", "-", "", "0"):
            return None
        base_str = raw.split("+")[0].strip()
        try:
            base = int(base_str)
        except ValueError:
            return None
        if base <= 0:
            return None
        if base < 120:
            return "Bullet"
        if base < 600:
            return "Blitz"
        if base < 1800:
            return "Rapid"
        return "Classical"

    def _calculate_stats(self):
        """Calculate comprehensive game statistics."""
        total = len(self.games)
        wins = draws = losses = 0
        total_acc = acc_count = best_win_rating = 0
        total_acpl = acpl_count = 0
        
        term_counts = {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandonment": 0, "Draw": 0, "Other": 0}
        win_modes = {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandonment": 0, "Other": 0}
        loss_modes = {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandonment": 0, "Other": 0}
        quality_counts = {k: 0 for k in QUALITY_ORDER}
        accuracy_history = []
        openings = {}
        opening_wins = {}
        
        time_control_stats = {k: {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0} for k in TIME_CONTROL_ORDER}
        opponent_elos = []
        has_clock = False
        think_times = []
        pressured_moves = 0
        clocked_moves = 0

        color_stats = {
            'white': {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0},
            'black': {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0}
        }

        # Games come timestamp DESC; reverse to process chronologically.
        chronological = list(reversed(self.games))

        for game in chronological:
            user_color = self._get_user_color(game)
            if not user_color: 
                continue
            
            res = game['result']
            color_stats[user_color]['total'] += 1
            
            is_win = (res == '1-0' and user_color == 'white') or (res == '0-1' and user_color == 'black')
            is_loss = (res == '1-0' and user_color == 'black') or (res == '0-1' and user_color == 'white')
            is_draw = not is_win and not is_loss
            
            # 1. Result
            if is_win:
                wins += 1
                color_stats[user_color]['wins'] += 1
            elif is_loss:
                losses += 1
                color_stats[user_color]['losses'] += 1
            else:
                draws += 1
                color_stats[user_color]['draws'] += 1

            # 2. Termination mode (via TerminationDetector)
            mode = self._normalize_termination_mode(self._detect_termination(game))
            if is_draw:
                term_counts["Draw"] += 1
            else:
                term_counts[mode] = term_counts.get(mode, 0) + 1
            if is_win:
                win_modes[mode] = win_modes.get(mode, 0) + 1
            elif is_loss:
                loss_modes[mode] = loss_modes.get(mode, 0) + 1

            # 3. Accuracy / Quality / ACPL
            game_acc = 0
            if game.get('summary_json'):
                try:
                    summary = json.loads(game['summary_json'])
                    s_data = summary.get(user_color, {})
                    
                    acc = s_data.get('accuracy', 0)
                    if acc > 0:
                        total_acc += acc
                        acc_count += 1
                        game_acc = acc
                        accuracy_history.append((game.get('timestamp') or 0, acc))
                    
                    acpl = s_data.get('acpl', 0)
                    if acpl > 0:
                        total_acpl += acpl
                        acpl_count += 1

                    quality_counts["Good"] += (s_data.get("Brilliant", 0) + s_data.get("Great", 0)
                                               + s_data.get("Excellent", 0) + s_data.get("Good", 0)
                                               + s_data.get("Best", 0))
                    quality_counts["Inaccuracy"] += s_data.get("Inaccuracy", 0)
                    quality_counts["Mistake"] += s_data.get("Mistake", 0)
                    quality_counts["Blunder"] += s_data.get("Blunder", 0)
                    quality_counts["Miss"] += s_data.get("Miss", 0)
                    quality_counts["Book"] += s_data.get("Book", 0)
                except Exception:
                    pass
            
            # 4. Opponent strength (order-independent aggregate)
            opp_key = 'black_elo' if user_color == 'white' else 'white_elo'
            opponent_elo = 0
            try:
                opponent_elo = int(game.get(opp_key, 0))
            except (TypeError, ValueError):
                opponent_elo = 0
            if opponent_elo > 0:
                opponent_elos.append(opponent_elo)

            # 5. Best Win
            if is_win and opponent_elo > best_win_rating:
                best_win_rating = opponent_elo

            # 6. Time control breakdown
            tc_bucket = self._time_control_bucket(game.get("time_control"))
            if tc_bucket:
                bucket = time_control_stats[tc_bucket]
                bucket['total'] += 1
                if is_win:
                    bucket['wins'] += 1
                elif is_draw:
                    bucket['draws'] += 1
                else:
                    bucket['losses'] += 1

            # 7. Time management (from per-move clock data)
            if game.get('moves_json'):
                try:
                    moves_data = json.loads(game['moves_json'])
                    # User moves: white -> odd ply (1,3,...), black -> even ply (2,4,...)
                    for m in moves_data:
                        ply = m.get("ply", 0)
                        is_user_move = (user_color == 'white' and ply % 2 == 1) or \
                                       (user_color == 'black' and ply % 2 == 0)
                        if not is_user_move:
                            continue
                        time_spent = m.get("time_spent")
                        if time_spent is not None:
                            think_times.append(time_spent)
                            has_clock = True
                        time_left = m.get("time_left")
                        if time_left is not None:
                            has_clock = True
                            clocked_moves += 1
                            if time_left < 30:
                                pressured_moves += 1
                except Exception:
                    pass

            # 8. Openings
            op_name = game.get("opening")
            if not op_name:
                pgn = game.get('pgn', "")
                if 'Opening "' in pgn:
                    match = re.search(r'\[Opening "([^"]+)"\]', pgn)
                    if match: 
                        op_name = match.group(1)
            
            if op_name:
                main_name = op_name.split(":")[0].split(",")[0].strip()
                openings[main_name] = openings.get(main_name, 0) + 1
                if is_win:
                    opening_wins[main_name] = opening_wins.get(main_name, 0) + 1

        # Streaks (chronological result sequence)
        best_streak = current_streak = 0
        run = 0
        for game in chronological:
            user_color = self._get_user_color(game)
            if not user_color:
                continue
            res = game['result']
            is_win = (res == '1-0' and user_color == 'white') or (res == '0-1' and user_color == 'black')
            if is_win:
                run += 1
                if run > best_streak:
                    best_streak = run
            else:
                run = 0
        current_streak = run

        accuracy_history.sort(key=lambda x: x[0])

        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': (wins / total * 100) if total else 0,
            'avg_accuracy': (total_acc / acc_count) if acc_count else 0,
            'best_win': str(best_win_rating) if best_win_rating > 0 else "N/A",
            'best_streak': best_streak,
            'current_streak': current_streak,
            'avg_acpl': (total_acpl / acpl_count) if acpl_count else 0,
            'has_acpl': acpl_count > 0,
            'term_counts': term_counts,
            'quality_counts': quality_counts,
            'accuracy_history': accuracy_history,
            'avg_opponent_elo': (sum(opponent_elos) / len(opponent_elos)) if opponent_elos else 0,
            'max_opponent_elo': max(opponent_elos) if opponent_elos else 0,
            'has_opponent_elo': len(opponent_elos) > 0,
            'time_control_stats': time_control_stats,
            'has_time_control': any(b['total'] > 0 for b in time_control_stats.values()),
            'win_modes': win_modes,
            'loss_modes': loss_modes,
            'has_termination': any(v > 0 for v in term_counts.values()),
            'avg_think_time': (sum(think_times) / len(think_times)) if think_times else 0,
            'time_pressure_pct': (pressured_moves / clocked_moves * 100) if clocked_moves else 0,
            'has_clock': has_clock,
            'openings': openings,
            'opening_wins': opening_wins,
            'color_stats': color_stats
        }
