"""K6: hybrid talk search, with FakeES (no cluster needed)."""

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch import BadRequestError, NotFoundError
from fastapi.testclient import TestClient

from app.es import get_es
from app.main import app
from app.search import talks

TALK = {"id": "t04", "title": "Cold starts are a choice", "slot": "tue-0900", "node": "tue-0900-room-hall-b"}


def api_error(cls, status):
    meta = ApiResponseMeta(status=status, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
    return cls("error", meta=meta, body={})


@pytest.fixture
def client_for():
    def make(es):
        app.dependency_overrides[get_es] = lambda: es
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def test_hybrid_retriever_fuses_semantic_and_bm25_with_slot_filter():
    retrievers = talks.hybrid_retriever("boot faster", "tue-1430")["rrf"]["retrievers"]
    semantic, lexical = (r["standard"] for r in retrievers)
    assert semantic["query"] == {"semantic": {"field": "abstract_semantic", "query": "boot faster"}}
    assert lexical["query"]["multi_match"]["fields"] == ["title^2", "abstract"]
    for r in (semantic, lexical):
        assert r["filter"] == [{"term": {"slot": "tue-1430"}}]


def test_no_slot_means_no_filter():
    retrievers = talks.hybrid_retriever("x", None)["rrf"]["retrievers"]
    assert all("filter" not in r["standard"] for r in retrievers)
    assert "filter" not in talks.keyword_query("x", None)["bool"]


def test_hybrid_mode_when_index_has_embeddings(client_for, fake_es):
    es = fake_es([TALK], semantic=True)
    body = client_for(es).get("/api/talks/search", params={"q": "make my apps boot quicker"}).json()
    assert body["mode"] == "hybrid"
    assert "retriever" in es.last_search and "query" not in es.last_search
    assert body["hits"][0]["id"] == "t04"
    assert body["hits"][0]["badges"] == [talks.MEANING_BADGE]  # no keyword highlight: meaning match


def test_keyword_mode_without_embeddings(client_for, fake_es):
    es = fake_es([TALK], semantic=False)
    body = client_for(es).get("/api/talks/search", params={"q": "cold starts", "slot": "tue-0900"}).json()
    assert body["mode"] == "keyword"
    assert "query" in es.last_search
    assert es.last_search["query"]["bool"]["filter"] == [{"term": {"slot": "tue-0900"}}]
    assert body["hits"][0]["badges"] == []


def test_falls_back_to_keyword_when_embeddings_fail(client_for, fake_es):
    es = fake_es([TALK], semantic=True)
    real_search = es.search

    def search(**kwargs):
        if "retriever" in kwargs:
            raise api_error(BadRequestError, 400)
        return real_search(**kwargs)

    es.search = search
    body = client_for(es).get("/api/talks/search", params={"q": "boot"}).json()
    assert body["mode"] == "keyword"
    assert body["total"] == 1


def test_missing_index_returns_a_note(client_for, fake_es):
    es = fake_es([])

    def get_mapping(index):
        raise api_error(NotFoundError, 404)

    es.indices.get_mapping = get_mapping
    body = client_for(es).get("/api/talks/search", params={"q": "x"}).json()
    assert body["hits"] == [] and "make ingest" in body["note"]


def test_legacy_route_uses_the_same_search(client_for, fake_es):
    body = client_for(fake_es([TALK], semantic=True)).get("/api/search", params={"q": "x"}).json()
    assert body["mode"] == "hybrid"


@pytest.mark.parametrize("params", [{"q": ""}, {"q": "x", "slot": "Tuesday 9am"}, {"q": "x", "size": 0}])
def test_rejects_bad_input(client_for, fake_es, params):
    assert client_for(fake_es([])).get("/api/talks/search", params=params).status_code == 422


def test_highlighted_hit_has_no_meaning_badge():
    raw = {"_id": "t01", "_score": 1.0, "_source": {"id": "t01"}, "highlight": {"title": ["<mark>eBPF</mark>"]}}
    hit = talks.to_hit(raw, "hybrid")
    assert hit["highlight"] == ["<mark>eBPF</mark>"] and hit["badges"] == []
