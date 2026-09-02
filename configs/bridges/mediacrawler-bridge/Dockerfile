FROM python:3.12-slim
WORKDIR /app
RUN pip install fastapi uvicorn httpx --no-cache-dir
COPY bridge.py .
CMD ["uvicorn", "bridge:app", "--host", "0.0.0.0", "--port", "8080"]
