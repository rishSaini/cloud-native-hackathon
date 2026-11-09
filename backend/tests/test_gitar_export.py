"""Tests for scripts/gitar_export.py, with fake GitHub data (no network)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gitar_export.py"
spec = importlib.util.spec_from_file_location("gitar_export", SCRIPT)
gitar_export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gitar_export)

GITAR = {"login": "gitar-bot[bot]"}
HUMAN = {"login": "karthikreddy-02"}


def pr_data(**overrides):
    data = {
        "number": 7,
        "title": "K9: Room reports",
        "url": "https://github.com/o/r/pull/7",
        "author": "karthikreddy-02",
        "state": "merged",
        "dashboard": [],
        "reviews": [],
        "inline": [],
        "fixes": [],
    }
    data.update(overrides)
    return data


def test_is_gitar_matches_bot_logins_only():
    assert gitar_export.is_gitar(GITAR)
    assert gitar_export.is_gitar({"login": "Gitar-AI"})
    assert not gitar_export.is_gitar(HUMAN)
    assert not gitar_export.is_gitar(None)


def test_render_pr_shows_inline_comment_with_code():
    data = pr_data(inline=[{
        "path": "backend/app/reports/routes.py",
        "line": 42,
        "html_url": "https://github.com/o/r/pull/7#discussion_r1",
        "diff_hunk": "@@ -40,3 +40,4 @@\n+    log.info('report from %s', card_text)",
        "body": "This logs card text. The privacy rule forbids card data in logs.",
    }])
    text = gitar_export.render_pr(data)
    assert "### `backend/app/reports/routes.py:42`" in text
    assert "card_text" in text
    assert "privacy rule forbids" in text


def test_render_index_counts_and_lists_fixes():
    reviewed = pr_data(fixes=[{
        "sha": "abc1234def",
        "html_url": "https://github.com/o/r/commit/abc1234def",
        "commit": {"message": "Fix failing ruff check\n\nDetails"},
    }])
    untouched = pr_data(number=8, title="Docs | tweak")
    text = gitar_export.render_index([reviewed, untouched])
    assert "| 2 | 1 | 0 | 0 | 0 | 1 |" in text
    assert "[pr-0007.md](pr-0007.md)" in text
    assert "no Gitar activity" in text
    assert "Docs \\| tweak" in text
    assert "`abc1234`" in text and "Fix failing ruff check" in text


def test_finding_title_reads_gitar_summary():
    body = "<details>\n<summary>💡 <b>Edge Case:</b> SSA deletes keys it pushed before</summary>\n\nDetails here"
    assert gitar_export.finding_title(body) == "💡 Edge Case: SSA deletes keys it pushed before"
    assert gitar_export.finding_title("Plain comment\nmore") == "Plain comment"
