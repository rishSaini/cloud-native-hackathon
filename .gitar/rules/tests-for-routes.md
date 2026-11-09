---
title: "Tests for API changes"
description: "Ask for tests when backend routes change without tests"
when: "PRs that change backend/app/ but do not change backend/tests/"
actions: "Post a comment that lists the changed routes and asks for tests"
---

# Tests for API changes

When a PR changes `backend/app/` and does not touch `backend/tests/`:
- List each route that the PR adds or changes.
- Ask for at least one test per route, using the `FakeES` pattern in `backend/tests/test_api.py`.
