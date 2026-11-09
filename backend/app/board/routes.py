"""GET /api/board (K12), plus the break summary that R10 writes for "nobody alone"."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query

from app.es import get_es
from app.search import mappings as m

router = APIRouter()

DENVER = ZoneInfo("America/Denver")
SLOTS = ["tue-0900", "tue-1030", "tue-1330", "tue-1430", "tue-1600"]  # contract fixed IDs
ROOMS = ["room-101", "room-155", "room-251", "room-hall-b"]
SUMMARY_INDEX = "board-summary"  # one doc, "last-break", written by record_break_summary
ACTIVE = ["open", "acknowledged"]


def current_slot(now: datetime) -> str:
    """The latest slot that has started (Tuesday, Denver time), or the first slot."""
    hhmm = now.astimezone(DENVER).strftime("%H%M")
    started = [s for s in SLOTS if s[4:] <= hhmm]
    return started[-1] if started else SLOTS[0]


def board_searches() -> list[dict]:
    return [
        {"index": m.ROOM_STATE, "ignore_unavailable": True},
        {"size": len(ROOMS) * 5, "query": {"terms": {"room": ROOMS}},
         "_source": ["room", "status", "signals", "changed_at", "seats_total", "seats_free"]},
        {"index": m.INCIDENTS, "ignore_unavailable": True},
        {"size": 50, "query": {"terms": {"state": ACTIVE}}, "_source": ["id", "room", "kind", "state", "opened_at"]},
        {"index": m.ROOM_REPORTS, "ignore_unavailable": True},
        {"size": 0, "query": {"range": {"@timestamp": {"gte": "now-30m"}}},
         "aggs": {"rooms": {"terms": {"field": "room", "size": 50},
                            "aggs": {"latest": {"max": {"field": "@timestamp"}}}}}},
        {"index": SUMMARY_INDEX, "ignore_unavailable": True},
        {"size": 1, "query": {"ids": {"values": ["last-break"]}}},
    ]


def _hits(resp: dict) -> list[dict]:
    return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]


def build_board(responses: list[dict], slot: str, now: datetime) -> dict:
    states = {s["room"]: s for s in _hits(responses[0])}
    incidents = {}
    for inc in _hits(responses[1]):
        incidents.setdefault(inc["room"], inc)
    latest = {
        b["key"]: b["latest"]["value"]
        for b in responses[2].get("aggregations", {}).get("rooms", {}).get("buckets", [])
    }
    summary = next(iter(_hits(responses[3])), None)

    rooms = []
    for room in ROOMS:
        st = states.get(room, {})
        signals = st.get("signals") or {}
        inc = incidents.get(room)
        minutes_ago = round((now.timestamp() * 1000 - latest[room]) / 60000) if room in latest else None
        seats, free = st.get("seats_total"), st.get("seats_free")
        captions = signals.get("captions") or "unknown"
        rooms.append({
            "id": room,
            "name": room,
            "slot": slot,
            "status": (st.get("status") or "open").upper(),  # words, never color alone
            "seats": seats,
            "seatsFree": free,
            "taken": seats - free if seats is not None and free is not None else None,
            "captions": captions,
            "openIncident": inc is not None,
            "incident": {"id": inc["id"], "type": inc["kind"], "state": inc["state"]} if inc else None,
            "reportedMinutesAgo": minutes_ago,
            "climate": {
                "noise": "loud" if signals.get("very_loud") else None,
                "light": None,
                "captions": None if captions == "unknown" else captions,
                "minutesAgo": minutes_ago,
            },
        })
    board = {"slot": slot, "rooms": rooms, "attendees": [], "groups": [], "events": []}
    if summary and summary.get("opted_in"):
        board["alone"] = summary.get("alone", 0)
        board["nobodyAloneRate"] = round(1 - summary.get("alone", 0) / summary["opted_in"], 3)
        board["lastBreak"] = summary.get("break")
    return board


@router.get("/api/board")
def get_board(slot: str | None = Query(None, pattern=r"^[a-z]{3}-\d{4}$"), es=Depends(get_es)):
    now = datetime.now(timezone.utc)
    slot = slot or current_slot(now)
    responses = es.msearch(searches=board_searches())["responses"]
    return {"board": build_board(responses, slot, now)}


def record_break_summary(es, break_id: str, opted_in: int, alone: int) -> None:
    """For R10: after a break is solved, store the counts the board shows. Counts only."""
    es.index(index=SUMMARY_INDEX, id="last-break",
             document={"break": break_id, "opted_in": opted_in, "alone": alone,
                       "at": datetime.now(timezone.utc).isoformat()})
