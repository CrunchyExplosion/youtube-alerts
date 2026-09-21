"""Pure parsing helpers: HTML/JSON in, :class:`Video` out.

Kept free of network calls so they can be unit tested against saved fixtures.
"""

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..config import WATCH_URL_TEMPLATE
from ..exceptions import NoVideosFoundError
from ..models import Video

_YT_INITIAL_DATA_ASSIGNMENT = re.compile(
    r"""(?:var\s+ytInitialData|window\s*\[\s*["']ytInitialData["']\s*\]|ytInitialData)\s*=\s*""" 
)

_CHANNEL_ID_IN_HTML = re.compile(r'"(?:externalId|channelId)"\s*:\s*"(UC[\w-]{22})"')

_DURATION_TEXT = re.compile(r"^\d{1,2}(:\d{2}){1,2}$")

_ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def extract_json_object(text: str, start: int) -> str:
    """Return the JSON object literal that begins at ``text[start]``.

    ``json.JSONDecoder.raw_decode`` cannot be pointed at a slice cheaply for very
    large documents, so we do a brace scan that is aware of strings and escapes.
    """
    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected '{' at the given start offset.")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("Unterminated JSON object literal.")


def extract_yt_initial_data(html: str) -> Dict[str, Any]:
    """Pull the ``ytInitialData`` blob that YouTube inlines into channel pages."""
    for match in _YT_INITIAL_DATA_ASSIGNMENT.finditer(html):
        brace = html.find("{", match.end())
        if brace == -1 or brace - match.end() > 4:
            continue
        try:
            return json.loads(extract_json_object(html, brace))
        except (ValueError, json.JSONDecodeError):
            continue
    raise NoVideosFoundError("Could not locate ytInitialData in the channel page.")


def extract_channel_id(html: str) -> Optional[str]:
    match = _CHANNEL_ID_IN_HTML.search(html)
    return match.group(1) if match else None


def _walk(node: Any) -> Iterator[Any]:
    """Depth-first traversal of the decoded JSON tree, parents before children."""
    stack: List[Any] = [node]
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, dict):
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))


def _text(node: Any) -> Optional[str]:
    """Flatten YouTube's ``simpleText`` / ``runs`` text containers."""
    if not isinstance(node, dict):
        return None
    if isinstance(node.get("simpleText"), str):
        return node["simpleText"]
    runs = node.get("runs")
    if isinstance(runs, list):
        joined = "".join(run.get("text", "") for run in runs if isinstance(run, dict))
        return joined or None
    return None


def _best_thumbnail(renderer: Dict[str, Any]) -> Optional[str]:
    thumbnails = renderer.get("thumbnail", {}).get("thumbnails")
    if isinstance(thumbnails, list) and thumbnails:
        return thumbnails[-1].get("url")
    return None


def _is_members_only(node: Any) -> bool:
    """Detect YouTube's members-only badge text in a video payload."""
    for value in _walk(node):
        if isinstance(value, str) and "member" in value.lower() and "only" in value.lower():
            return True
    return False


def _renderer_to_video(renderer: Dict[str, Any], channel_name: Optional[str]) -> Optional[Video]:
    video_id = renderer.get("videoId")
    title = _text(renderer.get("title"))
    if not isinstance(video_id, str) or not title:
        return None

    view_count = _text(renderer.get("viewCountText")) or _text(
        renderer.get("shortViewCountText")
    )

    return Video(
        video_id=video_id,
        title=title,
        url=WATCH_URL_TEMPLATE.format(video_id=video_id),
        channel_name=channel_name,
        published_text=_text(renderer.get("publishedTimeText")),
        duration_text=_text(renderer.get("lengthText")),
        view_count_text=view_count,
        thumbnail_url=_best_thumbnail(renderer),
        members_only=_is_members_only(renderer),
        source="html",
    )


def _lockup_duration(thumbnail_view_model: Dict[str, Any]) -> Optional[str]:
    for overlay in thumbnail_view_model.get("overlays", []):
        if not isinstance(overlay, dict):
            continue
        bottom = overlay.get("thumbnailBottomOverlayViewModel", {})
        for badge in bottom.get("badges", []):
            text = badge.get("thumbnailBadgeViewModel", {}).get("text")
            if isinstance(text, str) and _DURATION_TEXT.match(text):
                return text
    return None


