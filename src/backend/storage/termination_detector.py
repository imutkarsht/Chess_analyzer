from typing import Tuple, Optional, List
import chess
from .models import MoveAnalysis


class TerminationDetector:
    """
    Detects the game termination mode and produces human-readable descriptions
    matching online chess platforms (Chess.com / Lichess).
    """

    @staticmethod
    def detect_termination(
        headers: dict,
        moves: List[MoveAnalysis],
        starting_fen: Optional[str] = None,
        chess960: bool = False
    ) -> Tuple[str, str]:
        """
        Returns (termination_mode, termination_description).
        """
        result = headers.get("Result", "*").strip()
        header_term = headers.get("Termination", "").strip()
        term_lower = header_term.lower()

        # Replay board state to check physical terminal rules
        board = chess.Board(starting_fen) if starting_fen else chess.Board(chess960=chess960)
        for m in moves:
            try:
                board.push_uci(m.uci)
            except Exception:
                break

        winner_name = None
        if result == "1-0":
            winner_name = headers.get("White", "White")
        elif result == "0-1":
            winner_name = headers.get("Black", "Black")

        # 1. Authoritative Board States
        if board.is_checkmate():
            if result == "1-0":
                return "checkmate", f"{headers.get('White', 'White')} won by checkmate"
            elif result == "0-1":
                return "checkmate", f"{headers.get('Black', 'Black')} won by checkmate"
            return "checkmate", "Game won by checkmate"

        if board.is_stalemate():
            return "stalemate", "Drawn by stalemate"

        if board.is_insufficient_material():
            return "insufficient_material", "Drawn by insufficient material"

        if board.is_fivefold_repetition() or board.can_claim_threefold_repetition():
            return "threefold_repetition", "Drawn by repetition"

        if board.is_seventyfive_moves() or board.can_claim_fifty_moves():
            return "fifty_moves", "Drawn by 50-move rule"

        # 2. Explicit PGN Headers (Chess.com / Lichess strings)
        if "resign" in term_lower:
            if winner_name:
                return "resignation", f"{winner_name} won by resignation"
            return "resignation", "Game won by resignation"

        if any(kw in term_lower for kw in ("time", "clock", "timeout", "flag", "forfeit")):
            # Check for timeout vs insufficient material
            if result in ("1/2-1/2", "Draw"):
                return "timeout_insufficient", "Drawn on time (insufficient material)"
            if winner_name:
                return "timeout", f"{winner_name} won on time"
            return "timeout", "Game won on time"

        if any(kw in term_lower for kw in ("abandoned", "disconnected", "left the game")):
            if winner_name:
                return "abandonment", f"{winner_name} won - game abandoned"
            return "abandonment", "Game abandoned"

        if any(kw in term_lower for kw in ("rules", "cheat", "disqualif")):
            if winner_name:
                return "rules_violation", f"{winner_name} won by rules violation"
            return "rules_violation", "Game won by rules violation"

        if "repetition" in term_lower:
            return "threefold_repetition", "Drawn by repetition"

        if "50-move" in term_lower or "fifty-move" in term_lower:
            return "fifty_moves", "Drawn by 50-move rule"

        if "insufficient" in term_lower:
            return "insufficient_material", "Drawn by insufficient material"

        if any(kw in term_lower for kw in ("agreed", "agreement", "mutual")):
            return "agreed_draw", "Drawn by agreement"

        # 3. Fallback when Header is Missing or Generic ("Normal")
        if moves:
            last_move = moves[-1]

            # Check if losing player timed out (clock == 0)
            if result == "1-0":
                # Black lost. If Black's last clock is 0, it's a timeout.
                # Find Black's last move clock
                black_clks = [m.time_left for m in moves if m.ply % 2 == 0 and m.time_left is not None]
                if black_clks and black_clks[-1] == 0:
                    return "timeout", f"{headers.get('White', 'White')} won on time"
            elif result == "0-1":
                # White lost. Find White's last move clock
                white_clks = [m.time_left for m in moves if m.ply % 2 == 1 and m.time_left is not None]
                if white_clks and white_clks[-1] == 0:
                    return "timeout", f"{headers.get('Black', 'Black')} won on time"

        # Result-based fallback
        if result == "1-0":
            return "resignation", f"{headers.get('White', 'White')} won by resignation"
        elif result == "0-1":
            return "resignation", f"{headers.get('Black', 'Black')} won by resignation"
        elif result in ("1/2-1/2", "Draw"):
            return "agreed_draw", "Drawn by agreement"

        return "unterminated", "Game unterminated"
