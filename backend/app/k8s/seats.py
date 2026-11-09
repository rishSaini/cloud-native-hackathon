"""Seat counts from Kubernetes Nodes (contract, owner: Rishabh, R6)."""

SEATS = "affinity.dev/seats"
DONE_PHASES = {"Succeeded", "Failed"}


def count_free(nodes, pods) -> dict[str, int]:
    """Node allocatable seats minus the attendee Pods bound to each Node."""
    used: dict[str, int] = {}
    for pod in pods:
        node = pod.spec.node_name
        if node and (pod.status.phase or "") not in DONE_PHASES and pod.metadata.deletion_timestamp is None:
            used[node] = used.get(node, 0) + 1
    return {
        n.metadata.name: max(0, int((n.status.allocatable or {}).get(SEATS, "0")) - used.get(n.metadata.name, 0))
        for n in nodes
    }


def free_seats(slot: str, core=None, namespace: str | None = None) -> dict[str, int]:
    """Node name -> free `affinity.dev/seats` for every talk Node in `slot`."""
    from app.k8s import client

    core = core or client.core_api()
    namespace = namespace or client.namespace()
    nodes = core.list_node(label_selector=f"affinity.dev/kind=talk,affinity.dev/slot={slot}").items
    pods = core.list_namespaced_pod(namespace, label_selector=f"affinity.dev/slot={slot}").items
    return count_free(nodes, pods)
