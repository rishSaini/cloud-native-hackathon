"""Interest similarity between attendees, for the group solver (K7).

For each person, one nearest-neighbour search on `interests_semantic`, limited
to the given attendee IDs. All searches go in one msearch request. Without
embeddings, `more_like_this` on `interests` is the fallback.
Scores are scaled to 0..1, and each pair keeps the higher of its two scores.
"""

from opentelemetry import trace

from app.es import get_es
from app.search import mappings as m
from app.telemetry.attrs import set_attrs

tracer = trace.get_tracer("affinity")
SEMANTIC_FIELD = "interests_semantic"


def _semantic_available(es) -> bool:
    props = es.indices.get_mapping(index=m.PEOPLE)[m.PEOPLE]["mappings"].get("properties", {})
    return props.get(SEMANTIC_FIELD, {}).get("type") == "semantic_text"


def neighbour_query(person: str, interests: str, ids: list[str], k: int, semantic: bool) -> dict:
    others = {"bool": {"filter": [{"terms": {"attendee_id": ids}}], "must_not": [{"term": {"attendee_id": person}}]}}
    if semantic:
        match = {"semantic": {"field": SEMANTIC_FIELD, "query": interests}}
    else:
        match = {"more_like_this": {"fields": ["interests"], "like": interests, "min_term_freq": 1, "min_doc_freq": 1}}
    query = {"bool": {"must": [match], **others["bool"]}}
    return {"size": k, "_source": False, "query": query}


def _scaled(hits: list[dict], semantic: bool) -> dict[str, float]:
    if not hits:
        return {}
    if semantic:  # cosine-based scores are already 0..1
        return {h["_id"]: max(0.0, min(1.0, h["_score"])) for h in hits}
    top = hits[0]["_score"] or 1.0  # more_like_this scores are unbounded: scale by the best
    return {h["_id"]: h["_score"] / top for h in hits}


def similarity_matrix(attendee_ids: list[str], k: int = 20) -> dict[tuple[str, str], float]:
    """Symmetric, 0..1, only pairs within each person's top-k neighbours."""
    ids = sorted(set(attendee_ids))
    if len(ids) < 2:
        return {}
    es = get_es()
    with tracer.start_as_current_span("search.candidates") as span:
        docs = es.mget(index=m.PEOPLE, ids=ids)["docs"]
        interests = {d["_id"]: d["_source"]["interests"] for d in docs if d.get("found")}
        people = [p for p in ids if p in interests]
        semantic = _semantic_available(es)

        searches = []
        for person in people:
            searches += [{"index": m.PEOPLE}, neighbour_query(person, interests[person], ids, k, semantic)]
        responses = es.msearch(searches=searches)["responses"] if searches else []

        matrix: dict[tuple[str, str], float] = {}
        for person, resp in zip(people, responses, strict=True):
            for other, score in _scaled(resp.get("hits", {}).get("hits", []), semantic).items():
                for pair in ((person, other), (other, person)):
                    matrix[pair] = max(matrix.get(pair, 0.0), score)
        set_attrs(span, search_hits=len(matrix) // 2)
    return matrix
