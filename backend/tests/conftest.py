"""Shared test fixtures.

Append-only (see docs/tasks/karthik.md, "Who owns which files"): add your
fixtures at the end, and don't rewrite someone else's.
"""

import os

import pytest
from fastapi.testclient import TestClient

# Unknown span attributes raise in tests (app.telemetry.attrs).
os.environ.setdefault("AFFINITY_STRICT_TELEMETRY", "1")


class FakeES:
    """Stands in for Elasticsearch so tests run without a cluster."""

    def __init__(self, docs):
        self.docs = docs

    def ping(self):
        return True

    def search(self, **kwargs):
        return {
            "hits": {
                "total": {"value": len(self.docs)},
                "hits": [
                    {"_id": str(i), "_score": 1.0, "_source": d}
                    for i, d in enumerate(self.docs)
                ],
            }
        }


@pytest.fixture
def fake_es():
    """Factory: fake_es(docs) returns a FakeES holding those documents."""
    return FakeES


@pytest.fixture
def client_with():
    """Factory: client_with(docs) returns a TestClient whose app uses a FakeES."""
    from app.es import get_es
    from app.main import app

    def make(docs):
        app.dependency_overrides[get_es] = lambda: FakeES(docs)
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


class RecordingSpan:
    """A span stand-in that records set_attribute calls."""

    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


@pytest.fixture
def recording_span():
    return RecordingSpan()
