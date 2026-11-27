#!/bin/sh
set -e
cd "$(dirname "$0")"
docker compose build --no-cache cognitive-hub audio-engine virtual-stage
docker compose up -d --force-recreate audio-engine cognitive-hub virtual-stage

curl -fsS http://localhost:8090/health
echo
curl -fsS -o /dev/null -w "page %{http_code}\n" http://localhost:5174/
