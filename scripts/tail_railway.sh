#!/usr/bin/env bash
set -euo pipefail

# Stream railway logs from multiple services into one stdout, prefixed and color-tagged.
# Usage:
#   ./scripts/tail_railway.sh                  # default: web worker beat (runtime logs)
#   ./scripts/tail_railway.sh web worker       # specific services
#   ./scripts/tail_railway.sh --build web      # build logs instead of runtime
#   ./scripts/tail_railway.sh -e staging web   # specific environment

BUILD=""
ENV_FLAG=()
SERVICES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --build|-b) BUILD="--build"; shift ;;
    --environment|-e) ENV_FLAG=(--environment "$2"); shift 2 ;;
    -h|--help)
      sed -n '3,9p' "$0"
      exit 0 ;;
    *) SERVICES+=("$1"); shift ;;
  esac
done

if [ ${#SERVICES[@]} -eq 0 ]; then
  SERVICES=(web worker beat)
fi

trap 'kill 0' INT TERM

i=0
for svc in "${SERVICES[@]}"; do
  color=$((31 + i % 6))
  i=$((i + 1))
  prefix=$(printf '\033[1;%sm[%s]\033[0m' "$color" "$svc")
  # shellcheck disable=SC2086
  railway logs --service "$svc" ${ENV_FLAG[@]+"${ENV_FLAG[@]}"} $BUILD 2>&1 \
    | sed -u "s|^|$prefix |" &
done

wait
