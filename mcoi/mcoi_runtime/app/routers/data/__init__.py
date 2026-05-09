"""Data-plane endpoints package.

Originally a 1063-line `data.py`. Split into one module per concern:
conversations, schemas, prompts, tools, state, structured output, certification,
daemon, search, API keys, export, SLA, and data governance.

Existing imports of `from mcoi_runtime.app.routers.data import router` continue
to work via the aggregated `router` re-exported below.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    api_keys,
    certify,
    conversations,
    daemon,
    export,
    governance,
    output,
    prompts,
    schemas,
    search,
    sla,
    state,
    tools,
)

router = APIRouter()

for _sub in (
    governance,
    conversations,
    schemas,
    prompts,
    tools,
    state,
    output,
    certify,
    daemon,
    search,
    api_keys,
    export,
    sla,
):
    router.include_router(_sub.router)

__all__ = ["router"]
