"""Tests for the optional <podcast:chapters> tag in build_feed.py."""

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


def test_item_without_chapters_has_no_chapters_tag():
    assert "podcast:chapters" not in build_feed.item(EP, BASE)


def test_item_with_chapters_links_the_json_file():
    ep = dict(EP, chapters="audio/ep007.chapters.json")
    out = build_feed.item(ep, BASE)
    assert (
        f'<podcast:chapters url="{BASE}/audio/ep007.chapters.json" '
        'type="application/json+chapters"/>'
    ) in out


def test_feed_declares_the_podcast_namespace():
    feed = build_feed.render([EP], BASE, NOW)
    assert 'xmlns:podcast="https://podcastindex.org/namespace/1.0"' in feed
