#!/usr/bin/env python3
"""Rebuild feed.xml from episodes.json.

Base URL is derived from the git remote (user/repo -> https://user.github.io/repo)
unless given as argv[1] or $FEED_BASE.

Usage:

    python3 build_feed.py [BASE_URL]

Episodes are listed newest first. feed.xml is written next to this script.
"""

import datetime
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from email import utils as email_utils
from typing import Any, Optional
from xml.sax import saxutils

ROOT = os.path.dirname(os.path.abspath(__file__))
TITLE = "Threshold & Bar"
DESC = (
    "A weekly digest of middle- and long-distance running science, hybrid training for "
    "running and triathlon, and strength sports. Written and narrated by Claude."
)
AUTHOR, EMAIL, LANG = "Claude", "noreply@anthropic.com", "en-GB"
MUSIC_CREDIT = (
    " Music: intro and interludes from \u201cDans la tentative d\u2019accomplir quelque chose\u201d by "
    "Frederic Lardon feat. Laura Palm\u00e9e (CC0). Outro: \u201cCrap Transition\u201d by Jesse Spillane, "
    "https://freemusicarchive.org/music/Jesse_Spillane/Art_of_Presentation/Jesse_Spillane_-_Art_of_Presentation_-_04_Crap_Transition/ "
    "licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); trimmed, faded and mixed with narration."
)
COVER = "cover.jpg"  # 2000x2000 sRGB JPEG; Apple wants 1400-3000 px square, JPEG or PNG


def derive_base(argv: Sequence[str]) -> str:
    """Returns the public base URL the feed's links are built on.

    The first of these wins: argv[1], $FEED_BASE, or the GitHub Pages URL
    derived from the `origin` remote (user/repo becomes
    https://user.github.io/repo).

    Args:
        argv: The command line, program name first.

    Returns:
        The base URL as given, or the derived Pages URL with no trailing
        slash.

    Raises:
        SystemExit: If no URL was given and the origin remote is missing or
            is not a GitHub URL.
    """
    if len(argv) > 1:
        return argv[1]
    if os.environ.get("FEED_BASE"):
        return os.environ["FEED_BASE"]
    try:
        url = subprocess.check_output(
            ["git", "-C", ROOT, "remote", "get-url", "origin"], text=True
        ).strip()
    except Exception:
        sys.exit(
            "No origin remote yet. Pass the base URL: build_feed.py https://user.github.io/repo"
        )
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    if not m:
        sys.exit(f"Could not parse a GitHub user/repo from origin: {url}")
    return f"https://{m.group(1).lower()}.github.io/{m.group(2)}"


def item(e: Mapping[str, Any], base: str) -> str:
    """Renders one episode as an RSS <item> element.

    Args:
        e: An episodes.json entry with no, date, title, summary, file,
            bytes and duration keys, and an optional music flag that
            appends the music credit to the summary.
        base: The public base URL, without a trailing slash.

    Returns:
        The <item> element, indented for the channel, with no trailing
        newline.
    """
    summary = e["summary"] + (MUSIC_CREDIT if e.get("music") else "")
    pub = datetime.datetime.strptime(e["date"], "%Y-%m-%d").replace(
        hour=17, tzinfo=datetime.timezone.utc
    )
    return f"""    <item>
      <title>{saxutils.escape(e["title"])}</title>
      <description>{saxutils.escape(summary)}</description>
      <itunes:summary>{saxutils.escape(summary)}</itunes:summary>
      <pubDate>{email_utils.format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">threshold-and-bar-ep{e["no"]:03d}</guid>
      <enclosure url="{saxutils.escape(base + "/" + e["file"])}" length="{e["bytes"]}" type="audio/mpeg"/>
      <itunes:duration>{e["duration"]}</itunes:duration>
      <itunes:episode>{e["no"]}</itunes:episode>
      <itunes:image href="{saxutils.escape(base + "/" + COVER)}"/>
      <itunes:explicit>false</itunes:explicit>
      <link>{saxutils.escape(base)}/</link>
    </item>"""


def render(
    eps: Sequence[Mapping[str, Any]], base: str, now: datetime.datetime
) -> str:
    """Renders the complete RSS feed.

    Args:
        eps: The episodes.json entries, in the order they should appear.
        base: The public base URL, without a trailing slash.
        now: The time written as the channel's lastBuildDate.

    Returns:
        The feed document, ending in a newline.
    """
    items = "\n".join(item(e, base) for e in eps)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{saxutils.escape(TITLE)}</title>
    <link>{saxutils.escape(base)}/</link>
    <description>{saxutils.escape(DESC)}</description>
    <language>{LANG}</language>
    <lastBuildDate>{email_utils.format_datetime(now)}</lastBuildDate>
    <atom:link href="{saxutils.escape(base)}/feed.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>{saxutils.escape(AUTHOR)}</itunes:author>
    <itunes:owner><itunes:name>{saxutils.escape(AUTHOR)}</itunes:name><itunes:email>{EMAIL}</itunes:email></itunes:owner>
    <itunes:summary>{saxutils.escape(DESC)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:image href="{saxutils.escape(base + "/" + COVER)}"/>
    <image><url>{saxutils.escape(base + "/" + COVER)}</url><title>{saxutils.escape(TITLE)}</title><link>{saxutils.escape(base)}/</link></image>
    <itunes:category text="Health &amp; Fitness"><itunes:category text="Fitness"/></itunes:category>
{items}
  </channel>
</rss>
"""


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Rebuilds feed.xml from episodes.json and prints a one-line summary.

    Args:
        argv: The command line, program name first. Defaults to sys.argv.
    """
    if argv is None:
        argv = sys.argv
    base = derive_base(argv).rstrip("/")
    with open(os.path.join(ROOT, "episodes.json")) as f:
        eps = json.load(f)
    eps.sort(key=lambda e: e["no"], reverse=True)
    feed = render(eps, base, datetime.datetime.now(datetime.timezone.utc))
    with open(os.path.join(ROOT, "feed.xml"), "w") as f:
        f.write(feed)
    print(f"feed.xml rebuilt: {len(eps)} episode(s), base {base}")


if __name__ == "__main__":
    main()
