FROM python:3.12-slim
WORKDIR /app

# 生产 B 在国内，直连 PyPI ~23KB/s 会读超时；允许构建时切换索引，默认仍是官方源。
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

RUN pip install fastapi uvicorn httpx python-multipart --no-cache-dir
COPY bridge.py .
CMD ["uvicorn", "bridge:app", "--host", "0.0.0.0", "--port", "5001"]
