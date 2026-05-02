FROM python:3.13-slim

ARG MULLU_INSTALL_WORKER_DEPS=true
ARG MULLU_INSTALL_PLAYWRIGHT_BROWSERS=true

WORKDIR /app

COPY mcoi/ ./mcoi/
COPY gateway/ ./gateway/
COPY skills/ ./skills/
COPY installer/ ./installer/
COPY scripts/ ./scripts/

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* && \
    if [ "$MULLU_INSTALL_WORKER_DEPS" = "true" ]; then \
      pip install --no-cache-dir -e "mcoi[all]"; \
    else \
      pip install --no-cache-dir -e "mcoi[persistence,encryption,gateway,voice-worker]" anthropic; \
    fi && \
    if [ "$MULLU_INSTALL_WORKER_DEPS" = "true" ] && [ "$MULLU_INSTALL_PLAYWRIGHT_BROWSERS" = "true" ]; then \
      python -m playwright install --with-deps chromium; \
    fi

ENV MULLU_ENV=pilot
ENV PYTHONPATH=/app:/app/mcoi
ENV MULLU_STATE_DIR=/data/state
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Run as non-root for security
RUN adduser --disabled-password --gecos "" mullu && \
    mkdir -p /data/state /tmp/mullu-browser-evidence /ms-playwright && \
    chown -R mullu:mullu /data /tmp/mullu-browser-evidence /ms-playwright
USER mullu

EXPOSE 8000 8001 8010 8020 8030 8040 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "mcoi_runtime.app.server:app", "--host", "0.0.0.0", "--port", "8000"]
