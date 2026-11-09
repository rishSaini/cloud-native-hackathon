"""POST /api/ask (K13): retrieval-augmented answers about the talks.

1. Retrieve the top 5 talks with K6's hybrid search (filtered to `slot` if given).
2. Send only those talks and the question to the `affinity-chat` completion
   endpoint, through Elasticsearch's inference API.
3. Return the answer and the talks it cites.

Never sends people, cards or attendee data to the model: only public talk data.
"""

import logging
import re

from elasticsearch import ApiError, TransportError
from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from pydantic import BaseModel, Field

from app.es import get_es
from app.search import mappings as m
from app.search.talks import search_talks
from app.telemetry.attrs import set_attrs

log = logging.getLogger("affinity.ask")
tracer = trace.get_tracer("affinity")
router = APIRouter()
TOP_K = 5

INSTRUCTIONS = (
    "You help attendees at a Kubernetes conference choose talks. Answer in at most "
    "three short, plain sentences. Use only the talks listed below. Cite each talk "
    "you recommend with its ID in square brackets, like [t04]. If none of the talks "
    "fits, say so plainly. Do not invent talks, times or rooms."
)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    slot: str | None = Field(None, pattern=r"^[a-z]{3}-\d{4}$")


def build_prompt(question: str, talks: list[dict]) -> str:
    lines = [
        f"[{t['id']}] {t.get('title', '')} ({t.get('slot', '')}, {t.get('room', '')}): {t.get('abstract', '')}"
        for t in talks
    ]
    return f"{INSTRUCTIONS}\n\nTalks:\n" + "\n".join(lines) + f"\n\nQuestion: {question}\nAnswer:"


def cited_ids(answer: str, talks: list[dict]) -> list[str]:
    known = {t["id"] for t in talks}
    seen = []
    for tid in re.findall(r"\[(t\d+)\]", answer):
        if tid in known and tid not in seen:
            seen.append(tid)
    return seen


def talk_card(t: dict) -> dict:
    return {"id": t["id"], "title": t.get("title"), "abstract": t.get("abstract"), "room": t.get("room"),
            "slot": t.get("slot"), "startsAt": t.get("starts_at"), "badges": t.get("badges", [])}


@router.post("/api/ask")
def ask(body: AskIn, es=Depends(get_es)):
    with tracer.start_as_current_span("search.ask.rag") as span:
        found = search_talks(es, body.question, slot=body.slot, size=TOP_K)
        talks = found["hits"]
        set_attrs(span, search_hits=len(talks))
        if not talks:
            return {"answer": "I couldn't find any talks for that. Try other words, or another time slot.",
                    "talkIds": [], "talks": []}
        try:
            resp = es.options(request_timeout=35).inference.completion(
                inference_id=m.CHAT_ID, input=build_prompt(body.question, talks), timeout="30s")
            answer = resp["completion"][0]["result"].strip()
        except (ApiError, TransportError, KeyError, IndexError) as err:
            log.warning("ask: completion failed (%s)", type(err).__name__)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "Ask Affinity is unavailable right now. Search still works.")
    ids = cited_ids(answer, talks)
    by_id = {t["id"]: t for t in talks}
    return {"answer": answer, "talkIds": ids, "talks": [talk_card(by_id[i]) for i in ids]}
