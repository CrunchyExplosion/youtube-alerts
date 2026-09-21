# Codebase Guide — youtube-alerts

One job: given a YouTube channel, find its **latest uploaded video**. Optionally
watch the channel forever and email you when a new video appears.

## Mental model

```
CLI (cli.py)
  └─ one-shot: fetch_latest_video(url) → print/JSON
  └─ --watch:  scanner.run_forever() → loop: scan_once() → email if new
                     │
                     └─ fetch_latest_video() (same function, reused)

fetch_latest_video() [scraper/youtube.py]
  1. normalize_channel_videos_url()   [scraper/urls.py]   → canonical .../videos URL
  2. HTTP GET the page                [requests]
  3. extract_yt_initial_data(html)    [scraper/parsers.py] → YouTube's embedded JSON blob
  4. parse_latest_video(data)         [scraper/parsers.py] → first video in the grid
  5. if step 3/4 fails → fall back to the channel's Atom RSS feed
     (parse_latest_video_from_feed)
  → returns a Video (models.py) dataclass
```

Everything is layered so parsing is 100% pure/testable (no network calls),
and network code is a thin, separately-testable layer around it.

## File-by-file

- **[cli.py](../src/youtubealerts/cli.py)** — argparse CLI (`youtube-alerts`). Builds args, calls
  `fetch_latest_video` (or `run_forever` for `--watch`), prints human text or `--json`.
- **[config.py](../src/youtubealerts/config.py)** — constants only: URL templates, request timeout,
  a browser-like `User-Agent`/headers (YouTube serves simpler HTML to
  "real browsers"), and `hl=en&gl=US` query params to force English markup.
- **[models.py](../src/youtubealerts/models.py)** — `Video`, a frozen dataclass with every field the scraper can
  fill in (title, id, url, channel, published/duration/views as raw text,
  thumbnail, `members_only` flag, and `source` = `"html"` or `"feed"`).
  `.to_dict()` powers `--json`.
- **[exceptions.py](../src/youtubealerts/exceptions.py)** — `ScraperError` base class, with `InvalidChannelUrlError`,
  `ChannelFetchError` (network), `NoVideosFoundError` (parsed but empty).
  CLI catches `ScraperError` and prints a clean `Error: ...` instead of a traceback.
- **[scraper/urls.py](../src/youtubealerts/scraper/urls.py)** — `normalize_channel_videos_url()`. Accepts almost anything:
  bare `@handle`, bare channel name, `UC...` channel id, host-less
  `youtube.com/c/Name`, or a full URL with any tab (`/streams`, `/about`, etc).
  Strips known tabs and always appends `/videos` so results are newest-first.
  Rejects non-channel URLs (`/watch`, `/playlist`, ...).
- **[scraper/youtube.py](../src/youtubealerts/scraper/youtube.py)** — the only place that touches the network
  (`fetch_latest_video`). Fetches the page, tries HTML parsing first, and if
  YouTube served a JS-only/consent shell with no video renderers, falls back
  to the channel's Atom uploads feed (`/feeds/videos.xml?channel_id=...`).
  Accepts an optional `requests.Session` (used by tests/mocking).
- **[scraper/parsers.py](../src/youtubealerts/scraper/parsers.py)** — all the fragile-but-isolated HTML/JSON/XML parsing:
  - `extract_yt_initial_data`: regex-locates `ytInitialData = {...}` in the raw
    HTML, then does a hand-rolled string-aware brace scanner
    (`extract_json_object`) to pull out the exact JSON object (can't use
    `json.loads` on the whole HTML page).
  - `parse_latest_video`: depth-first walks the JSON tree looking for either
    the legacy `videoRenderer`/`gridVideoRenderer` shape or YouTube's newer
    `lockupViewModel` grid-item shape, and converts whichever it finds first
    into a `Video`. First match = latest video, because the uploads tab is
    sorted newest-first.
  - `parse_latest_video_from_feed`: parses the Atom/RSS XML fallback with
    `xml.etree.ElementTree` using YouTube's `yt:`/`media:` namespaces.
  - `_is_members_only`: recursively scans all strings in a video node for
    "member"+"only" to flag members-only uploads.
