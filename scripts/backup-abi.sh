#!/usr/bin/env bash
# ABI 每日加密备份骨架。
#
# 用法：
#   ./scripts/backup-abi.sh            安装/更新 cron（默认，重复执行安全）
#   ./scripts/backup-abi.sh --run      立即执行一次加密备份
#   ./scripts/backup-abi.sh --help     显示帮助
#
# 依赖：docker、openssl；安装模式额外依赖 crontab。
#
# 密钥：ABI_BACKUP_PASSPHRASE 只从环境读取，不写进本文件，也不写进 crontab
# 明文。生产建议放在 root 可读的 600 文件里，cron 行会先 source 它：
#   export ABI_BACKUP_PASSPHRASE='...'
#
# 恢复示例（先校验 .sha256，再解密）：
#   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
#     -in abi-20261028T031500Z.dump.enc \
#     -pass env:ABI_BACKUP_PASSPHRASE \
#     | pg_restore -d "$PGDATABASE"
#
# TODO(ABI): 当前只备份到本机目录。上线前必须补远端副本（rsync/rclone），
# 否则数据库主机磁盘故障时，备份会与源数据一起丢失。
set -euo pipefail
umask 077

MARKER="# ABI daily encrypted backup"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="${PROJECT_DIR}/scripts/backup-abi.sh"
LOG_FILE="${ABI_BACKUP_LOG:-/opt/data-achieve-scrapy/abi-backup.log}"
BACKUP_DIR="${ABI_BACKUP_DIR:-/opt/data-achieve-scrapy/abi-backups}"
RETENTION_DAYS="${ABI_BACKUP_RETENTION_DAYS:-14}"
DB_CONTAINER="${ABI_DB_CONTAINER:-data_achieve_scrapy_db}"
PG_USER="${ABI_PG_USER:-${SCRAPY_POSTGRES_USER:-}}"
PG_DB="${ABI_PG_DB:-${SCRAPY_POSTGRES_DB:-}}"
ENV_FILE="${ABI_BACKUP_ENV_FILE:-/opt/data-achieve-scrapy/.abi-backup.env}"
CRON_SCHEDULE="${ABI_BACKUP_CRON:-15 3 * * *}"

TMP_FILE=""

cleanup() {
  if [[ -n "$TMP_FILE" ]]; then
    rm -f "$TMP_FILE"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
用法：
  ./scripts/backup-abi.sh            安装/更新 cron（默认）
  ./scripts/backup-abi.sh --run      立即执行一次加密备份
  ./scripts/backup-abi.sh --help     显示本帮助

环境变量：
  ABI_BACKUP_PASSPHRASE       必填，openssl 加密口令（--run 模式）
  ABI_PG_USER / ABI_PG_DB     数据库账号与库名，默认取 SCRAPY_POSTGRES_*
  ABI_BACKUP_DIR              备份目录，默认 /opt/data-achieve-scrapy/abi-backups
  ABI_BACKUP_RETENTION_DAYS   保留天数，默认 14
  ABI_BACKUP_ENV_FILE         cron 触发时 source 的密钥文件
EOF
}

run_backup() {
  : "${ABI_BACKUP_PASSPHRASE:?ABI_BACKUP_PASSPHRASE 未设置；请先 source 密钥文件}"
  : "${PG_USER:?PG_USER 未设置；请设 ABI_PG_USER 或 SCRAPY_POSTGRES_USER}"
  : "${PG_DB:?PG_DB 未设置；请设 ABI_PG_DB 或 SCRAPY_POSTGRES_DB}"

  if ! command -v docker >/dev/null 2>&1; then
    echo "未找到 docker 命令，无法执行 pg_dump。" >&2
    exit 1
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    echo "未找到 openssl 命令，无法加密备份。" >&2
    exit 1
  fi
  if ! docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null | grep -q true; then
    echo "数据库容器 ${DB_CONTAINER} 未运行，无法备份。" >&2
    exit 1
  fi

  mkdir -p "$BACKUP_DIR"
  local stamp target
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="${BACKUP_DIR}/abi-${stamp}.dump.enc"
  TMP_FILE="$(mktemp "${BACKUP_DIR}/.abi-${stamp}.XXXXXX")"

  # 在 db 容器内执行 pg_dump：走容器本地 socket，口令不出现在命令行与进程表。
  # 自定义格式支持 pg_restore 选择性恢复；--no-owner / --no-privileges
  # 让备份能恢复到角色名不同的实例。
  # pipefail 保证 pg_dump 失败时整条管道失败，不会把半截密文当成有效备份。
  docker exec "$DB_CONTAINER" \
    pg_dump -U "$PG_USER" -d "$PG_DB" --format=custom \
      --no-owner --no-privileges \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
        -pass env:ABI_BACKUP_PASSPHRASE -out "$TMP_FILE"

  mv "$TMP_FILE" "$target"
  TMP_FILE=""

  # 校验和与密文分开存。恢复前先比对，避免拿到被截断或损坏的文件。
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$target" >"${target}.sha256"
  else
    shasum -a 256 "$target" >"${target}.sha256"
  fi

  # 只清理本目录下符合命名规则的过期备份，避免误删其它文件。
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'abi-*.dump.enc' \
    -mtime "+${RETENTION_DAYS}" -delete
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'abi-*.dump.enc.sha256' \
    -mtime "+${RETENTION_DAYS}" -delete

  echo "备份完成：$target"
  # TODO(ABI): 远端副本。目标机必须与数据库主机分离。
  # rsync -a --delete-after "$BACKUP_DIR/" backup@remote:/srv/abi-backups/
}

install_cron() {
  if ! command -v crontab >/dev/null 2>&1; then
    echo "未找到 crontab 命令，无法安装定时任务。" >&2
    exit 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo "警告：未找到 docker 命令。cron 条目仍会写入，但运行时需要 docker。" >&2
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "警告：${ENV_FILE} 不存在。cron 触发时会因缺少 ABI_BACKUP_PASSPHRASE 失败。" >&2
    echo "      请创建该文件（chmod 600），内容形如：" >&2
    echo "      export ABI_BACKUP_PASSPHRASE='...'" >&2
  fi

  local cron_line
  # 整行都重定向到日志：连 source 密钥文件失败也要留下证据，而不是只发 cron 邮件。
  cron_line="${CRON_SCHEDULE} { . ${ENV_FILE} && ${SCRIPT_PATH} --run; } >> ${LOG_FILE} 2>&1"

  TMP_FILE="$(mktemp)"
  # 当前用户没有 crontab 时，crontab -l 返回非零。这是正常情况。
  crontab -l >"$TMP_FILE" 2>/dev/null || true

  if grep -Fq "$MARKER" "$TMP_FILE"; then
    echo "ABI 备份 cron 已存在，未改动。"
    return 0
  fi

  {
    printf '%s\n' "$MARKER"
    printf '%s\n' "$cron_line"
  } >>"$TMP_FILE"

  crontab "$TMP_FILE"

  if [[ ! -e "$LOG_FILE" ]]; then
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    touch "$LOG_FILE" 2>/dev/null || \
      echo "提示：无法创建 ${LOG_FILE}。请确认 cron 用户对该路径有写权限。" >&2
  fi

  echo "已安装 ABI 加密备份 cron："
  echo "  $cron_line"
  echo "日志：$LOG_FILE"
}

case "${1:-}" in
  --run)
    run_backup
    ;;
  --install-cron | "")
    install_cron
    ;;
  --help | -h)
    usage
    ;;
  *)
    echo "未知参数：$1" >&2
    usage >&2
    exit 2
    ;;
esac
