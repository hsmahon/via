#!/usr/bin/env bash
# End-to-end smoke test against a running local stack.
#
# Flow: health -> create upload session -> PUT bytes to MinIO via the
# presigned URL -> webhook drives the worker -> video reaches PROCESSED ->
# agent answers a question about it.
set -euo pipefail

API_URL="${VIA_API_URL:-http://localhost:8080}"
AGENT_URL="${VIA_AGENT_URL:-http://localhost:8081}"
USER_ID="smoke-user"

echo "== 1. API health =="
curl -fsS "${API_URL}/health" | grep -q '"ok"' && echo "api healthy"

echo "== 2. Create upload session =="
CREATE=$(curl -fsS -X POST "${API_URL}/videos" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: ${USER_ID}" \
  -d '{"filename":"smoke.mp4","duration":5.5,"content_type":"video/mp4"}')
VIDEO_ID=$(printf '%s' "$CREATE" | python3 -c 'import json,sys;print(json.load(sys.stdin)["video_id"])')
UPLOAD_URL=$(printf '%s' "$CREATE" | python3 -c 'import json,sys;print(json.load(sys.stdin)["upload"]["url"])')
echo "video: ${VIDEO_ID}"

echo "== 3. Upload bytes to MinIO (presigned PUT) =="
head -c 1024 /dev/urandom > /tmp/via-smoke.bin
curl -fsS -X PUT "${UPLOAD_URL}" --upload-file /tmp/via-smoke.bin -H "Content-Type: video/mp4"
echo "uploaded"

echo "== 4. Wait for worker to reach PROCESSED =="
STATUS="none"
for _ in $(seq 1 20); do
  STATUS=$(curl -fsS "${API_URL}/videos/${VIDEO_ID}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"])')
  [ "${STATUS}" = "PROCESSED" ] && break
  sleep 0.5
done
[ "${STATUS}" = "PROCESSED" ] || { echo "FAIL: status=${STATUS}"; exit 1; }
echo "processed"

echo "== 5. Ask the agent about the video =="
ANSWER=$(curl -fsS -X POST "${AGENT_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: ${USER_ID}" \
  -d "{\"message\":\"What is this video?\",\"video_id\":\"${VIDEO_ID}\"}")
printf '%s\n' "${ANSWER}" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["answer"],d;print("agent:", d["answer"][:90])'

echo "== 6. Delete the video =="
curl -fsS -X DELETE "${API_URL}/videos/${VIDEO_ID}" -H "X-User-Id: ${USER_ID}" > /dev/null
echo "SMOKE TEST PASSED"
