"""Static configuration for outbound requests to YouTube."""

WATCH_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"
RSS_FEED_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

REQUEST_TIMEOUT_SECONDS = 20

# YouTube serves a much simpler, parseable page when it believes the client is a
# regular desktop browser and when the locale is pinned to English.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Forces the English/consent-free variant of the page.
LOCALE_QUERY = {"hl": "en", "gl": "US"}
