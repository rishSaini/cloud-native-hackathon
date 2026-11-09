# TalkScout

> Organizers build a schedule without clashes and see live demand, so every talk finds its audience.

Built at the WeMakeDevs Cloud Native Hackathon, Salt Lake City, November 9, 2026.

## Tracks

One project enters every sponsor track whose tool it really uses.

| Track | Tool | Where it lives in this repo | What the judges look for |
|---|---|---|---|
| 1 · AI code review | Gitar | `.gitar/`, `.github/workflows/ci.yaml`, `AGENTS.md` | Features land through PRs that Gitar reviewed. Review instructions and repository rules. CI failure diagnosis and auto-apply. |
| 2 · Observability | Dash0 | `backend/start.sh`, `backend/app/main.py` (spans, metrics, `/rum.js`) | Traces, logs, metrics and RUM. Agent0 or the MCP server finds and fixes a real issue. Observability in the product. A dashboard or SLO. |
| 3 · Kubernetes UI | Radar | `deploy/`, `argocd/`, `.agents/skills/`, [RADAR.md](RADAR.md) | Runs on Kubernetes with Radar. Radar UI and MCP used all day. One AI investigation on a real issue. |
| 4 · Search | Elasticsearch | `deploy/elasticsearch.yaml`, `backend/app/es.py`, `scripts/ingest.py` | Elasticsearch is the core data layer. Smart keyword, semantic, vector or hybrid search. |
| Merge Forward | (none) | | Makes conferences more inclusive and accessible. |

## Architecture

```
browser ──> app (FastAPI, Service "app") ──> Elasticsearch (StatefulSet)
   │              │
   │              └── OpenTelemetry: traces, metrics, logs ──> Dash0
   └── Dash0 web SDK (RUM) ──────────────────────────────────> Dash0

PR ──> CI + Gitar review ──> merge to main ──> build-and-deploy Action (image to GHCR)
   ──> Argo CD in the team cluster ──> https://<team>.cnh.radarhq.io   (watched in Radar)
```

## One-time team setup

1. **Gitar (repo owner).** Sign in to Gitar first. Then go to Settings > Configuration > Connect GitHub, and pick this repo. Each PR then gets a Gitar comment. To let Gitar fix CI failures on a PR, comment `gitar auto-apply:on`.
2. **Radar cluster.** Get the team cluster at join.cnh.radarhq.io (join code at the Radar table). Then run `./scripts/setup.sh <team-name>`, commit, and merge. Make the GHCR image public after the first build. [RADAR.md](RADAR.md) has every step.
3. **Secrets in the cluster.** Create Secret `app-credentials` in namespace `team-<team-name>` (Radar Cloud > Resources > Secrets > +). Never commit these values. Keys:
   - `OTEL_EXPORTER_OTLP_ENDPOINT`: Dash0 > Settings > Endpoints > "OTLP over HTTP"
   - `OTEL_EXPORTER_OTLP_HEADERS`: `Authorization=Bearer%20<ingest token>`
   - `DASH0_RUM_ENDPOINT` and `DASH0_RUM_TOKEN`: a separate ingest-only token, because the browser can see it
   - `OPENAI_API_KEY`: for embeddings

   Restart the app after you create or change the Secret.
4. **Coding agents (each person).** Connect the Radar and Dash0 MCP servers:
   ```bash
   claude mcp add --scope user radar-cloud --transport http https://api.radarhq.io/mcp
   claude mcp add --scope user dash0 --transport http https://api.<region>.aws.dash0.com/mcp
   ```
   Then run `/mcp` in Claude Code and sign in to each. For Radar, pick **Cloud Native Hackathon** under "Organization access".

## Develop locally

You need Docker and Python 3.11+.

```bash
make setup    # venv, packages, git hooks, .env
make es-up    # Elasticsearch 9.5.0 at http://localhost:9200
make ingest   # load data/sample.jsonl
make run      # app at http://localhost:8000
make test
```

Run `make help` for all commands. `make run-image` runs the same container image that the cluster runs.

## Ship a change

1. Create a branch, commit, and open a PR.
2. CI runs the tests, renders `deploy/`, and builds the image. Gitar reviews the PR.
3. Merge. The `build-and-deploy` Action pushes the image to GHCR and commits the new tag.
4. Argo CD deploys it. The page footer shows `version <commit>`, so you can check which commit is live.

## AI use

Required by hackathon Rule 5. TODO: list the AI tools the team used and what you used them for.

## Team

TODO
