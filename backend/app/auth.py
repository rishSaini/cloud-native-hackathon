"""Attendee sessions and hashing (contract, owner: Rishabh).

R0 stub: `current_attendee_id` always answers 401 until sessions land (R4).
Other routers can already `Depends(current_attendee_id)` and override it in tests:

    app.dependency_overrides[current_attendee_id] = lambda: "att-123"
"""

import hashlib
import hmac
import os

from fastapi import HTTPException, Request, status

_DEV_SIGNING_KEY = "affinity-dev-signing-key"


def _signing_key() -> bytes:
    return (os.getenv("SESSION_SIGNING_KEY") or _DEV_SIGNING_KEY).encode()


def current_attendee_id(request: Request) -> str:
    """FastAPI dependency: the signed-in attendee's random ID, or 401."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in",
    )


def attendee_hash(attendee_id: str) -> str:
    """HMAC-SHA256 of the attendee ID, hex. Safe for telemetry and ES."""
    return hmac.new(_signing_key(), attendee_id.encode(), hashlib.sha256).hexdigest()
