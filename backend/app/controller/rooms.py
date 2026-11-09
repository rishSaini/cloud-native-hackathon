"""Room state to Node taints and labels (R7).

Each pass reads `room-state` from Elasticsearch (one search) and makes the room's
talk Nodes for the current and next slot match it:

- full -> taint affinity.dev/full:NoSchedule (seated people stay)
- closed -> taint affinity.dev/closed:NoExecute (everyone is moved; R8)
- captions down / very loud / access blocked -> remove that capability label

Each change runs in span talkscout.k8s.node.taint, linked to the room-state document's
traceparent, so Dash0 shows report -> room state -> taint across both services.
It also writes seats_total, seats_free and controller_seen_at back to room-state.
"""

import logging
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from elasticsearch import NotFoundError
from opentelemetry import propagate, trace

from app.controller.loop import register
from app.es import get_es
from app.k8s.nodes import desired_taints, label_patch, taint_key, venue_caps
from app.k8s.seats import count_free
from app.telemetry.attrs import set_attrs

log = logging.getLogger("affinity.controller.rooms")
tracer = trace.get_tracer("talkscout")
DENVER = ZoneInfo("America/Denver")
SLOTS = ["tue-0900", "tue-1030", "tue-1330", "tue-1430", "tue-1600"]


def active_slots(now: datetime) -> list[str]:
    """The current and next slot. AFFINITY_CURRENT_SLOT pins the current one (demos)."""
    pinned = os.getenv("AFFINITY_CURRENT_SLOT")
    if pinned in SLOTS:
        i = SLOTS.index(pinned)
    else:
        hhmm = now.astimezone(DENVER).strftime("%H%M")
        started = [s for s in SLOTS if s[4:] <= hhmm]
        i = SLOTS.index(started[-1]) if started else 0
    return SLOTS[i:i + 2]


def room_states(es) -> dict[str, dict]:
    try:
        hits = es.search(index="room-state", size=100, query={"match_all": {}})["hits"]["hits"]
    except NotFoundError:
        return {}
    return {h["_source"]["room"]: h["_source"] for h in hits if "room" in h["_source"]}


def _link_to(traceparent: str | None):
    if not traceparent:
        return []
    ctx = trace.get_current_span(propagate.extract({"traceparent": traceparent})).get_span_context()
    return [trace.Link(ctx)] if ctx.is_valid else []


@register("rooms")
def reconcile_rooms(ctl) -> None:
    es = get_es()
    states = room_states(es)
    caps = venue_caps()
    slots = active_slots(datetime.now(UTC))
    nodes = [n for n in ctl.core.list_node(label_selector="affinity.dev/kind=talk").items
             if n.metadata.labels.get("affinity.dev/slot") in slots]
    pods = None

    for node in nodes:
        labels = node.metadata.labels
        room, slot = labels.get("affinity.dev/room"), labels.get("affinity.dev/slot")
        state = states.get(room, {})
        current = [{"key": t.key, "value": t.value, "effect": t.effect} for t in (node.spec.taints or [])]
        taints = desired_taints(state.get("status", "open"), current)
        patch = label_patch(labels, caps.get(room, set()), state.get("signals") or {})
        if taint_key(current) != taint_key(taints) or patch:
            with tracer.start_as_current_span("talkscout.k8s.node.taint", links=_link_to(state.get("traceparent"))) as span:
                set_attrs(span, room_id=room, slot_id=slot)
                body = {"spec": {"taints": taints}}
                if patch:
                    body["metadata"] = {"labels": patch}
                ctl.core.patch_node(node.metadata.name, body)
                log.info("node %s: taints=%s labels=%s", node.metadata.name,
                         [t["key"] for t in taints[1:]], patch)

        if slot == slots[0] and room in states:
            if pods is None:
                pods = ctl.core.list_namespaced_pod(ctl.namespace, label_selector=f"affinity.dev/slot={slot}").items
            free = count_free([node], pods)[node.metadata.name]
            total = int((node.status.allocatable or {}).get("affinity.dev/seats", "0"))
            es.update(index="room-state", id=room, doc={
                "seats_total": total, "seats_free": free,
                "controller_seen_at": datetime.now(UTC).isoformat(),
            })
