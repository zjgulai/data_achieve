FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    PIP_RETRIES=10 \
    UV_DEFAULT_INDEX=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.6 \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && apt-get update && apt-get install -y --no-install-recommends \
        chromium chromium-driver \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN uv sync --frozen --no-dev --extra browser \
    && python -m playwright install chromium --with-deps \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "data_intelligence_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
