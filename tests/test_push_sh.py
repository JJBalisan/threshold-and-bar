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


def _run_raw(script_dir):
    """Runs push.sh from script_dir/deploy; returns code and full output."""
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(script_dir.parent)
    result = subprocess.run(
        ["/bin/bash", str(script_dir / "deploy" / "push.sh")],
        cwd=script_dir.parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout


# Issue #9: push.sh counts origin/main..HEAD but pushes main.


def test_unpushed_main_is_pushed_from_another_branch(repos):
    bare, clone = repos
    _commit(clone, "episode")
    main_sha = _git("rev-parse", "main", cwd=clone)
    main_short = _git("rev-parse", "--short", "main", cwd=clone)
    _git("switch", "-q", "-c", "side", "origin/main", cwd=clone)
    code, _, lines = _run(clone)
    assert code == 0
    assert lines == ["pushing 1 commit(s)", f"ok -> {main_short}"]
    assert _git("rev-parse", "main", cwd=bare) == main_sha


def test_branch_ahead_with_main_pushed_is_nothing_to_push(repos):
    bare, clone = repos
    before = _git("rev-parse", "main", cwd=bare)
    _git("switch", "-q", "-c", "side", cwd=clone)
    _commit(clone, "a")
    _commit(clone, "b")
    code, _, lines = _run(clone)
    assert code == 0
    assert lines == ["nothing to push"]
    assert _git("rev-parse", "main", cwd=bare) == before


# Issue #10: any git rev-list error is reported as "nothing to push".


def test_missing_tracking_ref_and_failed_fetch_is_an_error(repos):
    _, clone = repos
    _commit(clone, "episode")
    _git("update-ref", "-d", "refs/remotes/origin/main", cwd=clone)
    _git("remote", "set-url", "origin", str(clone.parent / "gone"), cwd=clone)
    code, out = _run_raw(clone)
    assert code == 1, out
    assert "nothing to push" not in out


def test_not_a_repo_is_an_error(tmp_path):
    loose = tmp_path / "loose"
    (loose / "deploy").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "deploy" / "push.sh", loose / "deploy")
    code, out = _run_raw(loose)
    assert code == 1, out
    assert "nothing to push" not in out


# Issue #11: a diverged main fails every run with an SSH hint.


def test_diverged_main_is_not_blamed_on_ssh(repos):
    bare, clone = repos
    other = clone.parent / "other"
    _git("clone", "-q", str(bare), str(other), cwd=clone.parent)
    _commit(other, "merged-pr")
    _git("push", "-q", "origin", "main", cwd=other)
    _commit(clone, "episode")
    episode = _git("rev-parse", "main", cwd=clone)
    code, out = _run_raw(clone)
    assert "ssh -T" not in out, out
    if code == 0:
        # Fix by rebasing: origin now holds the episode on top of the PR.
        log = _git("log", "--format=%s", "main", cwd=bare).splitlines()
        assert log[:2] == ["episode", "merged-pr"], log
    else:
        # Fix by reporting: the log names the divergence, and nothing is
        # lost from either side.
        assert code == 1, out
        assert "diverged" in out.lower(), out
        assert _git("rev-parse", "main", cwd=clone) == episode
