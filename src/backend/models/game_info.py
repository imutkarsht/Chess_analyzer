from dataclasses import dataclass
import json
import datetime
from typing import Optional

@dataclass
class GameInfo:
    game_id: str
    source: str          # "lichess" | "chesscom"
    white: str
    black: str
    result: str          # "1-0", "0-1", "1/2-1/2", "*"
    date: str            # YYYY-MM-DD
    pgn: str
    white_elo: Optional[str] = None
    black_elo: Optional[str] = None
    time_class: Optional[str] = None  # "blitz", "rapid", "classical", "daily", etc.
    move_count: Optional[int] = None
    opening: Optional[str] = None     # ECO code or opening name
    cached_at: Optional[str] = None   # ISO timestamp, set by cache layer

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "source": self.source,
            "white": self.white,
            "black": self.black,
            "result": self.result,
            "date": self.date,
            "pgn": self.pgn,
            "white_elo": self.white_elo,
            "black_elo": self.black_elo,
            "time_class": self.time_class,
            "move_count": self.move_count,
            "opening": self.opening,
            "cached_at": self.cached_at
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'GameInfo':
        return cls(
            game_id=d.get("game_id", ""),
            source=d.get("source", ""),
            white=d.get("white", ""),
            black=d.get("black", ""),
            result=d.get("result", "*"),
            date=d.get("date", ""),
            pgn=d.get("pgn", ""),
            white_elo=d.get("white_elo"),
            black_elo=d.get("black_elo"),
            time_class=d.get("time_class"),
            move_count=d.get("move_count"),
            opening=d.get("opening"),
            cached_at=d.get("cached_at")
        )

    @classmethod
    def from_lichess_ndjson(cls, line: str) -> 'GameInfo':
        data = json.loads(line)
        
        # Players
        players = data.get("players", {})
        white_player = players.get("white", {})
        black_player = players.get("black", {})
        
        white = white_player.get("user", {}).get("name", "?")
        black = black_player.get("user", {}).get("name", "?")
        
        # Ratings
        white_elo = str(white_player.get("rating")) if white_player.get("rating") is not None else None
        black_elo = str(black_player.get("rating")) if black_player.get("rating") is not None else None
        
        # Date
        created_at_ms = data.get("createdAt", 0)
        date_str = datetime.datetime.fromtimestamp(created_at_ms / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        
        # Result mapping
        winner = data.get("winner")
        status = data.get("status")
        if winner == "white":
            result = "1-0"
        elif winner == "black":
            result = "0-1"
        elif status in ["draw", "stalemate", "threefoldRepetition", "insufficientMaterial", "fiftyMoves"]:
            result = "1/2-1/2"
        else:
            result = "*"
            
        # PGN
        pgn = data.get("pgn", "")
        
        # Opening
        opening = data.get("opening", {}).get("name")
        
        # Move count estimation
        move_count = None
        if pgn:
            import io
            import chess.pgn
            try:
                game = chess.pgn.read_game(io.StringIO(pgn))
                if game:
                    node = game
                    cnt = 0
                    while node.variations:
                        node = node.variation(0)
                        cnt += 1
                    move_count = (cnt + 1) // 2
                    if not opening:
                        opening = game.headers.get("Opening")
            except Exception:
                pass
                
        return cls(
            game_id=data.get("id", ""),
            source="lichess",
            white=white,
            black=black,
            result=result,
            date=date_str,
            pgn=pgn,
            white_elo=white_elo,
            black_elo=black_elo,
            time_class=data.get("speed"),
            move_count=move_count,
            opening=opening
        )
