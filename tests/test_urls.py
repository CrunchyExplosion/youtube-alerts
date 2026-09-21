import pytest

from autovideodownloadservice.exceptions import InvalidChannelUrlError
from autovideodownloadservice.scraper.urls import normalize_channel_videos_url

EXPECTED = "https://www.youtube.com/@channelname/videos"


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.youtube.com/@channelname",
        "https://www.youtube.com/@channelname/videos",
        "https://www.youtube.com/@channelname/streams",
        "http://youtube.com/@channelname/featured",
        "youtube.com/@channelname",
        "m.youtube.com/@channelname/videos",
        "@channelname",
        "channelname",
    ],
)
def test_normalizes_to_videos_tab(raw):
    assert normalize_channel_videos_url(raw) == EXPECTED


def test_preserves_channel_id_path():
    url = "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ"
    assert normalize_channel_videos_url(url) == url + "/videos"


def test_preserves_legacy_user_path():
    url = "https://www.youtube.com/user/LinusTechTips/videos"
    assert normalize_channel_videos_url(url) == url


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "https://vimeo.com/@channelname",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/feed/subscriptions",
    ],
)
def test_rejects_non_channel_urls(raw):
    with pytest.raises(InvalidChannelUrlError):
        normalize_channel_videos_url(raw)
