"""K16: end-to-end against a real Elasticsearch (docker compose), with OpenAI embeddings.

ES setup -> ingest the schedule -> hybrid search -> people + kNN similarity -> group solver.
Runs only with AFFINITY_INTEGRATION=1, a running ES (`make es-up`) and OPENAI_API_KEY:

    AFFINITY_INTEGRATION=1 python -m pytest -q tests/integration
"""

import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.getenv("AFFINITY_INTEGRATION") != "1", reason="needs AFFINITY_INTEGRATION=1")

ROOT = Path(__file__).resolve().parents[3]
CLUSTERS = {
    "startup": ["making containers start faster", "reducing pod cold start time", "slimmer images for quick launches"],
    "security": ["signing container images", "supply chain security and SBOMs", "admission policies for safe deploys"],
}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def es():
    from app.es import get_es
    from app.search import setup

    client = get_es()
    setup.ensure_all(client, os.getenv("OPENAI_API_KEY"))
    ingest = load_script("ingest")
    ingest.main(ROOT / "data" / "sample-schedule.json")
    yield client
    from app.search.people import delete_person

    for name, texts in CLUSTERS.items():
        for i in range(len(texts)):
            delete_person(f"it-{name}-{i}")


def test_hybrid_search_finds_the_startup_talk_by_meaning(es):
    from app.search.talks import search_talks

    result = search_talks(es, "make my apps boot quicker", size=3)
    assert result["mode"] == "hybrid"
    assert result["hits"][0]["id"] == "t04"  # "Cold starts are a choice": no shared words


def test_people_similarity_feeds_the_solver_into_interest_groups(es):
    from app.search.people import upsert_person
    from app.search.similarity import similarity_matrix
    from app.solver import SolverPerson, SolverTable, solve

    ids = []
    for name, texts in CLUSTERS.items():
        for i, text in enumerate(texts):
            upsert_person(f"it-{name}-{i}", text)
            ids.append(f"it-{name}-{i}")
    es.indices.refresh(index="people")

    sim = similarity_matrix(ids, k=5)
    people = [SolverPerson(i, frozenset(), frozenset(), frozenset()) for i in ids]
    tables = [SolverTable("brk-tue-1530-tbl-01", 3, frozenset()), SolverTable("brk-tue-1530-tbl-02", 3, frozenset())]
    result = solve(people, tables, sim, time_limit_ms=2000)

    assert result.unplaced == []
    for group in result.groups:
        clusters = {member.split("-")[1] for member in group.members}
        assert len(clusters) == 1, f"mixed group: {group.members}"
