"""Generate data/sample-schedule.json: synthetic talks on the contract's fixed IDs (K2).

One talk per talk Node (slot x room): 5 slots x 4 rooms = 20 talks, so every
`node` matches a Node from Rishabh's gen_nodes.py. Speakers are obviously
synthetic, and nothing comes from the real KubeCon schedule.

    python scripts/gen_schedule.py     # or `make schedule`

Search demo guard: no talk may contain the words of the K6 demo query
"make my apps boot quicker", so the cold-start talk can only win on meaning.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parents[1] / "data" / "sample-schedule.json"
DENVER = ZoneInfo("America/Denver")
DAY = (2026, 11, 10)  # Tuesday of KubeCon + CloudNativeCon North America 2026

# Fixed IDs from docs/tasks/karthik.md, "Shared contract".
SLOTS = ["tue-0900", "tue-1030", "tue-1330", "tue-1430", "tue-1600"]
ROOMS = ["room-101", "room-155", "room-251", "room-hall-b"]

# (track, title, abstract), in slot order, then room order within each slot.
TALKS = [
    # tue-0900
    ("Accessibility", "Captions, quiet rooms and the hallway track",
     "What deaf, autistic and first-time attendees need from a conference, and how organizers "
     "can provide it without singling anyone out."),
    ("Observability", "OpenTelemetry from zero to useful",
     "Add traces, metrics and logs to an existing service in one afternoon, and find your first "
     "real bottleneck."),
    ("Security", "Signed images and SBOMs without slowing developers down",
     "Sign container images, publish SBOMs and enforce both at admission time, with a rollout "
     "plan that teams accept."),
    ("Performance", "Cold starts are a choice",
     "Lazy image pulling, slimmer images and tuned startup probes cut pod start time from "
     "minutes to seconds."),
    # tue-1030
    ("Networking", "eBPF for people who are not kernel developers",
     "What eBPF can see inside your cluster, explained with diagrams instead of C code."),
    ("Platform engineering", "Platform engineering for teams of five",
     "A small team's path to golden paths, self-service environments and fewer support tickets."),
    ("Cost", "Cutting your cloud bill with right-sized requests",
     "Measure real CPU and memory use, set requests that fit, and stop paying for idle capacity."),
    ("AI", "Serving LLMs on Kubernetes without wasting GPUs",
     "Batching, GPU sharing and scale-to-zero patterns that keep expensive accelerators busy."),
    # tue-1330
    ("Community", "Your first pull request to Kubernetes",
     "Find a good first issue, get a reviewer's attention and land your first contribution "
     "this week."),
    ("Operations", "GitOps at scale: lessons from a thousand clusters",
     "What broke when one team moved every cluster to Argo CD, and the guardrails that fixed it."),
    ("Core Kubernetes", "How kube-scheduler picks a node",
     "Filters, scores, affinity, taints and extended resources, explained with live examples."),
    ("Security", "Zero-trust networking with a service mesh",
     "Mutual TLS, identity-based policy, and what to do when certificates expire at 3 AM."),
    # tue-1430
    ("Scaling", "Autoscaling explained for first-timers",
     "A beginner's tour of the Horizontal Pod Autoscaler, the Vertical Pod Autoscaler and KEDA, "
     "with one small demo service."),
    ("Data", "Postgres on Kubernetes in production",
     "Backups, failover and upgrades with an operator, and the mistakes to avoid."),
    ("Observability", "Tracing one slow request across forty services",
     "Follow a slow checkout through a real trace, and learn which spans actually matter."),
    ("Developer experience", "Faster CI with throwaway clusters",
     "Create a short-lived cluster for every pull request, and keep test runs under ten minutes."),
    # tue-1600
    ("Accessibility", "Accessible dashboards for screen reader users",
     "Keep operational dashboards usable without sight, color or a mouse."),
    ("Networking", "Gateway API: multi-cluster traffic, boring on purpose",
     "Route traffic across clusters with the Gateway API, and keep failover predictable."),
    ("Reliability", "Chaos engineering on a budget",
     "Run safe failure experiments in staging, and turn what breaks into runbooks."),
    ("Data", "Vector search next to your services with Elasticsearch",
     "Run hybrid keyword and semantic search inside your cluster, and size it for production."),
]


def starts_at(slot: str) -> str:
    """'tue-1430' -> '2026-11-10T14:30:00-07:00' (America/Denver, explicit offset)."""
    hour, minute = int(slot[4:6]), int(slot[6:8])
    return datetime(*DAY, hour, minute, tzinfo=DENVER).isoformat()


def build() -> dict:
    assert len(TALKS) == len(SLOTS) * len(ROOMS), "one talk per slot and room"
    talks = []
    for i, (track, title, abstract) in enumerate(TALKS):
        slot, room = SLOTS[i // len(ROOMS)], ROOMS[i % len(ROOMS)]
        talks.append({
            "id": f"t{i + 1:02d}",
            "slot": slot,
            "room": room,
            "node": f"{slot}-{room}",
            "starts_at": starts_at(slot),
            "track": track,
            "title": title,
            "abstract": abstract,
            "speakers": [f"Sample Speaker {i + 1:02d} (Example Co)"],
        })
    return {
        "note": "Synthetic schedule for development and demos. Not real KubeCon data.",
        "timezone": "America/Denver",
        "slots": [{"id": slot, "starts_at": starts_at(slot)} for slot in SLOTS],
        "rooms": ROOMS,
        "talks": talks,
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"Wrote {len(TALKS)} talks to {OUT}")
