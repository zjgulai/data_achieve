FROM python:3.12-slim AS runtime

# 包索引与系统软件源可在构建时切换：生产 B（腾讯云国内区）直连 PyPI 只有
# ~23KB/s，构建必然读超时（2026-10-11 实测）。默认值与官方源一致，只有显式
# 传参才改——compose 的 build.args 从 .env.production 的 SCRAPY_* 系列读取，
# 生产 A 不设这些键，行为与改动前完全相同。
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG UV_DEFAULT_INDEX=https://pypi.org/simple
ARG DEBIAN_MIRROR
ARG PLAYWRIGHT_DOWNLOAD_HOST

# PLAYWRIGHT_BROWSERS_PATH 必须显式钉住：构建时以 root 执行 playwright install，
# 浏览器落到 /root/.cache；运行时用户是 app（HOME=/app），默认去 /app/.cache 找，
# 于是报 "Executable doesn't exist at /app/.cache/ms-playwright/..."（2026-10-09 实测）。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_RETRIES=10 \
    UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX} \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

# apt 源（playwright --with-deps 与 INSTALL_OSINT 都用）；DEBIAN_MIRROR 为空则不动。
# bookworm 用老格式 sources.list，trixie 起改用 deb822 的 debian.sources，两个都覆盖。
RUN if [ -n "$DEBIAN_MIRROR" ]; then \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        [ -f "$f" ] && sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g; s|security.debian.org|${DEBIAN_MIRROR}|g" "$f"; \
      done; true; \
    fi

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.6 \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY pyproject.toml uv.lock README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

# uv.lock 记录每个包的绝对下载地址（files.pythonhosted.org）。只设
# UV_DEFAULT_INDEX 时，uv sync --frozen 仍按锁文件直连 pypi.org；生产 B
# 实测只有 26-46KB/s（2026-10-11），构建会拖到数小时。这里换掉锁文件里的
# 主机名：包路径与 sha256 都不变，uv 仍按锁文件校验哈希，镜像源换了也安全。
# 文件主机由索引地址去掉 /simple/ 后缀得到，所以索引地址必须以 /simple/ 结尾。
# 索引是官方源时整段跳过，生产 A 不受影响。
RUN if [ "$PIP_INDEX_URL" != "https://pypi.org/simple" ]; then \
      sed -i "s|https://files.pythonhosted.org|${PIP_INDEX_URL%/simple/}|g; s|https://pypi.org/simple|${PIP_INDEX_URL}|g" uv.lock; \
    fi

ARG INSTALL_PLAYWRIGHT=false
ARG INSTALL_OSINT=false
RUN uv sync --frozen --no-dev \
    && if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
         uv pip install playwright \
         && uv run playwright install chromium --with-deps; \
       fi \
    && if [ "$INSTALL_OSINT" = "true" ]; then \
         apt-get update \
         && apt-get install -y --no-install-recommends tor \
         && rm -rf /var/lib/apt/lists/*; \
       fi \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "data_intelligence_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
