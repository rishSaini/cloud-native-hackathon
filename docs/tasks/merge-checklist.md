# Merge checklist: Karthik + Rishabh

How we land one PR per phase (K0, R0, K1, …) without fighting merge conflicts. Phases, dependencies and file ownership come from [`karthik.md`](karthik.md) and [`rishabh.md`](rishabh.md); this file only covers how the PRs get onto `main`.

Status: K0 (#1) and R0 (#2) are merged.

## Every phase, every time

- [ ] Branch from fresh `main`: `git fetch`, then `git switch -c k1-es-foundation origin/main`. One branch per phase, named `k<N>-…` / `r<N>-…`.
- [ ] PR title starts with the phase: `K1: …`, `R3: …`.
- [ ] Start a phase only when everything on its **Depends** line is merged. Don't branch off someone's unmerged branch. If you must, write `Depends on #N` in the PR description; it gets rebased after #N merges.
- [ ] Stay inside your owned paths. Touching the other person's files? Say so in the PR description.
- [ ] Shared files are append-only: add your lines, don't reorder, reformat or delete anyone else's.
- [ ] Changing the Shared contract? Change it in both `karthik.md` and `rishabh.md` in the same PR, and tell the other person.
- [ ] Before opening the PR: `git fetch`, `git rebase origin/main`, `pytest` (and `ruff check` once K5 is in).
- [ ] After any merge to `main`: `git pull --rebase`. The deploy Action pushes a `deploy: <sha> [skip ci]` commit after every merge.
- [ ] Someone may rebase and force-push your branch to get it merged. Before pushing to it again, run `git pull --rebase`.

## Expected conflicts (keep both sides)

Two PRs that both append to the end of the same list always conflict in git. These conflicts are trivial: keep both sides' lines.

| File | Phases that touch it |
|---|---|
| `deploy/kustomization.yaml` (`resources:`) | R1, R2, R3, R5, K10 |
| `backend/app/main.py` (`include_router` lines) | K4 (service rename), K6, K9, K11, K12, K13, R4, R6, R9, R10, R11 |
| `backend/requirements.txt`, `.env.example`, `backend/tests/conftest.py` | most phases |
| `deploy/deployment.yaml` (`env:`) | K4, R3, R4, others |
| `docs/AFFINITY.md` | K16, R15 (merge one first, then rebase the other) |

Never edit `newName` / `newTag` in `deploy/kustomization.yaml`; the deploy Action owns them.

A conflict in actual logic (not appended lines) goes back to the file's owner. Don't guess.

## Merge order

These two PRs change the rules for every PR after them, so they merge first in wave 1:

- **K5** adds `ruff` lint and coverage to CI. Open PRs must pass lint after it lands.
- **K4** adds a test that fails on any direct `span.set_attribute` outside `app/telemetry/`, and renames `talkscout` → `affinity` in `main.py`.

| Wave | Merge order |
|---|---|
| 1 | **K5 → K4** → K1 → R1 → R5 → R3 → K2 → R2 → K3 |
| 2 | K6 → R6 → R7 → K7 → K9 → R4 → R9 |
| 3 | K8 → K10 → R8 → K11 → R10 → R11 → R12 → K13 |
| 4 | K12 → K14 → R13 → R14 |
| 5 | K15 → K16 → R15 |

Cross-person handoffs:

- [ ] **K8 merged:** tell Rishabh. R6 switches off its `rank_talks_for` fake.
- [ ] **K10 merged:** close a room on purpose. Check that the controller (R7) taints it and that the trace links in Dash0.
- [ ] **R10** needs K3. **K15** needs R13. **K16** needs R10. **R15** needs K8 and K3.
- [ ] **4:30 PM:** full demo run-through, then feature freeze; only fixes after this.

Cut line if behind at 3:00 PM: drop R11, K13, and K11's staff PATCH.

## Merging a PR (whoever merges)

1. [ ] Every phase on its Depends line is merged.
2. [ ] Rebase onto `main`, resolve the append-only conflicts, run `pytest`, then `git push --force-with-lease`.
3. [ ] CI is green and Gitar has reviewed. Address Gitar's requested changes or reply to them.
4. [ ] Merge. Wait for the `build-and-deploy` run and its `deploy: <sha> [skip ci]` commit.
5. [ ] Confirm the deploy (`ship` skill): Argo CD synced revision, workload health, and the new version at the public URL.
6. [ ] Move on to the next PR in the order above.
