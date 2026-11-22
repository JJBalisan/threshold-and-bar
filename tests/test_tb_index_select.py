"""Selector's adversarial checks for the episode list (dev-toolchain#110).

Written from the issue and the verifier's notes before any solver diff
was read. They run the page script through the same node harness as
test_tb_index.py and reuse its helpers.

Pinned: field text and attributes come through verbatim (no escaping,
no double escaping), no field reaches an HTML sink (the episode number
included), non-string fields do not break the list, numeric descending
order, and every failed load ends in a plain-text message with no
uncaught error. Not pinned: message wording, empty-list handling beyond
"no crash", and what a null or missing field displays.
"""

import pytest

from tests import test_tb_index as tb

pytestmark = tb.pytestmark

# Each field pairs a marker with characters that break HTML, attribute
# quoting, script blocks or template strings.
NASTY = {
    "no": 5,
    "date": "ZQD1 </script><script>alert(1)</script>",
    "duration": "ZQD2 `${x}` ' \" &amp; &lt; </span>",
    "file": "audio/ZQD3 it's \"a\" & b <x>.mp3",
    "title": "ZQD4 " + "x&<" * 7000,
    "summary": "ZQD5 ' \" ` </p><p>",
}
NASTY_MARKERS = ("ZQD1", "ZQD2", "ZQD3", "ZQD4", "ZQD5")

FAILURES = {
    "http_404": {"ok": False, "status": 404, "body": [tb.PLAIN]},
    "http_500": {"ok": False, "status": 500, "body": [tb.PLAIN]},
    # The harness maps status 0 to 200, so this is ok: false with a 200
    # status: a check on r.status instead of r.ok renders the body.
    "not_ok_status_200": {"ok": False, "status": 0, "body": [tb.PLAIN]},
    "network": {"fetch": "reject"},
    "bad_json": {"json": "reject"},
    "object_body": {"body": {"episodes": [tb.PLAIN]}},
    "null_body": {"body": None},
    "string_body": {"body": "episodes"},
    "number_body": {"body": 3},
}


def _articles(out):
    return tb._find(out["eplist"], cls="ep")


def _numbers(out):
    return [tb._find(a, cls="no")[0]["text"] for a in _articles(out)]


def _nonempty_sinks(out):
    return [s for s in out["sinks"] if s["value"].strip()]


def _assert_clean(out):
    ctx = tb._context(out)
    assert out["errors"] == [], ctx
    assert out["unknown"] == [], ctx


def test_nasty_fields_render_verbatim_and_never_reach_sinks(tmp_path):
    out = tb._run(tmp_path, {"body": [NASTY]})
    ctx = tb._context(out)
    _assert_clean(out)
    leaked = [
        (s["sink"], m)
        for s in out["sinks"]
        for m in NASTY_MARKERS
        if m in s["value"]
    ]
    assert leaked == [], ctx
    (art,) = _articles(out)
    spans = [n["text"] for n in tb._find(art, cls="epmeta")[0]["kids"]]
    assert spans == ["EP 005", NASTY["date"], NASTY["duration"]], ctx
    assert tb._find(art, cls="eptitle")[0]["text"] == NASTY["title"], ctx
    assert tb._find(art, cls="epdesc")[0]["text"] == NASTY["summary"], ctx
    audio = tb._find(art, tag="audio")
    assert len(audio) == 1, ctx
    assert tb._attr(audio[0], "src") == NASTY["file"], ctx


def test_episode_number_string_never_reaches_sinks(tmp_path):
    # The issue names date, duration and file, but the number also went
    # into innerHTML; a fix that keeps it there is still injectable.
    ep = dict(tb.PLAIN, no="<b>ZQNO</b>")
    out = tb._run(tmp_path, {"body": [ep]})
    ctx = tb._context(out)
    _assert_clean(out)
    assert [s for s in out["sinks"] if "ZQNO" in s["value"]] == [], ctx


def test_non_string_and_missing_fields_do_not_break_the_list(tmp_path):
    odd = {
        "no": 4,
        "date": 20260901,
        "duration": None,
        "title": 7,
        "summary": None,
    }
    bare = {"no": 2}
    out = tb._run(tmp_path, {"body": [tb.PLAIN, odd, bare]})
    ctx = tb._context(out)
    _assert_clean(out)
    # Skipping or blanking the odd entries is fine; the good one must
    # still render in full.
    plain = [a for a in _articles(out) if "EP 003" in a["text"]]
    assert len(plain) == 1, ctx
    assert tb._find(plain[0], cls="eptitle")[0]["text"] == "Third", ctx
    audio = tb._find(plain[0], tag="audio")
    assert [tb._attr(a, "src") for a in audio] == [tb.PLAIN["file"]], ctx


def test_episodes_sort_by_number_descending_with_their_own_fields(tmp_path):
    nos = [2, 10, 1, 7, 100]
    body = [
        dict(tb.PLAIN, no=n, title=f"T{n}", file=f"audio/ep{n}.mp3")
        for n in nos
    ]
    out = tb._run(tmp_path, {"body": body})
    ctx = tb._context(out)
    _assert_clean(out)
    assert _numbers(out) == [
        "EP 100",
        "EP 010",
        "EP 007",
        "EP 002",
        "EP 001",
    ], ctx
    for art, n in zip(_articles(out), [100, 10, 7, 2, 1]):
        assert tb._find(art, cls="eptitle")[0]["text"] == f"T{n}", ctx
        audio = tb._find(art, tag="audio")[0]
        assert tb._attr(audio, "src") == f"audio/ep{n}.mp3", ctx


@pytest.mark.parametrize("name", sorted(FAILURES))
def test_failure_shows_plain_text_message_without_errors(tmp_path, name):
    out = tb._run(tmp_path, FAILURES[name])
    ctx = tb._context(out)
    tb._assert_visible_message(out)
    _assert_clean(out)
    # The message goes in as text: an HTML sink would be empty under the
    # stub, and any error detail spliced into markup is a new sink.
    assert _nonempty_sinks(out) == [], ctx
    assert out["fetches"] == ["episodes.json"], ctx


def test_empty_list_does_not_crash(tmp_path):
    out = tb._run(tmp_path, {"body": []})
    ctx = tb._context(out)
    _assert_clean(out)
    assert _articles(out) == [], ctx
    assert _nonempty_sinks(out) == [], ctx


@pytest.mark.parametrize(
    "body",
    [[tb.PLAIN, None], [None], [None, tb.PLAIN]],
    ids=["after", "alone", "before"],
)
def test_null_entry_is_handled_without_uncaught_errors(tmp_path, body):
    # Malformed entry: either skipped or a message, never both shown.
    # "alone" reaches the render with no sort call in between.
    out = tb._run(tmp_path, {"body": body})
    ctx = tb._context(out)
    _assert_clean(out)
    arts = _articles(out)
    if arts:
        shown = "".join(a["text"] for a in arts)
        assert out["eplist"]["text"] == shown, ctx
    else:
        assert out["eplist"]["text"].strip(), ctx