- **[scanner.py](../src/youtubealerts/scanner.py)** — the `--watch` feature:
  - `EmailNotifier`: reads `YTA_SMTP_*` / `YTA_ALERT_*` env vars (via
    `python-dotenv` + `.env`), sends a plain-text email over SMTP+STARTTLS.
  - State file (default `.yta-state.json`): stores last seen `video_id` +
    `members_only`, written atomically (write to `.tmp`, then `replace`).
  - `scan_once()`: fetch → compare to saved state → decide whether to notify.
    First-ever scan only saves a baseline (no email). Notifies only when the
    video id changes **and** it's public (avoids emailing about members-only
    previews, but still remembers it so a later "became public" transition
    triggers a notification).
  - `run_forever()`: infinite loop of `scan_once` + `sleep(interval)`;
    swallows and logs exceptions per-iteration so one bad scan doesn't kill
    the watcher.
- **[__init__.py](../src/youtubealerts/__init__.py) / [__main__.py](../src/youtubealerts/__main__.py)** — package exports (`Video`,
  `fetch_latest_video`) and `python -m youtubealerts` entry point.

## Data flow example

```
youtube-alerts "@MKBHD" --json
  → normalize_channel_videos_url("@MKBHD")
      → "https://www.youtube.com/@MKBHD/videos"
  → GET that URL with browser headers + hl=en
  → extract_yt_initial_data(html) → dict
  → parse_latest_video(dict) → Video(video_id=..., title=..., ...)
  → print(json.dumps(video.to_dict()))
```

## Testing (`tests/`)

- `test_urls.py` — table-driven checks of `normalize_channel_videos_url`
  (handles, tabs, invalid URLs).
- `test_parsers.py` — feeds saved/handwritten JSON & XML fixtures straight
  into the parser functions; no HTTP involved.
- `test_scanner.py` — exercises `scan_once`/state-file logic with a fake
  `fetch` callable, no real email or network.

Run with `pytest` (config lives in `pyproject.toml`: `pythonpath = ["src"]`).

## Things to know if you touch this code

- **Everything HTML-related is fragile by design.** `parsers.py` is the only
  place that should ever change when YouTube tweaks its markup; it exists
  precisely so breakage is contained there.
- **Two rendering formats are supported simultaneously** (`videoRenderer` /
  `gridVideoRenderer` and `lockupViewModel`) because YouTube has been
  migrating channel pages between them — if parsing starts failing, check
  which shape the saved HTML actually uses.
- **The feed fallback has a different, smaller field set** (`source="feed"`,
  no `duration_text`/`members_only`) — don't assume all `Video` fields are
  always populated.
- **No download step exists yet** despite the project name — it only detects
  the latest video (see README "Next steps": HTTP API, real download).
- Email credentials live in `.env` (see `.env.example`), never hardcode them.

## Technical reference

### Function signatures (public surface)

```python
# scraper/youtube.py
def fetch_latest_video(channel_url: str, session: Optional[requests.Session] = None) -> Video: ...

# scraper/urls.py
def normalize_channel_videos_url(raw_url: str) -> str: ...

# scraper/parsers.py
def extract_json_object(text: str, start: int) -> str: ...            # raises ValueError
def extract_yt_initial_data(html: str) -> Dict[str, Any]: ...          # raises NoVideosFoundError
def extract_channel_id(html: str) -> Optional[str]: ...
def parse_latest_video(data: Dict[str, Any]) -> Video: ...             # raises NoVideosFoundError
def parse_latest_video_from_feed(xml_text: str) -> Video: ...          # raises NoVideosFoundError

# scanner.py
def scan_once(channel_url, state_file, notify, fetch=fetch_latest_video) -> bool: ...
def run_forever(channel_url, interval_seconds=300, state_file=..., notify=None, fetch=..., sleep=time.sleep) -> None: ...
```

Note `fetch`/`sleep`/`notify` are injected as callables in `scanner.py` purely
for testability (dependency injection, no framework) — `test_scanner.py`
passes fakes instead of hitting SMTP/network/real time.

### `extract_json_object` — the brace scanner

`json.JSONDecoder().raw_decode(text, idx)` was **not** used because YouTube's
page is tens to hundreds of KB and `ytInitialData` is one specific object
inside a `<script>` tag mixed with other JS statements (trailing `;`, more
assignments, etc.) — `raw_decode` still requires the decoder to tokenize
from `idx` and would choke on the JS wrapper before/after. Instead:

- Linear scan, O(n) in blob size, one pass, no backtracking.
- Tracks `in_string`/`escaped` so `{`/`}` inside JSON string values (e.g. a
  video title containing `"}"`) don't perturb `depth`.
- Stops as soon as `depth` returns to 0 → returns the exact substring, which
  is then handed to `json.loads` (so actual JSON validation is still
  delegated to the stdlib, this function only finds the boundaries).
