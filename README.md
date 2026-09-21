# youtube-alerts

Watch any YouTube channel and get an **email the moment a new video drops**.

Point it at a channel, and it scrapes the channel's uploads tab to find the
latest video. Run it once for a quick check, or leave it running to
continuously monitor and alert you.

```powershell
youtube-alerts "@MKBHD"
```

```
Latest video
----------------------------------------
Channel   : Marques Brownlee
Title     : The Best Phone of 2026!
Video ID  : dQw4w9WgXcQ
URL       : https://www.youtube.com/watch?v=dQw4w9WgXcQ
Published : 2 hours ago
Duration  : 18:42
Views     : 1.2M views
```

---

## Table of contents

- [youtube-alerts](#youtube-alerts)
  - [Table of contents](#table-of-contents)
  - [Features](#features)
  - [Requirements](#requirements)
  - [Setup](#setup)
    - [1. Create a virtual environment (required)](#1-create-a-virtual-environment-required)
    - [2. Install dependencies](#2-install-dependencies)
    - [3. Create your `.env` file (required for email alerts)](#3-create-your-env-file-required-for-email-alerts)
  - [Usage](#usage)
    - [One-off check](#one-off-check)
    - [JSON output](#json-output)
    - [Continuous monitoring with email alerts](#continuous-monitoring-with-email-alerts)
    - [Accepted channel formats](#accepted-channel-formats)
    - [Flags](#flags)
  - [Email alerts](#email-alerts)
    - [How the watcher decides to email you](#how-the-watcher-decides-to-email-you)
    - [Gmail setup](#gmail-setup)
  - [Running tests](#running-tests)
  - [Project structure](#project-structure)
    - [How it works](#how-it-works)
  - [Hosting on Azure](#hosting-on-azure)
  - [Documentation](#documentation)
  - [Troubleshooting](#troubleshooting)
  - [Notes and limitations](#notes-and-limitations)
  - [Roadmap](#roadmap)

---

## Features

- **Find the latest upload** from any YouTube channel — no API key required
- **Flexible channel input** — `@handle`, channel name, `UC...` ID, or full URL
- **Continuous watching** — scan on an interval and email you when a new video appears
- **Smart notifications** — skips members-only videos, no duplicate alerts, and
  no spam on first run
- **Resilient** — falls back to YouTube's RSS feed if page scraping fails
- **JSON output** — machine-readable, ready for an API or another tool
- **Cloud-ready** — [deployable to Azure](#hosting-on-azure) for ~$0/month

---

## Requirements

- **Python 3.9 or newer**
- An email account with SMTP access (only needed for the `--watch` alerts).
  Gmail works well — see [Email alerts](#email-alerts).

---

## Setup

> All commands below are for **PowerShell on Windows**. On macOS/Linux, swap
> the activation step for `source .venv/bin/activate`.

### 1. Create a virtual environment (required)

A virtual environment keeps this project's dependencies isolated from your
system Python. **Do not skip this step.**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your prompt should now be prefixed with `(.venv)`. To leave the environment
later, run `deactivate`.

> **If activation is blocked** with a "running scripts is disabled" error, run
> this once and try again:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### 2. Install dependencies

```powershell
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

The last command installs the project in editable mode and gives you the
`youtube-alerts` command.

### 3. Create your `.env` file (required for email alerts)

The project **does not ship with a `.env` file** — you must create one
yourself. A template is provided:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and fill in your real values:

```ini
YTA_SMTP_HOST=smtp.gmail.com
YTA_SMTP_PORT=587
YTA_SMTP_USERNAME=your-account@gmail.com
YTA_SMTP_PASSWORD=your-app-password
YTA_ALERT_FROM=your-account@gmail.com
YTA_ALERT_TO=your-alert-address@example.com
```

| Variable | Required | Description |
|---|---|---|
| `YTA_SMTP_HOST` | Yes | SMTP server hostname |
| `YTA_SMTP_PORT` | No | SMTP port (defaults to `587`) |
| `YTA_SMTP_USERNAME` | Yes | SMTP login username |
| `YTA_SMTP_PASSWORD` | Yes | SMTP password or **app password** |
| `YTA_ALERT_FROM` | No | Sender address (defaults to the username) |
| `YTA_ALERT_TO` | Yes | Where alerts get delivered |

> ⚠️ **Never commit your `.env` file.** It contains credentials and is already
> excluded via `.gitignore`.

> 💡 The `.env` file is only needed for `--watch`. One-off lookups work
> without it.

---

## Usage

### One-off check

```powershell
youtube-alerts "@MKBHD"
```

Or without installing the package:

```powershell
python -m youtubealerts "@MKBHD"
```

### JSON output

```powershell
youtube-alerts "@MKBHD" --json
```

### Continuous monitoring with email alerts

```powershell
youtube-alerts "@MKBHD" --watch
```

Keep the terminal open — press `Ctrl+C` to stop.

### Accepted channel formats

All of these resolve to the same channel:

| Input | Notes |
|---|---|
| `@MKBHD` | Handle |
| `MKBHD` | Bare name (treated as a handle) |
| `youtube.com/c/MKBHD` | Partial URL |
| `https://www.youtube.com/@MKBHD/videos` | Full URL |
| `https://www.youtube.com/channel/UC...` | Channel ID URL |
| `UCBJycsmduvYEL83R_U4JriQ` | Raw channel ID |

Any channel tab (`/streams`, `/about`, `/community`, …) is automatically
rewritten to `/videos`.

### Flags

| Flag | Default | Description |
|---|---|---|
| `--json` | off | Emit JSON instead of a formatted summary |
| `--watch` | off | Continuously scan and email on new uploads |
| `--interval SECONDS` | `300` | Seconds between scans in watch mode |
| `--state-file PATH` | `.yta-state.json` | Where the last seen video is remembered |
| `-v`, `--verbose` | off | Enable debug logging |

---

## Email alerts

### How the watcher decides to email you

1. **First scan** records the current latest video as a baseline — **no email
   is sent.** This prevents a burst of alerts when you first start watching.
2. Every subsequent scan compares the latest video ID against the saved state.
3. An email is sent only when the video ID **changes** *and* the video is
   **public**.
4. Members-only videos are recorded but never emailed — if one later becomes
   public, you get the alert then.

State is kept in `.yta-state.json` (configurable with `--state-file`) and
written atomically, so killing the process mid-write won't corrupt it.

### Gmail setup

Gmail blocks regular passwords for SMTP. You need an **App Password**:

1. Enable 2-Step Verification on your Google account
2. Go to **Google Account → Security → App passwords**
3. Generate a password for "Mail"
4. Paste the 16-character value into `YTA_SMTP_PASSWORD` in your `.env`

---

## Running tests

```powershell
pytest
```

The test suite runs entirely offline — no network calls, no real emails.
Parsers are tested against saved fixtures, and the scanner is tested with
injected fakes.

---

## Project structure

```
src/youtubealerts/
  cli.py              # terminal entry point (argparse)
  config.py           # request headers, timeouts, URL templates
  models.py           # Video dataclass
  exceptions.py       # ScraperError hierarchy
  scanner.py          # watch loop, state tracking, email notifications
  scraper/
    youtube.py        # network calls + orchestration
    parsers.py        # pure HTML/JSON/XML parsing (unit tested)
    urls.py           # channel URL normalisation
tests/                # pytest suite, no network access required
docs/                 # architecture + deployment guides
```

### How it works

1. The channel URL is normalised to `https://www.youtube.com/<channel>/videos`.
2. The page is fetched with a desktop user agent and `hl=en`, so YouTube
   inlines its `ytInitialData` JSON blob.
3. That blob is extracted with a string-aware brace scan, and the first video
   entry is returned — the uploads tab is sorted newest-first.
4. If YouTube serves a JS-only shell with no video data, the channel's Atom
   uploads feed (`/feeds/videos.xml?channel_id=...`) is used as a fallback.

---

## Hosting on Azure

Running locally is **completely free**, but the watcher only works while your
machine is on and the terminal is running.

To keep it running 24/7, you can deploy it to **Azure Functions** on the
Consumption plan for roughly **$0–$1/month** — the free execution grant covers
this workload, and you only pay a few cents for storage.

The cloud version also gives you:

- An **on/off toggle** in the Azure Portal — pause and resume scanning without
  touching code or redeploying
- A **changeable channel** via an app setting — switch which channel you're
  watching from the Portal, no redeploy needed

👉 Full step-by-step instructions: **[docs/AZURE_DEPLOYMENT.md](docs/AZURE_DEPLOYMENT.md)**

---

## Documentation

The `docs/` folder contains two guides:

| Document | What it's for | Read it when… |
|---|---|---|
| **[docs/CODEBASE.md](docs/CODEBASE.md)** | Complete technical walkthrough of the code — architecture, file-by-file breakdown, data flow, function signatures, parsing internals, edge cases, and gotchas | You want to understand, modify, or debug the code |
| **[docs/AZURE_DEPLOYMENT.md](docs/AZURE_DEPLOYMENT.md)** | Step-by-step Azure deployment guide — resource setup, code changes, secrets, cost breakdown, on/off toggle, and cleanup | You want to run this in the cloud instead of on your machine |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `youtube-alerts` command not found | Activate your venv, then run `pip install -e .` |
| Script activation blocked | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `Missing email settings: ...` | Your `.env` is missing or incomplete — see [step 3](#3-create-your-env-file-required-for-email-alerts) |
| Gmail login fails | Use an **App Password**, not your account password |
| `Error: '...' is not a youtube.com URL` | Check the channel input format — `youtu.be` short links aren't supported |
| No email arrives on the first run | Expected — the first scan only sets a baseline |
| Parsing suddenly breaks | YouTube changed its markup; see [docs/CODEBASE.md](docs/CODEBASE.md) |

Add `-v` to any command for debug logging:

```powershell
youtube-alerts "@MKBHD" --watch -v
```

---

## Notes and limitations

- YouTube's page markup is **unofficial and changes without warning**. The RSS
  feed fallback exists for exactly that reason. All fragile parsing is isolated
  in `scraper/parsers.py`.
- Keep request volume modest — a 5-minute interval is plenty for most channels.
- The watcher handles **one channel per process**. Watching multiple channels
  means running multiple instances.
- Despite the project name, **there is no download step yet** — it detects new
  videos and notifies you. See below.

---

## Roadmap

- [ ] Expose `fetch_latest_video` over an HTTP API (FastAPI) for a frontend
- [ ] Multi-channel watching in a single process
- [ ] The actual video download step
