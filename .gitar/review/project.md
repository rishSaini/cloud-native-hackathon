# Affinity review notes

- The repo is public. Flag any API key, token, kubeconfig or `.env` content in a diff.
- File ownership follows `docs/tasks/karthik.md` and `docs/tasks/rishabh.md` ("Who owns which files"). Flag a PR that rewrites the other person's files. Shared files (`backend/app/main.py`, `backend/requirements.txt`, `deploy/kustomization.yaml`, `.env.example`, `backend/tests/conftest.py`) are append-only.
- `/healthz` and `/readyz` must never call Elasticsearch or Postgres.
- Span names come from the telemetry contract: `room.report.received`, `room.state.updated`, `k8s.node.taint`, `placement.reconcile`, `elasticsearch.candidates`, `k8s.pod.create`, `k8s.pod.bound`, `notification.sent`, `solver.run`, `search.hybrid`, `ask.rag`. Custom attributes go only through `app.telemetry.attrs.set_attrs`.
- Every new API route needs a test. Tests must not need a running Elasticsearch, Postgres or cluster: use fakes (`FakeES` in `conftest.py`, dependency overrides).
- Every container in `deploy/` needs CPU and memory requests and limits. No privileged, hostPath, hostNetwork or hostPID pods.
- Commit messages and PR descriptions must not contain AI co-author or "Generated with" lines.
