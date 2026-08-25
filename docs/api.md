# Via API Reference

Base URL (local): `http://localhost:8080` · Interactive docs: `/docs`

## Conventions

- All request/response bodies are JSON.
- Identity: v0.1 accepts an `X-User-Id` header (default `dev-user`). The
  production authentication layer replaces this without route changes.
- Every response carries an `X-Request-ID` header used for tracing.

## System

### `GET /health`

```json
{ "service": "via-api", "status": "ok", "version": "0.1.0" }
```

## Videos

### `POST /videos` — create upload session

Request:

```json
{
  "filename": "holiday.mp4",
  "duration": 183.5,
  "content_type": "video/mp4"
}
```

| Field          | Type    | Rules                                     |
| -------------- | ------- | ----------------------------------------- |
| `filename`     | string  | required, 1-255 chars, no path separators |
| `duration`     | float?  | > 0 when present                          |
| `content_type` | string? | MIME hint stored for the upload           |

Response `201 Created`:

```json
{
  "video_id": "9f2c1a7e...",
  "user_id": "dev-user",
  "status": "UPLOADING",
  "upload": {
    "url": "http://localhost:9000/via-videos/videos/dev-user/<id>/holiday.mp4?<sig>",
    "method": "PUT",
    "expires_in_seconds": 900
  }
}
```

Upload the raw bytes with `PUT <upload.url>`; the object-created event then
drives processing automatically.

Errors: `409` id collision, `422` validation.

### `GET /videos?limit=20`

List the acting user's videos newest-first. Query params: `limit` (1-100).

```json
{
  "items": [
    {
      "video_id": "...",
      "user_id": "dev-user",
      "filename": "holiday.mp4",
      "duration": 183.5,
      "status": "PROCESSED",
      "created_at": "2026-08-24T12:00:00Z",
      "updated_at": "2026-08-24T12:03:11Z"
    }
  ],
  "count": 1
}
```

Statuses: `UPLOADING`, `PROCESSING`, `PROCESSED`, `FAILED`, `DELETED`.

### `GET /videos/{video_id}`

Fetch one video. Errors: `404`.

### `DELETE /videos/{video_id}`

Soft-delete (sets status `DELETED`, writes a `video.deleted` audit event).
Metadata is retained for auditability.

Errors: `403` not owner, `404` unknown, `409` already deleted/invalid state.

## Agent

Base URL (local): `http://localhost:8081` · Docs: `/docs`

### `POST /agent/invoke`

```json
{ "message": "What happens in this video?", "video_id": "<id>" }
```

Optional: `session_id`, `prompt_name` (default `video_assistant`).

Success `200`:

```json
{
  "run_id": "run_...",
  "trace_id": "8f14...c2",
  "session_id": "sess_...",
  "answer": "This is demo.mp4, about 15 seconds long.",
  "citations": [
    {
      "video_id": "<id>",
      "timestamp_start": 0.0,
      "timestamp_end": 15.0,
      "transcript_reference": null
    }
  ],
  "steps": [
    {
      "step": 1,
      "kind": "model",
      "name": "via-local-model",
      "status": "tool_use",
      "latency_ms": 1.2
    },
    {
      "step": 1,
      "kind": "tool",
      "name": "get_video_metadata",
      "status": "ok",
      "latency_ms": 3.4
    }
  ],
  "usage": { "input_tokens": 30, "output_tokens": 35 }
}
```

Citations carry timestamps the UI will use to jump into the video;
`transcript_reference` appears once transcripts exist.

Error envelope (status mapped by category):

```json
{
  "detail": "Tool invocation denied: user does not have access to this video",
  "category": "AUTHORIZATION_ERROR",
  "run_id": "run_..."
}
```

| Category                                              | HTTP |
| ----------------------------------------------------- | ---- |
| `AUTHORIZATION_ERROR`                                 | 403  |
| `INVALID_REQUEST`, `INVALID_TOOL_ARGUMENTS`           | 400  |
| `MODEL_ERROR`, `TOOL_ERROR`, `INVALID_MODEL_RESPONSE` | 502  |
| `TIMEOUT`                                             | 504  |
| `INTERNAL_ERROR`                                      | 500  |

### `GET /agent/runs/{run_id}/trace`

Debug endpoint returning recorded spans of one run (local tracer only):
name, ids, parent linkage, status, duration and attributes per span.

## Worker

Base URL (local): `http://localhost:8082`

- `GET /health` - liveness.
- `POST /events` - EventBridge-shaped lifecycle events (production contract).
- `POST /events/minio` - MinIO bucket notifications (local wiring).

Both return a handler outcome:

```json
{ "status": "processed", "video_id": "...", "detail": null }
```

`"ignored"` outcomes acknowledge events that reference unknown videos or
non-video keys without failing delivery.
