import hashlib
import io
import os
import re
import threading
from dataclasses import dataclass

import chess.pgn

from src.constants import MAX_PGN_FILE_BYTES, MAX_PGN_GAMES
from src.utils.logger import logger

from .models import GameAnalysis, GameMetadata, MoveAnalysis
from .termination_detector import TerminationDetector

# Matches [%clk H:MM:SS(.s)?] — chess.com style clock comments.
# The colon-separated hours/minutes/seconds format with optional decimal
# fraction. Examples: 0:09:56.1, 1:23:45, 0:00:03.4
_CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)\]")

# Lichess exposes the same game as both /game/<id> and /<id>. The Site header
# is part of the PGN content, so hashing the raw text would give one game two
# identities. Always hash the historical /game/<id> spelling instead.
_LICHESS_SITE_RE = re.compile(
    r'(?m)^\[Site "https?://(?:www\.)?lichess\.org/(?:game/)?'
    r'([A-Za-z0-9]{8,12})(?:/(?:white|black))?/?(?:[?#][^"]*)?"\]$'
)

_MOVE_NUMBER_RE = re.compile(r"(?:^|\s)(\d{1,3})\.\s+[A-Za-z]")


def move_count_from_pgn(pgn: str | None) -> int | None:
    """Cheap full-move count from PGN move numbers, without parsing SAN."""
    if not pgn:
        return None
    numbers = [int(n) for n in _MOVE_NUMBER_RE.findall(pgn) if int(n) <= 500]
    return max(numbers) if numbers else None


def normalize_lichess_site_for_id(pgn: str) -> str:
    """Normalize the Lichess Site header before deriving a game ID."""
    return _LICHESS_SITE_RE.sub(r'[Site "https://lichess.org/game/\1"]', pgn)


def looks_like_pgn(text: str | None) -> bool:
    """Cheap entry-point check before invoking the full PGN parser."""
    stripped = (text or "").strip()
    return bool(stripped) and ("[Event" in stripped or "1." in stripped)


class PGNImportError(Exception):
    """A PGN import failed for a reason that can be shown to the user."""


class PGNFileTooLargeError(PGNImportError):
    def __init__(self, size_bytes: int, limit_bytes: int):
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__("PGN file exceeds the size limit.")


class PGNTooManyGamesError(PGNImportError):
    def __init__(self, game_count: int, limit: int):
        self.game_count = game_count
        self.limit = limit
        super().__init__("PGN file contains too many games.")


class PGNParsingCancelledError(PGNImportError):
    """Raised when the caller cancels indexing."""


@dataclass(frozen=True)
class PGNGameSummary:
    """Header-only game record used by the import picker."""

    index: int
    start: int
    end: int
    white: str
    black: str
    date: str
    result: str
    time_control: str
    white_elo: str | None
    black_elo: str | None
    event: str
    opening: str | None
    eco: str | None
    termination: str | None
    variant: str | None
    white_rating_diff: str | None
    black_rating_diff: str | None
    move_count: int | None


@dataclass(frozen=True)
class PGNIndex:
    """The source text plus header summaries; no move data is materialised."""

    text: str
    games: tuple[PGNGameSummary, ...]

    def game_text(self, index: int) -> str:
        game = self.games[index]
        return self.text[game.start:game.end]


def _skip_leading_comments(handle: io.StringIO) -> bool:
    """Position the handle at the next game, skipping file-level comments.

    ``chess.pgn.read_headers()`` mishandles a braced comment that appears
    before headers: it returns empty headers and leaves the movetext behind.
    Skipping comments here keeps game boundaries and headers intact.
    """
    while True:
        start = handle.tell()
        line = handle.readline()
        if not line:
            return False
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "%")):
            continue
        if stripped.startswith("{"):
            remainder = line[line.find("{"):]
            while "}" not in remainder:
                remainder = handle.readline()
                if not remainder:
                    return False
            continue
        handle.seek(start)
        return True


def _summary_from_headers(
    headers: chess.pgn.Headers,
    start: int,
    end: int,
    index: int,
    move_count: int | None,
) -> PGNGameSummary:
    return PGNGameSummary(
        index=index,
        start=start,
        end=end,
        white=headers.get("White", "?"),
        black=headers.get("Black", "?"),
        date=headers.get("Date", "?"),
        result=headers.get("Result", "*"),
        time_control=headers.get("TimeControl", ""),
        white_elo=headers.get("WhiteElo"),
        black_elo=headers.get("BlackElo"),
        event=headers.get("Event", "?"),
        opening=headers.get("Opening"),
        eco=headers.get("ECO"),
        termination=headers.get("Termination"),
        variant=headers.get("Variant"),
        white_rating_diff=headers.get("WhiteRatingDiff"),
        black_rating_diff=headers.get("BlackRatingDiff"),
        move_count=move_count,
    )


