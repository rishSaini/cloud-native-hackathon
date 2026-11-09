"""Reroute (R8): move people whose room stopped meeting their needs.

Closed rooms need no code here: R7's NoExecute taint makes Kubernetes evict
their Pods, and the placement reconciler creates replacements that the taint
keeps out of the closed room.

This reconciler handles the other case. A Pod's required node affinity is only
checked at scheduling time ("IgnoredDuringExecution"), so when R7 removes a
capability label (captions down, too loud, access blocked) the Pod stays. For
each bound Pod whose Node no longer has every capability its owner needs, it
deletes the Pod once per person and slot (the `moves` table), and placement
places the person again.
"""

import logging
from datetime import UTC, datetime

from kubernetes.client.exceptions import ApiException

from app.controller import placement
from app.controller.loop import POD_SELECTOR, register
from app.db import pool

log = logging.getLogger("affinity.controller.reroute")
MAX_MOVES_PER_SLOT = 1


def required_caps(pod) -> set[str]:
    terms = pod.spec.affinity.node_affinity.required_during_scheduling_ignored_during_execution.node_selector_terms
    return {
        expr.key for term in terms for expr in (term.match_expressions or [])
        if expr.key.startswith("affinity.dev/cap-") and expr.operator == "Exists"
    }


def lost_caps(pod, node_labels: dict) -> set[str]:
    return {key for key in required_caps(pod) if node_labels.get(key) != "true"}


@register("reroute")
def reconcile_reroutes(ctl) -> None:
    pods = [p for p in ctl.core.list_namespaced_pod(ctl.namespace, label_selector=POD_SELECTOR).items
            if p.spec.node_name and p.metadata.deletion_timestamp is None]
    if not pods:
        return
    labels = {n.metadata.name: n.metadata.labels or {} for n in ctl.core.list_node(label_selector="type=kwok").items}
    with pool().connection() as conn:
        for pod in pods:
            lost = lost_caps(pod, labels.get(pod.spec.node_name, {}))
            if not lost:
                continue
            attendee = pod.metadata.labels["affinity.dev/attendee"]
            slot = pod.metadata.labels["affinity.dev/slot"]
            with conn.transaction():
                row = conn.execute(
                    "INSERT INTO moves (attendee_id, slot, count) VALUES (%s, %s, 0)"
                    " ON CONFLICT (attendee_id, slot) DO UPDATE SET count = moves.count RETURNING count",
                    (attendee, slot),
                ).fetchone()
                if row[0] >= MAX_MOVES_PER_SLOT:
                    continue  # moved once already this slot: stay, and the board shows the problem
                conn.execute("UPDATE moves SET count = count + 1 WHERE attendee_id = %s AND slot = %s", (attendee, slot))
            placement.reroute_started.setdefault(pod.metadata.name, datetime.now(UTC))
            try:
                ctl.core.delete_namespaced_pod(pod.metadata.name, ctl.namespace, grace_period_seconds=0)
            except ApiException as err:
                if err.status != 404:
                    raise
            log.info("rerouting %s: its room lost %s", pod.metadata.name, sorted(lost))
