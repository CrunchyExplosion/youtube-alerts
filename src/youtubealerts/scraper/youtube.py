"""Network-facing entry point for retrieving a channel's latest upload."""

import logging
from typing import Optional

import requests

from ..config import (
    DEFAULT_HEADERS,
    LOCALE_QUERY,
    REQUEST_TIMEOUT_SECONDS,
    RSS_FEED_URL_TEMPLATE,
)
from ..exceptions import ChannelFetchError, NoVideosFoundError
from ..models import Video
from .parsers import (
    extract_channel_id,
    extract_yt_initial_data,
    parse_latest_video,
    parse_latest_video_from_feed,
)
from .urls import normalize_channel_videos_url

logger = logging.getLogger(__name__)


def _get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ChannelFetchError(f"Failed to fetch {url}: {exc}") from exc
    return response


def _latest_from_feed(session: requests.Session, channel_id: str) -> Video:
    feed_url = RSS_FEED_URL_TEMPLATE.format(channel_id=channel_id)
    logger.debug("Falling back to uploads feed: %s", feed_url)
    response = _get(session, feed_url)
    video = parse_latest_video_from_feed(response.text)
    return video


def fetch_latest_video(channel_url: str, session: Optional[requests.Session] = None) -> Video:
    """Return the most recently uploaded video for the given channel.

    ``channel_url`` may be any channel form: ``/@handle``, ``/c/Name``,
    ``/user/Name``, ``/channel/UC...``, with or without a trailing tab.
    """
    videos_url = normalize_channel_videos_url(channel_url)
    logger.debug("Resolved channel URL to %s", videos_url)

    owns_session = session is None
    session = session or requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    try:
        response = _get(session, videos_url, params=LOCALE_QUERY)
        html = response.text
        channel_id = extract_channel_id(html)

        try:
            video = parse_latest_video(extract_yt_initial_data(html))
        except NoVideosFoundError:
            # YouTube occasionally serves a consent/JS-only shell with no
            # renderers. The uploads feed is a stable fallback.
            if not channel_id:
                raise
            logger.debug("HTML parse yielded no videos; using the uploads feed.")
            return _latest_from_feed(session, channel_id)

        if channel_id and not video.channel_id:
            video = Video(**{**video.to_dict(), "channel_id": channel_id})
        return video
    finally:
        if owns_session:
            session.close()
