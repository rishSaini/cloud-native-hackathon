# Privacy review

Affinity handles information that can reveal a disability. Flag any change where
card fields (name, pronouns, how to talk to me, reach me), attendee names, access
needs or capability meanings could reach:

- logs or error messages (including `log.info(..., body)` on `/api/card*`, `/c/*`, `/api/ask`)
- OpenTelemetry span attributes (only `app.telemetry.attrs.set_attrs`, with its allow-list)
- Kubernetes labels, annotations or Pod and Node specs (`backend/app/k8s/`, `backend/app/controller/`)
- Elasticsearch documents (`backend/app/search/`, `backend/app/reports/`, `backend/app/incidents/`)
- the public board (`backend/app/board/`)

Kubernetes objects may only contain random attendee IDs and opaque capability
labels such as `affinity.dev/cap-c7`. Capability meanings live only in
`backend/app/cards/capabilities.py`. Room reports store `reporter_hash`, never an attendee ID.
