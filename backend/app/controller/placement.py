"""Talk placement reconciler (R6).

For every placement request without a Pod, it creates one: required affinity
on the slot and the person's needs, preferred affinity from Karthik's
`rank_talks_for`, and one `affinity.dev/seats`. kube-scheduler then binds it to
a room with space. The reconciler records each binding, writes a notification,
and turns FailedScheduling events into plain language for that attendee only.
"""

import json
import logging
from datetime import datetime, timezone

from kubernetes.client.exceptions import ApiException
from opentelemetry import metrics, trace

from app.auth import attendee_hash
from app.controller.loop import POD_SELECTOR, pod_name, register
from app.db import pool
from app.k8s.pods import build_pod
from app.k8s.seats import count_free
from app.telemetry.attrs import set_attrs

log = logging.getLogger("affinity.controller.placement")
tracer = trace.get_tracer("talkscout")
meter = metrics.get_meter("talkscout")
placement_duration = meter.create_histogram(
    "talkscout.search.placement.duration", unit="s", description="Placement request to bound Pod"
)
reroute_duration = meter.create_histogram(
    "talkscout.search.reroute.duration", unit="s", description="Room change to the attendee's new placement"
)
# pod name -> when its reroute started (room change or eviction). Lost on restart: only the metric is.
reroute_started: dict = {}
unplaced_gauge = meter.create_gauge(
    "talkscout.search.unplaced_attendees", description="Attendees with no placement right now"
)

FULL = "The matching talks at this time are full. Here are the closest ones with space."
NO_MATCH = "No room at this time has everything you asked for. Here are the closest ones with space."
WAITING = "We're still finding you a seat."


def ranked_nodes(attendee_id: str, slot: str):
    """K8's ranking, or no preferences if it isn't available yet."""
    try:
        from app.search.ranking import rank_talks_for

        return rank_talks_for(attendee_id, slot)
    except Exception as err:  # NotImplementedError until K8 lands, or ES trouble
        log.info("no ranking for this placement (%s); placing without preferences", type(err).__name__)
        return []


def explain(message: str) -> str:
    if "Insufficient affinity.dev/seats" in message:
        return FULL
    if "didn't match Pod's node affinity" in message:
        return NO_MATCH
    return WAITING


def scheduler_message(core, namespace: str, pod) -> str:
    events = core.list_namespaced_event(
        namespace, field_selector=f"involvedObject.uid={pod.metadata.uid},reason=FailedScheduling"
    ).items
    latest = max(events, key=lambda e: e.last_timestamp or e.event_time or datetime.min.replace(tzinfo=timezone.utc), default=None)
    return latest.message if latest else ""


def room_of(node: str, slot: str) -> str:
    return node[len(slot) + 1:] if node.startswith(slot + "-") else node


@register("placement")
def reconcile_placements(ctl) -> None:
    with tracer.start_as_current_span("talkscout.search.placement.reconcile"), pool().connection() as conn:
        requests = conn.execute(
            "SELECT r.attendee_id, r.slot, r.created_at,"
            " COALESCE(array_agg(c.capability) FILTER (WHERE c.capability IS NOT NULL), '{}')"
            " FROM placement_requests r LEFT JOIN capabilities c USING (attendee_id)"
            " GROUP BY r.attendee_id, r.slot, r.created_at"
        ).fetchall()
        # People with needs first: a priority class only orders Pods that wait in the
        # scheduler queue together, so creating them first keeps accessible seats for them.
        requests.sort(key=lambda r: (not r[3], r[2]))
        known = {(a, s): (st, n, rs) for a, s, st, n, rs in conn.execute(
            "SELECT attendee_id, slot, status, node, reason FROM placements"
        )}
        pods = {p.metadata.name: p for p in ctl.core.list_namespaced_pod(ctl.namespace, label_selector=POD_SELECTOR).items}
        free_by_slot: dict[str, dict[str, int]] = {}
        unplaced = 0

        for attendee, slot, created_at, needs in requests:
            name, key = pod_name(attendee, slot), (attendee, slot)
            pod = pods.get(name)
            if pod is None:
                if known.get(key, (None,))[0] == "Scheduled":
                    reroute_started.setdefault(name, datetime.now(timezone.utc))  # evicted: R8 reroute
                with tracer.start_as_current_span("k8s.pod.create") as span:
                    set_attrs(span, slot_id=slot, attendee_hash=attendee_hash(attendee))
                    body = build_pod(attendee, slot, needs, ranked_nodes(attendee, slot), ctl.namespace)
                    try:
                        ctl.core.create_namespaced_pod(ctl.namespace, body)
                    except ApiException as err:
                        if err.status != 409:  # 409: it exists already, which is fine
                            raise
                conn.execute(
                    "INSERT INTO placements (attendee_id, slot, pod_name, status, reason) VALUES (%s, %s, %s, 'Pending', %s)"
                    " ON CONFLICT (attendee_id, slot) DO NOTHING",
                    (attendee, slot, name, WAITING),
                )
                unplaced += 1
                continue

            node = pod.spec.node_name
            if node:
                previous = known.get(key, (None, None))
                if previous[0] != "Scheduled" or previous[1] != node:
                    moved = previous[0] == "Scheduled" or name in reroute_started
                    with tracer.start_as_current_span("k8s.pod.bound") as span:
                        set_attrs(span, slot_id=slot, placement_outcome="bound", attendee_hash=attendee_hash(attendee))
                        conn.execute(
                            "INSERT INTO placements (attendee_id, slot, pod_name, status, node, reason, scheduler_message, options)"
                            " VALUES (%s, %s, %s, 'Scheduled', %s, NULL, NULL, '[]')"
                            " ON CONFLICT (attendee_id, slot) DO UPDATE SET status='Scheduled', node=EXCLUDED.node,"
                            " reason=NULL, scheduler_message=NULL, options='[]', updated_at=now()",
                            (attendee, slot, name, node),
                        )
                        conn.execute(
                            "INSERT INTO notifications (attendee_id, kind, payload) VALUES (%s, %s, %s)",
                            (attendee, "moved" if moved else "placed",
                             json.dumps({"slot": slot, "node": node, "room": room_of(node, slot)})),
                        )
                        started = reroute_started.pop(name, None)
                        if started:
                            reroute_duration.record((datetime.now(timezone.utc) - started).total_seconds())
                        else:
                            placement_duration.record((datetime.now(timezone.utc) - created_at).total_seconds())
                continue

            unplaced += 1
            message = scheduler_message(ctl.core, ctl.namespace, pod)
            reason = explain(message) if message else WAITING
            if known.get(key, (None, None, None))[2] != reason:
                if slot not in free_by_slot:
                    nodes = ctl.core.list_node(label_selector=f"affinity.dev/kind=talk,affinity.dev/slot={slot}").items
                    free_by_slot[slot] = count_free(nodes, pods.values())
                options = [
                    {"room": room_of(n, slot), "node": n, "seatsLeft": seats}
                    for n, seats in sorted(free_by_slot[slot].items(), key=lambda kv: -kv[1]) if seats > 0
                ][:3]
                conn.execute(
                    "UPDATE placements SET status='Pending', reason=%s, scheduler_message=%s, options=%s, updated_at=now()"
                    " WHERE attendee_id=%s AND slot=%s",
                    (reason, message or None, json.dumps(options), attendee, slot),
                )

        unplaced_gauge.set(unplaced)
