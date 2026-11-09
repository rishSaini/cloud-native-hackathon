"""GET /api/insights (K17): live, anonymous charts about people in rooms.

The controller writes the rows (app/controller/insights.py). This route only
reads and aggregates them, so the UI and Dash0 show the same numbers.

Privacy rules, enforced here and not in the UI:
- Counts only. No attendee ID is in the source tables.
- A group with fewer than MIN_GROUP people shows no numbers, only "hidden".
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.board.routes import SLOTS, current_slot
from app.db import pool

router = APIRouter()

MIN_GROUP = 5          # smallest group we show a number for
HISTORY_MINUTES = 120  # how far back the occupancy lines go
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


@router.get("/api/insights")
def insights(slot: str | None = Query(default=None)) -> dict:
    now = datetime.now(UTC)
    slot = slot if slot in SLOTS else current_slot(now)
    with pool().connection() as conn:
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
    seats = sum(r["seats"] for r in rooms)
    taken = sum(r["taken"] for r in rooms)
    return {
        "slot": slot,
        "generatedAt": now.isoformat(),
        "totals": {"seats": seats, "taken": taken, "occupancy": round(taken / seats, 3) if seats else None},
        "rooms": rooms,
        "timeToSeat": wait_stats(waits),
        "privacy": PRIVACY,
    }
