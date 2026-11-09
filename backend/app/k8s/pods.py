"""Attendee Pod specs (R6). An attendee's placement in one slot is one Pod.

The spec holds only a random attendee ID and opaque labels such as
`affinity.dev/cap-c3`: Pods are visible in Radar, through MCP and to AI
investigations, so they must never reveal a name or an access need.
"""

from app.cards.capabilities import label
from app.controller.loop import pod_name

SEATS = "affinity.dev/seats"
HARD = "affinity-hard-requirement"
STANDARD = "affinity-standard"


def build_pod(attendee_id: str, slot: str, needs, ranked, namespace: str) -> dict:
    """needs: capability codes (cap-cN) the room must have. ranked: RankedNode list from K8."""
    required = [
        {"key": "type", "operator": "In", "values": ["kwok"]},
        {"key": "affinity.dev/kind", "operator": "In", "values": ["talk"]},
        {"key": "affinity.dev/slot", "operator": "In", "values": [slot]},
    ] + [{"key": label(code), "operator": "Exists"} for code in sorted(set(needs))]
    preferred = [
        {"weight": r.weight, "preference": {"matchExpressions": [
            {"key": "kubernetes.io/hostname", "operator": "In", "values": [r.node]}
        ]}}
        for r in ranked if 1 <= r.weight <= 100
    ]
    affinity = {"requiredDuringSchedulingIgnoredDuringExecution": {"nodeSelectorTerms": [{"matchExpressions": required}]}}
    if preferred:
        affinity["preferredDuringSchedulingIgnoredDuringExecution"] = preferred
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name(attendee_id, slot),
            "namespace": namespace,
            "labels": {"affinity.dev/attendee": attendee_id, "affinity.dev/slot": slot},
        },
        "spec": {
            "priorityClassName": HARD if needs else STANDARD,
            "tolerations": [{"key": "kwok.x-k8s.io/node", "operator": "Exists", "effect": "NoSchedule"}],
            "affinity": {"nodeAffinity": affinity},
            "containers": [{
                "name": "attendee",
                "image": "registry.k8s.io/pause:3.10",
                "resources": {
                    "requests": {"cpu": "1m", "memory": "1Mi"},
                    "limits": {"cpu": "1m", "memory": "1Mi", SEATS: "1"},
                },
                "securityContext": {
                    "runAsNonRoot": True,
                    "runAsUser": 65535,
                    "allowPrivilegeEscalation": False,
                    "seccompProfile": {"type": "RuntimeDefault"},
                    "capabilities": {"drop": ["ALL"]},
                },
            }],
        },
    }
