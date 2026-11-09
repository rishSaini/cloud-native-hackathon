"""Room-state engine (K10): turn recent reports into live room state.

Room state lives in Elasticsearch, not app memory: an aggregation over the last
30 minutes of `room-reports` gives report counts per signal and minute. Each
report counts less as it ages:

    confidence(signal) = sum(weight * exp(-age_minutes / REPORT_DECAY_MINUTES))

Hysteresis stops flicker: a state turns on at SET_THRESHOLD and turns off only
below CLEAR_THRESHOLD. Three "full" reports make a room full at once, and with
no new reports it clears by itself about 11 minutes later.

On a change, it writes Karthik's fields of the `room-state` document, with the
current `traceparent`, so Rishabh's controller can link its taint span to
this trace.
"""

import math
import os
from datetime import datetime, timedelta, timezone

from elasticsearch import NotFoundError
from opentelemetry import propagate, trace

from app.es import get_es
from app.search import mappings as m
from app.telemetry.attrs import set_attrs

tracer = trace.get_tracer("affinity")

DECAY_MINUTES = float(os.getenv("REPORT_DECAY_MINUTES", "10"))
WINDOW = "30m"
SET_THRESHOLD = 2.5  # about three fresh reports
CLEAR_THRESHOLD = 1.0
WEIGHTS = {
    "full": 1.0,
    "standing_room": 0.5,  # counts towards full, but less
    "seats_available": 1.0,  # counts against full
    "very_loud": 1.0,
    "captions_working": 1.0,
    "captions_down": 1.0,
    "access_blocked": 1.0,
}
DEFAULT_STATE = {
    "status": "open",
    "signals": {"captions": "unknown", "very_loud": False, "access_blocked": False},
}


# ---------- Pure logic ----------

def confidences(agg: dict, now: datetime, cleared: dict[str, str] | None = None) -> dict[str, float]:
    """Decayed confidence per signal, from the signal x minute aggregation.

    `cleared` maps a signal to the time staff resolved it (K11): reports from
    before that minute stop counting, so a fixed room does not flip back.
    """
    result = {}
    cleared_ms = {sig: datetime.fromisoformat(ts).timestamp() * 1000 for sig, ts in (cleared or {}).items()}
    for sig in agg["signals"]["buckets"]:
        total = 0.0
        for minute in sig["per_minute"]["buckets"]:
            if minute["key"] < cleared_ms.get(sig["key"], float("-inf")):
                continue
            age = (now.timestamp() * 1000 - minute["key"]) / 60000 - 0.5  # middle of the minute
            total += minute["doc_count"] * math.exp(-max(age, 0.0) / DECAY_MINUTES)
        result[sig["key"]] = round(total * WEIGHTS.get(sig["key"], 1.0), 3)
    return result


def _flag(was_on: bool, score: float) -> bool:
    return score >= CLEAR_THRESHOLD if was_on else score >= SET_THRESHOLD


def derive(prev: dict, conf: dict[str, float]) -> dict:
    """The next state from the previous state and the confidences."""
    prev_signals = {**DEFAULT_STATE["signals"], **(prev.get("signals") or {})}
    prev_status = prev.get("status", "open")

    if prev_status == "closed":
        status = "closed"  # only staff or the controller reopen a closed room
    else:
        fullness = conf.get("full", 0.0) + conf.get("standing_room", 0.0) - conf.get("seats_available", 0.0)
        status = "full" if _flag(prev_status == "full", fullness) else "open"

    if _flag(prev_signals["captions"] == "down", conf.get("captions_down", 0.0)):
        captions = "down"
    elif conf.get("captions_working", 0.0) >= CLEAR_THRESHOLD:
        captions = "working"
    else:
        captions = "unknown"  # only state what we know

    return {
        "status": status,
        "signals": {
            "captions": captions,
            "very_loud": _flag(prev_signals["very_loud"], conf.get("very_loud", 0.0)),
            "access_blocked": _flag(prev_signals["access_blocked"], conf.get("access_blocked", 0.0)),
        },
    }


# ---------- Elasticsearch ----------

def report_aggregation(es, room: str) -> dict:
    try:
        return es.search(
            index=m.ROOM_REPORTS,
            size=0,
            query={"bool": {"filter": [
                {"term": {"room": room}},
                {"range": {"@timestamp": {"gte": f"now-{WINDOW}"}}},
            ]}},
            aggs={"signals": {
                "terms": {"field": "signal", "size": 20},
                "aggs": {"per_minute": {"date_histogram": {"field": "@timestamp", "fixed_interval": "1m"}}},
            }},
        )["aggregations"]
    except NotFoundError:
        return {"signals": {"buckets": []}}


def current_state(es, room: str) -> dict:
    try:
        return es.get(index=m.ROOM_STATE, id=room)["_source"]
    except NotFoundError:
        return {}


def current_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def recompute(room: str, now: datetime | None = None, es=None) -> dict:
    """Recompute one room's state. Writes to room-state only when something changed."""
    es = es or get_es()
    now = now or datetime.now(timezone.utc)
    prev = current_state(es, room)
    cleared = (prev.get("confidence") or {}).get("cleared") or {}
    conf = confidences(report_aggregation(es, room), now, cleared)
    nxt = derive(prev, conf)
    nxt["signals"]["captions"] = staff_confirmed_captions(nxt["signals"]["captions"], cleared, now)
    changed = nxt["status"] != prev.get("status", "open") or nxt["signals"] != {
        **DEFAULT_STATE["signals"], **(prev.get("signals") or {})
    }
    if changed or not prev:
        with tracer.start_as_current_span("talkscout.room.state.updated") as span:
            set_attrs(span, room_id=room)
            es.update(
                index=m.ROOM_STATE,
                id=room,
                doc={
                    "room": room,
                    **nxt,
                    "confidence": {**conf, "cleared": cleared},
                    "changed_at": now.isoformat(),
                    "traceparent": current_traceparent(),
                },
                doc_as_upsert=True,  # keeps Rishabh's seats fields
                refresh="wait_for",
            )
        open_incidents(es, room, prev, nxt)
    return {"room": room, **nxt, "confidence": conf, "changed": changed}


def staff_confirmed_captions(captions: str, cleared: dict[str, str], now: datetime) -> str:
    """A staff resolution (K11) is evidence too: captions count as working for
    30 minutes after it, unless new "down" reports turn them down again."""
    stamp = cleared.get("captions_down")
    if captions == "unknown" and stamp and now - datetime.fromisoformat(stamp) < timedelta(minutes=30):
        return "working"
    return captions


def open_incidents(es, room: str, prev: dict, nxt: dict) -> None:
    """K11: captions going down or access becoming blocked opens a staff incident."""
    from app.incidents.store import open_incident

    before = {**DEFAULT_STATE["signals"], **(prev.get("signals") or {})}
    if nxt["signals"]["captions"] == "down" and before["captions"] != "down":
        open_incident(es, room, "captions")
    if nxt["signals"]["access_blocked"] and not before["access_blocked"]:
        open_incident(es, room, "access")
