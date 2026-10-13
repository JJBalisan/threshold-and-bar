"""Characterization tests pinning build_feed.py's current output.

Every render happens in a temporary copy of the repo, never in the
checkout, because build_feed.py writes feed.xml next to itself.
"""

import email.utils
import importlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

import build_feed

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://jjbalisan.github.io/threshold-and-bar"
LAST_BUILD = re.compile(
    rb"    <lastBuildDate>"
    rb"[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} \+0000"
    rb"</lastBuildDate>\n"
)
MASK = b"    <lastBuildDate>MASKED</lastBuildDate>\n"


def _mask(feed):
    masked, count = LAST_BUILD.subn(MASK, feed)
    assert count == 1, "expected exactly one lastBuildDate line"
    return masked


@pytest.fixture
def workdir(tmp_path):
    for name in ("build_feed.py", "episodes.json"):
        shutil.copy2(REPO_ROOT / name, tmp_path / name)
    return tmp_path


def _run(workdir, args=(), extra_env=None, drop_feed_base=True):
    env = dict(os.environ)
    if drop_feed_base:
        env.pop("FEED_BASE", None)
    # Stop git from finding a repository above the temporary directory.
    env["GIT_CEILING_DIRECTORIES"] = str(workdir.parent)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(workdir / "build_feed.py"), *args],
        cwd=workdir,
        env=env,
        capture_output=True,
        check=False,
    )


def _episode_count():
    return len(json.loads((REPO_ROOT / "episodes.json").read_text()))


def _committed_feed():
    return (REPO_ROOT / "feed.xml").read_bytes()


def test_argv_base_reproduces_committed_feed(workdir):
    result = _run(workdir, [BASE])
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        f"feed.xml rebuilt: {_episode_count()} episode(s), base {BASE}\n".encode()
    )
    assert result.stderr == b""
    assert _mask((workdir / "feed.xml").read_bytes()) == _mask(
        _committed_feed()
    )


def test_trailing_slash_is_stripped(workdir):
    result = _run(workdir, [BASE + "/"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith(f"base {BASE}\n".encode())
    assert _mask((workdir / "feed.xml").read_bytes()) == _mask(
        _committed_feed()
    )


def test_feed_base_env_is_used_without_argv(workdir):
    result = _run(workdir, extra_env={"FEED_BASE": BASE})
    assert result.returncode == 0, result.stderr
    assert _mask((workdir / "feed.xml").read_bytes()) == _mask(
        _committed_feed()
    )


def test_argv_beats_feed_base_env(workdir):
    result = _run(
        workdir, [BASE], extra_env={"FEED_BASE": "https://example.org/x"}
    )
    assert result.returncode == 0, result.stderr
    assert _mask((workdir / "feed.xml").read_bytes()) == _mask(
        _committed_feed()
    )


def test_base_derived_from_github_remote(workdir):
    subprocess.run(["git", "init", "-q", str(workdir)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(workdir),
            "remote",
            "add",
            "origin",
            "git@github.com:JJBalisan/threshold-and-bar.git",
        ],
        check=True,
    )
    result = _run(workdir)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        f"feed.xml rebuilt: {_episode_count()} episode(s), base {BASE}\n".encode()
    )
    assert _mask((workdir / "feed.xml").read_bytes()) == _mask(
        _committed_feed()
    )


def test_no_remote_exits_with_message(workdir):
    result = _run(workdir)
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr.endswith(
        b"No origin remote yet. Pass the base URL: "
        b"build_feed.py https://user.github.io/repo\n"
    )
    assert not (workdir / "feed.xml").exists()


def test_unparsable_remote_exits_with_message(workdir):
    subprocess.run(["git", "init", "-q", str(workdir)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(workdir),
            "remote",
            "add",
            "origin",
            "https://gitlab.com/someone/repo.git",
        ],
        check=True,
    )
    result = _run(workdir)
    assert result.returncode == 1
    assert result.stderr == (
        b"Could not parse a GitHub user/repo from origin: "
        b"https://gitlab.com/someone/repo.git\n"
    )
    assert not (workdir / "feed.xml").exists()


def test_render_is_byte_identical_to_committed_feed():
    with open(REPO_ROOT / "episodes.json") as f:
        eps = json.load(f)
    eps.sort(key=lambda e: e["no"], reverse=True)
    committed = _committed_feed()
    # Take the timestamp from the committed feed, because the weekly
    # scheduled run rewrites feed.xml with a fresh lastBuildDate.
    match = re.search(rb"<lastBuildDate>([^<]+)</lastBuildDate>", committed)
    assert match is not None, "committed feed.xml has no lastBuildDate"
    now = email.utils.parsedate_to_datetime(match.group(1).decode("ascii"))
    feed = build_feed.render(eps, BASE, now)
    assert feed.encode("utf-8") == committed


def test_import_has_no_side_effects(monkeypatch):
    before = (REPO_ROOT / "feed.xml").stat().st_mtime_ns
    monkeypatch.setattr(sys, "argv", ["x"])
    importlib.reload(build_feed)
    assert (REPO_ROOT / "feed.xml").stat().st_mtime_ns == before
