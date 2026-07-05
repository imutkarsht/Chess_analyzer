import chess.pgn
import io
import re
from typing import List, Optional, Tuple
from .models import GameAnalysis, GameMetadata, MoveAnalysis
import uuid


# Matches [%clk H:MM:SS(.s)?] — chess.com style clock comments.
# The colon-separated hours/minutes/seconds format with optional decimal
# fraction. Examples: 0:09:56.1, 1:23:45, 0:00:03.4
_CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)\]")


def _parse_clk(comment: Optional[str]) -> Tuple[Optional[str], Optional[float]]:
    """
    Pull the first [%clk …] value out of a move comment.

    Returns (raw_string, seconds) or (None, None) if no clock is present,
    malformed, or contains out-of-range minute/second fields.

    Range checks:
      - minutes must be 0..59
      - the seconds integer part must be 0..59 (decimals like .9 are fine)

    A value of ``[0:99:00]`` would otherwise be accepted by the regex and
    silently parsed as 99*60 = 5940 seconds, which is clearly wrong; the
    range guards return ``(None, None)`` for those cases so the caller can
    treat them as "no clock data" instead of feeding garbage into the
    time-spent delta calculation.
    """
    if not comment:
        return None, None
    m = _CLK_RE.search(comment)
    if not m:
        return None, None
    h = int(m.group(1))
    mm = int(m.group(2))
    ss = float(m.group(3))
    if mm >= 60 or ss >= 60:
        return None, None
    seconds = h * 3600 + mm * 60 + ss
    return m.group(0).split()[-1].rstrip("]"), seconds


class PGNParser:
    @staticmethod
    def parse_pgn_file(file_path: str) -> List[GameAnalysis]:
        games = []
        with open(file_path, 'r', encoding='utf-8') as f:
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                # Skip games with no moves — garbage input like SQL text
                # produces a default game object from python-chess but has
                # no actual moves.
                if game.next() is None:
                    continue
                games.append(PGNParser._convert_to_game_analysis(game))
        return games

    @staticmethod
    def parse_pgn_text(text: str) -> List[GameAnalysis]:
        games = []
        pgn_io = io.StringIO(text)
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break
            # Skip games with no moves (see comment above).
            if game.next() is None:
                continue
            games.append(PGNParser._convert_to_game_analysis(game))
        return games

    @staticmethod
    def _convert_to_game_analysis(game: chess.pgn.Game) -> GameAnalysis:
        headers = dict(game.headers)
        metadata = GameMetadata(
            white=headers.get("White", "?"),
            black=headers.get("Black", "?"),
            event=headers.get("Event", "?"),
            date=headers.get("Date", "?"),
            result=headers.get("Result", "*"),
            headers=headers,
            white_elo=headers.get("WhiteElo"),
            black_elo=headers.get("BlackElo"),
            time_control=headers.get("TimeControl"),
            eco=headers.get("ECO"),
            termination=headers.get("Termination"),
            opening=headers.get("Opening"), # Some sites provide this
            starting_fen=headers.get("FEN")  # If started from position
        )
        
        # Infer source from Site header if present
        site = headers.get("Site", "").lower()
        if "chess.com" in site:
            metadata.source = "chesscom"
        elif "lichess.org" in site:
            metadata.source = "lichess"
        else:
            metadata.source = "file"
        
        moves = []
        board = game.board()
        # python-chess reads Variant/FEN headers internally and creates the
        # correct board type.  Use board.chess960 as the single source of truth.
        metadata.chess960 = board.chess960
        # Fallback: detect Chess960 from file-letter castling rights (a-h/A-H)
        # in the FEN header.  python-chess does not do this automatically when
        # no Variant header is present.
        if not metadata.chess960:
            setup_fen = headers.get("FEN", "")
            if setup_fen:
                fen_parts = setup_fen.split(" ")
                if len(fen_parts) >= 3:
                    castling = fen_parts[2]
                    if any(c not in "KQkq-" for c in castling):
                        metadata.chess960 = True
        # Track per-side running clock so we can compute time_spent.
        # chess.com PGN: [%clk H:MM:SS.s] on every move. We compute the delta
        # between consecutive clocks of the same side to derive time_spent.
        # We don't trust a single missing/invalid entry — fall back to None.
        last_clk: dict[chess.Color, float] = {chess.WHITE: None, chess.BLACK: None}

        # Derive the *initial* clock from the TimeControl header so we can
        # compute a delta for the very first move of each side. chess.com
        # emits values like "600" or "600+5"; lichess emits "60+0" or
        # just "blitz". We only need the leading integer (seconds) — the
        # increment does NOT change the starting clock, it gets added
        # *after* each move.
        def _initial_clock_seconds() -> Optional[float]:
            tc = headers.get("TimeControl", "")
            if not tc or tc == "-":
                return None
            # The first numeric chunk is the initial time in seconds.
            head = tc.split("+", 1)[0].strip()
            try:
                return float(head)
            except ValueError:
                return None

        start_clock = _initial_clock_seconds()

        for i, node in enumerate(game.mainline()):
            move = node.move
            san = node.san()
            uci = move.uci()
            fen_before = board.fen()
            side_to_move = board.turn  # who is about to play this move

            # node.comment is a free-form string.  We look for [%clk]
            # (chess.com / lichess) and compute the time delta against the
            # previous recorded clock on the same side, falling back to the
            # initial TimeControl value for the very first move of each side.
            raw_clk, time_left = _parse_clk(node.comment)
            time_spent = None
            if time_left is not None:
                # Determine the "previous" clock for this side. For the very
                # first move of each side we don't have a recorded previous
                # clock, but we can derive it from the TimeControl header
                # (e.g. "600" → 600 seconds starting clock). After that we
                # use the last recorded value of the same side.
                previous = last_clk[side_to_move]
                if previous is None and start_clock is not None:
                    previous = start_clock
                if previous is not None:
                    delta = previous - time_left
                    if delta >= 0:
                        time_spent = delta
                last_clk[side_to_move] = time_left

            # Basic move info, analysis will fill in the rest
            move_analysis = MoveAnalysis(
                move_number=board.fullmove_number,
                ply=board.ply(),
                san=san,
                uci=uci,
                fen_before=fen_before,
                time_left=time_left,
                time_spent=time_spent,
                raw_clk=raw_clk,
            )
            moves.append(move_analysis)
            board.push(move)
            
        # Use hash of PGN content as ID to prevent duplicates
        import hashlib
        pgn_content = str(game)
        game_id = hashlib.md5(pgn_content.encode('utf-8')).hexdigest()

        return GameAnalysis(
            game_id=game_id,
            metadata=metadata,
            moves=moves,
            pgn_content=pgn_content
        )
