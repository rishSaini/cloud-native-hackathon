"""Checks that Karthik's side of the shared contract exists with the agreed shapes."""

import dataclasses

import pytest

from app.search.people import delete_person, upsert_person  # noqa: F401
from app.search.ranking import RankedNode, rank_talks_for  # noqa: F401
from app.search.similarity import similarity_matrix  # noqa: F401
from app.solver import Group, SolverPerson, SolverResult, SolverTable, solve  # noqa: F401
from app.telemetry.attrs import ALLOWED_ATTRIBUTES, UnknownAttributeError, set_attrs


def test_solver_types_match_contract():
    person = SolverPerson(id="a1", needs=frozenset({"cap-c1"}), blocked=frozenset(), met=frozenset())
    table = SolverTable(id="brk-tue-1530-tbl-01", seats=4, caps=frozenset({"cap-c1"}))
    group = Group(id="g-0000abcd", table_id=table.id, members=[person.id])
    result = SolverResult(groups=[group], unplaced=[], duration_ms=0)
    assert result.groups[0].members == ["a1"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        person.id = "b2"


def test_ranked_node_is_frozen():
    ranked = RankedNode(node="tue-1430-room-251", weight=100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ranked.weight = 1


def test_allow_list_matches_contract():
    assert ALLOWED_ATTRIBUTES == {
        "room.id",
        "slot.id",
        "report.signal",
        "placement.outcome",
        "group.size",
        "solver.duration_ms",
        "attendee.hash",
        "search.hits",
        "search.query_length",
    }


def test_set_attrs_accepts_dotted_and_underscore_names(recording_span):
    set_attrs(recording_span, room_id="room-251", search_query_length=12, **{"slot.id": "tue-1430"})
    assert recording_span.attributes == {
        "room.id": "room-251",
        "search.query_length": 12,
        "slot.id": "tue-1430",
    }


def test_set_attrs_rejects_unknown_keys_in_tests(recording_span):
    with pytest.raises(UnknownAttributeError):
        set_attrs(recording_span, card_text="please face me")
    assert recording_span.attributes == {}


def test_set_attrs_drops_unknown_keys_outside_tests(recording_span, monkeypatch):
    monkeypatch.setenv("AFFINITY_STRICT_TELEMETRY", "0")
    set_attrs(recording_span, card_text="please face me", group_size=3)
    assert recording_span.attributes == {"group.size": 3}
