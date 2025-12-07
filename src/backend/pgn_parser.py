import chess.pgn
import io
from typing import List, Optional
from .models import GameAnalysis, GameMetadata, MoveAnalysis
import uuid

class PGNParser:
    @staticmethod
    def parse_pgn_file(file_path: str) -> List[GameAnalysis]:
        games = []
        with open(file_path, 'r', encoding='utf-8') as f:
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
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
        
        moves = []
        board = game.board()
        move_number = 1
        
        for i, node in enumerate(game.mainline()):
            move = node.move
            san = node.san()
            uci = move.uci()
            fen_before = board.fen()
            
            # Basic move info, analysis will fill in the rest
            move_analysis = MoveAnalysis(
                move_number=board.fullmove_number,
                ply=board.ply(),
                san=san,
                uci=uci,
                fen_before=fen_before
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
