#!/bin/bash

check_docker_daemon() {
  if run_with_timeout 8 docker info >/dev/null 2>&1; then
    return 0
  fi

  cat >&2 <<'EOF'
Docker daemon is not available or did not respond within 8 seconds.

Start Docker Desktop or another Docker daemon, then rerun this command.
EOF
  return 1
}

run_with_timeout() {
  local timeout_seconds="$1"
  shift

  "$@" &
  local command_pid=$!

  (
    sleep "$timeout_seconds"
    kill "$command_pid" >/dev/null 2>&1 || true
  ) &
  local timer_pid=$!

  local command_status=0
  wait "$command_pid" || command_status=$?

  kill "$timer_pid" >/dev/null 2>&1 || true
  wait "$timer_pid" 2>/dev/null || true

  return "$command_status"
}

start_db() {
  local root_dir="$1"
  docker compose --project-directory "$root_dir" up -d db
}

wait_for_db() {
  local root_dir="$1"
  local max_attempts="${2:-30}"
  local postgres_user="${POSTGRES_USER:-data_intel}"
  local postgres_db="${POSTGRES_DB:-data_intel}"

  for attempt in $(seq 1 "$max_attempts"); do
    if docker compose --project-directory "$root_dir" exec -T db \
      pg_isready -U "$postgres_user" -d "$postgres_db" >/dev/null 2>&1; then
      echo "PostgreSQL is ready."
      return 0
    fi
    echo "Waiting for PostgreSQL... ($attempt/$max_attempts)"
    sleep 2
  done

  echo "PostgreSQL did not become ready in time." >&2
  return 1
}
