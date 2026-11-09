"""Staff incident routes (K11).

Staff authenticate with the shared STAFF_TOKEN: either the X-Staff-Token header,
or the cookie that GET /api/staff/login?token=... sets (the frontend sends
cookies, not headers). Without STAFF_TOKEN set, every staff route answers 401.
"""

import hmac
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.es import get_es
from app.incidents import store

router = APIRouter()
COOKIE = "affinity_staff"


def _valid(token: str | None) -> bool:
    expected = os.getenv("STAFF_TOKEN")
    return bool(expected and token and hmac.compare_digest(token, expected))


def require_staff(request: Request) -> None:
    if not _valid(request.headers.get("x-staff-token") or request.cookies.get(COOKIE)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Staff only")


@router.get("/api/staff/login")
def staff_login(token: str, request: Request, response: Response):
    if not _valid(token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong staff token")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=proto == "https", max_age=60 * 60 * 12)
    return {"ok": True}


def to_api(doc: dict) -> dict:
    return {"id": doc["id"], "room": doc["room"], "roomName": doc["room"], "kind": doc["kind"],
            "state": doc["state"], "openedAt": doc["opened_at"],
            "acknowledgedAt": doc.get("acknowledged_at"), "resolvedAt": doc.get("resolved_at")}


@router.get("/api/staff/incidents", dependencies=[Depends(require_staff)])
def staff_incidents(all: bool = False, es=Depends(get_es)):
    return [to_api(d) for d in store.list_incidents(es, include_resolved=all)]


class IncidentPatch(BaseModel):
    state: Literal["acknowledged", "resolved"]


@router.patch("/api/staff/incidents/{incident_id}", dependencies=[Depends(require_staff)])
def update_incident(incident_id: str, patch: IncidentPatch, es=Depends(get_es)):
    try:
        return to_api(store.transition(es, incident_id, patch.state))
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such incident")
    except store.TransitionError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, str(err))
