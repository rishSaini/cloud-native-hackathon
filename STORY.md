# CoffeeCon: the story

## Before

Recorded 2026-11-09 14:50 MST, right after Argo CD took over the namespace (synced `main` at `f84ee6e`, app image `104f1b7`).

Radar Checks: https://app.radarhq.io/checks?scope=alQ0v6qbxks&namespace=team-coffeecon

7 findings in `team-coffeecon`: 0 critical, 0 high, 7 medium, 0 low.

### Medium

- Security · `automountServiceAccountToken` · Deployment `app`
- Security · `readOnlyRootFs` · Deployment `app` (container `app`)
- Security · `automountServiceAccountToken` · StatefulSet `elasticsearch`
- Security · `readOnlyRootFs` · StatefulSet `elasticsearch` (container `elasticsearch`)
- Reliability · `livenessProbeMissing` · StatefulSet `elasticsearch`
- Reliability · `missingPDB` · Deployment `app` (2 replicas, no PodDisruptionBudget)
- Reliability · `missingTopologySpread` · Deployment `app` (2 replicas, no topology spread constraints)
