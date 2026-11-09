"""Fill the conference with synthetic attendees for the demo (R13). Never real people.

Uses only the public API, like a phone would: create an attendee, save a card,
ask for a talk placement, and RSVP to a break.

    python scripts/seed_demo.py --url http://localhost:8000 --count 60 --dry-run
    python scripts/seed_demo.py --url http://localhost:8000 --count 60
    python scripts/seed_demo.py --url http://localhost:8000 --reset

Hard cap: 150 attendees. Rate-limited (default 10 requests a second).
Seeded sessions are saved to --state (default seed-demo-state.json, ignored by
git), and --reset uses only those, so it never touches a real attendee.
Standard library only, so it runs in the app image as Job seed-demo-001.
"""

import argparse
import http.cookiejar
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

HARD_CAP = 150
CLUSTERS = {
    "startup": ["making apps start faster", "cold starts and image size", "fast rollouts"],
    "observability": ["OpenTelemetry tracing", "debugging slow requests", "metrics and SLOs"],
    "security": ["supply chain security", "signing images", "zero trust networking"],
    "ai": ["serving LLMs on GPUs", "AI inference cost", "autoscaling inference"],
    "community": ["my first open source contribution", "mentoring new contributors", "inclusive meetups"],
}
NEEDS = [[], [], [], [], [], ["captions"], ["quiet"], ["step_free"], ["captions", "quiet"], ["lighting"]]


class Client:
    def __init__(self, base: str, rate: float, session: str | None = None):
        self.base, self.delay = base.rstrip("/"), 1.0 / rate
        self.fixed_cookie = f"affinity_session={session}" if session else None
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method: str, path: str, body=None):
        time.sleep(self.delay)
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.fixed_cookie:
            headers["Cookie"] = self.fixed_cookie
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        with self.opener.open(req, timeout=30) as resp:
            text = resp.read()
            return json.loads(text) if text else None

    def session(self) -> str | None:
        return next((c.value for c in self.jar if c.name == "affinity_session"), None)


def plan(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    people = []
    for i in range(count):
        cluster = list(CLUSTERS)[i % len(CLUSTERS)]
        people.append({
            "name": f"Demo Person {i + 1:03d}",
            "workingOn": rng.choice(CLUSTERS[cluster]),
            "askMeAbout": rng.choice(CLUSTERS[cluster]),
            "lookingFor": "people to learn from",
            "howToTalk": "Synthetic demo attendee.",
            "needs": rng.choice(NEEDS),
            "allowMatching": True,
            "cluster": cluster,
        })
    return people


def seed(args) -> None:
    count = min(args.count, HARD_CAP)
    people = plan(count, args.seed)
    if args.dry_run:
        by_cluster = {c: sum(p["cluster"] == c for p in people) for c in CLUSTERS}
        with_needs = sum(bool(p["needs"]) for p in people)
        print(f"Dry run: would create {count} attendees {by_cluster}, {with_needs} with needs,"
              f" placement for {args.slot}, RSVP to {args.break_id}.")
        return
    path = Path(args.state)
    state = json.loads(path.read_text()) if path.exists() else []
    try:
        for person in people:
            c = Client(args.url, args.rate)
            me = c.call("POST", "/api/attendees")
            state.append({"attendeeId": me["attendeeId"], "session": c.session()})
            path.write_text(json.dumps(state, indent=1))
            card = {k: v for k, v in person.items() if k != "cluster"}
            c.call("PUT", "/api/card", card)
            c.call("POST", "/api/placements", {"slot": args.slot})
            c.call("POST", f"/api/breaks/{args.break_id}/rsvp", {"going": True})
            print(f"seeded {me['displayId']} ({person['cluster']}, needs={person['needs']})")
    finally:
        path.write_text(json.dumps(state, indent=1))
    print(f"Seeded {len(state)} attendees. Sessions saved to {args.state} for --reset.")


def reset(args) -> None:
    path = Path(args.state)
    if not path.exists():
        sys.exit(f"No {path}: nothing to reset (only attendees this script seeded can be removed).")
    state = json.loads(path.read_text())
    for entry in state:
        c = Client(args.url, args.rate, session=entry["session"])
        c.call("POST", f"/api/breaks/{args.break_id}/rsvp", {"going": False})
        c.call("DELETE", "/api/card")
    path.unlink()
    print(f"Reset {len(state)} seeded attendees (cards deleted, RSVPs withdrawn).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--slot", default="tue-1430")
    parser.add_argument("--break-id", default="brk-tue-1530")
    parser.add_argument("--rate", type=float, default=10.0, help="requests per second")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--state", default="seed-demo-state.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    reset(args) if args.reset else seed(args)


if __name__ == "__main__":
    main()
