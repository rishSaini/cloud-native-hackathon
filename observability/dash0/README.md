# Dash0: the "Affinity live" dashboard, SLO checks and synthetic checks (K14)

Services: `affinity-api` (Deployment `app`) and `affinity-controller` (Deployment `controller`).
Both export traces, metrics and logs over OTLP when Secret `app-credentials` has
`OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS`.

`OTEL_METRICS_EXPORTER=otlp` and `OTEL_TRACES_SAMPLER=always_on` are set in
`deploy/deployment.yaml`, following Dash0's agent skills
(<https://github.com/dash0hq/agent-skills>, `otel-instrumentation/rules/sdks/python.md`).
Without the first, the `affinity_*` metrics below may never reach Dash0.
Add the same two lines to `deploy/controller.yaml` and `deploy/room-state-cronjob.yaml`.

## Dashboard "Affinity live"

Create it in Dash0 (Dashboards > New dashboard) with these panels. Each query is PromQL.
After building it, export the JSON into `dashboards/affinity-live.json`.

| Panel | Type | PromQL |
|---|---|---|
| Placement p95 (s) | Time series | `histogram_quantile(0.95, sum by (le) (rate(affinity_placement_duration_seconds_bucket[5m])))` |
| Reroute p95 (s) | Time series | `histogram_quantile(0.95, sum by (le) (rate(affinity_reroute_duration_seconds_bucket[5m])))` |
| Unplaced now | Stat | `max(affinity_unplaced_attendees)` |
| Group sizes | Bar | `sum by (le) (increase(affinity_group_size_bucket[1h]))` |
| Solver time p95 (s) | Time series | `histogram_quantile(0.95, sum by (le) (rate(affinity_solver_duration_seconds_bucket[15m])))` |
| Open incidents | Stat | `max(affinity_incidents_open)` |
| Room reports by signal | Stacked bars | `sum by (report_signal) (increase(affinity_room_reports_total[5m]))` |
| Dropped span attributes | Stat | `sum(increase(affinity_telemetry_dropped_attributes_total[1h]))` (should stay 0) |
| Search latency p95 (s) | Time series | `histogram_quantile(0.95, sum by (le) (rate(http_server_duration_milliseconds_bucket{http_route="/api/talks/search"}[5m]))) / 1000` |

Label names: Dash0 may show `report.signal` as `report_signal` in PromQL. Check the
metric explorer and adjust the `by (...)` label if needed.

## SLO checks

`checks/affinity-slos.yaml` holds the four AFFINITY.md SLOs as PromQL check rules,
plus a placement-speed check:

| SLO | Target | Check |
|---|---|---|
| Nobody alone | 99% of opted-in attendees grouped | `AffinityPeopleAloneAtBreaks` |
| Fast reroute | 95% within 5 s | `AffinityRerouteSlow` |
| Placement success | 99.5% placed | `AffinityAttendeesUnplaced` (proxy: unplaced > 0 for 10 min) |
| Incident response | 95% handled within 5 min | `AffinityIncidentNotHandled` (proxy: an incident open for 5 min) |

## Synthetic checks

Create in Dash0 (Synthetic monitoring > New check), every minute, from one location:

| Name | URL | Assert |
|---|---|---|
| affinity-healthz | `https://<team>.cnh.radarhq.io/healthz` | status 200, body `ok` |
| affinity-board | `https://<team>.cnh.radarhq.io/api/board` | status 200, body contains `"rooms"`, response < 500 ms |

## RUM

The page loads `/rum.js`, which starts Dash0 website monitoring when
`DASH0_RUM_ENDPOINT` and `DASH0_RUM_TOKEN` are in `app-credentials`. Use a
separate ingest-only token. Check in Dash0's website monitoring that page views
arrive with service `affinity-web`, and that form fields (the card form) are not
recorded as text.

## What is verified

- Seven metric names match the open PRs: placement duration and unplaced (R6), group size and solver
  duration (K3), incidents open (K11), room reports (K9), dropped attributes (K4).
- `affinity_reroute_duration_seconds` (R8) and `affinity_alone_at_break_total` (R10) are not built yet,
  so their panel and checks stay empty until those land.
- Not verified yet: the Dash0 import of the dashboard and checks, label spelling in
  Dash0's PromQL, and RUM masking. These need the team's Dash0 org and live traffic.
