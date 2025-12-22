"""
Worker threads for metrics calculations.
"""
import json
import re
from PyQt6.QtCore import QThread, pyqtSignal


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

    def _calculate_stats(self):
        """Calculate comprehensive game statistics."""
        total = len(self.games)
        wins = draws = losses = 0
        total_acc = acc_count = best_win_rating = 0
        
        term_counts = {"Checkmate": 0, "Resignation": 0, "Time": 0, "Abandon": 0, "Draw": 0}
        quality_counts = {"Best": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
        accuracy_history = []
        openings = {}
        opening_wins = {}
        
        color_stats = {
            'white': {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0},
            'black': {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0}
        }

        for game in self.games:
            user_color = self._get_user_color(game)
            if not user_color: 
                continue
            
            res = game['result']
            color_stats[user_color]['total'] += 1
            
            # 1. Result
            if res == '1-0':
                if user_color == 'white': 
                    wins += 1
                    color_stats['white']['wins'] += 1
                else: 
                    losses += 1
                    color_stats['black']['losses'] += 1
            elif res == '0-1':
                if user_color == 'black': 
                    wins += 1
                    color_stats['black']['wins'] += 1
                else: 
                    losses += 1
                    color_stats['white']['losses'] += 1
            else:
                draws += 1
                color_stats[user_color]['draws'] += 1
                
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

            # 3. Accuracy / Quality
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
                        
                    quality_counts["Best"] += s_data.get("Best", 0) + s_data.get("Brilliant", 0) + s_data.get("Great", 0)
                    quality_counts["Inaccuracy"] += s_data.get("Inaccuracy", 0)
                    quality_counts["Mistake"] += s_data.get("Mistake", 0)
                    quality_counts["Blunder"] += s_data.get("Blunder", 0)
                except:
                    pass
            
            if game_acc > 0:
                accuracy_history.append(game_acc)
            
            # 4. Best Win
            is_win = False
            opponent_elo = 0
            if (res == '1-0' and user_color == 'white') or (res == '0-1' and user_color == 'black'):
                is_win = True
                opp_key = 'black_elo' if user_color == 'white' else 'white_elo'
                try: 
                    opponent_elo = int(game.get(opp_key, 0))
                except: 
                    opponent_elo = 0
            if is_win and opponent_elo > best_win_rating:
                best_win_rating = opponent_elo
                
            # 5. Openings
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

        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': (wins / total * 100) if total else 0,
            'avg_accuracy': (total_acc / acc_count) if acc_count else 0,
            'best_win': str(best_win_rating) if best_win_rating > 0 else "N/A",
            'term_counts': term_counts,
            'quality_counts': quality_counts,
            'accuracy_history': accuracy_history,
            'openings': openings,
            'opening_wins': opening_wins,
            'color_stats': color_stats
        }
