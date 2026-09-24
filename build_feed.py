#!/usr/bin/env python3
"""Rebuild feed.xml from episodes.json.

Base URL is derived from the git remote (user/repo -> https://user.github.io/repo)
unless given as argv[1] or $FEED_BASE.
"""
import json, os, re, sys, subprocess
from email.utils import format_datetime
from datetime import datetime, timezone
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.abspath(__file__))

def derive_base():
    if len(sys.argv) > 1:
        return sys.argv[1]
    if os.environ.get("FEED_BASE"):
        return os.environ["FEED_BASE"]
    try:
        url = subprocess.check_output(
            ["git", "-C", ROOT, "remote", "get-url", "origin"], text=True).strip()
    except Exception:
        sys.exit("No origin remote yet. Pass the base URL: build_feed.py https://user.github.io/repo")
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    if not m:
        sys.exit(f"Could not parse a GitHub user/repo from origin: {url}")
    return f"https://{m.group(1).lower()}.github.io/{m.group(2)}"

BASE  = derive_base().rstrip("/")
TITLE = "Threshold & Bar"
DESC  = ("A weekly digest of middle- and long-distance running science, hybrid training for "
         "running and triathlon, and strength sports. Written and narrated by Claude.")
AUTHOR, EMAIL, LANG = "Claude", "noreply@anthropic.com", "en-GB"
MUSIC_CREDIT = (" Music: intro and interludes from \u201cDans la tentative d\u2019accomplir quelque chose\u201d by "
    "Frederic Lardon feat. Laura Palm\u00e9e (CC0). Outro: \u201cCrap Transition\u201d by Jesse Spillane, "
    "https://freemusicarchive.org/music/Jesse_Spillane/Art_of_Presentation/Jesse_Spillane_-_Art_of_Presentation_-_04_Crap_Transition/ "
    "licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); trimmed, faded and mixed with narration.")
COVER = "cover.jpg"   # 2000x2000 sRGB JPEG; Apple wants 1400-3000 px square, JPEG or PNG

eps = json.load(open(os.path.join(ROOT, "episodes.json")))
eps.sort(key=lambda e: e["no"], reverse=True)

def item(e):
    summary = e["summary"] + (MUSIC_CREDIT if e.get("music") else "")
    pub = datetime.strptime(e["date"], "%Y-%m-%d").replace(hour=17, tzinfo=timezone.utc)
    return f"""    <item>
      <title>{escape(e["title"])}</title>
      <description>{escape(summary)}</description>
      <itunes:summary>{escape(summary)}</itunes:summary>
      <pubDate>{format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">threshold-and-bar-ep{e["no"]:03d}</guid>
      <enclosure url="{escape(BASE + "/" + e["file"])}" length="{e["bytes"]}" type="audio/mpeg"/>
      <itunes:duration>{e["duration"]}</itunes:duration>
      <itunes:episode>{e["no"]}</itunes:episode>
      <itunes:image href="{escape(BASE + "/" + COVER)}"/>
      <itunes:explicit>false</itunes:explicit>
      <link>{escape(BASE)}/</link>
    </item>"""

feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(TITLE)}</title>
    <link>{escape(BASE)}/</link>
    <description>{escape(DESC)}</description>
    <language>{LANG}</language>
    <lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
    <atom:link href="{escape(BASE)}/feed.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>{escape(AUTHOR)}</itunes:author>
    <itunes:owner><itunes:name>{escape(AUTHOR)}</itunes:name><itunes:email>{EMAIL}</itunes:email></itunes:owner>
    <itunes:summary>{escape(DESC)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:image href="{escape(BASE + "/" + COVER)}"/>
    <image><url>{escape(BASE + "/" + COVER)}</url><title>{escape(TITLE)}</title><link>{escape(BASE)}/</link></image>
    <itunes:category text="Health &amp; Fitness"><itunes:category text="Fitness"/></itunes:category>
{chr(10).join(item(e) for e in eps)}
  </channel>
</rss>
"""
open(os.path.join(ROOT, "feed.xml"), "w").write(feed)
print(f"feed.xml rebuilt: {len(eps)} episode(s), base {BASE}")