def _lockup_metadata_parts(metadata: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return ``(display_text, accessibility_label)`` for each metadata part.

    The label matters because YouTube sometimes renders a view count as a bare
    ``"2.6M"`` next to an icon, with ``"2.6 million views"`` only in the label.
    """
    rows = (
        metadata.get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )
    parts: List[Tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for part in row.get("metadataParts", []):
            if not isinstance(part, dict):
                continue
            content = part.get("text", {}).get("content")
            if isinstance(content, str) and content.strip():
                label = part.get("accessibilityLabel")
                parts.append(
                    (content.strip(), label.strip() if isinstance(label, str) else "")
                )
    return parts


def _lockup_to_video(lockup: Dict[str, Any], channel_name: Optional[str]) -> Optional[Video]:
    """Convert YouTube's newer ``lockupViewModel`` grid item into a :class:`Video`."""
    if lockup.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
        return None

    video_id = lockup.get("contentId")
    metadata = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
    title = metadata.get("title", {}).get("content")
    if not isinstance(video_id, str) or not isinstance(title, str) or not title:
        return None

    view_count_text = None
    published_text = None
    for content, label in _lockup_metadata_parts(metadata):
        haystack = f"{content} {label}".lower()
        if view_count_text is None and "view" in haystack:
            view_count_text = content
        elif published_text is None and ("ago" in haystack or "streamed" in haystack):
            published_text = content

    thumbnail_view_model = lockup.get("contentImage", {}).get("thumbnailViewModel", {})
    sources = thumbnail_view_model.get("image", {}).get("sources")
    thumbnail_url = (
        sources[-1].get("url") if isinstance(sources, list) and sources else None
    )

    return Video(
        video_id=video_id,
        title=title,
        url=WATCH_URL_TEMPLATE.format(video_id=video_id),
        channel_name=channel_name,
        published_text=published_text,
        duration_text=_lockup_duration(thumbnail_view_model),
        view_count_text=view_count_text,
        thumbnail_url=thumbnail_url,
        members_only=_is_members_only(lockup),
        source="html",
    )


def _channel_name(data: Dict[str, Any]) -> Optional[str]:
    metadata = data.get("metadata", {}).get("channelMetadataRenderer", {})
    name = metadata.get("title")
    return name if isinstance(name, str) else None


def parse_latest_video(data: Dict[str, Any]) -> Video:
    """Return the first video rendered on the channel's uploads tab.

    The ``/videos`` tab is sorted newest-first by default, so document order is
    upload order. Both the legacy ``videoRenderer`` and the current
    ``lockupViewModel`` grid formats are supported.
    """
    channel_name = _channel_name(data)

    for node in _walk(data):
        if not isinstance(node, dict):
            continue

        renderer = node.get("videoRenderer") or node.get("gridVideoRenderer")
        if isinstance(renderer, dict):
            video = _renderer_to_video(renderer, channel_name)
            if video is not None:
                return video

        lockup = node.get("lockupViewModel")
        if isinstance(lockup, dict):
            video = _lockup_to_video(lockup, channel_name)
            if video is not None:
                return video

    raise NoVideosFoundError("The channel page contained no video entries.")


def parse_latest_video_from_feed(xml_text: str) -> Video:
    """Parse the channel's Atom uploads feed, which is already newest-first."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise NoVideosFoundError(f"Channel feed was not valid XML: {exc}") from exc

    channel_name = root.findtext("atom:author/atom:name", default=None, namespaces=_ATOM_NS)

    entry = root.find("atom:entry", _ATOM_NS)
    if entry is None:
        raise NoVideosFoundError("The channel feed contained no video entries.")

    # The feed-level <yt:channelId> drops the "UC" prefix; the entry-level one does not.
    channel_id = entry.findtext("yt:channelId", default=None, namespaces=_ATOM_NS)
    if not channel_id:
        feed_level = root.findtext("yt:channelId", default=None, namespaces=_ATOM_NS)
        if feed_level:
            channel_id = feed_level if feed_level.startswith("UC") else "UC" + feed_level

    video_id = entry.findtext("yt:videoId", default=None, namespaces=_ATOM_NS)
    title = entry.findtext("atom:title", default=None, namespaces=_ATOM_NS)
    if not video_id or not title:
        raise NoVideosFoundError("The channel feed entry was missing an id or title.")

    thumbnail_node = entry.find("media:group/media:thumbnail", _ATOM_NS)
    views_node = entry.find("media:group/media:community/media:statistics", _ATOM_NS)

    return Video(
        video_id=video_id,
        title=title,
        url=WATCH_URL_TEMPLATE.format(video_id=video_id),
        channel_name=channel_name,
        channel_id=channel_id,
        published_at=entry.findtext("atom:published", default=None, namespaces=_ATOM_NS),
        view_count_text=views_node.get("views") if views_node is not None else None,
        thumbnail_url=thumbnail_node.get("url") if thumbnail_node is not None else None,
        source="feed",
    )
