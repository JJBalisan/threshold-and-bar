# Threshold & Bar — private podcast feed

A weekly digest on middle- and long-distance running science, hybrid training for
running and triathlon, and strength sports. Audio is written and narrated
automatically each Wednesday at 18:00 London and added here.

## Setup — three steps, once

1. **Create the repo on GitHub.** Public, named `threshold-and-bar`, with no README
   or licence (this folder already has commits).

2. **Push it, from your own Terminal** (not from Cowork — see the note below):

       cd ~/Developer/active/threshold-and-bar
       git remote add origin git@github.com:<your-username>/threshold-and-bar.git
       python3 build_feed.py          # derives the Pages URL from the remote
       git add -A && git commit -m "feed.xml" && git push -u origin main

3. **Turn on Pages.** Repo → Settings → Pages → Source: *Deploy from a branch*,
   Branch: `main`, folder `/ (root)`. Give it a minute, then check
   `https://<your-username>.github.io/threshold-and-bar/feed.xml` loads.

## Subscribing

Paste `https://<your-username>.github.io/threshold-and-bar/feed.xml` into the
Pocket Casts search bar on the Discover or Podcasts screen, then subscribe to the
podcast that appears. Overcast and Apple Podcasts take the same URL.

The repo is public, so anyone given the URL can subscribe. Episodes carry no
personal training detail — no goals, numbers or injury history — so the feed is
safe to hand to anyone.

## Layout

    episodes.json      the register, one entry per episode, newest first
    audio/epNNN.mp3    episode audio
    build_feed.py      regenerates feed.xml from episodes.json
    feed.xml           the RSS feed podcast apps poll
    index.html         page listing the episodes with inline players
    gitsafe            git wrapper for use inside Cowork only (see below)

`build_feed.py` derives the public base URL from the `origin` remote, so
`github.com/<user>/threshold-and-bar` becomes `https://<user>.github.io/threshold-and-bar`.
Override with an argument or `$FEED_BASE`.

## Adding an episode by hand

    cp new.mp3 audio/ep002.mp3
    # add an entry to episodes.json — bytes is the file size, duration is HH:MM:SS
    python3 build_feed.py
    git add -A && git commit -m "ep002" && git push

## The gitsafe wrapper

Cowork mounts this folder without permission to unlink files, so git cannot clean
up `.git/index.lock` or its temp objects, and the *next* git command fails with
"File exists". `gitsafe` runs a git command and sweeps those files into
`_to_delete/` either side of it:

    bash gitsafe add -A
    bash gitsafe commit -m "ep002"

Use plain `git` in your own Terminal — the restriction is Cowork's mount, not your
Mac. `_to_delete/` is gitignored and safe to empty whenever you like.
