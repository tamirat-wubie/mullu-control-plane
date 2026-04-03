FROM python:3.13-slim

WORKDIR /app

COPY mcoi/ ./mcoi/
COPY gateway/ ./gateway/
COPY skills/ ./skills/
COPY installer/ ./installer/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e mcoi[dev] && \
    pip install --no-cache-dir fastapi uvicorn psycopg2-binary anthropic openai

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
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "mcoi_runtime.app.server:app", "--host", "0.0.0.0", "--port", "8000"]
