#!/bin/sh
# Starts the API on $PORT (8080 in the container).
# Turns on OpenTelemetry (traces, metrics, logs to Dash0) only when an OTLP endpoint is set.
set -e
PORT="${PORT:-8080}"
if [ -n "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
  exec opentelemetry-instrument uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
