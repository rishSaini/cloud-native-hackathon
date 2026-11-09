"""K13: Ask Affinity — grounded prompt, citations only from retrieved talks."""

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch import BadRequestError, TransportError
from fastapi.testclient import TestClient

from app.ask import routes
from app.es import get_es
from app.main import app

TALKS = [
    {"id": "t13", "title": "Autoscaling explained for first-timers", "slot": "tue-1430", "room": "room-101",
     "abstract": "A beginner's tour of HPA, VPA and KEDA.", "node": "tue-1430-room-101"},
    {"id": "t15", "title": "Tracing one slow request", "slot": "tue-1430", "room": "room-251",
     "abstract": "Follow a slow checkout through a trace.", "node": "tue-1430-room-251"},
]


class FakeAskES:
    def __init__(self, talks=TALKS, answer="Go to [t13]. Also [t99] and [t13] again.", fail=False,
                 transport_fail=False, response=None):
        self.talks, self.answer, self.fail, self.prompt = talks, answer, fail, None
        self.transport_fail = transport_fail
        self.response = response
        self.request_timeout = None
        self.completion_timeout = None
        outer = self

        class Indices:
            def get_mapping(self, index):
                return {index: {"mappings": {"properties": {"abstract_semantic": {"type": "semantic_text"}}}}}

        class Inference:
            def completion(self, inference_id, input, timeout=None):
                outer.prompt = input
                outer.completion_timeout = timeout
                if outer.transport_fail:
                    raise TransportError("down")
                if outer.fail:
                    meta = ApiResponseMeta(status=400, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
                    raise BadRequestError("down", meta=meta, body={})
                if outer.response is not None:
                    return outer.response
                return {"completion": [{"result": outer.answer}]}

        self.indices, self.inference = Indices(), Inference()

    def options(self, **kwargs):
        self.request_timeout = kwargs.get("request_timeout")
        return self

    def search(self, **kwargs):
        hits = [{"_id": t["id"], "_score": 1.0, "_source": t} for t in self.talks]
        return {"hits": {"total": {"value": len(hits)}, "hits": hits}}


@pytest.fixture
def client_for():
    def make(es):
        app.dependency_overrides[get_es] = lambda: es
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def test_answer_cites_only_retrieved_talks_once(client_for):
    es = FakeAskES()
    body = client_for(es).post("/api/ask", json={"question": "autoscaling for beginners?", "slot": "tue-1430"}).json()
    assert body["talkIds"] == ["t13"]  # t99 was never retrieved, so it is dropped
    assert body["talks"][0]["title"] == "Autoscaling explained for first-timers"


def test_prompt_holds_only_talks_and_the_question(client_for):
    es = FakeAskES()
    client_for(es).post("/api/ask", json={"question": "autoscaling for beginners?"})
    assert "[t13] Autoscaling explained" in es.prompt and "Question: autoscaling for beginners?" in es.prompt
    assert "attendee" not in es.prompt.lower().replace("attendees at a kubernetes", "")


def test_no_talks_found_gives_a_plain_answer_without_calling_the_model(client_for):
    es = FakeAskES(talks=[])
    body = client_for(es).post("/api/ask", json={"question": "underwater basket weaving"}).json()
    assert body["talkIds"] == [] and es.prompt is None


def test_model_failure_is_503_not_500(client_for):
    es = FakeAskES(fail=True)
    assert client_for(es).post("/api/ask", json={"question": "anything good?"}).status_code == 503
    assert es.request_timeout == 35
    assert es.completion_timeout == "30s"


@pytest.mark.parametrize("response", [{}, {"completion": []}])
def test_malformed_model_response_is_503(client_for, response):
    es = FakeAskES(response=response)
    assert client_for(es).post("/api/ask", json={"question": "anything good?"}).status_code == 503


def test_transport_failure_is_503(client_for):
    es = FakeAskES(transport_fail=True)
    assert client_for(es).post("/api/ask", json={"question": "anything good?"}).status_code == 503


def test_rejects_bad_input(client_for):
    c = client_for(FakeAskES())
    assert c.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert c.post("/api/ask", json={"question": "valid question", "slot": "2:30"}).status_code == 422
