"""Normalisation helpers for the many shapes of YouTube channel URLs."""

import re
from urllib.parse import urlparse, urlunparse

from ..exceptions import InvalidChannelUrlError

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}

# Channel tabs that we are allowed to rewrite to /videos.
_KNOWN_TABS = {"videos", "featured", "streams", "shorts", "playlists", "community", "about"}

_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")


def normalize_channel_videos_url(raw_url: str) -> str:
    """Return the canonical ``/videos`` URL for a channel.

    Accepts full URLs (``https://www.youtube.com/@handle/videos``), partial URLs
    (``youtube.com/c/Name``) and bare identifiers (``@handle``, ``UC...``).
    """
    if not raw_url or not raw_url.strip():
        raise InvalidChannelUrlError("Channel URL must not be empty.")

    candidate = raw_url.strip()

    if "://" not in candidate:
        # Bare handle/id, or a host-less URL such as "youtube.com/@handle".
        if candidate.lower().startswith(("youtube.com", "www.youtube.com", "m.youtube.com")):
            candidate = "https://" + candidate
        elif candidate.startswith("@") or _CHANNEL_ID_RE.match(candidate):
            candidate = "https://www.youtube.com/" + candidate
        else:
            candidate = "https://www.youtube.com/@" + candidate.lstrip("/")

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    if host not in _YOUTUBE_HOSTS:
        raise InvalidChannelUrlError(f"'{raw_url}' is not a youtube.com URL.")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        raise InvalidChannelUrlError(f"'{raw_url}' does not point at a channel.")

    if segments[0] in {"watch", "shorts", "playlist", "results", "feed"}:
        raise InvalidChannelUrlError(
            f"'{raw_url}' looks like a video or feed URL, not a channel URL."
        )

    # Drop a trailing tab so we can pin the request to the uploads tab.
    if len(segments) > 1 and segments[-1].lower() in _KNOWN_TABS:
        segments = segments[:-1]

    path = "/" + "/".join(segments) + "/videos"
    return urlunparse(("https", "www.youtube.com", path, "", "", ""))
