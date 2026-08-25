# Via — Agent Notes

Upload a video → wait for processing → chat with an AI that understands it.

## Repo map

```
packages/db/              DynamoDB single-table (entities, transitions, bootstrap via via_db.bootstrap)
packages/harness/         Agent runtime: AgentRunner, ports (ModelClient/PromptResolver/ToolRegistry/Authorizer/Tracer)
packages/tools/           Domain tools (get_video_metadata etc.) — register in build_default_registry
packages/prompts/         YAML prompts at prompts/<name>/v<N>.yaml (`video_assistant`/`transcript_summary`), via `via_prompts.FilePromptResolver`
packages/observability/   Structured logging (`via_observability`, structlog) — harness `Tracer` impl is `LocalTracer` in `packages/harness`
services/api/             FastAPI — presigned upload, video CRUD (pk via_api.main)
services/agent/           FastAPI wrapper over harness (via_agent.main, wiring in wiring.py)
services/workers/video-processing-worker/  Event-driven state machine (via_worker_video_processing.main)
apps/ui/                  Next.js + TypeScript (only npm workspace)
infrastructure/           Step Functions ASL + Terraform (environments/dev)
tests/                    Docstring meta-tests (marker `docstring`)
```

- **uv workspace** members: `packages/*`, `services/api`, `services/agent`, `services/workers/*`. Python `>=3.12,<3.13`.
- **npm workspaces**: `apps/*` (only `apps/ui` today). Node `>=22`.

## Setup & run

```bash
make bootstrap   # uv sync --all-packages + cp -n .env.example .env + npm ci
make dev         # docker compose up --build --wait  → http://localhost:3000
make down        # stop stack
make logs        # tail compose logs
```

All env vars use `VIA_` prefix — see `.env.example`. Key quirk:

- **Two S3 endpoints**: `VIA_S3_ENDPOINT_URL` (server-side SDK inside containers, e.g. `http://minio:9000`) vs `VIA_S3_PUBLIC_ENDPOINT_URL` (embedded in presigned URLs, must be reachable from host/browser, e.g. `http://localhost:9000`). In prod both unset. `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` must look like AWS creds for signing.

Local endpoints: UI 3000, API 8080 (`/docs`), agent 8081, worker 8082 (`/health`), MinIO 9000/9001, DynamoDB Local 8005→8000.

- Stuck in `UPLOADING`: worker unhealthy or webhook misconfigured — `docker compose ps` then `docker compose up minio-init`.
- `VIA_PROCESSING_HOOKS_ENABLED=false` by default — when `true`, Transcribe/Pegasus hooks raise `NotImplementedError` → video → `FAILED` (intentional seam until v0.2).
- Emulators are in-memory; `docker compose down && docker compose up --build` resets everything.

## Verify — use Make, don't guess flags

```bash
make lint        # ruff check + ruff format --check + eslint + prettier --check
make typecheck   # mypy on explicit prod paths + tsc -p apps/ui --noEmit
make docstrings  # interrogate 100% + pytest -m docstring + eslint JSDoc rules
make test        # pytest (root) + vitest (apps/ui)
make check       # lint + typecheck + docstrings + test  (no docker)
make build       # docker compose build
make smoke       # e2e against running stack: health → presigned upload → webhook → PROCESSED → agent invoke
```

Single-package / single-test:

```bash
uv run pytest packages/harness/tests/test_runner.py -k test_name -q
uv run pytest packages/db/tests -q
uv run mypy packages/harness/src --pretty
npm run typecheck   # tsc -p apps/ui --noEmit only
npx vitest run --root apps/ui -t "pattern" --reporter=verbose
npx eslint apps/ui --no-warn-ignored --max-warnings=0
```

CI order (`ci.yml`): `python-quality` (ruff → format → interrogate → mypy → pytest) + `js-quality` (eslint → prettier → tsc → vitest) → `docker-build` (compose build + ASL JSON validity) → `terraform-check`. Security workflow adds TruffleHog + `pip-audit` + `npm audit`.

## Architecture — non-obvious

