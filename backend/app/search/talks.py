"""Hybrid talk search (K6): semantic search and BM25, fused with RRF.

"make my apps boot quicker" finds "Cold starts are a choice" with no shared
words: the semantic retriever matches meaning, and BM25 still rewards exact
terms such as "eBPF". If the index has no embeddings, or the embedding service
fails, search falls back to BM25 and says so with mode = "keyword".
"""

import logging

from elasticsearch import ApiError, NotFoundError
from opentelemetry import trace

from app.search import mappings as m
from app.telemetry.attrs import set_attrs

log = logging.getLogger("affinity.search")
tracer = trace.get_tracer("affinity")

SOURCE_FIELDS = ["id", "title", "abstract", "speakers", "track", "room", "slot", "node", "starts_at"]
LEXICAL_FIELDS = ["title^2", "abstract"]
SEMANTIC_FIELD = "abstract_semantic"
HIGHLIGHT = {
    "pre_tags": ["<mark>"],
    "post_tags": ["</mark>"],
    "fields": {"title": {"number_of_fragments": 0}, "abstract": {"number_of_fragments": 0}},
}
MEANING_BADGE = "Matched by meaning"


def _filter(slot: str | None, exclude_rooms=()) -> dict:
    filters = [{"term": {"slot": slot}}] if slot else []
    if exclude_rooms:
        filters.append({"bool": {"must_not": [{"terms": {"room": sorted(exclude_rooms)}}]}})
    return {"filter": filters} if filters else {}


def keyword_query(q: str, slot: str | None, exclude_rooms=()) -> dict:
    return {
        "bool": {
            "must": [{"multi_match": {"query": q, "fields": LEXICAL_FIELDS}}],
            **_filter(slot, exclude_rooms),
        }
    }


def hybrid_retriever(q: str, slot: str | None, exclude_rooms=()) -> dict:
    flt = _filter(slot, exclude_rooms)
    return {
        "rrf": {
            "retrievers": [
                {"standard": {"query": {"semantic": {"field": SEMANTIC_FIELD, "query": q}}, **flt}},
                {"standard": {"query": {"multi_match": {"query": q, "fields": LEXICAL_FIELDS}}, **flt}},
            ]
        }
    }


def semantic_available(es) -> bool:
    """True when the talks index has the semantic_text field (K1 ran with an OpenAI key)."""
    props = es.indices.get_mapping(index=m.TALKS)[m.TALKS]["mappings"].get("properties", {})
    return props.get(SEMANTIC_FIELD, {}).get("type") == "semantic_text"


def to_hit(raw: dict, mode: str) -> dict:
    source = raw.get("_source", {})
    highlight = raw.get("highlight", {})
    snippets = highlight.get("title", []) + highlight.get("abstract", [])
    return {
        **source,
        "id": source.get("id", raw["_id"]),
        "score": raw.get("_score"),
        "highlight": snippets,
        # No keyword in common, yet it ranked: the semantic retriever found it.
        "badges": [MEANING_BADGE] if mode == "hybrid" and not snippets else [],
    }


def _run(es, q: str, slot: str | None, size: int, mode: str, exclude_rooms=()) -> dict:
    common = {"index": m.TALKS, "size": size, "source": SOURCE_FIELDS, "highlight": HIGHLIGHT}
    if mode == "hybrid":
        return es.search(retriever=hybrid_retriever(q, slot, exclude_rooms), **common)
    return es.search(query=keyword_query(q, slot, exclude_rooms), **common)


def search_talks(es, q: str, slot: str | None = None, size: int = 10, exclude_rooms=()) -> dict:
    """`exclude_rooms` drops talks in those rooms (K8 passes the closed rooms)."""
    with tracer.start_as_current_span("search.hybrid") as span:
        set_attrs(span, search_query_length=len(q))  # never the query text itself
        try:
            mode = "hybrid" if semantic_available(es) else "keyword"
            try:
                resp = _run(es, q, slot, size, mode, exclude_rooms)
            except NotFoundError:
                raise
            except ApiError as err:  # for example, the embedding service is down
                if mode != "hybrid":
                    raise
                log.warning("hybrid search failed (%s); falling back to keyword search", type(err).__name__)
                mode = "keyword"
                resp = _run(es, q, slot, size, mode, exclude_rooms)
        except NotFoundError:
            log.warning("index %s not found", m.TALKS)
            set_attrs(span, search_hits=0)
            return {"mode": "keyword", "total": 0, "hits": [], "note": "No talks loaded yet. Run: make ingest"}

        hits = [to_hit(raw, mode) for raw in resp["hits"]["hits"]]
        set_attrs(span, search_hits=len(hits))
    return {"mode": mode, "total": resp["hits"]["total"]["value"], "hits": hits}
