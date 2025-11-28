import chess
from typing import Optional

class BookManager:
    def __init__(self):
        # A small dictionary of common opening FENs or sequences
        # Key: FEN (without move counters), Value: Opening Name
        self.openings = {}
        self._initialize_book()

    def _initialize_book(self):
        # Standard starting position
        board = chess.Board()
        self._add_position(board, "Starting Position")

        # e4 Openings
        self._add_sequence("e2e4", "King's Pawn Opening")
        self._add_sequence("e2e4 e7e5", "King's Pawn Game")
        self._add_sequence("e2e4 c7c5", "Sicilian Defense")
        self._add_sequence("e2e4 e7e6", "French Defense")
        self._add_sequence("e2e4 c7c6", "Caro-Kann Defense")
        
        # d4 Openings
        self._add_sequence("d2d4", "Queen's Pawn Opening")
        self._add_sequence("d2d4 d7d5", "Queen's Pawn Game")
        self._add_sequence("d2d4 g8f6", "Indian Defense")
        
        # Others
        self._add_sequence("g1f3", "Reti Opening")
        self._add_sequence("c2c4", "English Opening")

        # Ruy Lopez
        self._add_sequence("e2e4 e7e5 g1f3 b8c6 f1b5", "Ruy Lopez")
        
        # Italian Game
        self._add_sequence("e2e4 e7e5 g1f3 b8c6 f1c4", "Italian Game")

    def _add_position(self, board, name):
        # Store FEN without halfmove/fullmove clocks for better matching
        fen = " ".join(board.fen().split(" ")[:4])
        self.openings[fen] = name

    def _add_sequence(self, moves_str, name):
        board = chess.Board()
        for move_uci in moves_str.split():
            board.push_uci(move_uci)
            self._add_position(board, name)

    def get_opening_name(self, fen_before: str, move_uci: str) -> Optional[str]:
        """
        Checks if the move leads to a known book position and returns the opening name.
        """
        board = chess.Board(fen_before)
        try:
            board.push_uci(move_uci)
            fen_after_key = " ".join(board.fen().split(" ")[:4])
            return self.openings.get(fen_after_key)
        except:
            return None

    def is_book_move(self, fen_before: str, move_uci: str) -> bool:
        return self.get_opening_name(fen_before, move_uci) is not None
