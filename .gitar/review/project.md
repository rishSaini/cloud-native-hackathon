# TalkScout review notes

- The repo is public. Flag any API key, token, kubeconfig or `.env` content in a diff.
- Backend code reaches Elasticsearch only through `app.es.get_es`, so tests can replace it with `FakeES`.
- Every new API route needs a test in `backend/tests/`. Tests must not need a running Elasticsearch.
- Keep `/healthz` and `/readyz` free of Elasticsearch calls. A slow Elasticsearch must not take the web page down.
- Name custom OpenTelemetry spans and metrics with a `talkscout.` or `search.` prefix. Do not put raw user query text in span attributes.
- Every container in `deploy/` needs CPU and memory requests and limits. No privileged, hostPath, hostNetwork or hostPID pods: the team cluster refuses them.
- Commit messages and PR descriptions must not contain AI co-author or "Generated with" lines.
