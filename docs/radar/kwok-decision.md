# R1: Where do the simulated rooms and attendees run?

Affinity runs the conference on Kubernetes: rooms are KWOK fake Nodes with seats, and attendees are Pods that kube-scheduler places. The team cluster is a vcluster, so we test before building on it.

## The spike

```bash
./scripts/kwok-spike.sh coffeecon            # uses ~/cnh-kubeconfig
./scripts/kwok-spike.sh coffeecon --cleanup
```

It installs the KWOK v0.8.0 controller from `deploy/kwok/` (upstream manifests, patched by `deploy/kwok/controller.yaml`: 50m/64Mi requests, 250m/128Mi limits, user 65532, no privileges, no host access), creates the fake Node `spike-room` with `affinity.dev/seats: 4`, waits for it to be Ready, creates the pause Pod `spike-attendee` (1m CPU, 1Mi), and waits 70 seconds.

| Check | How |
|---|---|
| 1. The Node survives a minute | `spike-room` still exists, with 4 seats |
| 2. The Pod binds to the fake Node and runs, with no host `SyncError` and no quota increase | Pod `nodeName` and phase; events filtered by the Pod's UID; ResourceQuota usage before and after |
| 3. Radar's topology shows both | Manual, in Radar Cloud |

## Results

### Local kind cluster (control run, 2026-11-09 14:40 MT)

| Check | Result |
|---|---|
| 1. Node survives a minute, 4 seats | PASS |
| 2. Pod bound to `spike-room`, `Running`, no `SyncError` or `FailedScheduling` | PASS |
| 3. Radar topology | Not tested (kind is not connected to Radar) |

This proves the manifests and the non-root patch work. It says nothing about the vcluster.

### Team vcluster `coffeecon`

> To fill in after `./scripts/kwok-spike.sh coffeecon` runs against the team cluster. Paste the script's output and add Radar evidence (`get_resource` on `spike-room`, `get_events` on `spike-attendee`, quota usage, a topology screenshot).

| Check | Result | Evidence |
|---|---|---|
| 1. Node survives a minute | `<PASS/FAIL>` | `<link or screenshot>` |
| 2. Pod bound, Running, no SyncError, no quota increase | `<PASS/FAIL>` | `<link or screenshot>` |
| 3. Radar topology shows both | `<PASS/FAIL>` | `<link or screenshot>` |

## Decision

> Pick one after the vcluster run.

- **A. vcluster-native** (all three checks pass): add `kwok` and the Nodes to Argo CD. Best Radar story.
- **B. Nested simulator in the namespace**: a Deployment running the all-in-one `registry.k8s.io/kwok/cluster` image; the controller targets it through `KUBE_TARGET_KUBECONFIG`.
- **C. Separate cluster**: `kwokctl` or kind with KWOK on a laptop (`deploy/kwok/` works there, as the control run shows), connected to Radar Cloud as an extra cluster.

**Chosen:** `<A/B/C>`, because `<reason>`.

Every later task works with any choice: R5's Kubernetes client takes its target from config.
