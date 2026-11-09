#!/usr/bin/env bash
# R1 spike: can KWOK fake Nodes and Pods live in this cluster?
#
#   ./scripts/kwok-spike.sh <team-name>            run the three checks, keep the objects for Radar
#   ./scripts/kwok-spike.sh <team-name> --cleanup  delete the spike Node and Pod
#
# Uses $KUBECONFIG (default ~/cnh-kubeconfig). Runs only against the hackathon
# cluster (*.cnh.radarhq.io) or a local kind cluster (127.0.0.1), never anything else.
# Then check the same things in Radar and write the result in docs/radar/kwok-decision.md.
set -euo pipefail

team="${1:?usage: $0 <team-name> [--cleanup]}"
ns="team-${team}"
cd "$(dirname "$0")/.."
export KUBECONFIG="${KUBECONFIG:-$HOME/cnh-kubeconfig}"
server="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
if ! printf '%s' "$server" | grep -qE '\.cnh\.radarhq\.io|127\.0\.0\.1'; then
  echo "Refusing: $server is not the hackathon cluster or a local kind cluster." >&2
  exit 1
fi
spike_pod() { sed "s/__TEAM__/${team}/g" deploy/kwok/spike-pod.yaml; }

if [ "${2:-}" = "--cleanup" ]; then
  spike_pod | kubectl delete --ignore-not-found -f -
  kubectl delete --ignore-not-found -f deploy/kwok/spike-node.yaml
  exit 0
fi

echo "== Cluster: $server, namespace $ns"
kubectl get namespace "$ns" >/dev/null 2>&1 || kubectl create namespace "$ns"
quota() { kubectl -n "$ns" get resourcequota -o jsonpath='{range .items[*]}{.status.used.requests\.cpu} cpu, {.status.used.requests\.memory} mem, {.status.used.pods} pods{"\n"}{end}' 2>/dev/null; }
before="$(quota)"

echo "== Install the KWOK controller"
kubectl apply -k deploy/kwok >/dev/null
kubectl -n kube-system rollout status deployment/kwok-controller --timeout=180s

echo "== Create the fake Node, wait for it to be Ready, then create the pause Pod and wait 70 seconds"
kubectl apply -f deploy/kwok/spike-node.yaml >/dev/null
kubectl wait node/spike-room --for=condition=Ready --timeout=60s >/dev/null
spike_pod | kubectl apply -f - >/dev/null
sleep 70

pass=0
check() { if eval "$2"; then echo "PASS  $1"; pass=$((pass + 1)); else echo "FAIL  $1"; fi; }
node_ok='kubectl get node spike-room >/dev/null 2>&1'
seats="$(kubectl get node spike-room -o jsonpath='{.status.allocatable.affinity\.dev/seats}' 2>/dev/null || true)"
bound="$(kubectl -n "$ns" get pod spike-attendee -o jsonpath='{.spec.nodeName}/{.status.phase}' 2>/dev/null || true)"
uid="$(kubectl -n "$ns" get pod spike-attendee -o jsonpath='{.metadata.uid}' 2>/dev/null || true)"
# Filter by UID: events from an earlier spike Pod with the same name stay for an hour.
sync_errors="$(kubectl -n "$ns" get events --field-selector "involvedObject.uid=${uid:-none}" -o jsonpath='{range .items[*]}{.reason}: {.message}{"\n"}{end}' 2>/dev/null | grep -E 'SyncError|FailedScheduling' || true)"
after="$(quota)"

check "1. The fake Node survives a minute (seats: ${seats:-none})" "$node_ok && [ \"$seats\" = 4 ]"
check "2a. The Pod binds to the fake Node and runs ($bound)" "[ \"$bound\" = spike-room/Running ]"
check "2b. No SyncError or FailedScheduling event" "[ -z \"$sync_errors\" ]"
echo "      quota before: ${before:-none}"
echo "      quota after:  ${after:-none}"
echo "      (2c. Compare the two quota lines: the pause Pod should add nothing, or almost nothing.)"
[ -n "$sync_errors" ] && echo "$sync_errors" | sed 's/^/      event: /'
echo "== $pass of 3 automatic checks passed. Check 3 is manual: open Radar's topology and look for spike-room and spike-attendee."
echo "   Record the result in docs/radar/kwok-decision.md. Clean up: $0 $team --cleanup"
