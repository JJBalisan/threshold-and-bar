"""Tests for the channel-level directory opt-out tags in build_feed.py."""

import datetime

import build_feed

BASE = "https://example.github.io/x"
EP = {
    "no": 7,
    "date": "2026-10-13",
    "title": "T",
    "summary": "S",
    "file": "audio/ep007.mp3",
    "bytes": 1,
    "duration": "00:01:00",
}
NOW = datetime.datetime(2026, 10, 13, tzinfo=datetime.timezone.utc)


def _channel_head(feed):
    return feed.split("<item>")[0]


def test_channel_blocks_apple_directory():
    feed = build_feed.render([EP], BASE, NOW)
    assert "<itunes:block>Yes</itunes:block>" in _channel_head(feed)


def test_channel_is_locked_to_the_owner():
    feed = build_feed.render([EP], BASE, NOW)
    expected = (
        f'<podcast:locked owner="{build_feed.EMAIL}">yes</podcast:locked>'
    )
    assert expected in _channel_head(feed)
