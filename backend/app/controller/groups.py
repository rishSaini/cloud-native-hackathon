"""Break groups (R10): the solver decides who sits together, Kubernetes decides where.

Five minutes before a break (or when staff press "form groups now"), the
controller loads everyone who RSVPed, asks Karthik's similarity_matrix and
solve for groups, stores them, and creates one Pod per member: required node
affinity to the chosen table Node, and required pod affinity on the group,
so a group lands at one table together. Members get card grants until the
break ends. People who end up with no group are counted, and the board gets
the break's summary.
"""

import json
import logging
from datetime import UTC, datetime

from kubernetes.client.exceptions import ApiException

from app.breaks.inputs import load_break_people
from app.controller.loop import register
from app.db import pool

log = logging.getLogger("affinity.controller.groups")
_alone = None


def alone_counter():
    global _alone
    if _alone is None:
        from opentelemetry import metrics

        _alone = metrics.get_meter("talkscout").create_counter(
            "talkscout.search.alone_at_break", description="Opted-in people who ended up with no group")
    return _alone


def table_inputs(nodes):
    from app.solver import SolverTable

    return [
        SolverTable(
            id=n.metadata.name,
            seats=int((n.status.allocatable or {}).get("affinity.dev/seats", "0")),
            caps=frozenset(k.split("/", 1)[1] for k, v in (n.metadata.labels or {}).items()
                           if k.startswith("affinity.dev/cap-") and v == "true"),
        )
        for n in nodes
    ]


def similarity_for(ids):
    try:
        from app.search.similarity import similarity_matrix

        return similarity_matrix(ids)
    except Exception as err:  # NotImplementedError until K7, or ES trouble: solver still forms groups
        log.info("no similarity (%s); grouping by needs and RSVP order", type(err).__name__)
        return {}


def group_pod(attendee: str, break_id: str, group_id: str, table: str, needs, namespace: str) -> dict:
    return {
        "apiVersion": "v1", "kind": "Pod",
        "metadata": {
            "name": f"attendee-{attendee}-{break_id}".lower(), "namespace": namespace,
            "labels": {"affinity.dev/attendee": attendee, "affinity.dev/slot": break_id, "affinity.dev/group": group_id},
        },
        "spec": {
            "priorityClassName": "affinity-hard-requirement" if needs else "affinity-standard",
            "tolerations": [{"key": "kwok.x-k8s.io/node", "operator": "Exists", "effect": "NoSchedule"}],
            "affinity": {
                "nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {"nodeSelectorTerms": [
                    {"matchExpressions": [{"key": "kubernetes.io/hostname", "operator": "In", "values": [table]}]}]}},
                "podAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [
                    {"labelSelector": {"matchLabels": {"affinity.dev/group": group_id}}, "topologyKey": "affinity.dev/table"}]},
            },
            "containers": [{
                "name": "attendee", "image": "registry.k8s.io/pause:3.10",
                "resources": {"requests": {"cpu": "1m", "memory": "1Mi"},
                              "limits": {"cpu": "1m", "memory": "1Mi", "affinity.dev/seats": "1"}},
                "securityContext": {"runAsNonRoot": True, "runAsUser": 65535, "allowPrivilegeEscalation": False,
                                    "seccompProfile": {"type": "RuntimeDefault"}, "capabilities": {"drop": ["ALL"]}},
            }],
        },
    }


def post_summary(break_id: str, opted_in: int, alone: int) -> None:
    """For Karthik's board (K12): counts only."""
    try:
        from app.es import get_es

        get_es().index(index="board-summary", id="last-break", document={
            "break": break_id, "opted_in": opted_in, "alone": alone, "at": datetime.now(UTC).isoformat()})
    except Exception as err:
        log.warning("board summary not written (%s)", type(err).__name__)


def form_groups(ctl, conn, break_id: str, ends_at) -> None:
    from app.solver import solve

    people = load_break_people(break_id, conn)
    nodes = ctl.core.list_node(label_selector=f"affinity.dev/kind=table,affinity.dev/slot={break_id}").items
    result = solve(people, table_inputs(nodes), similarity_for([p.id for p in people]))
    needs = {p.id: p.needs for p in people}
    for group in result.groups:
        conn.execute("INSERT INTO groups (id, slot, table_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                     (group.id, break_id, group.table_id))
        for member in group.members:
            conn.execute("INSERT INTO group_members (group_id, attendee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                         (group.id, member))
            for other in group.members:
                if other != member:
                    conn.execute("INSERT INTO card_grants (owner_id, viewer_id, reason, expires_at)"
                                 " VALUES (%s, %s, 'group', %s)", (member, other, ends_at))
            pod = group_pod(member, break_id, group.id, group.table_id, needs[member], ctl.namespace)
            try:
                ctl.core.create_namespaced_pod(ctl.namespace, pod)
            except ApiException as err:
                if err.status != 409:
                    raise
                try:
                    existing = ctl.core.read_namespaced_pod(pod["metadata"]["name"], ctl.namespace)
                except ApiException as read_err:
                    if read_err.status != 404:
                        raise
                    ctl.core.create_namespaced_pod(ctl.namespace, pod)
                else:
                    if (existing.metadata.labels or {}).get("affinity.dev/group") != group.id:
                        ctl.core.delete_namespaced_pod(
                            existing.metadata.name, ctl.namespace, grace_period_seconds=0)
                        ctl.core.create_namespaced_pod(ctl.namespace, pod)
            conn.execute("INSERT INTO notifications (attendee_id, kind, payload) VALUES (%s, 'group', %s)",
                         (member, json.dumps({"break": break_id, "group": group.id})))
    if result.unplaced:
        alone_counter().add(len(result.unplaced))
    post_summary(break_id, len(people), len(result.unplaced))
    conn.execute("UPDATE breaks SET formed_at = now() WHERE id = %s", (break_id,))
    log.info("break %s: %d groups, %d alone, solver %d ms",
             break_id, len(result.groups), len(result.unplaced), result.duration_ms)


@register("groups")
def reconcile_groups(ctl) -> None:
    with pool().connection() as conn:
        due = conn.execute(
            "SELECT id, GREATEST(ends_at, now() + interval '30 minutes') FROM breaks WHERE formed_at IS NULL"
            " AND (form_requested_at IS NOT NULL"
            "      OR (now() >= starts_at - interval '5 minutes' AND now() < ends_at))"
        ).fetchall()
        for break_id, ends_at in due:
            form_groups(ctl, conn, break_id, ends_at)
