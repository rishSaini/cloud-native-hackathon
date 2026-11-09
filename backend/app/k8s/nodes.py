"""Desired Node taints and labels from room state (R7). Pure functions, easy to test."""

import json
from pathlib import Path

from app.cards.capabilities import SIGNAL_REMOVES, label

KWOK_TAINT = {"key": "kwok.x-k8s.io/node", "value": "fake", "effect": "NoSchedule"}
FULL_TAINT = {"key": "affinity.dev/full", "value": "true", "effect": "NoSchedule"}
CLOSED_TAINT = {"key": "affinity.dev/closed", "value": "true", "effect": "NoExecute"}
OWNED = {FULL_TAINT["key"], CLOSED_TAINT["key"]}
VENUE = Path(__file__).resolve().parents[3] / "data" / "venue.json"


def venue_caps() -> dict[str, set[str]]:
    """room id -> capability codes the room has when nothing is wrong."""
    venue = json.loads(VENUE.read_text())
    return {room["id"]: set(room["caps"]) for room in venue["rooms"]}


def desired_taints(status: str, current: list[dict]) -> list[dict]:
    taints = [t for t in current if t["key"] not in OWNED]
    if status == "full":
        taints.append(FULL_TAINT)
    if status == "closed":
        taints.append(CLOSED_TAINT)
    return taints


def removed_codes(signals: dict) -> set[str]:
    removed = set()
    if signals.get("captions") == "down":
        removed.add(SIGNAL_REMOVES["captions_down"])
    if signals.get("very_loud"):
        removed.add(SIGNAL_REMOVES["very_loud"])
    if signals.get("access_blocked"):
        removed.add(SIGNAL_REMOVES["access_blocked"])
    return removed


def label_patch(current_labels: dict, room_caps: set[str], signals: dict) -> dict:
    """Labels to set ("true") or remove (None) so the Node offers only what works now."""
    removed = removed_codes(signals)
    patch = {}
    for code in room_caps:
        key = label(code)
        want = code not in removed
        has = current_labels.get(key) == "true"
        if want and not has:
            patch[key] = "true"
        elif has and not want:
            patch[key] = None
    return patch


def taint_key(taints) -> list[tuple]:
    return sorted((t["key"], t.get("value"), t["effect"]) for t in taints)
