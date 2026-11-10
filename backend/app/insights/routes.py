"""GET /api/insights (K17): live, anonymous charts about people in rooms.

The controller writes the rows (app/controller/insights.py). This route only
reads and aggregates them, so the UI and Dash0 show the same numbers.

Privacy rules, enforced here and not in the UI:
- Counts only. No attendee ID is in the source tables.
- A group with fewer than MIN_GROUP people shows no numbers, only "hidden".
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.board.routes import SLOTS, current_slot
from app.db import pool
from app.es import get_es
from app.search import mappings as m

log = logging.getLogger("affinity.insights")

router = APIRouter()

MIN_GROUP = 5          # smallest group we show a number for
HISTORY_MINUTES = 120  # how far back the occupancy lines go
DROP_WINDOW = 30       # seconds: the shortest window for a "drop" (it grows to 10% of the talk so far)
MIN_DROP = 5           # a drop smaller than this is not called out
PRIVACY = (
    "Counts only. No attendee IDs are stored for these charts. "
    f"A group with fewer than {MIN_GROUP} people is hidden."
)


def wait_stats(rows: list[tuple]) -> dict:
    """rows: (need_present, count, p50, p95) -> the timeToSeat block."""
    by = {need: (n, p50, p95) for need, n, p50, p95 in rows}

    def block(need: bool) -> dict:
        n, p50, p95 = by.get(need, (0, None, None))
        if n < MIN_GROUP:
            return {"count": n, "hidden": True}
        return {"count": n, "hidden": False, "p50Seconds": round(p50, 1), "p95Seconds": round(p95, 1)}

    with_needs, without = block(True), block(False)
    gap = None
    if not with_needs["hidden"] and not without["hidden"]:
        gap = round(with_needs["p95Seconds"] - without["p95Seconds"], 1)
    return {"withNeeds": with_needs, "withoutNeeds": without, "p95GapSeconds": gap}


def room_series(latest: list[tuple], history: list[tuple]) -> list[dict]:
    """latest: (room, node, seats, taken); history: (room, at, taken), oldest first."""
    points: dict[str, list[dict]] = {}
    for room, at, taken in history:
        points.setdefault(room, []).append({"at": at.isoformat(), "taken": taken})
    rooms = []
    for room, node, seats, taken in latest:
        rooms.append({
            "room": room,
            "node": node,
            "seats": seats,
            "taken": taken,
            "occupancy": round(taken / seats, 3) if seats else None,
            "history": points.get(room, []),
        })
    rooms.sort(key=lambda r: -(r["occupancy"] or 0))
    return rooms


def engagement(history: list[dict], started_at: datetime) -> dict | None:
    """How a talk held its room: peak, now, share of the peak that stayed, and the sharpest drop.

    history: [{"at": iso, "taken": n}], oldest first. Counts only, so this is about
    the room, never about a person.
    """
    pts = [((datetime.fromisoformat(p["at"]) - started_at).total_seconds(), p["taken"]) for p in history]
    if not pts:
        return None
    peak_t, peak = pts[0]
    for t, v in pts:
        if v >= peak:
            peak_t, peak = t, v
    now = pts[-1][1]
    window = max(DROP_WINDOW, 0.1 * (pts[-1][0] - pts[0][0]))
    drop = None
    for i, (ti, vi) in enumerate(pts):
        for tj, vj in pts[i + 1:]:
            if tj - ti > window:
                break
            if vi - vj >= MIN_DROP and (drop is None or vi - vj > drop["people"]):
                drop = {"people": vi - vj, "fromSeconds": round(ti), "toSeconds": round(tj)}
    kept = now / peak if peak else 1.0
    word = "HELD" if kept >= 0.9 else "STEADY" if kept >= 0.75 else "DROPPED"
    return {"peak": peak, "peakAtSeconds": round(peak_t), "now": now, "kept": round(kept, 3),
            "word": word, "drop": drop}


def talk_titles(nodes: list[str]) -> dict[str, dict]:
    """node -> {title, track} from the talks index. Best effort: the charts work without it."""
    if not nodes:
        return {}
    try:
        resp = get_es().search(index=m.TALKS, size=len(nodes), query={"terms": {"node": nodes}},
                               source=["node", "title", "track"])
    except Exception as err:  # search down or index missing: show rooms without titles
        log.info("no talk titles for insights (%s)", type(err).__name__)
        return {}
    return {h["_source"]["node"]: {"title": h["_source"].get("title"), "track": h["_source"].get("track")}
            for h in resp["hits"]["hits"]}


@router.get("/api/insights")
def insights(slot: str | None = Query(default=None)) -> dict:
    now = datetime.now(UTC)
    with pool().connection() as conn:
        if slot not in SLOTS:
            # The slot with the newest numbers, so the charts show what is happening, not an empty slot.
            newest = conn.execute("SELECT slot FROM occupancy_samples ORDER BY at DESC LIMIT 1").fetchone()
            slot = newest[0] if newest and newest[0] in SLOTS else current_slot(now)
        latest = conn.execute(
            "SELECT DISTINCT ON (node) room, node, seats, taken FROM occupancy_samples"
            " WHERE slot = %s ORDER BY node, at DESC", (slot,)
        ).fetchall()
        history = conn.execute(
            "SELECT room, at, taken FROM occupancy_samples WHERE slot = %s"
            " AND at > now() - make_interval(mins => %s) ORDER BY at", (slot, HISTORY_MINUTES)
        ).fetchall()
        waits = conn.execute(
            "SELECT need_present, count(*),"
            " percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds),"
            " percentile_cont(0.95) WITHIN GROUP (ORDER BY seconds)"
            " FROM seat_waits WHERE slot = %s GROUP BY need_present", (slot,)
        ).fetchall()
    rooms = room_series(latest, history)
    times = [datetime.fromisoformat(p["at"]) for r in rooms for p in r["history"]]
    started_at = min(times) if times else now
    titles = talk_titles([r["node"] for r in rooms])
    for r in rooms:
        r["talk"] = titles.get(r["node"])
        r["engagement"] = engagement(r["history"], started_at)
    seats = sum(r["seats"] for r in rooms)
    taken = sum(r["taken"] for r in rooms)
    return {
        "slot": slot,
        "generatedAt": now.isoformat(),
        "startedAt": started_at.isoformat(),
        "totals": {"seats": seats, "taken": taken, "occupancy": round(taken / seats, 3) if seats else None},
        "rooms": rooms,
        "timeToSeat": wait_stats(waits),
        "privacy": PRIVACY,
    }
