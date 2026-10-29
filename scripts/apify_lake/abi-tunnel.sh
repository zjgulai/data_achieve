#!/usr/bin/env bash
# 建立到腾讯云 ABI 数据库的 SSH 隧道。
#
# 为什么要隧道：目标库地址 172.22.0.3 是那台服务器上 Docker 容器的内网 IP，
# 只在服务器自身的网络命名空间里有效，公网直接连不通（实测端口不可达）。
# 唯一稳定的入口是经 43.163.92.244 的 SSH 转发。
#
# 用法：
#   ./abi-tunnel.sh start     # 建立隧道，本地 15432 → 172.22.0.3:5432
#   ./abi-tunnel.sh stop      # 关闭
#   ./abi-tunnel.sh status    # 查看状态
#   ./abi-tunnel.sh psql      # 建隧道并直接进 psql
#
# 连上之后，任何客户端都按这个 DSN 用：
#   postgresql://zhoujian:<密码>@127.0.0.1:15432/postgres
set -uo pipefail

PEM="${ABI_PEM:-/Users/lute/Project/data_scrapy/zhoujian_pachong.pem}"
HOST="43.163.92.244"
SSH_PORT="22222"
SSH_USER="ubuntu"
REMOTE="172.22.0.3:5432"
LOCAL_PORT="15432"
DB_USER="zhoujian"
DB_NAME="postgres"

tunnel_pids() {
  pgrep -f "${LOCAL_PORT}:${REMOTE}" 2>/dev/null || true
}

start_tunnel() {
  if [[ -n "$(tunnel_pids)" ]]; then
    echo "隧道已在运行（pid $(tunnel_pids | tr '\n' ' ')）"
    return 0
  fi
  if [[ ! -f "$PEM" ]]; then
    echo "[ERROR] 找不到密钥: $PEM" >&2
    return 1
  fi
  ssh -i "$PEM" -p "$SSH_PORT" \
      -o StrictHostKeyChecking=no \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 \
      -f -N -L "${LOCAL_PORT}:${REMOTE}" "${SSH_USER}@${HOST}"
  sleep 1
  if [[ -n "$(tunnel_pids)" ]]; then
    echo "隧道已建立：127.0.0.1:${LOCAL_PORT} → ${REMOTE}"
    echo "DSN: postgresql://${DB_USER}:<密码>@127.0.0.1:${LOCAL_PORT}/${DB_NAME}"
  else
    echo "[ERROR] 隧道建立失败" >&2
    return 1
  fi
}

stop_tunnel() {
  local pids
  pids="$(tunnel_pids)"
  if [[ -z "$pids" ]]; then
    echo "没有运行中的隧道"
    return 0
  fi
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null
  sleep 1
  echo "隧道已关闭"
}

status_tunnel() {
  if [[ -n "$(tunnel_pids)" ]]; then
    echo "运行中（pid $(tunnel_pids | tr '\n' ' ')）"
    echo "本地端口 ${LOCAL_PORT} → ${REMOTE}"
  else
    echo "未运行"
    return 1
  fi
}

open_psql() {
  start_tunnel || return 1
  echo "连接中…（密码见 ABI_DB_PASSWORD 或向管理员索取）"
  PGPASSWORD="${ABI_DB_PASSWORD:-}" psql \
    -h 127.0.0.1 -p "$LOCAL_PORT" -U "$DB_USER" -d "$DB_NAME"
}

case "${1:-status}" in
  start)  start_tunnel ;;
  stop)   stop_tunnel ;;
  status) status_tunnel ;;
  psql)   open_psql ;;
  *)      echo "用法: $0 {start|stop|status|psql}" >&2; exit 2 ;;
esac
