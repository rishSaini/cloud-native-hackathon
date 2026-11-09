"""K2: the synthetic schedule matches the contract's fixed IDs, and ingest reads it."""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen_schedule = load_script("gen_schedule")
ingest = load_script("ingest")

CONTRACT_SLOTS = {"tue-0900", "tue-1030", "tue-1330", "tue-1430", "tue-1600"}
CONTRACT_ROOMS = {"room-101", "room-155", "room-251", "room-hall-b"}


def test_one_talk_per_contract_node():
    talks = gen_schedule.build()["talks"]
    nodes = {t["node"] for t in talks}
    assert nodes == {f"{s}-{r}" for s in CONTRACT_SLOTS for r in CONTRACT_ROOMS}
    assert len(talks) == 20
    for t in talks:
        assert t["node"] == f"{t['slot']}-{t['room']}"


def test_times_are_denver_with_offset():
    talks = {t["slot"]: t for t in gen_schedule.build()["talks"]}
    assert talks["tue-0900"]["starts_at"] == "2026-11-10T09:00:00-07:00"
    assert talks["tue-1430"]["starts_at"] == "2026-11-10T14:30:00-07:00"


def test_speakers_are_obviously_synthetic():
    for t in gen_schedule.build()["talks"]:
        assert all(s.startswith("Sample Speaker") for s in t["speakers"])


def test_k6_demo_query_shares_no_words_with_any_talk():
    query_words = {"make", "my", "apps", "boot", "quicker"}
    for t in gen_schedule.build()["talks"]:
        words = set(re.findall(r"[a-z]+", f"{t['title']} {t['abstract']}".lower()))
        assert not words & query_words, t["title"]


def test_committed_schedule_is_up_to_date():
    committed = json.loads((ROOT / "data" / "sample-schedule.json").read_text())
    assert committed == gen_schedule.build(), "run `make schedule` and commit the result"


def test_ingest_reads_schedule_and_jsonl():
    talks = ingest.load_docs(ROOT / "data" / "sample-schedule.json")
    assert len(talks) == 20
    assert set(talks[0]) == set(ingest.TALK_FIELDS)
    sample = ingest.load_docs(ROOT / "data" / "sample.jsonl")
    assert sample and "title" in sample[0]


def test_ingest_uses_talk_ids_as_document_ids():
    docs = [{"id": "t01", "title": "x"}, {"title": "no id"}]
    actions = list(ingest.actions(docs, "talks"))
    assert actions[0]["_id"] == "t01"
    assert "_id" not in actions[1]
