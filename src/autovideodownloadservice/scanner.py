"""Continuous channel monitoring and email notifications."""

import json
import logging
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv

from .models import Video
from .scraper import fetch_latest_video

logger = logging.getLogger(__name__)
load_dotenv()


class EmailNotifier:
    """Send new-video notifications through an SMTP server."""

    def __init__(self) -> None:
        self.host = os.environ.get("AVDS_SMTP_HOST")
        self.port = int(os.environ.get("AVDS_SMTP_PORT", "587"))
        self.username = os.environ.get("AVDS_SMTP_USERNAME")
        self.password = os.environ.get("AVDS_SMTP_PASSWORD")
        self.sender = os.environ.get("AVDS_ALERT_FROM") or self.username
        self.recipient = os.environ.get("AVDS_ALERT_TO")

        missing = [
            name
            for name, value in (
                ("AVDS_SMTP_HOST", self.host),
                ("AVDS_SMTP_USERNAME", self.username),
                ("AVDS_SMTP_PASSWORD", self.password),
                ("AVDS_ALERT_TO", self.recipient),
            )
            if not value
        ]
        if missing or not self.sender:
            raise ValueError(f"Missing email settings: {', '.join(missing)}")

    def send(self, video: Video) -> None:
        message = EmailMessage()
        message["Subject"] = f"Hey, a new video just dropped: {video.title}"
        message["From"] = self.sender
        message["To"] = self.recipient
        message.set_content(
            f"Hey! A new video from {video.channel_name or 'your favorite creator'} "
            "just dropped.\n\n"
            f"Title: {video.title}\n"
            f"Watch it here: {video.url}\n\n"
            "Enjoy the video!"
        )

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(message)


def _load_state(state_file: Path) -> tuple[Optional[str], Optional[bool]]:
    if not state_file.exists():
        return None, None
    with state_file.open(encoding="utf-8") as handle:
        state = json.load(handle)
    video_id = state.get("video_id")
    members_only = state.get("members_only")
    return (
        video_id if isinstance(video_id, str) else None,
        members_only if isinstance(members_only, bool) else None,
    )


def _save_state(state_file: Path, video: Video) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = state_file.with_suffix(state_file.suffix + ".tmp")
    with temporary_file.open("w", encoding="utf-8") as handle:
        json.dump(
            {"video_id": video.video_id, "members_only": video.members_only},
            handle,
        )
    temporary_file.replace(state_file)


def scan_once(
    channel_url: str,
    state_file: Path,
    notify: Callable[[Video], None],
    fetch: Callable[[str], Video] = fetch_latest_video,
) -> bool:
    """Check once and return whether a new video notification was sent."""
    video = fetch(channel_url)
    previous_video_id, previous_members_only = _load_state(state_file)

    if previous_video_id is None:
        _save_state(state_file, video)
        logger.info("Monitoring latest video: %s", video.title)
        return False

    is_new_video = video.video_id != previous_video_id
    became_public = video.members_only is False and previous_members_only is not False
    if not is_new_video and not became_public:
        logger.info("No new video; latest is %s", video.video_id)
        return False

    if video.members_only is not False:
        _save_state(state_file, video)
        logger.info("Skipping non-public video %s", video.video_id)
        return False

    notify(video)
    _save_state(state_file, video)
    logger.info("Notification sent for %s", video.video_id)
    return True


def run_forever(
    channel_url: str,
    interval_seconds: int = 300,
    state_file: Path = Path(".avds-state.json"),
    notify: Optional[Callable[[Video], None]] = None,
    fetch: Callable[[str], Video] = fetch_latest_video,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Monitor a channel until interrupted."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")
    notify = notify or EmailNotifier().send

    while True:
        try:
            scan_once(channel_url, state_file, notify, fetch)
        except Exception:
            logger.exception("Channel scan failed; will retry")
        sleep(interval_seconds)