- **Single DynamoDB table** (`pk`/`sk`, `gsi1: USER#<user_id>` → `<created_at>#<video_id>`). Entities: `VIDEO#<id>/META`, `VIDEO#<id>/AUDIT#<ts>`, `ANALYTICS#<scope>/COUNTER#<name>`. Transitions enforced in `packages/db` — invalid → `InvalidTransition`.
- **Status lifecycle**: `UPLOADING → PROCESSING → PROCESSED → DELETED`; `UPLOADING/PROCESSING → FAILED → DELETED` (see `docs/architecture.md`).
- **Upload is direct browser→S3** via presigned PUT; API never proxies bytes.
- **Object-created event** normalized to one envelope: locally MinIO webhook `POST /events/minio` on `worker:8082` (prod: S3 → EventBridge → Step Functions). `dynamodb-local` started with `-sharedDb -inMemory`; `dynamodb-init` runs `via_db.bootstrap`, `minio-init` creates bucket + webhook.
- **Harness is Via-owned, not a framework**: `AgentRunner.execute()` + ports `ModelClient/PromptResolver/ToolRegistry/Authorizer/Tracer`. Local impls: `LocalModelClient`, `FilePromptResolver`, `InProcessToolRegistry`, `LocalTracer`; prod swaps in `wiring.py` only. Domain logic lives under `packages/*`; services are thin FastAPI wrappers.
- **Tool contract** (`packages/tools/…/base.py::ToolContract`) mandates permission + DynamoDB ownership check; denial aborts run with `AUTHORIZATION_ERROR` (never leaked to model). New tool: class with `ToolContract` in `packages/tools/src/via_tools/implementations/` + register in `build_default_registry`.
- **Prompts are immutable `(name, version, environment)` YAML triples** under `packages/prompts/src/via_prompts/prompts/<name>/v<N>.yaml`; missing/unexpected variables → `INVALID_REQUEST`.
- **Step Functions ASL** at `infrastructure/stepfunctions/video_processing.asl.json` (CI validates it's valid JSON).

## Conventions & gotchas

- **No agent frameworks** — `langchain`/`langgraph`/`llamaindex`/`crewai` anywhere (manifests or code) fails CI `dependency-policy` job. See `docs/agent-harness.md`.
- **Docstrings are a hard gate** (not optional): ruff `D` rules (google convention), `interrogate fail-under=100` (`ignore-init-method=true`), pytest `tests/test_docstrings.py` + `test_docstring_validity.py` (`-m docstring`), and `eslint-plugin-jsdoc` (`require-jsdoc`/`require-description` error). Fix them, don't suppress.
- **Ruff**: `target-version py312`, `line-length 100`, `src = ["packages","services","tests"]`. `B008` ignored only in `services/agent/src/via_agent/main.py` and `services/workers/video-processing-worker/src/via_worker_video_processing/main.py` (FastAPI DI).
- **mypy `strict=true` + `pydantic.mypy`**, `warn_unreachable=true`. Test modules (`packages.*.tests`, `services.*.tests`) relax `disallow_untyped_defs` etc. (see `pyproject.toml`). Production typecheck is `uv run mypy packages/*/src services/api/src services/agent/src services/workers/video-processing-worker/src tests`.
- **pytest** from repo root (`testpaths = ["packages","services","services/workers","tests"]`, `import-mode=importlib`, `filterwarnings=error`, `asyncio_mode=auto`). Moto emulates DynamoDB/S3; no AWS creds needed (`AWS_*=test` locally). Fresh `uv` sync needs `uv sync --all-packages`.
- **Prettier** `printWidth 88`, `uv.lock` + `package-lock.json` ignored (`.prettierignore`); use `make format` (ruff fix+format + prettier).
- **`X-User-Id` header** is the v0.1 auth seam (prod will be IAM/Cognito/OIDC). Smoke and API tests use it explicitly.

## References

- `README.md`, `docs/architecture.md`, `docs/local-development.md`, `docs/agent-harness.md`, `docs/api.md`
- `Makefile`, `docker-compose.yml`, `pyproject.toml`, `package.json`, `eslint.config.mjs`, `tsconfig.base.json`
- `.env.example`, `scripts/smoke.sh`, `.github/workflows/ci.yml` + `security.yml`
