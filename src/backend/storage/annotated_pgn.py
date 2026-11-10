# SPDX-License-Identifier: GPL-3.0-only
"""Export analyzed games as annotated PGN."""

import io
import re
from collections.abc import Iterable

import chess
import chess.pgn

from src.backend.storage.models import GameAnalysis, MoveAnalysis

_CLASSIFICATION_NAGS = {
    "brilliant": 3,
    "great": 1,
    "inaccuracy": 6,
    "mistake": 2,
    "blunder": 4,
    "miss": 5,
}
_EVAL_TAG_RE = re.compile(r"\[%eval\s+[^\]]*\]")
_DEPTH_TAG_RE = re.compile(r"\[%depth\s+[^\]]*\]")
_CLK_TAG_RE = re.compile(r"\[%clk\s+[^\]]*\]")
_VARIANT_HEADER_RE = re.compile(r'(?m)^\[Variant\s+"[^"]*"\][ \t]*$')
_FEN_HEADER_RE = re.compile(r'(?m)^\[FEN\s+"[^"]*"\][ \t]*$')


class AnnotatedPGNExporter:
    """Build standards-compatible PGN from stored game and engine analysis data."""

    @classmethod
    def export_game(cls, game: GameAnalysis) -> str:
        """Return one PGN game with move annotations and engine variations."""
        pgn_game = cls._load_game(game)
        mainline = list(pgn_game.mainline())

        for move_analysis, node in zip(game.moves, mainline, strict=False):
            cls._annotate_move(node, move_analysis)
            cls._add_pv_variations(node.parent, move_analysis)

        exporter = chess.pgn.StringExporter(
            headers=True, variations=True, comments=True, columns=80
        )
        return pgn_game.accept(exporter)

    @classmethod
    def export_games(cls, games: Iterable[GameAnalysis]) -> str:
        """Return multiple PGN games separated by the standard blank line."""
        exported = [cls.export_game(game).strip() for game in games]
        return "\n\n".join(exported) + ("\n" if exported else "")

    @classmethod
    def _load_game(cls, game: GameAnalysis) -> chess.pgn.Game:
        if game.pgn_content:
            pgn_content = cls._prepare_pgn_content(game)
            pgn_game = chess.pgn.read_game(io.StringIO(pgn_content))
            if pgn_game is None:
                raise ValueError(f"Game {game.game_id} does not contain a readable PGN game.")
            if pgn_game.errors:
                raise ValueError(
                    f"Game {game.game_id} contains invalid PGN: {pgn_game.errors[0]}"
                )
        else:
            pgn_game = cls._game_from_analysis(game)

        for key, value in game.metadata.headers.items():
            if value and key not in pgn_game.headers:
                pgn_game.headers[key] = str(value)

        metadata_headers = {
            "White": game.metadata.white,
            "Black": game.metadata.black,
            "Event": game.metadata.event,
            "Date": game.metadata.date,
            "Result": game.metadata.result,
            "WhiteElo": game.metadata.white_elo,
            "BlackElo": game.metadata.black_elo,
            "TimeControl": game.metadata.time_control,
            "ECO": game.metadata.eco,
            "Opening": game.metadata.opening,
            "Termination": game.metadata.termination,
        }
        for key, value in metadata_headers.items():
            result_is_placeholder = (
                key == "Result"
                and pgn_game.headers.get(key) == "*"
                and value not in (None, "", "*", "?")
            )
            if (
                value
                and value != "?"
                and (pgn_game.headers.get(key) in (None, "?") or result_is_placeholder)
            ):
                pgn_game.headers[key] = str(value)

        return pgn_game

    @staticmethod
    def _prepare_pgn_content(game: GameAnalysis) -> str:
        content = game.pgn_content or ""
        if not game.metadata.chess960:
            return content

        variant_match = _VARIANT_HEADER_RE.search(content)
        if variant_match:
            content = _VARIANT_HEADER_RE.sub('[Variant "Chess960"]', content, count=1)
            headers: list[str] = []
        else:
            headers = ['[Variant "Chess960"]']
        if game.metadata.starting_fen and not _FEN_HEADER_RE.search(content):
            headers.extend(
                (
                    '[SetUp "1"]',
                    f'[FEN "{game.metadata.starting_fen}"]',
                )
            )
        if headers:
            header_text = "\n".join(headers) + "\n"
            first_header = re.search(r"(?m)^\[", content)
            if first_header:
                content = f"{content[:first_header.start()]}{header_text}{content[first_header.start():]}"
            else:
                content = f"{header_text}\n{content}"
        return content

    @classmethod
    def _game_from_analysis(cls, game: GameAnalysis) -> chess.pgn.Game:
        metadata = game.metadata
        board = chess.Board(
            metadata.starting_fen or chess.STARTING_FEN,
            chess960=metadata.chess960,
        )
        pgn_game = chess.pgn.Game()
        pgn_game.setup(board)
        if metadata.chess960 and "Variant" not in metadata.headers:
            pgn_game.headers["Variant"] = "Chess960"

        for key, value in metadata.headers.items():
            if value:
                pgn_game.headers[key] = str(value)

        node = pgn_game
        for move_analysis in game.moves:
            move = cls._parse_played_move(board, move_analysis)
            node = node.add_variation(move)
            board.push(move)
        return pgn_game

    @staticmethod
    def _parse_played_move(board: chess.Board, move: MoveAnalysis) -> chess.Move:
        if move.uci:
            try:
                return board.parse_uci(move.uci)
            except ValueError:
                pass
        if move.san:
            try:
                return board.parse_san(move.san)
            except ValueError as exc:
                raise ValueError(
                    f"Cannot export illegal move {move.san!r} in position {board.fen()}."
                ) from exc
        raise ValueError(f"Move {move.ply} has neither a legal UCI nor SAN representation.")

    @classmethod
    def _annotate_move(cls, node: chess.pgn.ChildNode, move: MoveAnalysis) -> None:
        nag = _CLASSIFICATION_NAGS.get((move.classification or "").strip().lower())
        if nag is not None:
            node.nags.add(nag)

        comment = node.comment
        eval_text = cls._format_eval(move.eval_after_cp, move.eval_after_mate)
        if eval_text is not None:
            comment = _EVAL_TAG_RE.sub("", comment).strip()
            comment = cls._append_tag(comment, f"[%eval {eval_text}]")

        depth = cls._analysis_depth(move)
        if depth is not None:
            comment = _DEPTH_TAG_RE.sub("", comment).strip()
            comment = cls._append_tag(comment, f"[%depth {depth}]")

        if not _CLK_TAG_RE.search(comment):
            clock = move.raw_clk or cls._format_clock(move.time_left)
            if clock:
                comment = cls._append_tag(comment, f"[%clk {clock}]")

        node.comment = comment

    @staticmethod
    def _append_tag(comment: str, tag: str) -> str:
        return f"{comment} {tag}".strip()

    @staticmethod
    def _format_eval(cp: int | None, mate: int | None) -> str | None:
        if mate is not None:
            return f"#{mate}"
        if cp is not None:
            return f"{cp / 100:+.2f}"
        return None

    @staticmethod
    def _analysis_depth(move: MoveAnalysis) -> int | None:
        depths: list[int] = []
        for line in move.multi_pvs:
            if not isinstance(line, dict):
                continue
            try:
                depth = int(line.get("depth"))
            except (TypeError, ValueError):
                continue
            if depth > 0:
                depths.append(depth)
        return max(depths) if depths else None

    @staticmethod
    def _format_clock(seconds: float | None) -> str | None:
        if seconds is None or seconds < 0:
            return None
        tenths = round(seconds * 10)
        hours, remainder = divmod(tenths, 36_000)
        minutes, remainder = divmod(remainder, 600)
        whole_seconds, fractional = divmod(remainder, 10)
        seconds_text = (
            f"{whole_seconds:02d}.{fractional}" if fractional else f"{whole_seconds:02d}"
        )
        return f"{hours}:{minutes:02d}:{seconds_text}"

    @classmethod
    def _add_pv_variations(
        cls, parent: chess.pgn.GameNode, move: MoveAnalysis
    ) -> None:
        if parent is None:
            return

        lines: list[list[chess.Move]] = []
        for line in move.multi_pvs:
            if isinstance(line, dict):
                raw_pv = line.get("pv_uci") or line.get("pv") or []
                pv = cls._validated_pv(parent.board(), raw_pv)
                if pv and pv not in lines:
                    lines.append(pv)

        if move.pv:
            pv = cls._validated_pv(parent.board(), move.pv)
            if pv and pv not in lines:
                lines.append(pv)

        for line in lines:
            cls._insert_variation(parent, line)

    @staticmethod
    def _validated_pv(board: chess.Board, raw_pv: object) -> list[chess.Move]:
        if not isinstance(raw_pv, (list, tuple)):
            return []
        position = board.copy(stack=False)
        moves: list[chess.Move] = []
        for raw_move in raw_pv:
            try:
                move = (
                    raw_move
                    if isinstance(raw_move, chess.Move)
                    else position.parse_uci(str(raw_move))
                )
            except (ValueError, TypeError):
                break
            if move not in position.legal_moves:
                break
            moves.append(move)
            position.push(move)
        return moves

    @staticmethod
    def _insert_variation(parent: chess.pgn.GameNode, line: list[chess.Move]) -> None:
        node = parent
        index = 0
        while index < len(line):
            mainline = node.variation(0) if node.variations else None
            if mainline is None or mainline.move != line[index]:
                break
            node = mainline
            index += 1

        if index == len(line):
            return

        branch = line[index:]
        for existing in node.variations:
            if existing.move == branch[0] and AnnotatedPGNExporter._contains_line(
                existing, branch[1:]
            ):
                return

        branch_node = node.add_variation(branch[0])
        for move in branch[1:]:
            branch_node = branch_node.add_variation(move)

    @staticmethod
    def _contains_line(node: chess.pgn.ChildNode, moves: list[chess.Move]) -> bool:
        for move in moves:
            matching_child = next((child for child in node.variations if child.move == move), None)
            if matching_child is None:
                return False
            node = matching_child
        return True
