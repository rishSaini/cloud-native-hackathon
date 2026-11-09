---
title: "Kubernetes objects stay opaque"
description: "Pod and Node specs hold only random IDs and opaque capability labels"
when: "PRs that change backend/app/k8s/, backend/app/controller/, scripts/gen_nodes.py or deploy/kwok/"
actions: "Check every label, annotation and name the change writes, then post a comment"
---

# Kubernetes objects stay opaque

Pods and Nodes are visible in Radar, through MCP and to AI investigations. When a
PR changes code that builds them:
- Labels and names may hold only random attendee IDs, slots, rooms, tables and `affinity.dev/cap-*` codes.
- No card text, name or capability meaning (captions, quiet, step-free …) in any label, annotation or name.
- Raw scheduler messages never go to the public board.
Post a comment that lists what the change writes into Pod or Node specs.
