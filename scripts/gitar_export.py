"""Export every Gitar review on this repo's pull requests into gitar/results/.

For each PR that Gitar touched, it writes gitar/results/pr-0001.md with Gitar's
dashboard comment, review summaries, inline comments (with the code they point
at) and the fix commits Gitar pushed. gitar/results/README.md gets the totals,
so the team can show in the demo what Gitar caught and fixed.

Usage:
    python scripts/gitar_export.py [owner/repo]

Token: GITHUB_TOKEN or GH_TOKEN, else `gh auth token`.
Gitar's account: any login matching GITAR_LOGIN_PATTERN (default "gitar", any case).
Standard library only, so it runs in CI without installing anything.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
OUT = Path(__file__).resolve().parents[1] / "gitar" / "results"
PATTERN = os.getenv("GITAR_LOGIN_PATTERN", "gitar")


# ---------- GitHub API ----------

def github_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def fetch_page(url: str, token: str, attempts: int = 4) -> tuple[list, str]:
    """GET one page. Retries network errors, because venue Wi-Fi drops requests."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp), resp.headers.get("Link", "")
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            time.sleep(2 * attempt)


def get_all(path: str, token: str) -> list:
    """GET every page of a GitHub list endpoint."""
    url = f"{API}{path}{'&' if '?' in path else '?'}per_page=100"
    items = []
    while url:
        page, link = fetch_page(url, token)
        items.extend(page)
        match = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = match.group(1) if match else None
    return items


