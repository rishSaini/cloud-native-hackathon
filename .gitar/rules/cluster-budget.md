---
title: "Team cluster budget"
description: "Keep deploy/ inside the hackathon cluster's resource budget"
when: "PRs that change files in deploy/"
actions: "Add up requests, limits and storage for all workloads and post a comment with the totals"
---

# Team cluster budget

The team cluster allows, in total: 2 CPU and 4 GiB of requests, 4 CPU and 8 GiB of limits, and 4 PVCs with 20 GiB of storage.

When a PR changes `deploy/`:
- Add up CPU and memory requests and limits over all containers, multiplied by replicas.
- Add up PVC count and storage, including StatefulSet volumeClaimTemplates.
- Post a comment with the totals next to the budget.
- Flag the PR if a total is over budget, or if a container has no requests or limits.
