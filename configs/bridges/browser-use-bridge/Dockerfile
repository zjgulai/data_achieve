FROM python:3.12-slim
WORKDIR /app

# 生产 B 在国内，直连 PyPI 会读超时；允许构建时切换索引，默认仍是官方源。
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

# INSTALL_CHROMIUM=false 用于只接 Obscura（CDP）的部署，可省约 400MB。
ARG INSTALL_CHROMIUM=true
ARG PLAYWRIGHT_DOWNLOAD_HOST=

# browser-use 0.13.x 不带 playwright Python 包，也不带浏览器：
#   - 它在 ~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 找本地浏览器；
#   - 找不到时才兜底执行 `uvx playwright install chromium`（需要 uv）。
# 所以这里显式装 playwright 并预装 Chromium，让第一条路径命中，不必依赖 uvx。
RUN pip install --no-cache-dir "browser-use==0.13.11" fastapi uvicorn httpx uv playwright

RUN if [ "$INSTALL_CHROMIUM" = "true" ]; then \
      PLAYWRIGHT_DOWNLOAD_HOST="${PLAYWRIGHT_DOWNLOAD_HOST}" \
        python -m playwright install --with-deps chromium; \
    fi \
    && rm -rf /var/lib/apt/lists/*

COPY bridge.py .

EXPOSE 5002
CMD ["uvicorn", "bridge:app", "--host", "0.0.0.0", "--port", "5002"]
