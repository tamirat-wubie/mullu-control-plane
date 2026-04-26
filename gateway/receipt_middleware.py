"""Gateway Receipt Middleware — entry-point trust-boundary certification.

Purpose: Closes the High-severity gap documented in
docs/MAF_RECEIPT_COVERAGE.md §"Routes NOT covered". Every gateway
webhook entry-point invocation now produces a TransitionReceipt that
captures the entry-point trust decision (admitted / rejected / errored).

Governance scope: gateway entry surface only — does not duplicate the
per-action receipts produced downstream by GovernanceMiddleware on
/api/v1/* routes.

Coverage matrix (after this middleware ships):

    /webhook/whatsapp                            → certified
    /webhook/telegram                            → certified
    /webhook/slack                               → certified
    /webhook/discord                             → certified
    /webhook/web                                 → certified
    /webhook/approve/{request_id}                → certified
    /authority/approval-chains/expire-overdue    → certified
    /authority/obligations/{id}/satisfy          → certified
    /authority/obligations/escalate-overdue      → certified

Outcome mapping (HTTP status → governance outcome):

    2xx → "allowed"   (entry admitted)
    4xx → "denied"    (signature fail / bad input / unauthorized)
    5xx → "error"     (engine fault)

Receipt detail captures the channel name, HTTP method, status code, and
path so downstream auditors can correlate the gateway receipt with the
audit trail entry and any /api/v1/* receipts produced by downstream
calls.

Limitations:
  - The middleware certifies the BOUNDARY decision (was this request
    admitted?), not the BUSINESS decision (was the action allowed?).
    Business-level certification still happens at /api/v1/* via
    GovernanceMiddleware.
  - If proof_bridge is None (platform unavailable), middleware is a
    no-op. Gateway continues to function; absence of receipts is
    observable via the platform health check.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log = logging.getLogger(__name__)


# Path prefixes whose entry decisions we certify. Anything outside these
# prefixes is left alone (e.g., /health, /metrics, static assets).
_CERTIFIED_PREFIXES: tuple[str, ...] = (
    "/webhook/",
    "/authority/",
)


def _channel_from_path(path: str) -> str:
    """Extract a stable channel name from the request path.

    /webhook/whatsapp                                 → "whatsapp"
    /webhook/approve/{id}                             → "approve"
    /authority/approval-chains/expire-overdue         → "authority"
    /authority/obligations/{id}/satisfy               → "authority"
    Anything else                                     → "other"
    """
    if path.startswith("/webhook/"):
        rest = path[len("/webhook/"):]
        head = rest.split("/", 1)[0]
        return head or "webhook"
    if path.startswith("/authority/"):
        return "authority"
    return "other"


def _outcome_from_status(status_code: int) -> tuple[str, str]:
    """Map HTTP status to (governance_decision, audit_outcome).

    Returns a 2-tuple because ProofBridge.certify_governance_decision
    takes `decision` ('allowed'|'denied') and we want the audit outcome
    ('success'|'denied'|'error') to match conventions elsewhere.
    """
    if 200 <= status_code < 300:
        return "allowed", "success"
    if 400 <= status_code < 500:
        return "denied", "denied"
    return "denied", "error"


class GatewayReceiptMiddleware(BaseHTTPMiddleware):
    """Emits a TransitionReceipt for each gateway entry-point invocation.

    Wraps the FastAPI app so every webhook/authority POST produces a
    receipt regardless of which endpoint handler runs. This is the
    inverse pattern of GovernanceMiddleware: that one runs BEFORE the
    handler to gate it; this one runs AFTER to record the outcome.

    The "after" placement is deliberate. Boundary certification needs
    to capture the realized status (was the request actually admitted?),
    which is only known after the handler returns. Pre-handler
    certification could not distinguish a 200 from a 403.
    """

    def __init__(
        self,
        app: Any,
        *,
        proof_bridge: Any | None,
        certified_prefixes: tuple[str, ...] = _CERTIFIED_PREFIXES,
    ) -> None:
        super().__init__(app)
        self._proof_bridge = proof_bridge
        self._prefixes = certified_prefixes

    def _should_certify(self, request: Request) -> bool:
        if request.method != "POST":
            return False
        path = request.url.path
        return any(path.startswith(p) for p in self._prefixes)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Always run the handler. Receipt emission is observability,
        # not a gate — gateway availability must not depend on it.
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
                decision, audit_outcome = _outcome_from_status(status_code)
                channel = _channel_from_path(request.url.path)
                reason_suffix = "exception" if handler_exc is not None else "response"
                self._proof_bridge.certify_governance_decision(
                    tenant_id=f"gateway:{channel}",
                    endpoint=request.url.path,
                    guard_results=[
                        {
                            "guard_name": "gateway.entry_admission",
                            "allowed": decision == "allowed",
                            "reason": f"http_{status_code}_{reason_suffix}",
                        },
                    ],
                    decision=decision,
                    actor_id=f"gateway:{channel}",
                    reason=f"gateway entry-point {request.method} {request.url.path}",
                )
            except Exception:
                # Receipt emission must NEVER break the gateway. Log and
                # continue — missing receipts are observable via
                # proof_bridge.receipt_count drift vs request log volume.
                _log.exception(
                    "gateway receipt emission failed for %s %s",
                    request.method, request.url.path,
                )

        if handler_exc is not None:
            # Re-raise so Starlette's outer error middleware produces
            # the 500 response (we don't fabricate a Response object).
            raise handler_exc
        return response


def install_gateway_receipt_middleware(app: Any, platform: Any) -> bool:
    """Attach GatewayReceiptMiddleware to a FastAPI app if a platform is available.

    Returns True if installed, False if skipped (no platform or no
    proof_bridge). Skip is non-fatal — the gateway just falls back to
    the pre-G10.1 behavior with a logged warning.
    """
    if platform is None:
        _log.warning(
            "gateway receipt middleware not installed: no platform available "
            "(entry-point boundary will not be certified — see "
            "docs/MAF_RECEIPT_COVERAGE.md)"
        )
        return False

    proof_bridge = getattr(platform, "proof_bridge", None)
    if proof_bridge is None:
        _log.warning(
            "gateway receipt middleware not installed: platform has no "
            "proof_bridge (entry-point boundary will not be certified)"
        )
        return False

    app.add_middleware(GatewayReceiptMiddleware, proof_bridge=proof_bridge)
    _log.info(
        "gateway receipt middleware installed: entry-point boundary "
        "certified for %s",
        ", ".join(_CERTIFIED_PREFIXES),
    )
    return True
