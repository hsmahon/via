# Slice #1 — POST /videos API Contract

Scope: minimal production-quality admission of a video for a user. No bytes
flow through the API, no S3/event/worker work, no transcription.

## Endpoint

`POST /videos` → `202 Accepted` on success.

Auth: existing `X-User-Id` header. When both header and `VIA_DEFAULT_USER_ID`
are absent/empty → `401 Unauthorized`. `GET /videos/{id}` and `DELETE` retain
their prior auth semantics; only `POST` needed the new 401 path.

## Request

```json
{
  "filename": "holiday.mp4",
  "video_name": "holiday.mp4",
  "duration": 183.5,
  "content_type": "video/mp4",
  "file_size": 104857600
}
```

- `filename` preferred; `video_name` accepted as legacy alias. One of them
  required (400 if neither).
- `filename` 1-255 chars, no path separators (400).
- `duration` > 0 when present (422 from Pydantic otherwise).
- `content_type` 1-100 chars free-form, rejected with 415 when not in
  `VIA_ALLOWED_VIDEO_CONTENT_TYPES` allow-list.
- `file_size` >= 0 when present.

Quotas / policy live in `via_api.settings.Settings`:
`VIA_MAX_VIDEOS_PER_USER` (default 20), `VIA_ALLOWED_VIDEO_CONTENT_TYPES`
(default common video/* list).

## Response

Success (`202`):

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

Minimal contract is `{video_id, status}`; `upload` is attached when the
deployment is configured to presign (kept for the existing browser→S3 flow).
Clients must tolerate its absence.

## Status codes

| Code | Condition                                                         |
| ---- | ----------------------------------------------------------------- |
| 202  | Created with conditional write                                    |
| 400  | Malformed / invalid request (e.g. missing name, path traversal)   |
| 401  | Not authenticated                                                 |
| 403  | Reserved (route-level auth; not used by creation beyond identity) |
| 409  | Quota exceeded or id collision (retry)                            |
| 415  | Unsupported media type                                            |
| 422  | Pydantic validation (fallback)                                    |
| 500  | Unexpected DynamoDB/presign failure                               |

## DynamoDB

Table `via`, key `pk=VIDEO#<id>` / `sk=META`, plus `gsi1` for listing.
Write uses `ConditionExpression=attribute_not_exists(pk)` (surfaced as 409).
Item:

```
pk              VIDEO#<video_id>
sk              META
gsi1pk          USER#<user_id>
gsi1sk          <created_at>#<video_id>
status          UPLOADING
s3_key          videos/<user_id>/<video_id>/<filename>   (placeholder)
s3_bucket       via-videos
file_size?      int
content_type?   string
video_name      <filename>   (compat mirror)
upload_date     <created_at> (compat mirror)
created_at/updated_at ISO-8601 UTC
```

Only fields above are written; no speculative attributes.

## Lifecycle

```
UPLOADING → PROCESSING → PROCESSED → DELETED
     │           │
     ├──▶ FAILED─┘  (FAILED → DELETED)
     └─────────────▶ DELETED
```

Slice #1 only writes `UPLOADING`. Transitions are enforced by
`backend/db/src/via_db/entities.py::ALLOWED_TRANSITIONS`.

## Explicitly deferred

S3 byte upload, presign as hard dependency, EventBridge/webhook, Step
Functions, Transcribe, Pegasus/TwelveLabs, transcription artifacts, search
indexing, multi-agent flows, UI changes.

## Separation of concerns

- `backend/api/src/via_api/routes/videos.py` — HTTP (202, error mapping, presign orchestration).
- `backend/api/src/via_api/schemas.py` — request/response shape + alias.
- `backend/api/src/via_api/services/videos.py` — business rules (MIME + quota + write ordering).
- `backend/db/src/via_db/videos.py` — repository (conditional put, `count_by_user`).
- `backend/api/src/via_api/settings.py` — config (`max_videos_per_user`, allow-list).
- `backend/api/src/via_api/deps.py` — auth seam (401 when identity absent).

No LangChain/EventBridge/worker code introduced.
