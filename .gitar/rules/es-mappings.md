---
title: "Elasticsearch mappings stay safe"
description: "Mapping changes keep es_setup idempotent and never map card fields"
when: "PRs that change backend/app/search/mappings.py or backend/app/search/setup.py"
actions: "Check idempotency and card-field safety, then post a comment with the result"
---

# Elasticsearch mappings stay safe

When a PR changes `backend/app/search/mappings.py` or `backend/app/search/setup.py`:
- `scripts/es_setup.py` must stay idempotent: it only creates what is missing, and a second run changes nothing.
- No index may map a card field (name, pronouns, how to talk, reach me) or an access need.
- `people`, `room-state`, `incidents` and `room-reports` keep `"dynamic": "strict"`.
Post a comment that lists the changed indices and says whether each check passes.
