#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT/server/app/static"
if [ ! -d "$TARGET" ]; then
  echo "no built bundle at $TARGET; run scripts/build_frontend.sh first."
  exit 1
fi
if grep -rEi "client_secret|session_secret|encryption_key|GOCSPX-" "$TARGET" >/dev/null; then
  echo "FAIL: secret-like string found in built bundle"
  grep -rEni "client_secret|session_secret|encryption_key|GOCSPX-" "$TARGET" || true
  exit 1
fi
echo "OK: no secret strings in $TARGET"
