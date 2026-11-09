"""R12: deletion reaches every store, and orphaned Pods are found."""

from types import SimpleNamespace

from app.cards.delete import delete_everywhere
from app.controller.cleanup import orphans


def test_delete_everywhere_calls_search_then_postgres():
    calls = []
    delete_everywhere("ab12", postgres=lambda a: calls.append(("postgres", a)),
                      search=lambda a: calls.append(("search", a)))
    assert calls == [("search", "ab12"), ("postgres", "ab12")]


def pod(attendee):
    labels = {"affinity.dev/attendee": attendee}
    return SimpleNamespace(metadata=SimpleNamespace(labels=labels, name=f"attendee-{attendee}"))


def test_pods_of_deleted_attendees_are_orphans():
    pods = [pod("keep1"), pod("gone2"), pod("keep3")]
    assert [p.metadata.name for p in orphans(pods, {"keep1", "keep3"})] == ["attendee-gone2"]
