"""Command line interface. A future HTTP API can reuse ``fetch_latest_video``."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .exceptions import ScraperError
from .models import Video
from .scanner import run_forever
from .scraper import fetch_latest_video


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube-alerts",
        description="Print the latest video uploaded to a YouTube channel.",
    )
    parser.add_argument(
        "url",
        help="Channel URL or handle, e.g. https://www.youtube.com/@beyondASI/videos",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a summary.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously scan and email when a new video appears.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconds between watch scans (default: 300).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(".yta-state.json"),
        help="File used to remember the last seen video.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser


def _format_human(video: Video) -> str:
    rows = [
        ("Channel", video.channel_name),
        ("Title", video.title),
        ("Video ID", video.video_id),
        ("URL", video.url),
        ("Published", video.published_at or video.published_text),
        ("Duration", video.duration_text),
        ("Views", video.view_count_text),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Latest video", "-" * 40]
    lines += [f"{label:<{width}} : {value}" for label, value in rows if value]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.watch:
        try:
            run_forever(args.url, args.interval, args.state_file)
        except KeyboardInterrupt:
            print("Scanner stopped.")
            return 0
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    try:
        video = fetch_latest_video(args.url)
    except ScraperError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(video.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(_format_human(video))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
