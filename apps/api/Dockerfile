FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    PIP_RETRIES=10 \
    UV_DEFAULT_INDEX=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.6 \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY pyproject.toml uv.lock README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

ARG INSTALL_PLAYWRIGHT=false
RUN uv sync --frozen --no-dev \
    && if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
         uv pip install playwright \
         && uv run playwright install chromium --with-deps; \
       fi \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "data_intelligence_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
