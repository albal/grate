#!/usr/bin/env bash
# Build the image and list free-tier Gemini models by requests-per-day.
# Usage: ./run.sh [project-id] [extra gemini_rpd.py options]
set -euo pipefail

cd "$(dirname "$0")"

PROJECT="${1:-${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}}"
[ $# -gt 0 ] && shift
if [ -z "$PROJECT" ]; then
  echo "No project ID. Pass one as the first argument or set GOOGLE_CLOUD_PROJECT." >&2
  exit 1
fi

CREDS="$HOME/.config/gcloud/application_default_credentials.json"
if [ ! -f "$CREDS" ]; then
  echo "No credentials at $CREDS. Run: gcloud auth application-default login" >&2
  exit 1
fi

docker build -q -t gemini-rpd . >/dev/null

docker run --rm --user "$(id -u)" \
  -v "$CREDS:/creds.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds.json \
  ${GEMINI_API_KEY:+-e GEMINI_API_KEY} \
  gemini-rpd --project "$PROJECT" --tier free "$@"
