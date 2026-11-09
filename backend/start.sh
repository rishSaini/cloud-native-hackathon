#!/bin/sh
# Starts the API on $PORT (8080 in the container).
# Turns on OpenTelemetry (traces, metrics, logs to Dash0) only when an OTLP endpoint is set.
set -e
PORT="${PORT:-8080}"
if [ -n "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
  # K17: the image's version becomes service.version, so Dash0 can compare releases.
  export OTEL_RESOURCE_ATTRIBUTES="service.version=${APP_VERSION:-dev}${OTEL_RESOURCE_ATTRIBUTES:+,$OTEL_RESOURCE_ATTRIBUTES}"
  exec opentelemetry-instrument uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
