"""Break routes (R10): RSVP, the current group, check-in, and staff "form groups now"."""

import hmac
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth import current_attendee_id
from app.cards.store import get_store
from app.db import pool

router = APIRouter()
PLACES = {"tbl-quiet-window": "the quiet table by the window"}
OPENER = "What are you working on this week?"


class RsvpIn(BaseModel):
    going: bool = True


class CheckInIn(BaseModel):
    status: Literal["here", "on-the-way", "late"] = "here"


def require_staff(request: Request) -> None:
    expected = os.getenv("STAFF_TOKEN")
    token = request.headers.get("x-staff-token") or request.cookies.get("affinity_staff")
    if not (expected and token and hmac.compare_digest(token, expected)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Staff only")


@router.post("/api/breaks/{break_id}/rsvp")
def rsvp(break_id: str, body: RsvpIn, attendee_id: str = Depends(current_attendee_id)):
    with pool().connection() as conn:
        if not conn.execute("SELECT 1 FROM breaks WHERE id = %s", (break_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such break")
        conn.execute("INSERT INTO attendees (id) VALUES (%s) ON CONFLICT DO NOTHING", (attendee_id,))
        if body.going:
            conn.execute("INSERT INTO break_rsvps (break_id, attendee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                         (break_id, attendee_id))
        else:
            conn.execute("DELETE FROM break_rsvps WHERE break_id = %s AND attendee_id = %s", (break_id, attendee_id))
    return {"breakId": break_id, "status": "going" if body.going else "not-going"}


@router.post("/api/staff/breaks/{break_id}/form", dependencies=[Depends(require_staff)])
def form_now(break_id: str):
    """Demo: ask the controller to form this break's groups on its next pass."""
    with pool().connection() as conn:
        row = conn.execute("UPDATE breaks SET form_requested_at = now() WHERE id = %s RETURNING id", (break_id,))
        if not row.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such break")
    return {"breakId": break_id, "status": "forming"}


def member_view(store, viewer: str, member: str, check_in_status: str) -> dict:
    card = None
    try:
        card = store.load(member)
    except Exception:  # an unreadable card shows as just the display ID
        card = None
    view = {"displayId": f"attendee-{member}", "status": check_in_status}
    if card:
        view.update({k: card.get(k) for k in ("name", "pronouns", "workingOn", "askMeAbout", "howToTalk", "lookingFor")})
    return view


@router.get("/api/groups/current")
def current_group(attendee_id: str = Depends(current_attendee_id), store=Depends(get_store)):
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT g.id, g.slot, g.table_id, b.starts_at, gm.check_in_status FROM group_members gm"
            " JOIN groups g ON g.id = gm.group_id JOIN breaks b ON b.id = g.slot"
            " WHERE gm.attendee_id = %s ORDER BY b.starts_at DESC LIMIT 1", (attendee_id,)).fetchone()
        if row is None:
            return {"group": None}
        group_id, break_id, table_node, starts_at, my_status = row
        # Only members with a valid grant from this viewer's group are shown with their card.
        others = conn.execute(
            "SELECT gm.attendee_id, gm.check_in_status FROM group_members gm"
            " JOIN card_grants cg ON cg.owner_id = gm.attendee_id AND cg.viewer_id = %s"
            "  AND cg.reason = 'group' AND cg.revoked_at IS NULL AND cg.expires_at > now()"
            " WHERE gm.group_id = %s AND gm.attendee_id <> %s ORDER BY gm.attendee_id",
            (attendee_id, group_id, attendee_id)).fetchall()
    table = table_node[len(break_id) + 1:]
    return {"group": {
        "id": group_id, "breakId": break_id, "tableId": table,
        "place": PLACES.get(table, f"table {table.removeprefix('tbl-')}"),
        "startsAt": starts_at.isoformat(), "opener": OPENER,
        "myStatus": my_status,
        "members": [member_view(store, attendee_id, m, check_in_status) for m, check_in_status in others],
    }}


@router.post("/api/groups/{group_id}/check-in")
def check_in(group_id: str, body: CheckInIn, attendee_id: str = Depends(current_attendee_id)):
    with pool().connection() as conn:
        row = conn.execute(
            "UPDATE group_members SET check_in_status = %s,"
            " checked_in_at = CASE WHEN %s = 'here' THEN now() ELSE NULL END"
            " WHERE group_id = %s AND attendee_id = %s RETURNING group_id",
            (body.status, body.status, group_id, attendee_id)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not in this group")
    return {"groupId": group_id, "status": body.status}
