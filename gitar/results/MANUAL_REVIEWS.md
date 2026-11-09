# Gitar reviews, logged by hand

A running log of Gitar's verdicts from the Gitar dashboard, with what we did about each finding. `scripts/gitar_export.py` does not touch this file (it writes `README.md` and `pr-*.md`). Put demo-worthy catches in [HIGHLIGHTS.md](HIGHLIGHTS.md) as well.

Gitar rates every PR's **risk** from what it touches (auth, data, deploy), even when the code is fine. Risk is not a finding. **Findings** are the problems it asks us to fix.

## Summary

| PR | Title | Risk | Verdict | Findings | Rules applied | Outcome |
|---|---|---|---|---|---|---|
| [#1](https://github.com/rishSaini/cloud-native-hackathon/pull/1) | K0: Contract stubs for search, solver, and telemetry | Medium | Approved | 0 | none | Merged, no changes needed |
| [#2](https://github.com/rishSaini/cloud-native-hackathon/pull/2) | R0: contract stubs for auth, break inputs and free seats | High | Approved | 0 | none | Merged, no changes needed |

## Reviews

### #1 · K0: Contract stubs for search, solver, and telemetry

- **Reviewed:** 2026-11-09
- **Risk:** Medium (search ranking, the group solver and telemetry attributes)
- **Verdict:** Approved
- **Findings:** none
- **Rules applied:** none. The team's `.gitar/` rules arrive with [#3](https://github.com/rishSaini/cloud-native-hackathon/pull/3) and weren't on `main` yet.
- **What we changed:** nothing

### #2 · R0: contract stubs for auth, break inputs and free seats

- **Reviewed:** 2026-11-09
- **Risk:** High (touches auth: `current_attendee_id` and the HMAC `attendee_hash` keyed by `SESSION_SIGNING_KEY`)
- **Verdict:** Approved
- **Findings:** none
- **Rules applied:** none, for the same reason as #1.
- **What we changed:** nothing
