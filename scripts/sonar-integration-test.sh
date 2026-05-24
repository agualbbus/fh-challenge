#!/usr/bin/env bash
# End-to-end check: SonarQube up, healthy, and scanner upload succeeds.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

wait_sonar_healthy() {
  local timeout="${1:-180}"
  local elapsed=0
  echo "Waiting for SonarQube at http://localhost:9000 ..."
  while (( elapsed < timeout )); do
    if status="$(curl -sf "http://localhost:9000/api/system/status" 2>/dev/null)"; then
      if echo "$status" | grep -q '"status":"UP"'; then
        echo "SonarQube is UP."
        return 0
      fi
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "SonarQube did not become healthy within ${timeout}s." >&2
  return 1
}

echo "==> Starting SonarQube (persistent data: docker/sonarqube/)"
docker compose -f docker-compose.sonar.yml up -d

wait_sonar_healthy 180

echo "==> Running scanner"
./scripts/sonar-scan.sh

echo "==> Integration test passed."
echo "Dashboard: http://localhost:9000/dashboard?id=fh"
