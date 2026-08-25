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

### `POST /videos` — accept a video for upload (Vertical Slice #1)

**Purpose:** admit a video for the authenticated user and return its opaque
server-assigned identifier. The client needs the `video_id` to correlate future
requests. Bytes are **not** proxied through the API.

Request (minimal production-quality shape):

```json
{
  "filename": "holiday.mp4",
  "video_name": "holiday.mp4",
  "duration": 183.5,
  "content_type": "video/mp4",
  "file_size": 104857600
}
```

| Field          | Type    | Rules                                                                                  |
| -------------- | ------- | -------------------------------------------------------------------------------------- |
| `filename`     | string? | preferred; 1-255 chars, no path separators                                             |
| `video_name`   | string? | alias accepted for backwards compatibility; either `filename` or `video_name` required |
| `duration`     | float?  | > 0 when present                                                                       |
| `content_type` | string? | MIME hint; rejected with 415 when not in the configured allow-list                     |
| `file_size`    | int?    | >= 0 when present                                                                      |

Response `202 Accepted`:

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

The `upload` presigned PUT target is attached when the deployment is configured
to issue one; the minimal contract is `{video_id, status}` and clients must
tolerate its absence in future configurations. When present, bytes go
`PUT <upload.url>` directly to storage — the object-created event that drives
`UPLOADING → PROCESSING → PROCESSED | FAILED` is **not** implemented in this slice.

Status codes:

| Code | Meaning                                                                          |
| ---- | -------------------------------------------------------------------------------- |
| 202  | Accepted — record written with `attribute_not_exists(pk)` guard                  |
| 400  | Malformed/invalid request (e.g. path traversal in filename)                      |
| 401  | Not authenticated (no `X-User-Id` and no `VIA_DEFAULT_USER_ID`)                  |
| 403  | Forbidden (reserved; not used by this slice beyond route-level auth)             |
| 409  | Conflict — id collision (retry) or quota `max_videos_per_user` exceeded          |
| 415  | Unsupported media type (`content_type` not in `VIA_ALLOWED_VIDEO_CONTENT_TYPES`) |
| 422  | Validation error from Pydantic (if schema cannot be satisfied)                   |
| 500  | Unexpected server/presign failure                                                |

DynamoDB record (single table `via`, `pk=VIDEO#<id> sk=META` + `gsi1`):

```
pk              VIDEO#<video_id>
sk              META
gsi1pk          USER#<user_id>
gsi1sk          <created_at>#<video_id>
status          UPLOADING
s3_key          videos/<user_id>/<video_id>/<filename>   (placeholder until S3 exists)
s3_bucket       via-videos
file_size?      int
content_type?   string
created_at      ISO-8601 UTC (also mirrored as upload_date / video_name for compat)
```

Requested fields and quota are in `via_api.settings.Settings`
(`VIA_MAX_VIDEOS_PER_USER`, `VIA_ALLOWED_VIDEO_CONTENT_TYPES`).

Lifecycle in this slice:

```
UPLOADING ──▶ PROCESSING ──▶ PROCESSED ──▶ DELETED
     │             │
     │             ▼
     ├──▶ FAILED ◀─┘          (FAILED → DELETED allowed)
     └────────────────────────▶ DELETED
```

Only `UPLOADING` is written by this slice. Future slices add the worker that
moves `UPLOADING → PROCESSING → PROCESSED | FAILED`.

Explicitly deferred (not in Slice #1): S3 byte handling, EventBridge/webhook
routing, Step Functions, Transcribe, Pegasus/TwelveLabs, transcription or
derived artifacts, and multi-agent orchestration.

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

Soft-delete (sets status `DELETED`).

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
