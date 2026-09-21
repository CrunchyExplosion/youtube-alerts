"""YouTube alerts.

Currently exposes a single capability: find the latest video uploaded to a
YouTube channel. The public surface is kept small so a future API layer can
import it directly.
"""

from .models import Video
from .scraper import fetch_latest_video

__all__ = ["Video", "fetch_latest_video"]
__version__ = "0.1.0"
