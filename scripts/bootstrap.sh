#!/usr/bin/env bash
# Bootstrap the local development stack: emulators, table, bucket, webhook.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Starting emulators and init jobs..."
docker compose up -d dynamodb-local minio worker dynamodb-init minio-init

echo "Waiting for services..."
for service in api agent worker; do
  port_map=(api:8080 agent:8081 worker:8082)
  case $service in
    api) port=8080 ;;
    agent) port=8081 ;;
    worker) port=8082 ;;
  esac
  until curl -fsS "http://localhost:${port}/health" > /dev/null 2>&1; do
    sleep 0.5
  done
  echo "  ${service} healthy on :${port}"
done

echo "Local stack ready:"
echo "  UI      http://localhost:3000"
echo "  API     http://localhost:8080/docs"
echo "  Agent   http://localhost:8081/docs"
echo "  Worker  http://localhost:8082/health"
echo "  MinIO   http://localhost:9001 (via-local / via-local-secret)"
