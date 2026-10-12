"""Characterization tests pinning deploy/push.sh's log output.

launchd sends the script's stdout and stderr to the same log file, so
the tests capture both streams together. The remote is a temporary
bare repository; nothing leaves the machine.
"""

import os
import pathlib
import re
import shutil
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]
HEADER = re.compile(r"^=== \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \S+  (.*)$")
SCRIPT_LINES = (
    "=== ",
    "repo not found",
    "fetch failed, continuing",
    "nothing to push",
    "pushing ",
    "ok -> ",
    "PUSH FAILED",
)


def _git(*args, cwd):
    return subprocess.run(
        ["git", *GIT_ID, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repos(tmp_path):
    bare = tmp_path / "origin.git"
    clone = tmp_path / "clone"
    _git("init", "-q", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    _git("init", "-q", "-b", "main", str(clone), cwd=tmp_path)
    (clone / "deploy").mkdir()
    shutil.copy2(REPO_ROOT / "deploy" / "push.sh", clone / "deploy")
    _git("add", "-A", cwd=clone)
    _git("commit", "-q", "-m", "init", cwd=clone)
    _git("remote", "add", "origin", str(bare), cwd=clone)
    _git("push", "-q", "-u", "origin", "main", cwd=clone)
    return bare, clone


def _commit(clone, name):
    (clone / name).write_text(name)
    _git("add", name, cwd=clone)
    _git("commit", "-q", "-m", name, cwd=clone)


def _run(clone):
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(clone.parent)
    result = subprocess.run(
        ["/bin/bash", str(clone / "deploy" / "push.sh")],
        cwd=clone.parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    lines = [
        line
        for line in result.stdout.splitlines()
        if line.startswith(SCRIPT_LINES)
    ]
    header = HEADER.match(lines[0])
    assert header, lines[0]
    return result.returncode, header.group(1), lines[1:]


def test_nothing_to_push(repos):
    _, clone = repos
    code, repo, lines = _run(clone)
    assert code == 0
    assert repo == str(clone.resolve())
    assert lines == ["nothing to push"]


def test_pushes_commits_ahead(repos):
    bare, clone = repos
    _commit(clone, "a")
    _commit(clone, "b")
    head = _git("rev-parse", "--short", "HEAD", cwd=clone)
    code, _, lines = _run(clone)
    assert code == 0
    assert lines == ["pushing 2 commit(s)", f"ok -> {head}"]
    assert _git("rev-parse", "main", cwd=bare) == _git(
        "rev-parse", "HEAD", cwd=clone
    )


def test_fetch_failure_still_reports_nothing_to_push(repos):
    _, clone = repos
    _git("remote", "set-url", "origin", str(clone.parent / "gone"), cwd=clone)
    code, _, lines = _run(clone)
    assert code == 0
    assert lines == ["fetch failed, continuing", "nothing to push"]


def test_push_failure_exits_1(repos):
    _, clone = repos
    _commit(clone, "a")
    _git("remote", "set-url", "origin", str(clone.parent / "gone"), cwd=clone)
    code, _, lines = _run(clone)
    assert code == 1
    assert lines == [
        "fetch failed, continuing",
        "pushing 1 commit(s)",
        "PUSH FAILED (check: ssh -T git@github.com)",
    ]
