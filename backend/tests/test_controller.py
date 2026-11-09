"""R5: controller loop, with a fake Kubernetes API (no cluster needed)."""

import urllib.request
from types import SimpleNamespace

import pytest

from app.controller.loop import Controller, pod_name


class FakeCore:
    def __init__(self, nodes=2, pods=3):
        self.nodes, self.pods = nodes, pods
        self.selectors = []

    def list_node(self, label_selector):
        self.selectors.append(("node", label_selector))
        return SimpleNamespace(items=[object()] * self.nodes)

    def list_namespaced_pod(self, namespace, label_selector):
        self.selectors.append(("pod", namespace, label_selector))
        return SimpleNamespace(items=[object()] * self.pods)


def test_pod_names_are_deterministic_and_valid():
    assert pod_name("7f3k", "tue-1430") == "attendee-7f3k-tue-1430"
    assert pod_name("7F3K", "tue-1430") == pod_name("7f3k", "tue-1430")
    with pytest.raises(ValueError):
        pod_name("bad id!", "tue-1430")


def test_pass_runs_every_reconciler_and_counts_objects():
    calls = []
    ctl = Controller(FakeCore(), "team-x", reconcilers=[("a", lambda c: calls.append("a")), ("b", lambda c: calls.append("b"))])
    summary = ctl.run_once()
    assert calls == ["a", "b"]
    assert summary == {"pass": 1, "nodes": 2, "pods": 3, "failed": []}
    assert ("node", "type=kwok") in ctl.core.selectors
    assert ("pod", "team-x", "affinity.dev/attendee") in ctl.core.selectors


def test_a_failing_reconciler_does_not_stop_the_others():
    calls = []

    def boom(c):
        raise RuntimeError("broken")

    ctl = Controller(FakeCore(), "team-x", reconcilers=[("boom", boom), ("ok", lambda c: calls.append("ok"))])
    assert ctl.run_once()["failed"] == ["boom"]
    assert calls == ["ok"]


def test_health_endpoint_reports_fresh_passes():
    ctl = Controller(FakeCore(), "team-x", reconcilers=[], resync=10)
    server = ctl.start_health_server(port=0)
    port = server.server_address[1]
    ctl.run_once()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz") as resp:
        assert resp.status == 200
    server.shutdown()
