"""Search routes (owner: Karthik)."""

from fastapi import APIRouter, Depends, Query

from app.es import get_es
from app.search.talks import search_talks

router = APIRouter()


@router.get("/api/talks/search")
def talks_search(
    q: str = Query(min_length=1, max_length=500),
    slot: str | None = Query(None, pattern=r"^[a-z]{3}-\d{4}$"),
    size: int = Query(10, ge=1, le=50),
    es=Depends(get_es),
):
    """Hybrid talk search. `mode` says whether hybrid or keyword-only search ran."""
    return search_talks(es, q, slot=slot, size=size)


@router.get("/api/search")
def legacy_search(
    q: str = Query(min_length=1, max_length=500),
    size: int = Query(10, ge=1, le=50),
    es=Depends(get_es),
):
    """The original search route, kept for the current page. Same code as /api/talks/search."""
    return search_talks(es, q, size=size)
