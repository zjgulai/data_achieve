#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_DOCKER="${SCRAPY_TRAINING_USE_DOCKER:-0}"
ENV_FILE="${ENV_FILE:-../.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-configs/deploy/scrapy/docker-compose.yml}"
CURATION_PATH="${SCRAPY_TRAINING_CURATION_PATH:-tmp/outputs/training-content-curation-20260615.json}"
SNAPSHOT_PATH="${SCRAPY_TRAINING_SNAPSHOT_PATH:-tmp/outputs/training-content-snapshot-20260615.json}"

resolve_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s\n' "$ROOT_DIR/$1" ;;
  esac
}

CURATION_ABS="$(resolve_path "$CURATION_PATH")"
SNAPSHOT_ABS="$(resolve_path "$SNAPSHOT_PATH")"

usage() {
  cat <<'EOF'
Usage: scripts/seed-training-content.sh [--execute]

Seeds curated_training content into the demo workspace. Without --execute, the
command runs in dry-run mode and does not write to the database.

Set SCRAPY_TRAINING_USE_DOCKER=1 to run through production docker compose.
EOF
}

args=(
  "--curation-path"
  "$CURATION_ABS"
  "--snapshot-path"
  "$SNAPSHOT_ABS"
)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      args+=("--execute")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$USE_DOCKER" == "1" ]]; then
  cd "$ROOT_DIR"
  mount_dir="$(dirname "$CURATION_ABS")"
  if [[ "$(dirname "$SNAPSHOT_ABS")" != "$mount_dir" ]]; then
    echo "Docker mode requires curation and snapshot files to be in the same directory." >&2
    exit 2
  fi
  curation_file="$(basename "$CURATION_ABS")"
  snapshot_file="$(basename "$SNAPSHOT_ABS")"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm \
    -v "$mount_dir:/tmp/training-content:ro" \
    api \
    python -m data_intelligence_hub.seed.training_content \
      --curation-path "/tmp/training-content/$curation_file" \
      --snapshot-path "/tmp/training-content/$snapshot_file" \
      "${args[@]:4}"
else
  cd "$ROOT_DIR/apps/api"
  uv run python -m data_intelligence_hub.seed.training_content "${args[@]}"
fi
