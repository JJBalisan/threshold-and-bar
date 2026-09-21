# Threshold & Bar — private podcast feed

A weekly digest on running science, hybrid training and strength sports.
Audio is written and narrated automatically each Wednesday at 18:00 London.

## Layout

    episodes.json      the register, one entry per episode
    audio/epNNN.mp3    episode audio
    build_feed.py      regenerates feed.xml from episodes.json
    feed.xml           the RSS feed Pocket Casts subscribes to
    index.html         human-facing page listing the episodes

`build_feed.py` derives the public base URL from the `origin` remote, so
`https://github.com/<user>/threshold-and-bar` becomes
`https://<user>.github.io/threshold-and-bar`. Override with an argument or `$FEED_BASE`.

## Adding an episode by hand

    cp new.mp3 audio/ep002.mp3
    # add an entry to episodes.json (bytes = file size, duration = HH:MM:SS)
    python3 build_feed.py
    git add -A && git commit -m "ep002" && git push

## Subscribing

Paste `https://<user>.github.io/threshold-and-bar/feed.xml` into the Pocket Casts
search bar on the Discover or Podcasts screen, then subscribe to what appears.
