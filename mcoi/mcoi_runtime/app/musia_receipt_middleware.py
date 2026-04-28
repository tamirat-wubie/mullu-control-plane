"""MUSIA Receipt Middleware — entry-point trust-boundary certification for
the MUSIA surfaces (cognition, constructs, domains, musia/*, ucja).

Purpose: Closes the High-severity gap surfaced by
`scripts/validate_receipt_coverage.py` and documented in
`docs/MAF_RECEIPT_COVERAGE.md` — every state-mutating MUSIA route now
produces a TransitionReceipt that captures the entry decision
(admitted / rejected / errored).

Governance scope: MUSIA entry surface only. The middleware is the inverse
pattern of GovernanceMiddleware: that one runs BEFORE the handler to gate
it via the guard chain; this one runs AFTER to record the realized
outcome. MUSIA endpoints are deliberately not on the /api/ prefix that
GovernanceMiddleware filters on, so without this middleware they would
produce no governance receipts at all.

Coverage matrix (after this middleware ships, every state-mutating path
under one of the certified prefixes is certified):

    /cognition/*    → certified
    /constructs/*   → certified
    /domains/*      → certified
    /musia/*        → certified
    /ucja/*         → certified

Outcome mapping (HTTP status → governance outcome) mirrors
`gateway/receipt_middleware.py`:

    2xx → "allowed"   (entry admitted)
    4xx → "denied"    (validation fail / unauthorized / not found)
    5xx → "denied"    (engine fault, audit outcome "error")

What this middleware does NOT do:
  - It does NOT impose new guards. MUSIA's own substrate (Φ_gov,
    25-construct framework) handles MUSIA-internal governance. This
    middleware only records the boundary decision so a downstream
    auditor can correlate MUSIA HTTP calls with the receipt chain.
  - It does NOT duplicate work for /api/ paths. If a future
    refactoring moves a MUSIA endpoint under /api/, GovernanceMiddleware
    would already cover it; this middleware skips paths outside its
    declared prefixes.

Limitations:
  - The middleware certifies the BOUNDARY decision (was the request
    admitted?), not the BUSINESS decision (was the MUSIA reasoning
    correct?). The latter is recorded by MUSIA's own substrate via the
    Φ_gov mechanism documented in docs/27_mfidel_semantic_layer.md.
  - If proof_bridge is None (platform unavailable), middleware is a
    no-op. MCOI continues to function; absence of receipts is
    observable via proof_bridge.receipt_count drift.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log = logging.getLogger(__name__)


# Path prefixes whose entry decisions we certify. Every one of these is
# a MUSIA surface that lives outside the /api/ filter of
# GovernanceMiddleware. Ordering is alphabetical for readability; the
# match logic uses startswith so order is not semantically significant.
_CERTIFIED_PREFIXES: tuple[str, ...] = (
    "/cognition/",
    "/constructs/",
    "/domains/",
    "/musia/",
    "/ucja/",
)

# Methods considered state-mutating. GET/HEAD/OPTIONS are read-only by
# REST convention and produce no governed transition. This matches the
# rule encoded in scripts/validate_receipt_coverage.py.
_CERTIFIED_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _surface_from_path(path: str) -> str:
    """Extract a stable MUSIA surface name from the request path.

    /cognition/run                       → "cognition"
    /constructs/boundary                 → "constructs"
    /domains/finance/process             → "domains"
    /musia/tenants/{tenant_id}/snapshot  → "musia"
    /musia/governance/stats/reset        → "musia"
    /ucja/define-job                     → "ucja"
    Anything else                        → "other"
    """
    for prefix in _CERTIFIED_PREFIXES:
        if path.startswith(prefix):
            # Strip leading "/" and trailing "/", take first segment
            return prefix.strip("/")
    return "other"


def _outcome_from_status(status_code: int) -> tuple[str, str]:
    """Map HTTP status to (governance_decision, audit_outcome).

    Mirrors gateway/receipt_middleware.py::_outcome_from_status so the
    two boundary middlewares produce comparable receipts.
    """
    if 200 <= status_code < 300:
        return "allowed", "success"
    if 400 <= status_code < 500:
        return "denied", "denied"
    return "denied", "error"


class MusiaReceiptMiddleware(BaseHTTPMiddleware):
    """Emits a TransitionReceipt for each state-mutating MUSIA request.

    Wraps the FastAPI app so every POST/PUT/PATCH/DELETE on a MUSIA-
    prefixed path produces a receipt regardless of which endpoint
    handler runs. Receipt-only — does not impose guards.

    Mirrors GatewayReceiptMiddleware's "after-handler" placement: the
    middleware needs the realized status code (was the request actually
    admitted?), which is only known after the handler returns.
    """

    def __init__(
        self,
        app: Any,
        *,
        proof_bridge: Any | None,
        certified_prefixes: tuple[str, ...] = _CERTIFIED_PREFIXES,
        certified_methods: frozenset[str] = _CERTIFIED_METHODS,
    ) -> None:
        super().__init__(app)
        self._proof_bridge = proof_bridge
        self._prefixes = certified_prefixes
        self._methods = certified_methods

    def _should_certify(self, request: Request) -> bool:
        if request.method not in self._methods:
            return False
        path = request.url.path
        return any(path.startswith(p) for p in self._prefixes)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Always run the handler. Receipt emission is observability,
        # not a gate — MUSIA availability must not depend on it.
        # If the handler raises (uncaught exception, not HTTPException),
        # we still emit a receipt for the boundary decision before
        # re-raising. Otherwise crash-paths would be uncertified.
        handler_exc: Exception | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            handler_exc = exc
            response = None
            status_code = 500

        if self._should_certify(request) and self._proof_bridge is not None:
            try:
                decision, _audit_outcome = _outcome_from_status(status_code)
                surface = _surface_from_path(request.url.path)
                # Bounded reason — status code class, not the exact code, and
                # never the request method/path. Full status, method, and path
                # are recoverable from the audit trail entry that accompanies
                # this receipt. v4.43.0 (audit governance contract guard).
                guard_reason = (
                    "http_5xx_exception" if handler_exc is not None
                    else "http_5xx_response" if status_code >= 500
                    else "http_4xx_response" if status_code >= 400
                    else "http_2xx_response"
                )
                self._proof_bridge.certify_governance_decision(
                    tenant_id=f"musia:{surface}",
                    endpoint=request.url.path,
                    guard_results=[
                        {
                            "guard_name": "musia.entry_admission",
                            "allowed": decision == "allowed",
                            "reason": guard_reason,
                        },
                    ],
                    decision=decision,
                    actor_id=f"musia:{surface}",
                    reason="musia entry-point admission decision",
                )
            except Exception:
                # Receipt emission must NEVER break MUSIA. Log and
                # continue — missing receipts are observable via
                # proof_bridge.receipt_count drift vs request log volume.
                _log.exception(
                    "musia receipt emission failed for %s %s",
                    request.method, request.url.path,
                )

        if handler_exc is not None:
            # Re-raise so Starlette's outer error middleware produces
            # the 500 response (we don't fabricate a Response object).
            raise handler_exc
        return response


# Module-level status. Set by install_musia_receipt_middleware so that
# health-check endpoints and observability scrapers can confirm whether
# MUSIA entry-point certification is actually active. Mirrors the pattern
# in gateway/receipt_middleware.py.
_RECEIPT_MIDDLEWARE_STATUS: dict[str, Any] = {
    "installed": False,
    "reason": "not yet attempted",
    "certified_prefixes": list(_CERTIFIED_PREFIXES),
}


def get_musia_receipt_middleware_status() -> dict[str, Any]:
    """Return the current install status of the MUSIA receipt middleware.

    Intended for health endpoints / metrics scrapers. Shape:

        {
            "installed": bool,        # True iff middleware is wired
            "reason": str,            # human-readable status
            "certified_prefixes": [str, ...],  # paths the middleware would cover
        }

    A dashboard alerting on `installed=False` catches the
    "we thought MUSIA receipts were on but they weren't" failure mode.
    """
    return dict(_RECEIPT_MIDDLEWARE_STATUS)


def install_musia_receipt_middleware(app: Any, proof_bridge: Any | None) -> bool:
    """Attach MusiaReceiptMiddleware to a FastAPI app if proof_bridge is available.

    Returns True if installed, False if skipped (no proof_bridge). Skip
    is non-fatal — MUSIA endpoints continue to serve, but the boundary
    is uncertified. The skip is observable via
    get_musia_receipt_middleware_status().
    """
    if proof_bridge is None:
        _log.warning(
            "musia receipt middleware not installed: no proof_bridge "
            "(MUSIA entry-point boundary will not be certified — see "
            "docs/MAF_RECEIPT_COVERAGE.md)"
        )
        _RECEIPT_MIDDLEWARE_STATUS.update({
            "installed": False,
            "reason": "proof_bridge is None",
        })
        return False

    app.add_middleware(MusiaReceiptMiddleware, proof_bridge=proof_bridge)
    _log.info(
        "musia receipt middleware installed: entry-point boundary "
        "certified for %s",
        ", ".join(_CERTIFIED_PREFIXES),
    )
    _RECEIPT_MIDDLEWARE_STATUS.update({
        "installed": True,
        "reason": "active",
    })
    return True
