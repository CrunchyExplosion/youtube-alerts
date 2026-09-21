import json

import pytest

from youtubealerts.exceptions import NoVideosFoundError
from youtubealerts.scraper.parsers import (
    extract_channel_id,
    extract_json_object,
    extract_yt_initial_data,
    parse_latest_video,
    parse_latest_video_from_feed,
)

CHANNEL_ID = "UCBJycsmduvYEL83R_U4JriQ"


def _initial_data(video_ids):
    return {
        "metadata": {"channelMetadataRenderer": {"title": "Marques Brownlee"}},
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "content": {
                                "richGridRenderer": {
                                    "contents": [
                                        {
                                            "richItemRenderer": {
                                                "content": {
                                                    "videoRenderer": {
                                                        "videoId": video_id,
                                                        "title": {
                                                            "runs": [{"text": f"Video {video_id}"}]
                                                        },
                                                        "publishedTimeText": {
                                                            "simpleText": "2 days ago"
                                                        },
                                                        "lengthText": {"simpleText": "12:34"},
                                                        "viewCountText": {
                                                            "simpleText": "1,234,567 views"
                                                        },
                                                        "thumbnail": {
                                                            "thumbnails": [
                                                                {"url": "https://img/small.jpg"},
                                                                {"url": "https://img/large.jpg"},
                                                            ]
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                        for video_id in video_ids
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        },
    }


def _lockup_data(video_ids):
    """Mirrors the current channel grid format YouTube serves."""
    return {
        "metadata": {"channelMetadataRenderer": {"title": "Marques Brownlee"}},
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "selected": True,
                            "content": {
                                "richGridRenderer": {
                                    "contents": [
                                        {
                                            "richItemRenderer": {
                                                "content": {
                                                    "lockupViewModel": {
                                                        "contentId": video_id,
                                                        "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                                                        "contentImage": {
                                                            "thumbnailViewModel": {
                                                                "image": {
                                                                    "sources": [
                                                                        {"url": "https://img/360.jpg"},
                                                                        {"url": "https://img/720.jpg"},
                                                                    ]
                                                                },
                                                                "overlays": [
                                                                    {
                                                                        "thumbnailBottomOverlayViewModel": {
                                                                            "badges": [
                                                                                {
                                                                                    "thumbnailBadgeViewModel": {
                                                                                        "text": "16:36"
                                                                                    }
                                                                                }
                                                                            ]
                                                                        }
                                                                    }
                                                                ],
                                                            }
                                                        },
                                                        "metadata": {
                                                            "lockupMetadataViewModel": {
                                                                "title": {
                                                                    "content": f"Video {video_id}"
                                                                },
                                                                "metadata": {
                                                                    "contentMetadataViewModel": {
                                                                        "metadataRows": [
                                                                            {
                                                                                "metadataParts": [
                                                                                    {
                                                                                        "text": {
                                                                                            "content": "10M views"
                                                                                        }
                                                                                    },
                                                                                    {
                                                                                        "text": {
                                                                                            "content": "4 days ago"
                                                                                        }
                                                                                    },
                                                                                ]
                                                                            }
                                                                        ]
                                                                    }
                                                                },
                                                            }
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                        for video_id in video_ids
                                    ]
                                }
                            },
                        }
                    }
                ]
            }
        },
    }


def test_extract_json_object_handles_braces_inside_strings():
    text = 'var x = {"a": "}{ not real", "b": {"c": 1}}; more'
    start = text.index("{")
    extracted = extract_json_object(text, start)
    assert json.loads(extracted) == {"a": "}{ not real", "b": {"c": 1}}


def test_extract_json_object_rejects_unterminated_literal():
    with pytest.raises(ValueError):
        extract_json_object('{"a": 1', 0)


def test_extract_yt_initial_data_from_html():
    payload = _initial_data(["abc12345678"])
    html = (
        "<html><body><script>var ytInitialData = "
        + json.dumps(payload)
        + ";</script></body></html>"
    )
    assert extract_yt_initial_data(html) == payload


def test_extract_yt_initial_data_raises_when_absent():
    with pytest.raises(NoVideosFoundError):
        extract_yt_initial_data("<html><body>no data here</body></html>")


def test_extract_channel_id():
    assert extract_channel_id(f'{{"externalId":"{CHANNEL_ID}"}}') == CHANNEL_ID
    assert extract_channel_id("{}") is None


def test_parse_latest_video_returns_first_grid_item():
    video = parse_latest_video(_initial_data(["newest00001", "older000002"]))

    assert video.video_id == "newest00001"
    assert video.title == "Video newest00001"
    assert video.url == "https://www.youtube.com/watch?v=newest00001"
    assert video.channel_name == "Marques Brownlee"
    assert video.published_text == "2 days ago"
    assert video.duration_text == "12:34"
    assert video.view_count_text == "1,234,567 views"
    assert video.thumbnail_url == "https://img/large.jpg"
    assert video.members_only is False
    assert video.source == "html"


def test_parse_latest_video_raises_when_no_renderers():
    with pytest.raises(NoVideosFoundError):
        parse_latest_video({"contents": {}})


def test_parse_latest_video_reads_lockup_view_model():
    video = parse_latest_video(_lockup_data(["newest00001", "older000002"]))

    assert video.video_id == "newest00001"
    assert video.title == "Video newest00001"
    assert video.url == "https://www.youtube.com/watch?v=newest00001"
    assert video.channel_name == "Marques Brownlee"
    assert video.view_count_text == "10M views"
    assert video.published_text == "4 days ago"
    assert video.duration_text == "16:36"
    assert video.thumbnail_url == "https://img/720.jpg"
    assert video.members_only is False
    assert video.source == "html"


def test_parse_latest_video_detects_members_only_renderer():
    data = _initial_data(["newest00001"])
    renderer = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0][
        "tabRenderer"
    ]["content"]["richGridRenderer"]["contents"][0]["richItemRenderer"]["content"][
        "videoRenderer"
    ]
    renderer["badges"] = [{"metadataBadgeRenderer": {"label": "Members only"}}]

    assert parse_latest_video(data).members_only is True


def test_parse_latest_video_reads_icon_only_view_count():
    """YouTube renders some view counts as a bare '2.6M' next to an icon."""
    data = _lockup_data(["newest00001"])
    row = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"][
        "content"
    ]["richGridRenderer"]["contents"][0]["richItemRenderer"]["content"]["lockupViewModel"][
        "metadata"
    ][
        "lockupMetadataViewModel"
    ][
        "metadata"
    ][
        "contentMetadataViewModel"
    ][
        "metadataRows"
    ][
        0
    ]
    row["metadataParts"][0] = {
        "text": {"content": "2.6M"},
        "accessibilityLabel": "2.6 million views",
    }

    video = parse_latest_video(data)
    assert video.view_count_text == "2.6M"
    assert video.published_text == "4 days ago"


def test_parse_latest_video_skips_non_video_lockups():
    data = _lockup_data(["newest00001"])
    grid = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"][
        "content"
    ]["richGridRenderer"]
    playlist = json.loads(json.dumps(grid["contents"][0]))
    playlist["richItemRenderer"]["content"]["lockupViewModel"][
        "contentType"
    ] = "LOCKUP_CONTENT_TYPE_PLAYLIST"
    grid["contents"].insert(0, playlist)

    assert parse_latest_video(data).video_id == "newest00001"


FEED_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <yt:channelId>{CHANNEL_ID[2:]}</yt:channelId>
  <author><name>Marques Brownlee</name></author>
  <entry>
    <yt:videoId>newest00001</yt:videoId>
    <yt:channelId>{CHANNEL_ID}</yt:channelId>
    <title>The newest upload</title>
    <published>2026-09-20T15:00:00+00:00</published>
    <media:group>
      <media:thumbnail url="https://img/feed.jpg"/>
      <media:community><media:statistics views="4242"/></media:community>
    </media:group>
  </entry>
  <entry>
    <yt:videoId>older000002</yt:videoId>
    <title>An older upload</title>
  </entry>
</feed>
"""


def test_parse_latest_video_from_feed():
    video = parse_latest_video_from_feed(FEED_XML)

    assert video.video_id == "newest00001"
    assert video.title == "The newest upload"
    assert video.channel_id == CHANNEL_ID
    assert video.channel_name == "Marques Brownlee"
    assert video.published_at == "2026-09-20T15:00:00+00:00"
    assert video.view_count_text == "4242"
    assert video.thumbnail_url == "https://img/feed.jpg"
    assert video.members_only is None
    assert video.source == "feed"


def test_parse_latest_video_from_feed_rejects_empty_feed():
    empty = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    with pytest.raises(NoVideosFoundError):
        parse_latest_video_from_feed(empty)


def test_parse_latest_video_from_feed_restores_uc_prefix():
    xml_text = FEED_XML.replace(f"    <yt:channelId>{CHANNEL_ID}</yt:channelId>\n", "")
    assert parse_latest_video_from_feed(xml_text).channel_id == CHANNEL_ID
