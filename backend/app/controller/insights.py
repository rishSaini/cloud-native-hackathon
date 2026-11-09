"""Human insights reconciler (K17).

Two numbers for people, not servers, as OpenTelemetry metrics and as rows the
API turns into live charts:

- Room occupancy: seats taken on each talk Node, from the bound attendee Pods.
- Time to seat, split by "asked for an access need" (yes or no). The gap
  between the two is the accessibility equity gap.

Privacy: metric attributes are room, slot and a boolean only. No attendee ID
goes into a metric or into the insights tables.
"""

import logging

from opentelemetry import metrics

from app.controller.loop import POD_SELECTOR, register
from app.db import pool
from app.k8s.seats import SEATS, count_free

log = logging.getLogger("affinity.controller.insights")
meter = metrics.get_meter("affinity")
seats_taken_gauge = meter.create_gauge(
    "affinity_room_seats_taken", unit="{seat}", description="Seats taken in each talk room now"
)
occupancy_gauge = meter.create_gauge(
    "affinity_room_occupancy_ratio", unit="1", description="Seats taken divided by seats in each talk room"
)
time_to_seat = meter.create_histogram(
    "affinity_time_to_seat_seconds", unit="s",
    description="Placement request to first seat, split by need.present (the equity gap)",
)

# node -> last taken count written, so we only write when it changes
_last_taken: dict[str, int] = {}


def room_of(node: str, slot: str) -> str:
    return node[len(slot) + 1:] if slot and node.startswith(slot + "-") else node


def occupancy(nodes, pods) -> list[dict]:
    free = count_free(nodes, pods)
    rows = []
    for n in nodes:
        labels = n.metadata.labels or {}
        slot = labels.get("affinity.dev/slot", "")
        seats = int((n.status.allocatable or {}).get(SEATS, "0"))
        rows.append({
            "node": n.metadata.name, "slot": slot, "room": room_of(n.metadata.name, slot),
            "seats": seats, "taken": seats - free.get(n.metadata.name, seats),
        })
    return rows


# First seats since the watermark. A rerouted person (moves.count > 0) is left
# out: their updated_at is the move, not the first seat.
NEW_SEATS = (
    "SELECT p.slot, p.updated_at, EXTRACT(EPOCH FROM (p.updated_at - r.created_at)),"
    " EXISTS (SELECT 1 FROM capabilities c WHERE c.attendee_id = p.attendee_id)"
    " FROM placements p JOIN placement_requests r USING (attendee_id, slot)"
    " LEFT JOIN moves m USING (attendee_id, slot)"
    " WHERE p.status = 'Scheduled' AND p.updated_at > %s AND COALESCE(m.count, 0) = 0"
    " ORDER BY p.updated_at"
)


@register("insights")
def reconcile_insights(ctl) -> None:
    nodes = ctl.core.list_node(label_selector="affinity.dev/kind=talk").items
    pods = ctl.core.list_namespaced_pod(ctl.namespace, label_selector=POD_SELECTOR).items
    rows = occupancy(nodes, pods)

    for r in rows:
        attrs = {"room.id": r["room"], "slot.id": r["slot"]}
        seats_taken_gauge.set(r["taken"], attrs)
        if r["seats"]:
            occupancy_gauge.set(r["taken"] / r["seats"], attrs)

    with pool().connection() as conn:
        if not _last_taken:
            _last_taken.update(conn.execute(
                "SELECT DISTINCT ON (node) node, taken FROM occupancy_samples ORDER BY node, at DESC"
            ).fetchall())
        for r in rows:
            if _last_taken.get(r["node"]) != r["taken"]:
                conn.execute(
                    "INSERT INTO occupancy_samples (node, slot, room, seats, taken) VALUES (%s, %s, %s, %s, %s)",
                    (r["node"], r["slot"], r["room"], r["seats"], r["taken"]),
                )
                _last_taken[r["node"]] = r["taken"]

        mark = conn.execute(
            "SELECT COALESCE(max(at), 'epoch'::timestamptz) FROM seat_waits"  # first run backfills
        ).fetchone()[0]
        for slot, at, seconds, need in conn.execute(NEW_SEATS, (mark,)).fetchall():
            seconds = max(0.0, float(seconds))
            time_to_seat.record(seconds, {"slot.id": slot, "need.present": bool(need)})
            conn.execute(
                "INSERT INTO seat_waits (slot, need_present, seconds, at) VALUES (%s, %s, %s, %s)",
                (slot, bool(need), seconds, at),
            )
