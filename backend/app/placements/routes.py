"""POST /api/placements and GET /api/placements/current (R6).

The API only writes the request; the controller does the placing. The response
follows the shape the frontend uses: status "Pending" or "Scheduled", talk,
room, a plain-language reason, options and a kubectl line.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.auth import current_attendee_id
from app.db import pool
from app.es import get_es

router = APIRouter()


class PlacementIn(BaseModel):
    slot: str = Field(pattern=r"^[a-z]{3}-\d{4}$")


@router.post("/api/placements", status_code=status.HTTP_202_ACCEPTED)
def request_placement(body: PlacementIn, attendee_id: str = Depends(current_attendee_id)):
    with pool().connection() as conn:
        conn.execute("INSERT INTO attendees (id) VALUES (%s) ON CONFLICT DO NOTHING", (attendee_id,))
        conn.execute(
            "INSERT INTO placement_requests (attendee_id, slot) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (attendee_id, body.slot),
        )
    return {"status": "Pending", "slot": body.slot}


def talk_for(es, node: str) -> dict | None:
    try:
        hits = es.search(index="talks", size=1, query={"term": {"node": node}},
                         source=["id", "title", "starts_at", "slot", "room"])["hits"]["hits"]
    except Exception:  # the talk title is a nicety; the placement stands without it
        return None
    if not hits:
        return None
    t = hits[0]["_source"]
    return {"id": t.get("id"), "title": t.get("title"), "startsAt": t.get("starts_at"), "slot": t.get("slot")}


def to_response(row, es) -> dict:
    attendee_id, slot, pod, state, node, reason, sched_msg, options = row
    if state == "Scheduled":
        room = node[len(slot) + 1:]
        return {
            "status": "Scheduled", "slot": slot, "reason": None, "options": [],
            "talk": talk_for(es, node),
            "room": {"id": room, "name": room},
            "kubectl": f"{pod}   Running   {node}",
        }
    return {
        "status": "Pending", "slot": slot, "talk": None, "room": None,
        "reason": reason, "options": options or [],
        # The raw scheduler text goes only to this attendee's own kubectl view, never to the board.
        "kubectl": f"{pod}   Pending   {sched_msg}" if sched_msg else f"{pod}   Pending   <none>",
    }


@router.get("/api/placements/current")
def current_placement(attendee_id: str = Depends(current_attendee_id), es=Depends(get_es)):
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT attendee_id, slot, pod_name, status, node, reason, scheduler_message, options"
            " FROM placements WHERE attendee_id = %s ORDER BY updated_at DESC LIMIT 1",
            (attendee_id,),
        ).fetchone()
        if row is None:
            requested = conn.execute(
                "SELECT slot FROM placement_requests WHERE attendee_id = %s ORDER BY created_at DESC LIMIT 1",
                (attendee_id,),
            ).fetchone()
            if requested is None:
                return {"placement": None}
            return {"placement": {"status": "Pending", "slot": requested[0], "talk": None, "room": None,
                                  "reason": "We're still finding you a seat.", "options": [], "kubectl": None}}
    return {"placement": to_response(row, es)}