def _parse_clk(comment: str | None) -> tuple[str | None, float | None]:
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
    def index_pgn_text(
        text: str,
        *,
        max_games: int = MAX_PGN_GAMES,
        cancel: threading.Event | None = None,
    ) -> PGNIndex:
        """Index game headers without converting moves to MoveAnalysis."""
        logger.debug("Indexing PGN text (%d chars)", len(text))
        handle = io.StringIO(text)
        games: list[PGNGameSummary] = []
        while _skip_leading_comments(handle):
            if cancel is not None and cancel.is_set():
                raise PGNParsingCancelledError()
            start = handle.tell()
            headers = chess.pgn.read_headers(handle)
            end = handle.tell()
            if headers is None:
                break
            if end <= start:
                # Defensive: malformed input must never spin forever.
                handle.readline()
                continue
            chunk = text[start:end]
            if not headers and not looks_like_pgn(chunk):
                continue
            if len(games) >= max_games:
                raise PGNTooManyGamesError(len(games) + 1, max_games)
            games.append(
                _summary_from_headers(
                    headers,
                    start,
                    end,
                    len(games),
                    move_count_from_pgn(chunk),
                )
            )
        logger.debug("Indexed %d game(s) from PGN text", len(games))
        return PGNIndex(text=text, games=tuple(games))

    @staticmethod
    def index_pgn_file(
        file_path: str,
        *,
        max_bytes: int = MAX_PGN_FILE_BYTES,
        max_games: int = MAX_PGN_GAMES,
        cancel: threading.Event | None = None,
    ) -> PGNIndex:
        """Read a PGN once and index its headers in memory."""
        try:
            size = os.path.getsize(file_path)
        except OSError as exc:
            raise PGNImportError("Could not read this PGN file.") from exc
        logger.debug(
            "Indexing PGN file: %s (%.1f MB)", file_path, size / (1024 * 1024)
        )
        if size > max_bytes:
            raise PGNFileTooLargeError(size, max_bytes)
        try:
            with open(file_path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as exc:
            raise PGNImportError("Could not read this PGN file.") from exc
        except MemoryError as exc:
            raise PGNImportError("This PGN is too large to process.") from exc
        if cancel is not None and cancel.is_set():
            raise PGNParsingCancelledError()
        index = PGNParser.index_pgn_text(
            text, max_games=max_games, cancel=cancel
        )
        logger.info(
            "Indexed %d game(s) from %s", len(index.games), file_path
        )
        return index

    @staticmethod
    def parse_first_game(text: str) -> GameAnalysis | None:
        """Parse the first game that actually contains moves."""
        handle = io.StringIO(text)
        while _skip_leading_comments(handle):
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            if game.next() is None:
                continue
            return PGNParser._convert_to_game_analysis(game)
        return None

    @staticmethod
    def parse_pgn_file(file_path: str) -> list[GameAnalysis]:
        logger.info("Parsing PGN file: %s", file_path)
        games = []
        try:
            with open(file_path, encoding="utf-8") as f:
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
            logger.info("Successfully parsed %d game(s) from %s", len(games), file_path)
        except Exception as e:
            logger.error("Failed to parse PGN file %s: %s", file_path, e)
            raise
        return games

    @staticmethod
    def parse_pgn_text(text: str) -> list[GameAnalysis]:
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
        logger.debug("Successfully parsed %d game(s) from PGN text", len(games))
        return games

    @staticmethod
    def _metadata_from_game(game: chess.pgn.Game) -> tuple[GameMetadata, dict[str, str]]:
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
            opening=headers.get("Opening"),  # Some sites provide this
            starting_fen=headers.get("FEN"),  # If started from position
        )

        site = headers.get("Site", "").lower()
        if "chess.com" in site:
            metadata.source = "chesscom"
        elif "lichess.org" in site:
            metadata.source = "lichess"
        else:
            metadata.source = "file"

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
        metadata.speed_category = PGNParser.detect_speed_category(
            metadata.time_control, metadata.event
        )
        return metadata, headers

    @staticmethod
    def parse_game_stub(text: str) -> GameAnalysis | None:
        """Parse metadata and canonical identity without per-move analysis."""
        handle = io.StringIO(text)
        while _skip_leading_comments(handle):
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            if game.next() is None:
                continue
            metadata, _headers = PGNParser._metadata_from_game(game)
            final_board = game.end().board()
            metadata.move_count = (len(final_board.move_stack) + 1) // 2
            metadata.last_fen = final_board.fen()
            pgn_content = str(game)
            game_id = hashlib.md5(
                normalize_lichess_site_for_id(pgn_content).encode("utf-8")
            ).hexdigest()
            return GameAnalysis(
                game_id=game_id,
                metadata=metadata,
                moves=[],
                pgn_content=pgn_content,
            )
        return None

    @staticmethod
    def _convert_to_game_analysis(game: chess.pgn.Game) -> GameAnalysis:
        metadata, headers = PGNParser._metadata_from_game(game)
        moves = []
        board = game.board()
        # Track per-side running clock so we can compute time_spent.
        # chess.com PGN: [%clk H:MM:SS.s] on every move. We compute the delta
        # between consecutive clocks of the same side to derive time_spent.
        # We don't trust a single missing/invalid entry — fall back to None.
        last_clk: dict[chess.Color, float | None] = {chess.WHITE: None, chess.BLACK: None}

        # Derive the *initial* clock from the TimeControl header so we can
        # compute a delta for the very first move of each side. chess.com
        # emits values like "600" or "600+5"; lichess emits "60+0" or
        # just "blitz". We only need the leading integer (seconds) — the
        # increment does NOT change the starting clock, it gets added
        # *after* each move.
        def _initial_clock_seconds() -> float | None:
            tc = headers.get("TimeControl", "")
            if not tc or tc == "-":
                return None
            head = tc.split("+", 1)[0].strip()
            slash_match = re.match(r"^1/(\d+)$", head)
            if slash_match:
                try:
                    return float(slash_match.group(1))
                except ValueError:
                    pass
            try:
                return float(head)
            except ValueError:
                return None

        def _increment_seconds() -> float:
            """Seconds added after each move, e.g. the ``2`` in ``180+2``."""
            tc = headers.get("TimeControl", "")
            if not tc or "+" not in tc:
                return 0.0
            try:
                return float(tc.rsplit("+", 1)[1])
            except ValueError:
                return 0.0

        start_clock = _initial_clock_seconds()
        increment = _increment_seconds()

        for node in game.mainline():
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
                    # The recorded clock already includes the increment granted
                    # after the move, so add it back to recover think time.
                    delta = previous - time_left + increment
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

        # Detect termination mode and human-readable description
        term_mode, term_desc = TerminationDetector.detect_termination(
            headers=headers,
            moves=moves,
            starting_fen=metadata.starting_fen,
            chess960=metadata.chess960,
        )
        metadata.termination_mode = term_mode
        metadata.termination_description = term_desc

        # Use hash of PGN content as ID to prevent duplicates. The Site header
        # must be normalized first so URL spelling does not split one game into
        # two history rows.
        pgn_content = str(game)
        game_id = hashlib.md5(
            normalize_lichess_site_for_id(pgn_content).encode("utf-8")
        ).hexdigest()

        return GameAnalysis(
            game_id=game_id,
            metadata=metadata,
            moves=moves,
            pgn_content=pgn_content,
        )

    @staticmethod
    def detect_speed_category(time_control: str | None, event: str | None) -> str:
        """Classify game into UltraBullet, Bullet, Blitz, Rapid, Classical, or Daily."""
        tc = (time_control or "").strip()

        # Handle slash notation: e.g. "1/259200" (Daily) or "40/7200" (Classical)
        slash_match = re.match(r"^(\d+)/(\d+)$", tc)
        if slash_match:
            try:
                moves_count = int(slash_match.group(1))
                sec_count = int(slash_match.group(2))
                if sec_count >= 86400 or (moves_count == 1 and sec_count >= 3600):
                    return "Daily"
                elif sec_count >= 1800:
                    return "Classical"
                elif sec_count >= 600:
                    return "Rapid"
                else:
                    return "Blitz"
            except ValueError:
                pass

        match = re.match(r"^(\d+)(?:\+(\d+))?$", tc)
        if match:
            try:
                base_sec = int(match.group(1))
                inc_sec = int(match.group(2)) if match.group(2) else 0
                total_sec = base_sec + 40 * inc_sec
                if total_sec < 30:
                    return "UltraBullet"
                elif total_sec < 180:
                    return "Bullet"
                elif total_sec < 600:
                    return "Blitz"
                elif total_sec < 1800:
                    return "Rapid"
                elif total_sec >= 86400:
                    return "Daily"
                else:
                    return "Classical"
            except ValueError:
                pass

        evt_lower = (event or "").lower()
        tc_lower = tc.lower()
        if "ultrabullet" in evt_lower or "ultrabullet" in tc_lower:
            return "UltraBullet"
        elif "bullet" in evt_lower or "bullet" in tc_lower:
            return "Bullet"
        elif "blitz" in evt_lower or "blitz" in tc_lower:
            return "Blitz"
        elif "rapid" in evt_lower or "rapid" in tc_lower:
            return "Rapid"
        elif any(k in evt_lower or k in tc_lower for k in ("daily", "correspondence")):
            return "Daily"
        elif "classical" in evt_lower or "classical" in tc_lower:
            return "Classical"

        return "Blitz"

    _detect_speed_category = detect_speed_category
