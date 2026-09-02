#!/usr/bin/env bash
# =============================================================================
# Data Intelligence Hub — 新服务器一键部署脚本
# 服务器：192.168.204.230  用户：lute
# 用法：在新服务器上直接执行
#   bash <(curl -s ...) 或 bash deploy-new-server.sh
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/zjgulai/data_achieve.git"
BRANCH="codex/social-api-private-matrix-20260708"
APP_DIR="$HOME/apps/data_scrapy"
DATA_DIR="/data/scrapy"
ENV_FILE="$DATA_DIR/configs/.env.production"
COMPOSE_FILE="configs/deploy/scrapy-new/docker-compose.yml"

# --- 颜色输出 ---
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
die()   { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

# =============================================================================
# Step 1: 安装 Docker
# =============================================================================
info "Step 1: 检查 / 安装 Docker..."
if command -v docker &>/dev/null; then
  ok "Docker 已安装：$(docker --version)"
else
  info "  安装 Docker Engine..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  sudo systemctl enable --now docker
  ok "Docker 安装完成"
  warn "  ⚠ 已将 $USER 加入 docker 组，当前 shell 需重启才生效。脚本继续用 sudo docker..."
fi

DOCKER="docker"
if ! docker ps &>/dev/null 2>&1; then
  DOCKER="sudo docker"
fi

# =============================================================================
# Step 2: 准备目录结构（/data 数据盘）
# =============================================================================
info "Step 2: 准备目录结构..."
sudo mkdir -p \
  "$DATA_DIR/postgres" \
  "$DATA_DIR/exports/datasets" \
  "$DATA_DIR/browser_data" \
  "$DATA_DIR/configs"
sudo chown -R "$USER:$USER" "$DATA_DIR"
ok "目录已创建：$DATA_DIR"

# =============================================================================
# Step 3: 拉取项目代码
# =============================================================================
info "Step 3: 拉取项目代码..."
mkdir -p "$HOME/apps"
if [ -d "$APP_DIR/.git" ]; then
  info "  已有仓库，执行 git pull..."
  cd "$APP_DIR"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git merge --ff-only "origin/$BRANCH"
else
  info "  克隆仓库..."
  git clone --branch "$BRANCH" --depth 50 "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi
ok "代码已就绪：$(git log --oneline -1)"

# =============================================================================
# Step 4: 写入 .env.production（从旧服务器迁移的真实值）
# =============================================================================
info "Step 4: 写入 .env.production..."
cat > "$ENV_FILE" << 'ENVEOF'
# ============================================================
# Data Intelligence Hub — 生产环境变量（新服务器）
# 说明：将下方 <PLACEHOLDER> 替换为真实值后再执行本脚本
#       真实值存放在团队密钥管理系统中，不得 commit 到 git
# ============================================================

# 数据库
SCRAPY_POSTGRES_DB=data_intel
SCRAPY_POSTGRES_USER=data_intel
SCRAPY_POSTGRES_PASSWORD=<SCRAPY_POSTGRES_PASSWORD>

# 认证
SCRAPY_JWT_SECRET=<SCRAPY_JWT_SECRET>
SCRAPY_AUTH_COOKIE_SECURE=true

# 采集器数据目录
SCRAPY_DATASET_EXPORT_DIR=/app/exports/datasets

# SMTP（可选）
SCRAPY_SMTP_HOST=smtp.gmail.com
SCRAPY_SMTP_PORT=587
SCRAPY_SMTP_USER=<SMTP_USER>
SCRAPY_SMTP_PASSWORD=<SMTP_PASSWORD>
SCRAPY_SMTP_FROM=<SMTP_FROM>

# 调度器
SCRAPY_SCHEDULER_ENABLED=true
SCRAPY_SCHEDULER_POLL_INTERVAL_SECONDS=60

# API Keys
TIKHUB_API_KEY=<TIKHUB_API_KEY>
APIFY_API_TOKEN=<APIFY_API_TOKEN>
ANYSEARCH_API_KEY=<ANYSEARCH_API_KEY>
JINA_API_KEY=<JINA_API_KEY>
PLATFORM_CREDENTIAL_MASTER_KEY=<PLATFORM_CREDENTIAL_MASTER_KEY>

# CORS（内网访问）
SCRAPY_CORS_ORIGINS=["http://192.168.204.230","https://scrapy.lute-tlz-dddd.top"]

# 代理（暂禁用）
PROXY_ROTATOR_ENABLED=false
HTTP_PROXY=
HTTPS_PROXY=

# OSINT 服务
MAIGRET_URL=http://maigret:5000
SPIDERFOOT_BASE_URL=http://spiderfoot:5001
SPIDERFOOT_TIMEOUT=300
MEDIACRAWLER_BASE_URL=http://mediacrawler-bridge:8080
ENVEOF

chmod 600 "$ENV_FILE"
ok ".env.production 已写入：$ENV_FILE"

# =============================================================================
# Step 5: 配置宿主机 Nginx
# =============================================================================
info "Step 5: 配置宿主机 Nginx..."
if ! command -v nginx &>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y nginx
fi

sudo cp "$APP_DIR/configs/deploy/scrapy-new/nginx.conf" \
  /etc/nginx/sites-available/scrapy
sudo ln -sf /etc/nginx/sites-available/scrapy \
  /etc/nginx/sites-enabled/scrapy
# 移除 default（避免端口冲突）
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
ok "Nginx 已配置"

# =============================================================================
# Step 6: 防火墙开放 80/443
# =============================================================================
info "Step 6: 防火墙配置..."
sudo ufw allow 80/tcp  2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
ok "端口 80/443 已开放"

# =============================================================================
# Step 7: 构建并启动容器
# =============================================================================
info "Step 7: docker compose build + up（约 10-20 分钟）..."
cd "$APP_DIR"
$DOCKER compose \
  -f "$COMPOSE_FILE" \
  --env-file "$ENV_FILE" \
  build --no-cache api console

$DOCKER compose \
  -f "$COMPOSE_FILE" \
  --env-file "$ENV_FILE" \
  up -d

ok "容器已启动"

# =============================================================================
# Step 8: 等待健康并验收
# =============================================================================
info "Step 8: 等待 API 就绪（最多 60 秒）..."
for i in $(seq 1 12); do
  if curl -sf http://127.0.0.1:8080/api/health &>/dev/null; then
    ok "API 健康！"
    break
  fi
  echo -n "."
  sleep 5
done

echo ""
info "=== 健康检查 ==="
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool 2>/dev/null || \
  curl -s http://127.0.0.1:8080/api/health

echo ""
info "=== catalog 验收 ==="
curl -s http://127.0.0.1:8080/api/collectors/catalog | python3 -c "
import sys, json
d = json.load(sys.stdin)
v  = sum(1 for g in d['collectors'] for e in g['endpoints'] if e.get('status')=='verified')
di = sum(1 for g in d['collectors'] for e in g['endpoints'] if e.get('status')=='disabled')
t  = sum(1 for g in d['collectors'] for e in g['endpoints'])
print(f'groups={len(d[\"collectors\"])}, total={t}, verified={v}, disabled={di}')
" 2>/dev/null || echo "(catalog 解析失败，请手动检查)"

echo ""
info "=== 容器状态 ==="
$DOCKER ps --filter name=data_achieve_scrapy --format "table {{.Names}}\t{{.Status}}"

echo ""
ok "=============================================="
ok " 部署完成！访问地址："
ok "   http://192.168.204.230/platforms"
ok "   http://192.168.204.230/api/health"
ok "=============================================="
