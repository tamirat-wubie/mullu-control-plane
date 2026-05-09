"""LLM / completion-related endpoints extracted from server.py.

Covers governed completion, streaming, chat, cost analytics, model routing,
circuit-breaker status, A/B testing, and bootstrap info.

Originally a single 709-line module. Split into:
- ``_common``: shared helpers (validation, error raising, action proof)
- ``_models``: 5 pydantic request models
- ``completion``: complete, stream, safe, auto-routed (4 endpoints)
- ``chat``: chat, streaming chat, chat workflow + history (4 endpoints)
- ``costs``: cost summary + breakdowns + projection (5 endpoints)
- ``ab_test``: A/B test run + summary (2 endpoints)
- ``admin``: budget, history, bootstrap, circuit, models (5 endpoints)

External callers only import ``router``; the public surface is preserved
via the aggregation below.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import ab_test, admin, chat, completion, costs

router = APIRouter()

for _sub in (completion, chat, costs, ab_test, admin):
    router.include_router(_sub.router)

__all__ = ["router"]
