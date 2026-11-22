"""Checks for index.html's episode list (dev-toolchain#110).

The page's inline script runs under node against the stub DOM in
tb_index_harness.js; no npm packages are needed. The stub records
innerHTML instead of parsing it, so the page must build episode nodes
with createElement, textContent and attributes for the render checks to
pass (escaping into innerHTML is not supported by this harness).

Bug checks: test_fields_never_reach_html_sinks and the four failure
tests. The render tests guard the rewrite against regressions.
"""

import json
import pathlib
import re
import shutil
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HARNESS = pathlib.Path(__file__).resolve().parent / "tb_index_harness.js"
NODE = shutil.which("node") or (
    "/opt/homebrew/bin/node"
    if pathlib.Path("/opt/homebrew/bin/node").exists()
    else None
)

pytestmark = pytest.mark.skipif(
    NODE is None, reason="node is not installed; the page checks need it"
)

# Each field carries a unique marker next to the characters that break
# HTML: a marker reaching an HTML sink means the field went in raw or
# only partly escaped.
HOSTILE = {
    "no": 12,
    "date": 'ZQDATE <img src=x onerror="alert(1)"> & 19 Nov',
    "duration": "ZQDUR 12:34 </span><b>",
    "file": 'audio/ZQFILE".mp3" onerror="alert(2)',
    "title": "ZQTITLE <i>Heat</i> & carbs",
    "summary": "ZQSUM <script>x()</script>",
}
PLAIN = {
    "no": 3,
    "date": "2026-09-02",
    "duration": "18:05",
    "file": "audio/ep003.mp3",
    "title": "Third",
    "summary": "Third summary.",
}
MARKERS = ("ZQDATE", "ZQDUR", "ZQFILE", "ZQTITLE", "ZQSUM")


def _page_script():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 1, "expected one inline <script> in index.html"
    return scripts[0]


def _run(tmp_path, scenario):
    script = tmp_path / "page.js"
    script.write_text(_page_script(), encoding="utf-8")
    sc = tmp_path / "scenario.json"
    sc.write_text(json.dumps(scenario), encoding="utf-8")
    proc = subprocess.run(
        [NODE, str(HARNESS), str(script), str(sc)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _walk(node):
    yield node
    for kid in node.get("kids", []):
        yield from _walk(kid)


def _find(root, cls=None, tag=None):
    return [
        n
        for n in _walk(root)
        if "tag" in n
        and (cls is None or cls in n["classes"])
        and (tag is None or n["tag"] == tag)
    ]


def _attr(node, name):
    if name in node["attrs"]:
        return node["attrs"][name]
    return node["props"].get(name)


def _context(out):
    return "unknown DOM members: {}; errors: {}; sinks: {}".format(
        out["unknown"], out["errors"], out["sinks"]
    )


def test_fields_never_reach_html_sinks(tmp_path):
    out = _run(tmp_path, {"body": [PLAIN, HOSTILE]})
    leaked = [
        (s["sink"], m) for s in out["sinks"] for m in MARKERS if m in s["value"]
    ]
    assert leaked == [], _context(out)


def test_renders_each_episode_from_text_and_attributes(tmp_path):
    out = _run(tmp_path, {"body": [PLAIN, HOSTILE]})
    ctx = _context(out)
    assert out["unknown"] == [], ctx
    assert out["errors"] == [], ctx
    arts = _find(out["eplist"], cls="ep")
    assert [a["tag"] for a in arts] == ["article", "article"], ctx
    first, second = arts

    assert _find(first, cls="no")[0]["text"] == "EP 012", ctx
    assert _find(second, cls="no")[0]["text"] == "EP 003", ctx
    meta = _find(first, cls="epmeta")[0]["text"]
    assert HOSTILE["date"] in meta, ctx
    assert HOSTILE["duration"] in meta, ctx
    spans = [n["text"] for n in _find(first, cls="epmeta")[0]["kids"]]
    assert spans == ["EP 012", HOSTILE["date"], HOSTILE["duration"]], ctx

    title = _find(first, cls="eptitle")
    assert [t["tag"] for t in title] == ["h3"], ctx
    assert title[0]["text"] == HOSTILE["title"], ctx
    desc = _find(first, cls="epdesc")
    assert [d["tag"] for d in desc] == ["p"], ctx
    assert desc[0]["text"] == HOSTILE["summary"], ctx

    audio = _find(first, tag="audio")
    assert len(audio) == 1, ctx
    assert _attr(audio[0], "src") == HOSTILE["file"], ctx
    assert _attr(audio[0], "controls") not in (None, False), ctx
    assert _attr(audio[0], "preload") == "none", ctx
    assert _attr(_find(second, tag="audio")[0], "src") == PLAIN["file"]


def test_success_shows_no_error_text_outside_episodes(tmp_path):
    out = _run(tmp_path, {"body": [PLAIN]})
    ctx = _context(out)
    arts = _find(out["eplist"], cls="ep")
    assert len(arts) == 1, ctx
    assert out["eplist"]["text"] == arts[0]["text"], ctx
    assert out["fetches"] == ["episodes.json"], ctx


def _assert_visible_message(out):
    ctx = _context(out)
    assert _find(out["eplist"], cls="ep") == [], ctx
    assert out["eplist"]["text"].strip(), (
        "no message in #eplist after a failed load; " + ctx
    )


def test_http_error_shows_message_and_ignores_body(tmp_path):
    # A 404 whose body still parses must not be rendered as episodes.
    out = _run(tmp_path, {"ok": False, "status": 404, "body": [PLAIN]})
    _assert_visible_message(out)


def test_network_error_shows_message(tmp_path):
    out = _run(tmp_path, {"fetch": "reject"})
    _assert_visible_message(out)


def test_invalid_json_shows_message(tmp_path):
    out = _run(tmp_path, {"json": "reject"})
    _assert_visible_message(out)


def test_json_that_is_not_a_list_shows_message(tmp_path):
    out = _run(tmp_path, {"body": {"episodes": "nope"}})
    _assert_visible_message(out)