def repo_name(argv: list[str]) -> str:
    if len(argv) > 1:
        return argv[1]
    if os.getenv("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True).stdout
    return re.sub(r"^(git@github\.com:|https://github\.com/)|\.git\s*$", "", remote.strip())


# ---------- Collect ----------

def is_gitar(user: dict | None, pattern: str = PATTERN) -> bool:
    return bool(user) and re.search(pattern, user.get("login", ""), re.IGNORECASE) is not None


def collect(repo: str, pr: dict, token: str) -> dict:
    n = pr["number"]
    commits = get_all(f"/repos/{repo}/pulls/{n}/commits", token)
    return {
        "number": n,
        "title": pr["title"],
        "url": pr["html_url"],
        "author": pr["user"]["login"],
        "state": "merged" if pr.get("merged_at") else pr["state"],
        "dashboard": [c for c in get_all(f"/repos/{repo}/issues/{n}/comments", token) if is_gitar(c["user"])],
        "reviews": [
            r for r in get_all(f"/repos/{repo}/pulls/{n}/reviews", token)
            if is_gitar(r["user"]) and r.get("body")
        ],
        "inline": [c for c in get_all(f"/repos/{repo}/pulls/{n}/comments", token) if is_gitar(c["user"])],
        "fixes": [
            c for c in commits
            if is_gitar(c.get("author")) or is_gitar(c.get("committer"))
            or re.search(PATTERN, c["commit"]["author"]["name"], re.IGNORECASE)
        ],
    }


def has_activity(data: dict) -> bool:
    return any(data[key] for key in ("dashboard", "reviews", "inline", "fixes"))


# ---------- Render ----------

def first_line(text: str, limit: int = 140) -> str:
    line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    line = re.sub(r"[#*`>|]", "", line).strip()
    return line if len(line) <= limit else line[: limit - 1] + "…"


def finding_title(body: str, limit: int = 140) -> str:
    """Gitar wraps each finding in <details><summary>...</summary>: use that title."""
    match = re.search(r"<summary>(.*?)</summary>", body or "", re.DOTALL)
    text = match.group(1) if match else (body or "")
    return first_line(re.sub(r"<[^>]+>", "", text), limit)


def render_pr(data: dict) -> str:
    out = [
        f"# PR #{data['number']}: {data['title']}",
        "",
        f"- Link: {data['url']}",
        f"- Author: {data['author']}",
        f"- State: {data['state']}",
        f"- Gitar: {len(data['dashboard'])} dashboard comment(s), {len(data['reviews'])} review(s), "
        f"{len(data['inline'])} inline comment(s), {len(data['fixes'])} fix commit(s)",
        "",
    ]
    if data["dashboard"]:
        out += ["## Dashboard comment", ""]
        for c in data["dashboard"]:
            out += [f"[Open on GitHub]({c['html_url']})", "", c["body"].strip(), ""]
    if data["reviews"]:
        out += ["## Reviews", ""]
        for r in data["reviews"]:
            out += [f"### {r['state'].title()} ([link]({r['html_url']}))", "", r["body"].strip(), ""]
    if data["inline"]:
        out += ["## Inline comments", ""]
        for c in data["inline"]:
            line = c.get("line") or c.get("original_line") or "?"
            hunk = "\n".join((c.get("diff_hunk") or "").splitlines()[-6:])
            out += [f"### `{c['path']}:{line}` ([link]({c['html_url']}))", ""]
            if hunk:
                out += ["```diff", hunk, "```", ""]
            out += [c["body"].strip(), ""]
    if data["fixes"]:
        out += ["## Fix commits pushed by Gitar", ""]
        for c in data["fixes"]:
            out.append(f"- [`{c['sha'][:7]}`]({c['html_url']}) {first_line(c['commit']['message'])}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_index(all_prs: list[dict]) -> str:
    reviewed = [d for d in all_prs if has_activity(d)]
    totals = {key: sum(len(d[key]) for d in all_prs) for key in ("dashboard", "reviews", "inline", "fixes")}
    out = [
        "# Gitar review results",
        "",
        "Generated by `scripts/gitar_export.py`. Do not edit by hand: the next export overwrites it.",
        "Put the team's own notes for the demo in [HIGHLIGHTS.md](HIGHLIGHTS.md).",
        "",
        "## Totals",
        "",
        "| Pull requests | Reviewed by Gitar | Dashboard comments | Reviews | Inline comments | Fix commits by Gitar |",
        "|---|---|---|---|---|---|",
        f"| {len(all_prs)} | {len(reviewed)} | {totals['dashboard']} | {totals['reviews']} "
        f"| {totals['inline']} | {totals['fixes']} |",
        "",
        "## Pull requests",
        "",
        "| PR | Title | State | Inline comments | Fix commits | Details |",
        "|---|---|---|---|---|---|",
    ]
    for d in sorted(all_prs, key=lambda d: d["number"]):
        details = f"[pr-{d['number']:04d}.md](pr-{d['number']:04d}.md)" if has_activity(d) else "no Gitar activity"
        title = d["title"].replace("|", "\\|")
        out.append(f"| [#{d['number']}]({d['url']}) | {title} | {d['state']} "
                   f"| {len(d['inline'])} | {len(d['fixes'])} | {details} |")
    findings = [(d, c) for d in sorted(all_prs, key=lambda d: d["number"]) for c in d["inline"]]
    if findings:
        out += ["", "## What Gitar flagged", ""]
        for d, c in findings:
            out.append(f"- [#{d['number']} `{c['path']}`]({c['html_url']}): {finding_title(c['body'])}")
    fixes = [(d, c) for d in sorted(all_prs, key=lambda d: d["number"]) for c in d["fixes"]]
    if fixes:
        out += ["", "## Fixes Gitar pushed", ""]
        for d, c in fixes:
            out.append(f"- [#{d['number']} `{c['sha'][:7]}`]({c['html_url']}): {first_line(c['commit']['message'])}")
    return "\n".join(out) + "\n"


# ---------- Main ----------

def main(argv: list[str]) -> None:
    repo = repo_name(argv)
    token = github_token()
    prs = get_all(f"/repos/{repo}/pulls?state=all", token)
    all_prs = [collect(repo, pr, token) for pr in prs]
    OUT.mkdir(parents=True, exist_ok=True)
    for data in all_prs:
        if has_activity(data):
            (OUT / f"pr-{data['number']:04d}.md").write_text(render_pr(data))
    (OUT / "README.md").write_text(render_index(all_prs))
    reviewed = sum(has_activity(d) for d in all_prs)
    print(f"Exported Gitar activity for {reviewed} of {len(all_prs)} PRs in {repo} to {OUT}")


if __name__ == "__main__":
    main(sys.argv)
