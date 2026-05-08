"""
/domains/* — HTTP wrappers for the six concrete domain adapters.

One POST endpoint per domain. Each accepts the domain's request shape as
JSON, runs the full UCJA → SCCCE pipeline, and returns the domain's
result shape.

These endpoints do not require scope `musia.write` even though they
execute cycles, because the UCJA gate fronts every adapter and the
adapter outputs are read-only domain results — no construct registry
state persists from /domains/* calls. Scope is `musia.read` instead.
``persist_run=true`` upgrades the requirement to `musia.write` (audit F13).

Originally a single 614-line module. Split into one file per domain,
plus ``_common`` (shared response shape + helpers) and ``index`` for
the list endpoint. Each sub-router uses full paths in its decorators
(e.g. ``/domains/software-dev/process``) so the receipt-coverage scanner
sees the same URLs the server exposes.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    business,
    education,
    healthcare,
    index,
    manufacturing,
    research,
    software_dev,
)

router = APIRouter()

for _sub in (
    software_dev,
    business,
    research,
    manufacturing,
    healthcare,
    education,
    index,
):
    router.include_router(_sub.router)

__all__ = ["router"]
