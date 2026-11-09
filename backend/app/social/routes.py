"""POST /api/connections, /api/blocks, /api/safety-reports (R11).

People are addressed by displayId ("attendee-<id>"). A connection is saved only
when both people propose it. Blocks feed R10's solver inputs. Safety reports are
stored for organizers and never written to logs.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import current_attendee_id
from app.db import pool

router = APIRouter()


def attendee_of(display_id: str) -> str:
    if not display_id.startswith("attendee-") or len(display_id) > 40:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown person")
    return display_id.removeprefix("attendee-")


class ConnectionIn(BaseModel):
    displayId: str
    groupId: str | None = None


class BlockIn(BaseModel):
    blockedDisplayId: str


class SafetyIn(BaseModel):
    kind: Literal["harassment", "unsafe", "other"] = "other"
    aboutDisplayId: str | None = None
    details: str = Field("", max_length=1000)


@router.post("/api/connections")
def propose_connection(body: ConnectionIn, attendee_id: str = Depends(current_attendee_id)):
    other = attendee_of(body.displayId)
    if other == attendee_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That's you")
    with pool().connection() as conn:
        if conn.execute("SELECT 1 FROM blocks WHERE (blocker_id, blocked_id) IN ((%s, %s), (%s, %s))",
                        (attendee_id, other, other, attendee_id)).fetchone():
            return {"status": "pending"}  # never reveal a block
        conn.execute("INSERT INTO connection_proposals (from_id, to_id, group_id) VALUES (%s, %s, %s)"
                     " ON CONFLICT DO NOTHING", (attendee_id, other, body.groupId))
        mutual = conn.execute("SELECT group_id FROM connection_proposals WHERE from_id = %s AND to_id = %s",
                              (other, attendee_id)).fetchone()
        if not mutual:
            return {"status": "pending"}
        a, b = sorted((attendee_id, other))
        place = body.groupId or mutual[0] or "Affinity"
        conn.execute("INSERT INTO connections (attendee_a, attendee_b, met_at_label) VALUES (%s, %s, %s)"
                     " ON CONFLICT DO NOTHING", (a, b, place))
    return {"status": "connected"}


@router.post("/api/blocks")
def block(body: BlockIn, attendee_id: str = Depends(current_attendee_id)):
    other = attendee_of(body.blockedDisplayId)
    with pool().connection() as conn:
        if conn.execute("SELECT 1 FROM attendees WHERE id = %s", (other,)).fetchone():
            conn.execute("INSERT INTO blocks (blocker_id, blocked_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                         (attendee_id, other))
            conn.execute("DELETE FROM connection_proposals WHERE (from_id, to_id) IN ((%s, %s), (%s, %s))",
                         (attendee_id, other, other, attendee_id))
    return {"ok": True}


@router.post("/api/safety-reports", status_code=status.HTTP_201_CREATED)
def safety_report(body: SafetyIn, attendee_id: str = Depends(current_attendee_id)):
    about = attendee_of(body.aboutDisplayId) if body.aboutDisplayId else None
    with pool().connection() as conn:
        conn.execute("INSERT INTO safety_reports (reporter_id, about_id, kind, details) VALUES (%s, %s, %s, %s)",
                     (attendee_id, about, body.kind, body.details))
    return {"ok": True}
