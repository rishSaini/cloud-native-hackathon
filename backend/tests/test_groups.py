from datetime import datetime, timezone
from types import SimpleNamespace

from kubernetes.client.exceptions import ApiException

from app.controller import groups


class _Connection:
    def execute(self, *_args):
        return None


class _Core:
    namespace = "team-test"

    def __init__(self):
        self.create_calls = []
        self.delete_calls = []

    def list_node(self, label_selector):
        return SimpleNamespace(items=[SimpleNamespace(
            metadata=SimpleNamespace(name="brk-tue-1530-tbl-quiet-window", labels={}),
            status=SimpleNamespace(allocatable={"affinity.dev/seats": "4"}),
        )])

    def create_namespaced_pod(self, namespace, pod):
        self.create_calls.append((namespace, pod))
        if len(self.create_calls) == 1:
            raise ApiException(status=409)

    def read_namespaced_pod(self, name, namespace):
        assert name == "attendee-att-1-brk-tue-1530"
        assert namespace == self.namespace
        return SimpleNamespace(metadata=SimpleNamespace(
            name=name, labels={"affinity.dev/group": "g-old"}
        ))

    def delete_namespaced_pod(self, name, namespace, grace_period_seconds):
        self.delete_calls.append((name, namespace, grace_period_seconds))


def test_group_formation_replaces_a_conflicting_pod_from_an_old_group(monkeypatch):
    core = _Core()
    ctl = SimpleNamespace(core=core, namespace=core.namespace)
    person = SimpleNamespace(id="att-1", needs=frozenset())
    result = SimpleNamespace(
        groups=[SimpleNamespace(id="g-new", table_id="brk-tue-1530-tbl-quiet-window", members=["att-1"])],
        unplaced=[],
        duration_ms=1,
    )
    monkeypatch.setattr(groups, "load_break_people", lambda *_args: [person])
    monkeypatch.setattr(groups, "similarity_for", lambda *_args: {})
    monkeypatch.setattr("app.solver.solve", lambda *_args: result)
    monkeypatch.setattr(groups, "post_summary", lambda *_args: None)

    groups.form_groups(ctl, _Connection(), "brk-tue-1530", datetime(2026, 11, 10, tzinfo=timezone.utc))

    assert core.delete_calls == [("attendee-att-1-brk-tue-1530", "team-test", 0)]
    assert len(core.create_calls) == 2
    assert core.create_calls[1][1]["metadata"]["labels"]["affinity.dev/group"] == "g-new"
