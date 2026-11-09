#!/usr/bin/env bash
# Copy secret values from .env into Secret app-credentials in the team cluster.
# It never prints a value. It copies only these keys, and only when they are set
# to a real value (not empty, not a YOUR_... placeholder):
#   OPENAI_API_KEY  OTEL_EXPORTER_OTLP_ENDPOINT  OTEL_EXPORTER_OTLP_HEADERS
#   DASH0_RUM_ENDPOINT  DASH0_RUM_TOKEN
#
#   ./scripts/push-secrets.sh <team-name>
#
# Uses the kubeconfig in $KUBECONFIG, or ~/cnh-kubeconfig. Get it from Radar Cloud
# (RADAR.md, "kubectl") and keep it outside the repo. The script refuses any
# cluster whose server is not *.cnh.radarhq.io, so it can't touch other clusters.
# Other keys already in the Secret stay as they are (server-side apply).
set -euo pipefail

KEYS=(OPENAI_API_KEY OTEL_EXPORTER_OTLP_ENDPOINT OTEL_EXPORTER_OTLP_HEADERS DASH0_RUM_ENDPOINT DASH0_RUM_TOKEN)
SERVER_PATTERN="${CNH_SERVER_PATTERN:-\.cnh\.radarhq\.io}"

team="${1:-}"
if [[ ! "$team" =~ ^[a-z0-9]([a-z0-9-]{0,18}[a-z0-9])?$ ]]; then
  echo "usage: $0 <team-name>" >&2
  exit 1
fi
namespace="team-${team}"

cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo "No .env here. Run make setup and fill it in first." >&2
  exit 1
fi

export KUBECONFIG="${KUBECONFIG:-$HOME/cnh-kubeconfig}"
if [ ! -f "$KUBECONFIG" ]; then
  echo "No kubeconfig at $KUBECONFIG. Copy it from Radar Cloud (RADAR.md, \"kubectl\")." >&2
  exit 1
fi
server="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
if ! printf '%s' "$server" | grep -qE "$SERVER_PATTERN"; then
  echo "Refusing: $server is not a hackathon team cluster." >&2
  exit 1
fi

tmp="$(mktemp)"
chmod 600 "$tmp"
trap 'rm -f "$tmp"' EXIT

copied=()
for key in "${KEYS[@]}"; do
  line="$(grep -E "^${key}=" .env | tail -1 || true)"
  value="${line#*=}"
  if [ -n "$value" ] && [[ "$value" != *YOUR_* ]]; then
    printf '%s\n' "$line" >> "$tmp"
    copied+=("$key")
  fi
done
if [ ${#copied[@]} -eq 0 ]; then
  echo "Nothing to copy: none of ${KEYS[*]} has a real value in .env." >&2
  exit 1
fi

kubectl create secret generic app-credentials --namespace "$namespace" \
  --from-env-file="$tmp" --dry-run=client -o yaml |
  kubectl apply --server-side --force-conflicts --field-manager=push-secrets -f -

echo "Set in Secret app-credentials ($namespace on $server): ${copied[*]}"
echo "Pods read it at start. Restart them to pick it up: kubectl -n $namespace rollout restart deployment/app"
