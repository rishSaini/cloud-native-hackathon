"""POST /api/attendees and PUT/GET/DELETE /api/card (R4).

These routes never log a request body. Only the consented interest text
(working on, ask me about, looking for) leaves Postgres, and only to Karthik's
`people` index through upsert_person, and only when the card allows matching.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth import COOKIE, attendee_from_session, current_attendee_id, new_attendee_id, set_session
from app.cards.capabilities import NEED_CODES
from app.cards.store import get_store

log = logging.getLogger("affinity.cards")
router = APIRouter()


class CardIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    pronouns: str = Field("", max_length=30)
    workingOn: str = Field("", max_length=140)
    askMeAbout: str = Field("", max_length=140)
    howToTalk: str = Field("", max_length=200)
    reachMe: str = Field("", max_length=100)
    lookingFor: str = Field("", max_length=140)
    needs: list[str] = Field(default_factory=list, max_length=len(NEED_CODES))
    allowMatching: bool = True


def display_id(attendee_id: str) -> str:
    return f"attendee-{attendee_id}"


def consented_interests(card: CardIn) -> str:
    return " ".join(part.strip() for part in (card.workingOn, card.askMeAbout, card.lookingFor) if part.strip())


def sync_matching(attendee_id: str, card: CardIn | None) -> None:
    """Karthik's people index gets the interest text only, and only with consent."""
    from app.search.people import delete_person, upsert_person  # imported here: Karthik's side

    try:
        if card is not None and card.allowMatching and consented_interests(card):
            upsert_person(attendee_id, consented_interests(card))
        else:
            delete_person(attendee_id)
    except NotImplementedError:
        log.info("people index not available yet (K7); matching skipped")


@router.post("/api/attendees")
def create_attendee(request: Request, response: Response, store=Depends(get_store)):
    """Creates a random attendee and a session. With a valid session, returns the same attendee."""
    attendee_id = attendee_from_session(request.cookies.get(COOKIE))
    if attendee_id:
        store.ensure_attendee(attendee_id)
    else:
        for _ in range(5):
            attendee_id = new_attendee_id()
            if store.create_attendee(attendee_id):
                break
        else:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not create an attendee. Try again.")
    set_session(response, request, attendee_id)
    return {"attendeeId": attendee_id, "displayId": display_id(attendee_id)}


@router.put("/api/card")
def save_card(card: CardIn, attendee_id: str = Depends(current_attendee_id), store=Depends(get_store)):
    unknown = [n for n in card.needs if n not in NEED_CODES]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown needs: {unknown}")
    codes = sorted({NEED_CODES[n] for n in card.needs})
    store.save(attendee_id, card.model_dump(), codes)
    sync_matching(attendee_id, card)
    return {**card.model_dump(), "displayId": display_id(attendee_id)}


@router.get("/api/card")
def get_card(attendee_id: str = Depends(current_attendee_id), store=Depends(get_store)):
    card = store.load(attendee_id)
    return {**card, "displayId": display_id(attendee_id)} if card else None


def get_deleter():
    from app.cards.delete import delete_everywhere

    return delete_everywhere


@router.delete("/api/card")
def delete_card(response: Response, attendee_id: str = Depends(current_attendee_id), store=Depends(get_store),
                delete_everywhere=Depends(get_deleter)):
    """R12: deletes the card and the attendee everywhere, and ends the session."""
    store.delete(attendee_id)
    delete_everywhere(attendee_id)
    response.delete_cookie(COOKIE)
    return None
