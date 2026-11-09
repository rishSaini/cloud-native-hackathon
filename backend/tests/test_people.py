"""K7: people index and similarity matrix, with a fake ES."""

import pytest

from app.search import people, similarity


class FakePeopleES:
    def __init__(self, semantic=True, scores=None):
        self.docs = {}
        self.scores = scores or {}  # (person, other) -> score
        self.semantic = semantic
        self.searches = None
        outer = self

        class Indices:
            def get_mapping(self, index):
                props = {"interests": {"type": "text"}}
                if outer.semantic:
                    props["interests_semantic"] = {"type": "semantic_text"}
                return {index: {"mappings": {"properties": props}}}

        self.indices = Indices()

    def index(self, index, id, document):
        self.docs[id] = document

    def delete(self, index, id):
        from elastic_transport import ApiResponseMeta, HttpHeaders
        from elasticsearch import NotFoundError

        if id not in self.docs:
            meta = ApiResponseMeta(status=404, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
            raise NotFoundError("missing", meta=meta, body={})
        del self.docs[id]

    def mget(self, index, ids):
        return {"docs": [{"_id": i, "found": i in self.docs, "_source": self.docs.get(i)} for i in ids]}

    def msearch(self, searches):
        self.searches = searches
        responses = []
        for body in searches[1::2]:
            me = body["query"]["bool"]["must_not"][0]["term"]["attendee_id"]
            hits = sorted(
                ({"_id": o, "_score": s} for (p, o), s in self.scores.items() if p == me),
                key=lambda h: -h["_score"],
            )
            responses.append({"hits": {"hits": hits}})
        return {"responses": responses}


@pytest.fixture
def es(monkeypatch):
    fake = FakePeopleES()
    monkeypatch.setattr(people, "get_es", lambda: fake)
    monkeypatch.setattr(similarity, "get_es", lambda: fake)
    return fake


def test_upsert_stores_only_id_interests_and_time(es):
    people.upsert_person("7f3k", "  making apps start faster ")
    assert set(es.docs["7f3k"]) == {"attendee_id", "interests", "updated_at"}
    assert es.docs["7f3k"]["interests"] == "making apps start faster"


def test_empty_interests_remove_the_person(es):
    people.upsert_person("7f3k", "ebpf")
    people.upsert_person("7f3k", "")
    assert "7f3k" not in es.docs
    people.delete_person("never-existed")  # no error


def test_matrix_is_symmetric_and_keeps_the_higher_score(es):
    for p in ("a", "b", "c"):
        people.upsert_person(p, f"interest {p}")
    es.scores = {("a", "b"): 0.9, ("b", "a"): 0.7, ("a", "c"): 0.4}
    matrix = similarity.similarity_matrix(["a", "b", "c"])
    assert matrix[("a", "b")] == matrix[("b", "a")] == 0.9
    assert matrix[("c", "a")] == 0.4
    assert ("b", "c") not in matrix


def test_queries_exclude_self_and_stay_within_the_ids(es):
    for p in ("a", "b"):
        people.upsert_person(p, "x")
    similarity.similarity_matrix(["a", "b", "z"], k=5)
    body = es.searches[1]
    assert body["size"] == 5
    assert body["query"]["bool"]["filter"] == [{"terms": {"attendee_id": ["a", "b", "z"]}}]
    assert body["query"]["bool"]["must"][0]["semantic"]["field"] == "interests_semantic"


def test_fallback_scales_more_like_this_scores(es):
    es.semantic = False
    for p in ("a", "b", "c"):
        people.upsert_person(p, "x")
    es.scores = {("a", "b"): 8.0, ("a", "c"): 2.0}
    matrix = similarity.similarity_matrix(["a", "b", "c"])
    assert "more_like_this" in es.searches[1]["query"]["bool"]["must"][0]
    assert matrix[("a", "b")] == 1.0 and matrix[("a", "c")] == 0.25


def test_fewer_than_two_people_gives_empty_matrix(es):
    assert similarity.similarity_matrix(["a"]) == {}
