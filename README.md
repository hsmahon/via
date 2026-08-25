# Via - Video Intelligence Agent

Upload a video, wait for processing, then talk to an AI agent that
understands it.

| Piece              | Tech                                                                                                              |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- |
| API service        | FastAPI (`backend/api`)                                                                                           |
| Agent runtime      | Via-owned harness, zero framework deps (`backend/agent/harness`) + thin FastAPI wrapper (`backend/agent/service`) |
| Processing worker  | event-driven state machine (`backend/workers/video-processing-worker`)                                            |
| UI                 | Next.js + TypeScript (`frontend/ui`)                                                                              |
| State              | DynamoDB single table (DynamoDB Local in dev)                                                                     |
| Storage            | S3 (MinIO in dev), direct presigned uploads                                                                       |
| Production targets | Amazon Bedrock / TwelveLabs Pegasus · Transcribe · AgentCore · Step Functions · EventBridge                       |

## Quickstart

```bash
make bootstrap   # deps + .env
make dev         # build & start everything
open http://localhost:3000
```

Full walkthrough: [docs/local-development.md](docs/local-development.md).

## Repository Structure

```
frontend/
  ui/                     User-facing Next.js UI
backend/
  api/                    HTTP API (FastAPI — presigned uploads, video CRUD)
  agent/
    harness/              Via-owned agent harness (AgentRunner + ports)
    observability/        Structured logging / tracing (structlog + OTel)
    prompts/              Versioned YAML prompts (FilePromptResolver)
    tools/                Domain tools (get_video_metadata, etc.)
    service/              Thin FastAPI wrapper over harness (wiring.py)
  workers/
    video-processing-worker/  Async event-driven state machine (S3 → DDB)
  db/                     Persistence (DynamoDB single-table, entities, repo)
  shared/                 Genuinely shared backend code (empty by default)
  Dockerfile.python       Shared Python service image (uv workspace aware)
infrastructure/
  Docker/Terraform/AWS (Step Functions ASL, Terraform envs)
docs/
  Engineering docs and project plans
legacy/
  Preserved legacy material (do not modify)
```

> **Rule:** Folder structure reflects ownership and runtime responsibility. Do not create generic packages merely to avoid placing code in its owning subsystem.

## Documentation

- [Architecture](docs/architecture.md) - system design and decisions
- [Agent Harness](docs/agent-harness.md) - why no LangChain; what we own vs AWS
- [Local development](docs/local-development.md)
- [API reference](docs/api.md)

## Development gates

```bash
make check   # lint + typecheck + docstrings + tests
make build   # docker compose build
make smoke   # end-to-end against a running stack
```

CI enforces all of the above plus secret scanning (TruffleHog) and dependency
auditing.
