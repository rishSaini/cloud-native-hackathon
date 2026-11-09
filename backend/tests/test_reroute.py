"""R8: which Pods have lost a capability their owner needs."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from kubernetes.client import ApiClient
from kubernetes.client.exceptions import ApiException

from app.controller import reroute
from app.controller.reroute import lost_caps, required_caps
from app.k8s.pods import build_pod


def as_pod(body):
    """Turn the dict spec into a typed V1Pod, as the API returns it."""
    return ApiClient().deserialize(json.dumps(body), "V1Pod", "application/json")


def test_required_caps_come_from_the_pod_spec():
    pod = as_pod(build_pod("ab12", "tue-1430", ["cap-c1", "cap-c3"], [], "team-x"))
    assert required_caps(pod) == {"affinity.dev/cap-c1", "affinity.dev/cap-c3"}


def test_lost_caps_when_a_label_goes_away():
    pod = as_pod(build_pod("ab12", "tue-1430", ["cap-c1"], [], "team-x"))
    assert lost_caps(pod, {"affinity.dev/cap-c1": "true"}) == set()
    assert lost_caps(pod, {}) == {"affinity.dev/cap-c1"}
    no_needs = as_pod(build_pod("cd34", "tue-1430", [], [], "team-x"))
    assert lost_caps(no_needs, {}) == set()


def test_move_counts_commit_per_pod_and_404_delete_is_tolerated(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.moves = {}
            self.commits = []

        @contextmanager
        def transaction(self):
            before = self.moves.copy()
            try:
                yield
            except Exception:
                self.moves = before
                raise
            else:
                self.commits.append(self.moves.copy())

        def execute(self, query, params):
            if query.startswith("INSERT INTO moves"):
                key = tuple(params)
                self.moves.setdefault(key, 0)
                return SimpleNamespace(fetchone=lambda: (self.moves[key],))
            attendee, slot = params
            self.moves[(attendee, slot)] += 1
            return None

    class FakePool:
        @contextmanager
        def connection(self):
            yield connection

    class FakeCore:
        def __init__(self, pods):
            self.pods = pods
            self.delete_errors = [ApiException(status=404), ApiException(status=500)]

        def list_namespaced_pod(self, *args, **kwargs):
            return SimpleNamespace(items=self.pods)

        def list_node(self, *args, **kwargs):
            node = SimpleNamespace(metadata=SimpleNamespace(name="node-1", labels={}))
            return SimpleNamespace(items=[node])

        def delete_namespaced_pod(self, *args, **kwargs):
            error = self.delete_errors.pop(0)
            if error is not None:
                raise error

    def pod(name, attendee):
        expr = SimpleNamespace(key="affinity.dev/cap-c1", operator="Exists")
        terms = SimpleNamespace(match_expressions=[expr])
        required = SimpleNamespace(node_selector_terms=[terms])
        node_affinity = SimpleNamespace(required_during_scheduling_ignored_during_execution=required)
        spec = SimpleNamespace(
            node_name="node-1",
            affinity=SimpleNamespace(node_affinity=node_affinity),
        )
        metadata = SimpleNamespace(
            name=name,
            deletion_timestamp=None,
            labels={"affinity.dev/attendee": attendee, "affinity.dev/slot": "tue-1430"},
        )
        return SimpleNamespace(spec=spec, metadata=metadata)

    connection = FakeConnection()
    core = FakeCore([pod("pod-1", "attendee-1"), pod("pod-2", "attendee-2")])
    monkeypatch.setattr(reroute, "pool", FakePool)
    monkeypatch.setattr(reroute.placement, "reroute_started", {})
    ctl = SimpleNamespace(core=core, namespace="team-x")

    with pytest.raises(ApiException) as raised:
        reroute.reconcile_reroutes(ctl)

    assert raised.value.status == 500
    assert connection.moves == {("attendee-1", "tue-1430"): 1, ("attendee-2", "tue-1430"): 1}
    assert len(connection.commits) == 2
