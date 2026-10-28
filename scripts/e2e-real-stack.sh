#!/usr/bin/env bash
#
# 一次性真实链路 E2E 栈。见 docs/architecture/decisions/ADR-008-real-chain-e2e-gate.md
#
# 子命令：
#   up [--build]   生成运行时凭据，起栈，等健康
#   wait           只等健康
#   status         打印各服务状态与公网探针结果
#   down           停栈并删卷（永远 -v）
#   logs [服务]    跟随日志
#
# 设计约束：
#   - 凭据在运行时生成到 .env.e2e（已 gitignore），仓库里不出现任何密钥。
#   - down 一律带 -v。留下的卷会让下一次运行带着上一轮的脏数据，
#     那会让「种子可重复」这个前提悄悄失效。
#   - 项目名独立（data-achieve-e2e），不会碰到生产栈的容器与卷。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/configs/deploy/scrapy/docker-compose.e2e.yml"
ENV_FILE="$ROOT_DIR/.env.e2e"
HTTP_PORT="${E2E_HTTP_PORT:-8090}"
BASE_URL="http://127.0.0.1:$HTTP_PORT"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

die() {
  echo "失败：$*" >&2
  exit 1
}

# 生成运行时凭据。已存在则复用，保证 up 之后 status/down 仍能连上同一套。
ensure_env() {
  if [[ -f "$ENV_FILE" ]]; then
    echo "  复用现有凭据：$ENV_FILE"
    return 0
  fi

  # 密码进 DATABASE_URL，会被 URL 解析。只用 URL 安全字符，避免 % 转义问题。
  local pw jwt
  pw="e2e$(openssl rand -hex 16)"
  jwt="$(openssl rand -hex 32)"

  cat > "$ENV_FILE" <<EOF
# 由 scripts/e2e-real-stack.sh 生成。一次性栈专用，勿用于任何其他环境。
E2E_POSTGRES_DB=e2e_chain
E2E_POSTGRES_USER=e2e_chain
E2E_POSTGRES_PASSWORD=$pw
E2E_JWT_SECRET=$jwt
E2E_HTTP_PORT=$HTTP_PORT
EOF
  chmod 600 "$ENV_FILE"
  echo "  已生成凭据：$ENV_FILE"
}

# 等 edge 就绪。edge 的 healthcheck 依赖 api 与 web 都 healthy，
# 所以这一条就覆盖了整条链的启动顺序。
wait_ready() {
  local deadline=$(( $(date +%s) + ${E2E_WAIT_SECONDS:-420} ))
  while :; do
    if curl -fsS --max-time 3 "$BASE_URL/api/health" >/dev/null 2>&1; then
      echo "  栈已就绪：$BASE_URL"
      return 0
    fi
    if (( $(date +%s) >= deadline )); then
      echo "等待超时。各服务状态：" >&2
      compose ps >&2 || true
      echo "api 日志尾部：" >&2
      compose logs --tail 40 api >&2 || true
      die "栈未在 ${E2E_WAIT_SECONDS:-420} 秒内就绪"
    fi
    sleep 3
  done
}

cmd_up() {
  ensure_env
  echo "== 起栈 =="
  # macOS 自带 bash 3.2：空数组配 set -u 时 "${arr[@]}" 会报 unbound variable。
  # 用条件展开绕过，不依赖 bash 4+。
  if [[ "${1:-}" == "--build" ]]; then
    compose up -d --build
  else
    compose up -d
  fi
  echo "== 等健康 =="
  wait_ready
  cmd_status
}

cmd_status() {
  echo
  echo "== 容器状态 =="
  compose ps --format '  {{.Name}}\t{{.Status}}'

  echo
  echo "== 探针（${BASE_URL}）=="
  local probe code
  for probe in /api/health /login /dashboard /api/projects; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL$probe" || echo 000)"
    printf '  %-16s %s\n' "$probe" "$code"
  done

  echo
  echo "== 模式自检 =="
  # 门禁的全部价值在于「无 mock」。这里顺带把两个最容易配错的点打出来。
  local health
  health="$(curl -fsS --max-time 5 "$BASE_URL/api/health" 2>/dev/null || true)"
  if [[ -n "$health" ]]; then
    printf '  health: %s\n' "$(printf '%s' "$health" | head -c 200)"
  fi
  # 未登录访问 API 必须是 401。若是 200，说明 demo 回退没关，
  # 门禁会测到一条生产不存在的路径。
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL/api/projects" || echo 000)"
  if [[ "$code" == "401" ]]; then
    echo "  demo 回退：已关闭（/api/projects 无 cookie 返回 401）"
  else
    echo "  警告：/api/projects 无 cookie 返回 $code，期望 401。APP_ENV 可能不是 production。" >&2
  fi
}

cmd_down() {
  if [[ ! -f "$ENV_FILE" ]]; then
    # 凭据丢了也要能收尾：用名字直接删容器与卷，不依赖 compose 解析。
    echo "  未找到 ${ENV_FILE}，按名字清理"
    docker ps -aq --filter "name=data_achieve_e2e_" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker volume rm -f data-achieve-e2e_e2e_postgres_data data-achieve-e2e_e2e_export_data >/dev/null 2>&1 || true
    docker network rm data_achieve_e2e_internal >/dev/null 2>&1 || true
    echo "  已清理"
    return 0
  fi

  echo "== 停栈并删卷 =="
  # -v 是硬要求，不提供「只停不删」的开关。
  compose down -v --remove-orphans || true

  echo "== 复核 =="
  local left
  left="$(docker ps -aq --filter "name=data_achieve_e2e_" | wc -l | tr -d ' ')"
  echo "  残留容器：$left"
  local vols
  vols="$(docker volume ls -q | grep -c '^data-achieve-e2e_' || true)"
  echo "  残留卷：$vols"
  [[ "$left" == "0" && "$vols" == "0" ]] || die "清理不完整，请手工核对"
}

cmd_logs() {
  ensure_env
  compose logs -f "${1:-}"
}

case "${1:-}" in
  up) shift; cmd_up "${1:-}" ;;
  wait) ensure_env; wait_ready ;;
  status) ensure_env; cmd_status ;;
  down) cmd_down ;;
  logs) shift; cmd_logs "${1:-}" ;;
  *)
    cat <<'EOF'
用法：scripts/e2e-real-stack.sh <up|wait|status|down|logs> [选项]

  up [--build]   起栈并等健康。--build 强制重建 api 与 web 镜像。
  wait           只等健康。
  status         打印容器状态、四个探针与模式自检。
  down           停栈并删卷（永远 -v）。
  logs [服务]    跟随日志。

环境变量：
  E2E_HTTP_PORT      宿主端口，默认 8090。
  E2E_WAIT_SECONDS   等待就绪的秒数，默认 420。
EOF
    exit 2
    ;;
esac
