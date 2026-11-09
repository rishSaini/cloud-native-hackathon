"""K1: Elasticsearch setup is idempotent, uses hosted embeddings, and keeps private data out."""

from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch import NotFoundError

from app.search import mappings as m
from app.search import setup


def not_found():
    meta = ApiResponseMeta(status=404, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
    return NotFoundError("not found", meta=meta, body={})


class FakeAdminES:
    """Records what setup creates, and remembers it like a real cluster would."""

    def __init__(self):
        self.created = []
        self.inference_endpoints = {}
        self.index_mappings = {}
        self.policies = set()
        self.templates = set()
        outer = self

        class Inference:
            def get(self, inference_id):
                if inference_id not in outer.inference_endpoints:
                    raise not_found()
                return {"endpoints": [outer.inference_endpoints[inference_id]]}

            def put(self, task_type, inference_id, inference_config):
                outer.inference_endpoints[inference_id] = {"task_type": task_type, **inference_config}
                outer.created.append(f"inference {inference_id}")

        class Indices:
            def exists(self, index):
                return index in outer.index_mappings

            def create(self, index, mappings):
                outer.index_mappings[index] = mappings
                outer.created.append(f"index {index}")

            def get_mapping(self, index):
                return {index: {"mappings": outer.index_mappings[index]}}

            def exists_index_template(self, name):
                return name in outer.templates

            def put_index_template(self, name, **body):
                outer.templates.add(name)
                outer.created.append(f"template {name}")

            def create_data_stream(self, name):
                outer.index_mappings[name] = {}
                outer.created.append(f"data stream {name}")

        class Ilm:
            def get_lifecycle(self, name):
                if name not in outer.policies:
                    raise not_found()
                return {name: {}}

            def put_lifecycle(self, name, policy):
                outer.policies.add(name)
                outer.created.append(f"policy {name}")

        self.inference = Inference()
        self.indices = Indices()
        self.ilm = Ilm()


def test_without_key_creates_everything_but_embeddings():
    es = FakeAdminES()
    result = setup.ensure_all(es, openai_key=None)
    assert result[f"inference {m.INFERENCE_ID}"] == "skipped"
    assert "abstract_semantic" not in es.index_mappings[m.TALKS]["properties"]
    assert set(es.index_mappings) == {m.TALKS, m.PEOPLE, m.ROOM_STATE, m.INCIDENTS, m.ROOM_REPORTS}


def test_with_key_uses_openai_and_semantic_text():
    es = FakeAdminES()
    setup.ensure_all(es, openai_key="sk-test")
    endpoint = es.inference_endpoints[m.INFERENCE_ID]
    assert endpoint["task_type"] == "text_embedding"
    assert endpoint["service"] == "openai"
    assert endpoint["service_settings"]["model_id"] == "text-embedding-3-small"
    talks = es.index_mappings[m.TALKS]["properties"]
    assert talks["abstract"]["copy_to"] == "abstract_semantic"
    assert talks["abstract_semantic"] == {"type": "semantic_text", "inference_id": "affinity-embed"}
    assert es.index_mappings[m.PEOPLE]["properties"]["interests_semantic"]["type"] == "semantic_text"


def test_second_run_changes_nothing():
    es = FakeAdminES()
    setup.ensure_all(es, openai_key="sk-test")
    created_first = list(es.created)
    result = setup.ensure_all(es, openai_key="sk-test")
    assert es.created == created_first
    assert set(result.values()) == {"exists"}


def test_people_index_holds_no_private_fields():
    props = m.people_mapping(semantic=True)
    assert props["dynamic"] == "strict"
    assert set(props["properties"]) == {"attendee_id", "interests", "interests_semantic", "updated_at"}


def test_room_state_has_both_writers_fields():
    fields = set(m.room_state_mapping()["properties"])
    assert {"room", "status", "signals", "confidence", "changed_at", "traceparent"} <= fields
    assert {"seats_total", "seats_free", "controller_seen_at"} <= fields


def test_room_reports_store_only_a_hash():
    props = m.room_reports_template()["template"]["mappings"]["properties"]
    assert set(props) == {"@timestamp", "room", "slot", "signal", "reporter_hash"}
