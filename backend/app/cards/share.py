"""Signed, expiring, revocable card links for QR codes (R11).

A link is /c/<grant id>.<expiry>.<signature>. The HMAC uses SHARE_SIGNING_KEY;
the grant row in card_grants (reason 'qr') makes it revocable. Expired or
revoked links answer 410.
"""

import hashlib
import hmac
import html
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.auth import current_attendee_id
from app.cards.store import get_store
from app.db import pool

router = APIRouter()
TTL_SECONDS = 600
_DEV_KEY = "affinity-dev-share-key"


def _key() -> bytes:
    return (os.getenv("SHARE_SIGNING_KEY") or _DEV_KEY).encode()


def sign(grant_id: str, expires: int) -> str:
    mac = hmac.new(_key(), f"{grant_id}.{expires}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{grant_id}.{expires}.{mac}"


def verify(token: str) -> tuple[str, int] | None:
    try:
        grant_id, expires, mac = token.split(".")
        expires_at = int(expires)
    except ValueError:
        return None
    if not hmac.compare_digest(sign(grant_id, expires_at), token):
        return None
    return grant_id, expires_at


@router.post("/api/card/share")
def share_card(request: Request, attendee_id: str = Depends(current_attendee_id)):
    expires = int(time.time()) + TTL_SECONDS
    with pool().connection() as conn:
        grant_id = conn.execute(
            "INSERT INTO card_grants (owner_id, reason, expires_at) VALUES (%s, 'qr', to_timestamp(%s)) RETURNING id",
            (attendee_id, expires)).fetchone()[0]
    return {"url": f"{request.base_url}c/{sign(str(grant_id), expires)}", "expiresInSeconds": TTL_SECONDS}


FIELDS = [("pronouns", "Pronouns"), ("workingOn", "Working on"), ("askMeAbout", "Ask me about"),
          ("howToTalk", "How to talk to me"), ("reachMe", "Best way to reach me"), ("lookingFor", "Looking for")]


@router.get("/c/{token}", response_class=HTMLResponse)
def view_shared_card(token: str, store=Depends(get_store)):
    parsed = verify(token)
    if parsed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a valid card link")
    grant_id, expires = parsed
    with pool().connection() as conn:
        row = conn.execute("SELECT owner_id, revoked_at FROM card_grants WHERE id = %s AND reason = 'qr'",
                           (grant_id,)).fetchone()
    if row is None or row[1] is not None or time.time() > expires:
        raise HTTPException(status.HTTP_410_GONE, "This card link has expired or was turned off")
    card = store.load(row[0])
    if card is None:
        raise HTTPException(status.HTTP_410_GONE, "This card was deleted")
    rows = "".join(f"<dt>{label}</dt><dd>{html.escape(card[k])}</dd>" for k, label in FIELDS if card.get(k))
    return (f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<title>{html.escape(card['name'])}'s card</title><main><h1>{html.escape(card['name'])}</h1>"
            f"<dl>{rows}</dl><p>Shared with Affinity. This link expires soon.</p></main></html>")
