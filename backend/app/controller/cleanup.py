"""Cleanup (R12): delete attendee Pods whose attendee was deleted.

The attendees table is the source of truth. A Pod whose attendee ID is gone
belongs to someone who deleted their card, so it goes too.
"""

import logging

from app.controller.loop import POD_SELECTOR, register
from app.db import pool

log = logging.getLogger("affinity.controller.cleanup")


def orphans(pods, existing: set[str]) -> list:
    return [p for p in pods if p.metadata.labels.get("affinity.dev/attendee") not in existing]


@register("cleanup")
def reconcile_cleanup(ctl) -> None:
    pods = ctl.core.list_namespaced_pod(ctl.namespace, label_selector=POD_SELECTOR).items
    if not pods:
        return
    ids = sorted({p.metadata.labels["affinity.dev/attendee"] for p in pods})
    with pool().connection() as conn:
        existing = {r[0] for r in conn.execute("SELECT id FROM attendees WHERE id = ANY(%s)", (ids,))}
    for pod in orphans(pods, existing):
        ctl.core.delete_namespaced_pod(pod.metadata.name, ctl.namespace, grace_period_seconds=0)
        log.info("deleted %s: its attendee was deleted", pod.metadata.name)
