"""K8: talk ranking for placement, with a fake ES."""

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch import NotFoundError

from app.search import ranking
from app.search.ranking import RankedNode


def not_found():
    meta = ApiResponseMeta(status=404, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
    return NotFoundError("missing", meta=meta, body={})


class FakeRankES:
    def __init__(self, people, talks, closed=()):
        self.people = people
        self.talks = talks  # in ranked order
        self.closed = closed
        self.talk_search = None
        outer = self

        class Indices:
            def get_mapping(self, index):
                return {index: {"mappings": {"properties": {"abstract_semantic": {"type": "semantic_text"}}}}}

        self.indices = Indices()

    def get(self, index, id, source):
        if id not in self.people:
            raise not_found()
        return {"_source": {"interests": self.people[id]}}

    def search(self, index, **kwargs):
        if index == "room-state":
            return {"hits": {"hits": [{"_source": {"room": r}} for r in self.closed]}}
        self.talk_search = kwargs
        hits = [{"_id": t["id"], "_score": 1.0, "_source": t} for t in self.talks]
        return {"hits": {"total": {"value": len(hits)}, "hits": hits}}


def talk(i, room):
    return {"id": f"t{i}", "room": room, "slot": "tue-1430", "node": f"tue-1430-{room}"}


@pytest.fixture
def use(monkeypatch):
    def install(es):
        monkeypatch.setattr(ranking, "get_es", lambda: es)
        return es

    return install


def test_weights_run_from_100_to_1():
    assert ranking.weights(4) == [100, 67, 34, 1]
    assert ranking.weights(1) == [100]
    assert ranking.weights(0) == []


def test_ranks_nodes_in_search_order(use):
    use(FakeRankES({"a1": "autoscaling"}, [talk(1, "room-101"), talk(2, "room-251")]))
    assert ranking.rank_talks_for("a1", "tue-1430") == [
        RankedNode("tue-1430-room-101", 100),
        RankedNode("tue-1430-room-251", 1),
    ]


def test_no_interests_gives_empty_list(use):
    use(FakeRankES({}, [talk(1, "room-101")]))
    assert ranking.rank_talks_for("unknown", "tue-1430") == []


def test_closed_rooms_are_excluded_in_the_query(use):
    es = use(FakeRankES({"a1": "x"}, [talk(1, "room-101")], closed=["room-251"]))
    ranking.rank_talks_for("a1", "tue-1430", k=5)
    filters = es.talk_search["retriever"]["rrf"]["retrievers"][0]["standard"]["filter"]
    assert {"term": {"slot": "tue-1430"}} in filters
    assert {"bool": {"must_not": [{"terms": {"room": ["room-251"]}}]}} in filters
    assert es.talk_search["size"] == 5


def test_missing_room_state_index_means_nothing_closed():
    class NoIndex:
        def search(self, **kwargs):
            raise not_found()

    assert ranking.closed_rooms(NoIndex()) == set()
