import json

from autovideodownloadservice.models import Video
from autovideodownloadservice.scanner import scan_once


def _video(video_id, members_only=False):
    return Video(
        video_id=video_id,
        title=f"Video {video_id}",
        url=f"https://www.youtube.com/watch?v={video_id}",
        members_only=members_only,
    )


def test_scan_once_baselines_without_notifying(tmp_path):
    state_file = tmp_path / "state.json"
    notifications = []

    sent = scan_once(
        "@creator",
        state_file,
        notifications.append,
        fetch=lambda _: _video("first"),
    )

    assert sent is False
    assert notifications == []
    assert json.loads(state_file.read_text()) == {
        "video_id": "first",
        "members_only": False,
    }


def test_scan_once_notifies_only_when_video_id_changes(tmp_path):
    state_file = tmp_path / "state.json"
    notifications = []

    scan_once("@creator", state_file, notifications.append, fetch=lambda _: _video("first"))
    assert scan_once(
        "@creator", state_file, notifications.append, fetch=lambda _: _video("first")
    ) is False
    assert scan_once(
        "@creator", state_file, notifications.append, fetch=lambda _: _video("second")
    ) is True

    assert [video.video_id for video in notifications] == ["second"]
    assert json.loads(state_file.read_text()) == {
        "video_id": "second",
        "members_only": False,
    }


def test_scan_once_skips_members_only_video(tmp_path):
    state_file = tmp_path / "state.json"
    notifications = []

    scan_once(
        "@creator",
        state_file,
        notifications.append,
        fetch=lambda _: _video("members", members_only=True),
    )

    assert notifications == []
    assert json.loads(state_file.read_text())["members_only"] is True


def test_scan_once_skips_unknown_membership_status(tmp_path):
    state_file = tmp_path / "state.json"
    notifications = []

    scan_once("@creator", state_file, notifications.append, fetch=lambda _: _video("first"))
    scan_once(
        "@creator",
        state_file,
        notifications.append,
        fetch=lambda _: Video(
            video_id="unknown",
            title="Unknown status",
            url="https://www.youtube.com/watch?v=unknown",
        ),
    )

    assert notifications == []


def test_scan_once_notifies_when_members_only_video_becomes_public(tmp_path):
    state_file = tmp_path / "state.json"
    notifications = []

    scan_once(
        "@creator",
        state_file,
        notifications.append,
        fetch=lambda _: _video("video", members_only=True),
    )
    assert scan_once(
        "@creator",
        state_file,
        notifications.append,
        fetch=lambda _: _video("video", members_only=False),
    ) is True

    assert [video.video_id for video in notifications] == ["video"]


def test_scan_once_keeps_previous_id_when_notification_fails(tmp_path):
    state_file = tmp_path / "state.json"
    scan_once("@creator", state_file, lambda _: None, fetch=lambda _: _video("first"))

    def fail(_):
        raise RuntimeError("mail server unavailable")

    try:
        scan_once("@creator", state_file, fail, fetch=lambda _: _video("second"))
    except RuntimeError:
        pass

    assert json.loads(state_file.read_text()) == {
        "video_id": "first",
        "members_only": False,
    }