#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
deploy-new-server.sh 已停用。

当前生产环境位于腾讯云 43.163.92.244，使用：
  /opt/data-achieve-scrapy/app/configs/deploy/scrapy/docker-compose.yml

请按以下文档执行：
  - docs/deployment-new-server.md
  - docs/workflows/workflow-release-rollback-stable.md
  - docs/workflows/【运维手册】scrapy-luteos全量重建.md

旧脚本面向 192.168.204.230 和 scrapy-new 编排，继续执行会创建错误路径、
错误 Nginx 配置和错误持久化目录，因此主动退出。
EOF

exit 2
