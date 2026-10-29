# Threshold & Bar — private podcast feed

A weekly digest on middle- and long-distance running science, hybrid training for
running and triathlon, and strength sports. Audio is written and narrated
automatically each Wednesday afternoon (London) and added here.

## Feed

The repo is public and served by GitHub Pages from `main`, folder `/`. The
feed is <https://jjbalisan.github.io/threshold-and-bar/feed.xml>: paste it
into the search bar of Pocket Casts, Overcast or Apple Podcasts and
subscribe.

Anyone given the URL can subscribe. Episodes carry no personal training
detail (no goals, numbers or injury history), so the feed is safe to hand
to anyone.

## Layout

    episodes.json      the register, one entry per episode, newest first
    audio/epNNN.mp3    episode audio
    show.json          the show's feed settings (title, categories, guid prefix)
    feed.xml           the RSS feed podcast apps poll
    index.html         page listing the episodes with inline players
    deploy/push.sh     catch-up push, run by launchd (see below)

The feed is built by the shared kit (`podcast-kit`,
`bin/build_feed.py`), which derives the public base URL from the `origin` remote, so
`github.com/<user>/threshold-and-bar` becomes `https://<user>.github.io/threshold-and-bar`.
Override with an argument, `$FEED_BASE` or `base_url` in `show.json`.

## Adding an episode by hand

    ~/.local/share/threshold-and-bar/venv-mlx/bin/python \
      ~/.local/share/threshold-and-bar/bin/publish_episode.py . --no 2 \
      --title "<title>" --summary "<summary>" --mp3 new.mp3

It switches to main, copies the MP3, appends episodes.json, rebuilds the
feed, commits and pushes.

## How episodes get here

A local Claude Code scheduled task (`threshold-and-bar-digest`, Wednesdays 14:00
London) researches the week, renders the MP3 on this Mac, and commits and pushes it
here directly. It needs the Claude desktop app open; if the app is closed then it
runs on next launch.

If that push fails (SSH agent locked, offline), the commit stays local and
`deploy/push.sh` pushes it on the next launchd run: Wednesday 20:30 and Thursday
09:00. The LaunchAgent plist lives in `~/Developer/active/launchd-jobs/threshold-and-bar/`.

Until 24 September 2026 the digest was a Cowork cloud routine working through a
mounted folder. That mount could not delete files, hence the old `gitsafe` wrapper,
now removed.