- `extract_yt_initial_data` calls this for every regex match of the
  `ytInitialData = ` assignment forms and tries `json.loads`; first
  successful parse wins. Guards against `brace - match.end() > 4` to skip
  matches where `{` isn't immediately after `=` (avoids drifting into an
  unrelated blob).

### `parse_latest_video` — traversal shape

`_walk()` is an **explicit stack, not recursion** (`while stack: pop()`) —
deliberate choice since `ytInitialData` trees from large channels can nest
deep enough to risk hitting Python's default recursion limit (1000) with a
recursive walk. It's a pre-order DFS (parent yielded before children,
`reversed()` on children so list order is preserved despite stack popping
from the end). `parse_latest_video` relies on **document order** — the
first `videoRenderer`/`gridVideoRenderer`/`lockupViewModel` encountered is
returned immediately, no scoring/sorting; correctness depends entirely on
YouTube always rendering the `/videos` tab newest-first.

### URL normalization edge cases (`normalize_channel_videos_url`)

| Input | Result |
|---|---|
| `@MKBHD` | `https://www.youtube.com/@MKBHD/videos` |
| `MKBHD` (bare word) | `https://www.youtube.com/@MKBHD/videos` (assumed handle) |
| `youtube.com/c/Name` | scheme added, `/videos` appended |
| `.../channel/UC.../community` | known tab stripped, replaced with `/videos` |
| `UCxxxxxxxxxxxxxxxxxxxxxxxx` (24 chars, `UC` + 22) | treated as channel id via `_CHANNEL_ID_RE` |
| `youtube.com/watch?v=...` | raises `InvalidChannelUrlError` (blocklist: watch/shorts/playlist/results/feed) |
| `""` / whitespace | raises `InvalidChannelUrlError` |
| host not in `_YOUTUBE_HOSTS` (e.g. `youtu.be`) | raises `InvalidChannelUrlError` — short links are NOT resolved |

`_YOUTUBE_HOSTS` is an exact allow-list (`youtube.com`, `www.`, `m.`,
`music.`) — subdomains not in the set are rejected rather than silently
matched with a suffix check (avoids `evilyoutube.com` style bypass).

### Error/control flow

```
ScraperError (base)
├── InvalidChannelUrlError   – urls.py, before any network call
├── ChannelFetchError        – youtube.py, wraps requests.RequestException
└── NoVideosFoundError       – parsers.py, HTML or feed parsed but empty
```

`fetch_latest_video` control flow on `NoVideosFoundError` from the HTML
path: if no `channel_id` could be scraped from the page either, the
original exception re-raises (no channel_id → no feed URL possible).
Otherwise it silently retries via the Atom feed — this is the **only**
retry/fallback in the codebase; there is no retry on `ChannelFetchError`
(network failures are not retried, they propagate immediately).

### Session handling

`fetch_latest_video` creates its own `requests.Session()` when none is
passed and closes it in a `finally` (`owns_session` flag) — but if you pass
your own session (e.g. to reuse connections across many channels in a
loop), you own its lifecycle and headers get mutated in place
(`session.headers.update(DEFAULT_HEADERS)` — this **mutates the caller's
session** rather than copying headers, so a shared session's headers
change after the first call).

### State file (`scanner.py`) durability

`_save_state` writes to `<state_file>.tmp` then `Path.replace()`, which is
atomic on POSIX and on Windows (NTFS) for same-volume renames — protects
against a half-written JSON file if the process is killed mid-write.
Not protected against concurrent `run_forever` processes on the same
`state_file` (no file locking) — running two watchers against the same
state file is a race condition, don't do it.

### `_is_members_only` cost

O(all string nodes in the renderer subtree) per video candidate — cheap in
practice (single renderer, not the whole page tree) but note it's a full
`_walk()` over the *matched renderer only*, not the whole `ytInitialData`
document.

### Concurrency / async

None. Fully synchronous, single-threaded, blocking `requests` calls
throughout. `run_forever` is a blocking `while True` + `time.sleep` loop —
one channel per process. Watching N channels means N processes (or a
future rewrite), not a built-in feature.

### Dependency/version notes

- `requests-toolbelt`-style retry/backoff is **not** implemented — one
  `session.get()` attempt per call, `raise_for_status()` converts 4xx/5xx
  into `ChannelFetchError` immediately.
- `python-dotenv` `load_dotenv()` is called at import time in `scanner.py`
  (module-level side effect) — importing `scanner` anywhere loads `.env`
  from CWD, which matters if you embed this in a larger app.
- Target Python `>=3.9` (see `pyproject.toml`) — code avoids 3.10+ syntax
  (no `match` statements, no `X | Y` unions in runtime-evaluated positions).
