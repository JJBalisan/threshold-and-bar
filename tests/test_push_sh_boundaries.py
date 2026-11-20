"""Boundary tests for deploy/push.sh beyond the committed checks.

Reuses the fixtures and helpers in test_push_sh.py, which stays as
committed for issues #9, #10 and #11.
"""

import test_push_sh

repos = test_push_sh.repos


def _push_from_other_clone(bare, clone, name):
    other = clone.parent / "other"
    test_push_sh._git("clone", "-q", str(bare), str(other), cwd=clone.parent)
    test_push_sh._commit(other, name)
    test_push_sh._git("push", "-q", "origin", "main", cwd=other)


def test_missing_local_main_is_an_error(repos):
    _, clone = repos
    test_push_sh._git("switch", "-q", "-c", "side", cwd=clone)
    test_push_sh._git("branch", "-q", "-D", "main", cwd=clone)
    code, out = test_push_sh._run_raw(clone)
    assert code == 1, out
    assert "nothing to push" not in out
    assert "cannot compare main with origin/main" in out


def test_behind_only_is_nothing_to_push(repos):
    bare, clone = repos
    _push_from_other_clone(bare, clone, "pr")
    code, _, lines = test_push_sh._run(clone)
    assert code == 0
    assert lines == ["nothing to push"]


def test_diverged_main_pushes_nothing(repos):
    bare, clone = repos
    _push_from_other_clone(bare, clone, "pr")
    pr = test_push_sh._git("rev-parse", "main", cwd=bare)
    test_push_sh._commit(clone, "episode")
    code, out = test_push_sh._run_raw(clone)
    assert code == 1, out
    assert "1 ahead, 1 behind" in out
    assert "pushing" not in out
    assert test_push_sh._git("rev-parse", "main", cwd=bare) == pr


def test_tag_named_main_does_not_hide_unpushed_main(repos):
    bare, clone = repos
    test_push_sh._git("tag", "main", cwd=clone)
    test_push_sh._commit(clone, "episode")
    main_sha = test_push_sh._git("rev-parse", "refs/heads/main", cwd=clone)
    short = test_push_sh._git(
        "rev-parse", "--short", "refs/heads/main", cwd=clone
    )
    code, _, lines = test_push_sh._run(clone)
    assert code == 0
    assert lines == ["pushing 1 commit(s)", f"ok -> {short}"]
    assert test_push_sh._git("rev-parse", "main", cwd=bare) == main_sha
