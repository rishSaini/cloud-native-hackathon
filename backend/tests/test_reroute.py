"""R8: which Pods have lost a capability their owner needs."""

import json

from kubernetes.client import ApiClient

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
