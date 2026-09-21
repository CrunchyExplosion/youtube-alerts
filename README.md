# autovideodownloadservice

Scrapes a YouTube channel page and returns the latest uploaded video.

Right now the result is printed to the terminal. The scraping logic lives behind a
single function (`fetch_latest_video`) so an HTTP API can be layered on later
without touching the scraper.

## Project layout

```
src/autovideodownloadservice/
  cli.py              # terminal entry point
  config.py           # request headers, timeouts, URL templates
  models.py           # Video dataclass
  exceptions.py       # ScraperError hierarchy
  scraper/
    youtube.py        # network calls + orchestration
    parsers.py        # pure HTML/JSON/XML parsing (unit tested)
    urls.py           # channel URL normalisation
tests/                # pytest suite, no network access required
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

## Usage

```powershell
python -m autovideodownloadservice "https://www.youtube.com/@MKBHD/videos"
```

Or, after `pip install -e .`:

```powershell
avds "@MKBHD" --json
```

Accepted inputs: `@handle`, `channelname`, `youtube.com/c/Name`,
`https://www.youtube.com/channel/UC.../videos`, and any channel tab URL — all are
normalised to the channel's `/videos` tab.

Flags:

- `--json` — machine-readable output (the same shape a future API will return)
- `--watch` — continuously scan and email when a new video appears
- `--interval SECONDS` — watch interval (default: `300`)
- `--state-file PATH` — file used to remember the last seen video
- `-v` / `--verbose` — debug logging

## Continuous email alerts

The watcher records the latest video ID in `.avds-state.json`. Its first scan
creates the baseline without sending an email; a message is sent only when the
video ID changes. Copy `.env.example` to `.env` and fill in your mail settings:

```powershell
Copy-Item .env.example .env
# Edit .env and add your SMTP details once.
avds "@TechwithShapingpixel" --watch
```

For Gmail, use an app password rather than your normal account password. Keep
the terminal or scheduled process running continuously; `Ctrl+C` stops it.

## How it works

1. The channel URL is normalised to `https://www.youtube.com/<channel>/videos`.
2. The page is fetched with a desktop user agent and `hl=en` so YouTube inlines
   the `ytInitialData` JSON blob.
3. That blob is extracted with a string-aware brace scan and the first
   `videoRenderer` is returned — the uploads tab is sorted newest-first.
4. If YouTube serves a JS-only shell with no renderers, the channel's Atom
   uploads feed (`/feeds/videos.xml?channel_id=...`) is used as a fallback.

## Tests

```powershell
pytest
```

## Notes

YouTube's page markup is unofficial and changes without warning; the feed
fallback exists for exactly that reason. Keep request volume modest.

## Next steps

- Expose `fetch_latest_video` over an HTTP API (FastAPI) for the frontend.
- Poll/schedule checks and persist seen video IDs.
- Add the actual download step.
