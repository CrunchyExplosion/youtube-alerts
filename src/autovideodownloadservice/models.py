"""Domain models shared between the scraper, CLI and any future API layer."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    url: str
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    published_at: Optional[str] = None
    published_text: Optional[str] = None
    duration_text: Optional[str] = None
    view_count_text: Optional[str] = None
    thumbnail_url: Optional[str] = None
    members_only: Optional[bool] = None
    source: str = "html"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
