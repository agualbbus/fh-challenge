#!/usr/bin/env bash
# Run SonarScanner CLI in Docker against the local SonarQube instance.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

if [[ -z "${SONAR_TOKEN:-}" ]]; then
  echo "SONAR_TOKEN is not set. Add it to .env (see .env.example)." >&2
  exit 1
fi

if [[ -n "${SONAR_SCANNER_HOST_URL:-}" ]]; then
  SCANNER_HOST_URL="$SONAR_SCANNER_HOST_URL"
elif [[ -n "${SONAR_HOST_URL:-}" ]] && [[ ! "$SONAR_HOST_URL" =~ localhost|127\.0\.0\.1 ]]; then
  SCANNER_HOST_URL="$SONAR_HOST_URL"
else
  SCANNER_HOST_URL="http://host.docker.internal:9000"
fi
export SONAR_HOST_URL="$SCANNER_HOST_URL"

echo "Scanning $ROOT -> $SCANNER_HOST_URL"

# Git Bash (MSYS) rewrites -w /usr/src to C:/Program Files/Git/usr/src unless disabled.
DOCKER=(docker)
if [[ -n "${MSYSTEM:-}" ]]; then
  DOCKER=(env MSYS_NO_PATHCONV=1 docker)
fi

"${DOCKER[@]}" run --rm \
  -e SONAR_HOST_URL="$SCANNER_HOST_URL" \
  -e SONAR_TOKEN="$SONAR_TOKEN" \
  -v "$ROOT:/usr/src" \
  -w /usr/src \
  sonarsource/sonar-scanner-cli
