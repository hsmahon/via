# Via - Video Intelligence Agent

Upload a video, wait for processing, then talk to an AI agent that
understands it.

| Piece              | Tech                                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------------- |
| API service        | FastAPI (`services/api`)                                                                              |
| Agent runtime      | Via-owned harness, zero framework deps (`packages/harness`) + thin FastAPI wrapper (`services/agent`) |
| Processing worker  | event-driven state machine (`services/workers/video-processing-worker`)                               |
| UI                 | Next.js + TypeScript (`apps/ui`)                                                                      |
| State              | DynamoDB single table (DynamoDB Local in dev)                                                         |
| Storage            | S3 (MinIO in dev), direct presigned uploads                                                           |
| Production targets | Amazon Bedrock / TwelveLabs Pegasus · Transcribe · AgentCore · Step Functions · EventBridge           |

## Quickstart

```bash
make bootstrap   # deps + .env
make dev         # build & start everything
open http://localhost:3000
```

Full walkthrough: [docs/local-development.md](docs/local-development.md).

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
