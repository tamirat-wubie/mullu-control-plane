#!/bin/sh
# Purpose: start the Render pilot gateway worker before the gateway web server.
# Governance scope: deployment witness anchoring and command-spine continuation.
# Dependencies: python, gateway.worker, and the installed uvicorn Python module.
# Invariants: only gateway.server:app starts the inline worker; uvicorn remains the foreground process.

set -eu

if [ "${MULLU_RENDER_INLINE_GATEWAY_WORKER:-1}" = "1" ] \
  && [ "${MULLU_GATEWAY_WORKER_INLINE_STARTED:-0}" != "1" ] \
  && [ "${1:-}" = "gateway.server:app" ]; then
  export MULLU_GATEWAY_WORKER_INLINE_STARTED=1
  python -m gateway.worker &
  worker_pid="$!"
  boot_check_seconds="${MULLU_RENDER_INLINE_GATEWAY_WORKER_BOOT_CHECK_SECONDS:-2}"
  sleep "$boot_check_seconds"
  if ! kill -0 "$worker_pid" 2>/dev/null; then
    wait "$worker_pid"
  fi
fi

exec python -m uvicorn "$@"
