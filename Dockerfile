FROM python:3.13-slim

WORKDIR /app

COPY mcoi/ ./mcoi/
COPY gateway/ ./gateway/
COPY skills/ ./skills/
COPY installer/ ./installer/
COPY scripts/ ./scripts/

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -e mcoi[all] && \
    pip install --no-cache-dir fastapi uvicorn anthropic openai

ENV MULLU_ENV=pilot
ENV PYTHONPATH=/app:/app/mcoi
ENV MULLU_STATE_DIR=/data/state

# Run as non-root for security
RUN adduser --disabled-password --gecos "" mullu && \
    mkdir -p /data/state && \
    chown -R mullu:mullu /data
USER mullu

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "mcoi_runtime.app.server:app", "--host", "0.0.0.0", "--port", "8000"]
