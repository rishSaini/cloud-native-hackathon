"""Attendee sessions and hashing (contract, owner: Rishabh, R4).

A session is an HttpOnly cookie `affinity_session` holding `<attendee id>.<HMAC>`.
`current_attendee_id` checks the HMAC and needs no database call. Tests can still
override it:

    app.dependency_overrides[current_attendee_id] = lambda: "att-123"
"""

import hashlib
import hmac
import logging
import os
import secrets

from fastapi import HTTPException, Request, Response, status

log = logging.getLogger("affinity.auth")

COOKIE = "affinity_session"
ID_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no 0/o or 1/l, so IDs read clearly aloud
ID_LENGTH = 6
_DEV_SIGNING_KEY = "affinity-dev-signing-key"


def _signing_key() -> bytes:
    return (os.getenv("SESSION_SIGNING_KEY") or _DEV_SIGNING_KEY).encode()


def new_attendee_id() -> str:
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(ID_LENGTH))


def attendee_hash(attendee_id: str) -> str:
    """HMAC-SHA256 of the attendee ID, hex. Safe for telemetry and ES."""
    return hmac.new(_signing_key(), attendee_id.encode(), hashlib.sha256).hexdigest()


def _signature(attendee_id: str) -> str:
    return hmac.new(_signing_key(), f"session:{attendee_id}".encode(), hashlib.sha256).hexdigest()


def session_value(attendee_id: str) -> str:
    return f"{attendee_id}.{_signature(attendee_id)}"


def attendee_from_session(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    attendee_id, signature = value.rsplit(".", 1)
    if hmac.compare_digest(signature, _signature(attendee_id)):
        return attendee_id
    return None


def set_session(response: Response, request: Request, attendee_id: str) -> None:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    response.set_cookie(
        COOKIE,
        session_value(attendee_id),
        httponly=True,
        samesite="lax",
        secure=proto == "https",
        max_age=60 * 60 * 24 * 7,
    )


def current_attendee_id(request: Request) -> str:
    """FastAPI dependency: the signed-in attendee's random ID, or 401."""
    attendee_id = attendee_from_session(request.cookies.get(COOKIE))
    if attendee_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    return attendee_id
