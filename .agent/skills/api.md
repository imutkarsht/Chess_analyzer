# Skill: External APIs & LLM Integration

## Purpose
Manages all outbound network calls: Chess.com and Lichess game import APIs, GitHub update checker, and LLM provider integration for AI game summaries and coaching.

---

## Relevant Files
| File | Role |
|---|---|
| `src/backend/api/chess_com_api.py` | `ChessComAPI` — Chess.com game import |
| `src/backend/api/lichess_api.py` | `LichessAPI` — Lichess game import |
| `src/backend/api/base_api.py` | Abstract base for API clients |
| `src/backend/services/groq_service.py` | `GroqService` — LLM AI summaries |
| `src/backend/updater/update_checker.py` | GitHub release checker |
| `src/backend/updater/updater.py` | Download worker + platform installers |
| `src/constants.py` | All API base URLs, provider catalogue, platform rules |

---

## LLM Service (`GroqService`)

### Supported Providers
All providers use OpenAI-compatible `/v1/chat/completions`. Config from `ConfigManager` active profile:

| Provider Key | Base URL | Requires Key |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | Yes (`gsk_…`) |
| `openai` | `https://api.openai.com/v1` | Yes (`sk-proj-…`) |
| `lmstudio` | `http://localhost:1234/v1` | No |
| `minimax` | `https://api.minimax.io/v1` | Yes |
| `custom` | User-configured | Optional |

### Usage
```python
from src.backend.services.groq_service import GroqService

service = GroqService()         # Reads active profile from ConfigManager
if service.client:              # None if not configured
    summary = service.generate_summary(pgn_text, analysis_summary, time_stats)
    insights = service.generate_coach_insights(stats_text)
```

### Reconfigure at Runtime
```python
service.configure(provider, api_key, model, base_url)
# Or re-instantiate: GroqService() re-reads active profile from ConfigManager
```

### Key Implementation Details
- **Placeholder detection**: `_is_placeholder_key()` catches `${VAR}`, `{{ secrets.X }}`, `<YOUR_KEY>`, `xxxx…` patterns to avoid confusing connection errors.
- **Language detection**: Reads `LANG`/`LANGUAGE` env vars, falls back to `locale.getdefaultlocale()`. Response language is set via system message.
- **Base URL normalization**: Strips trailing `/chat/completions` from user-pasted URLs.
- **Class name**: Still `GroqService` for backward compat — it handles all providers.

---

## Chess.com API (`ChessComAPI`)

```python
api = ChessComAPI()
games_pgn = api.fetch_user_games(username, month=None, year=None, limit=20)
game_pgn  = api.fetch_game_by_url(game_url)
```

- Base URL: `https://api.chess.com/pub`
- Requires `User-Agent` header (set in `CHESSCOM_HEADERS` constant): `"ChessAnalyzer/1.0 (contact: ...)"` — omitting this causes 403 errors.
- No authentication required for public game data.
- Returns PGN strings directly.

---

## Lichess API (`LichessAPI`)

```python
api = LichessAPI(token=optional_oauth_token)
games_pgn = api.fetch_user_games(username, limit=20)
game_pgn  = api.fetch_game_by_url(game_url)
```

- Base URL: `https://lichess.org/api/games/user`
- Optional OAuth token (`lichess_token` in config) — required for private games.
- Returns NDJSON or PGN depending on endpoint; client normalizes to PGN.

---

## Update Checker

```python
from src.backend.updater.update_checker import UpdateCheckerWorker
worker = UpdateCheckerWorker()
worker.update_checked.connect(handler)   # Signal: emits UpdateInfo dataclass
worker.start()
```

- Polls `GITHUB_RELEASES_API` (see `src/constants.py`)
- Rate-limited to once/day via `last_update_check` in config
- `UpdateInfo.available: bool`, `UpdateInfo.version: str`, `UpdateInfo.assets: List[dict]`

### Download + Install Flow
```python
from src.backend.updater.updater import DownloadWorker, install_and_quit, get_download_destination

dest = get_download_destination(download_url)
worker = DownloadWorker(download_url, dest)
worker.progress.connect(update_progress_bar)
worker.finished.connect(lambda path: install_and_quit(path, QApplication.quit))
worker.error.connect(show_error)
worker.start()
```

Platform behavior:
- **Windows**: Silent Inno Setup installer (`/VERYSILENT /NORESTART /CLOSEAPPLICATIONS`)
- **macOS**: Strip quarantine xattr, open DMG in Finder for manual drag
- **Linux**: Hot-swap AppImage via detached shell script (waits for PID to exit)

---

## Key Assumptions
- All API calls are **synchronous** in the API classes themselves; call them from QThread workers in the GUI.
- LLM prompts truncate PGN at 10,000 chars to avoid token limits.
- Chess.com User-Agent header is **required** — don't remove it.
- Lichess token is stored in `config.json` as `lichess_token` — not encrypted.
- The `PROVIDERS` dict in `constants.py` is the single source of truth for provider metadata (label, base URL, model defaults, key requirements).

---

## Common Pitfalls
- **Chess.com 403**: Missing or incorrect User-Agent header. Always use `CHESSCOM_HEADERS` from constants.
- **LLM "not connected"**: `GroqService.client is None` — check that active profile has a valid API key and base URL. Also check for placeholder key patterns.
- **Lichess rate limiting**: Bulk exports can be slow. Always run in a QThread and show progress.
- **Platform installer path**: `get_download_destination()` puts macOS downloads in `~/Downloads`, Windows/Linux in temp dir. Do not hardcode paths.
- **Linux AppImage swap**: Only works when `APPIMAGE` env var is set (AppImage runtime). In dev mode (running from source), the swap completes but relaunch is skipped.

---

## Extension Guidelines
- **New LLM provider**: Add to `PROVIDERS` in `constants.py`. No code changes needed in `GroqService`.
- **New Chess platform**: Implement `BaseAPI`, add to `load_game_dialog.py` tabs, add source constant to `constants.py`.
- **New update asset format**: Update `PLATFORM_RULES` in `constants.py` (priority suffixes, fallback keywords).
