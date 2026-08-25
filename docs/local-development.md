# Local Development

## Prerequisites

- Docker + Docker Compose
- Python 3.12 (uv manages it automatically)
- Node.js >= 22 (npm workspaces)
- [uv](https://docs.astral.sh/uv/) installed

## Quickstart

```bash
make bootstrap     # install deps (uv sync --all-packages, npm ci), create .env
make dev           # build & start the whole stack, wait for health
```

Open:

| Service            | URL                                                      |
| ------------------ | -------------------------------------------------------- |
| UI                 | http://localhost:3000                                    |
| API docs (Swagger) | http://localhost:8080/docs                               |
| Agent docs         | http://localhost:8081/docs                               |
| Worker health      | http://localhost:8082/health                             |
| MinIO console      | http://localhost:9001 (`via-local` / `via-local-secret`) |

## End-to-end verification

```bash
make smoke         # upload → process → agent answer → delete, via real HTTP
```

The smoke script exercises the full loop against the running stack:
presigned upload to MinIO → webhook → worker state machine → local-model
agent invocation with the metadata tool.

## Everyday commands

```bash
make lint          # ruff check + format check, eslint, prettier check
make format        # auto-fix formatting
make typecheck     # mypy + tsc
make test          # pytest + vitest
make docstrings    # interrogate + docstring meta-tests + eslint JSDoc rules
make check         # all of the above except docker build
make logs          # tail compose logs
make down          # stop the stack
```

## How the local loop mirrors production

| Concern        | Local                                   | Production                                   |
| -------------- | --------------------------------------- | -------------------------------------------- |
| Object storage | MinIO (S3-compatible)                   | Amazon S3                                    |
| Table          | DynamoDB Local                          | DynamoDB                                     |
| Upload event   | MinIO webhook → `POST /events/minio`    | S3 → EventBridge → Step Functions → handlers |
| Model          | `LocalModelClient` (deterministic stub) | Bedrock Converse / TwelveLabs Pegasus        |
| Prompts        | YAML files via `FilePromptResolver`     | Bedrock Prompt Management                    |
| Traces         | in-memory `LocalTracer` + logs          | AgentCore Observability / CloudWatch         |

Only endpoints and implementation bindings change - handler logic, state
transitions, tool contracts and response validation are byte-identical.

### The two S3 endpoints

`VIA_S3_ENDPOINT_URL` is used by server-side SDK calls inside containers.
`VIA_S3_PUBLIC_ENDPOINT_URL` is embedded into presigned URLs and must be
reachable from your browser/curl on the host (`http://localhost:9000`
locally). In production both are unset (real S3).

## Environment variables

All use the `VIA_` prefix; see `.env.example`. Key ones:

| Variable                       | Default      | Purpose                                 |
| ------------------------------ | ------------ | --------------------------------------- |
| `VIA_TABLE_NAME`               | `via`        | single-table name                       |
| `VIA_BUCKET`                   | `via-videos` | media bucket                            |
| `VIA_DYNAMODB_ENDPOINT_URL`    | -            | DynamoDB Local endpoint (server-side)   |
| `VIA_S3_ENDPOINT_URL`          | -            | MinIO endpoint (server-side SDK calls)  |
| `VIA_S3_PUBLIC_ENDPOINT_URL`   | -            | endpoint embedded in presigned URLs     |
| `VIA_MODEL_BACKEND`            | `local`      | `local` or `bedrock`                    |
| `VIA_PEGASUS_MODEL_ID`         | -            | required when backend is `bedrock`      |
| `VIA_PROCESSING_HOOKS_ENABLED` | `false`      | invoke pending Transcribe/Pegasus hooks |

## Troubleshooting

- **Port conflicts** - DynamoDB Local uses host port 8005 (container 8000); services use 8080-8082. Set
  `VIA_*_PORT` variables to remap.
- **Uploads stuck in UPLOADING** - the MinIO webhook targets
  `http://worker:8082/events/minio`; ensure the worker container is healthy
  (`docker compose ps`) then re-run the minio-init job:
  `docker compose up minio-init`.
- **Reset everything** - `docker compose down && docker compose up --build`.
  Emulators are in-memory/volume-less by design; recreating them re-runs init
  jobs automatically.

## Testing without AWS

All unit/integration tests run offline: moto emulates DynamoDB/S3,
`LocalModelClient` replaces Bedrock, and prompt resolution uses the packaged
YAML files. See the ten harness test areas in
`backend/agent/harness/tests/` covering prompt resolution through structured
response validation.
