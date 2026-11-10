# Human insights (K17)

Telemetry about people, not servers, with no tracking of any one person.
The controller measures two things. The API and Dash0 show the same numbers.

| What | Why it matters | Where |
|---|---|---|
| **Room occupancy:** seats taken in each talk room, live | Organizers see which room fills first and when to open overflow | `GET /api/insights`, metrics `affinity_room_seats_taken` and `affinity_room_occupancy_ratio` |
| **Accessibility equity gap:** time to a seat for people who asked for an access need, against people who did not | Fairness as a number: people who need captions or step-free access must not wait longer | `GET /api/insights`, metric `affinity_time_to_seat_seconds` with `need.present` |

## Privacy

- The tables `occupancy_samples` and `seat_waits` have no attendee ID. Deleting a person has nothing to delete here.
- `seat_waits` stores only "asked for any need: yes or no". It never stores which need.
- A group with fewer than 5 people shows `"hidden": true` and no numbers.
- Metric attributes are `room.id`, `slot.id` and `need.present` only.

## API for the UI

`GET /api/insights?slot=tue-0900`. `slot` is optional; the default is the slot with the newest numbers. Poll every 5 seconds.

The app shows this at `#/insights` (link on Home). Each room also has:

- `talk`: `{ "title", "track" }` from the talks index, or `null` when search is down.
- `engagement`: how the talk held its room, or `null` before the first sample.
  `{ "peak": 111, "peakAtSeconds": 60, "now": 48, "kept": 0.432, "word": "DROPPED", "drop": { "people": 52, "fromSeconds": 91, "toSeconds": 118 } }`.
  `word` is HELD (90% or more of the peak stayed), STEADY (75% or more) or DROPPED. `drop` is the most people lost within a window of 30 s or 10% of the talk so far, whichever is longer, and only when 5 or more left.
- The top level has `startedAt`, the first sample of the slot. Seconds in `engagement` count from it.

```json
{
  "slot": "tue-0900",
  "generatedAt": "2026-11-10T16:02:11+00:00",
  "totals": { "seats": 30, "taken": 16, "occupancy": 0.533 },
  "rooms": [
    {
      "room": "room-155", "node": "tue-0900-room-155",
      "seats": 10, "taken": 8, "occupancy": 0.8,
      "history": [ { "at": "2026-11-10T15:58:40+00:00", "taken": 5 }, { "at": "2026-11-10T16:01:02+00:00", "taken": 8 } ]
    }
  ],
  "timeToSeat": {
    "withNeeds":    { "count": 6,  "hidden": false, "p50Seconds": 14.5, "p95Seconds": 16.8 },
    "withoutNeeds": { "count": 10, "hidden": false, "p50Seconds": 4.0,  "p95Seconds": 5.0 },
    "p95GapSeconds": 11.8
  },
  "privacy": "Counts only. No attendee IDs are stored for these charts. A group with fewer than 5 people is hidden."
}
```

- `rooms` is sorted fullest first. `history` has a point only when the count changed, so draw it as a step line.
- `p95GapSeconds` is `null` when either group is hidden.
- When a group is hidden, show "Too few people to show", not zero.

## Suggested UI (for Diya)

1. **Room fill:** one bar for each room with `taken / seats`, plus a step line from `history`. Show the number in words too, not color alone.
2. **Fairness:** two numbers side by side, "With access needs: 95% seated within 16.8 s" and "Without: 5.0 s", and the gap.
3. Print the `privacy` text under the charts.

## Dash0

Chart the same metrics in Dash0 (PromQL):

```promql
max by (room_id) (affinity_room_occupancy_ratio{slot_id="tue-0900"})
histogram_quantile(0.95, sum by (le, need_present) (rate(affinity_time_to_seat_seconds_bucket[10m])))
```

K17 also fixes two gaps that the Dash0 agent skills (`dash0hq/agent-skills`) find:

- **Service identity:** both workloads now set `service.namespace`, `service.version`, `service.instance.id`, `deployment.environment.name` and the `k8s.*` pod attributes. Dash0 can compare releases and link a trace to the Pod that Radar shows.
- **Service map:** Postgres calls (psycopg) and Kubernetes API calls (urllib3) are now CLIENT spans, so the map shows api → Postgres and controller → kube-apiserver.
