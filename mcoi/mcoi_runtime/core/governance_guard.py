"""Phase 207B — Governance Guards.

Purpose: Pre-request validation layer that enforces governance invariants
    before any endpoint logic runs. Checks rate limits, budget,
    tenant validity, and audit logging in a single pass.
Governance scope: request validation only — never modifies business state.
Dependencies: rate_limiter, tenant_budget, audit_trail, metrics.
Invariants:
  - Guards run before every governed request.
  - Rejected requests are audited with reason.
  - Guard evaluation order is deterministic.
  - Guards never modify request payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypedDict


def _classify_guard_exception(exc: Exception) -> str:
    """Return a bounded guard failure reason."""
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"guard timeout ({exc_type})"
    return f"guard error ({exc_type})"


def _bounded_tenant_mismatch_reason() -> str:
    """Return a bounded tenant mismatch reason."""
    return "tenant mismatch"


def _looks_like_jwt_bearer(token: str) -> bool:
    """Return True when a bearer token matches JWT's 3-part structure."""
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


class GuardContext(TypedDict, total=False):
    """Typed context passed through the governance guard chain.

    All fields are optional — guards check for presence before use.
    Mutable: guards may enrich context (e.g., tenant_id from JWT).
    """

    tenant_id: str
    endpoint: str
    method: str
    authorization: str
    prompt: str
    content: str
    # Set by auth guards
    authenticated_key_id: str
    authenticated_subject: str
    authenticated_tenant_id: str
    jwt_scopes: frozenset[str]
    # Set by content safety guard
    content_safety_flags: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Result of a governance guard check."""

    allowed: bool
    guard_name: str
    reason: str = ""
    detail: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class GuardChainResult:
    """Result of running the full guard chain."""

    allowed: bool
    results: tuple[GuardResult, ...]
    blocking_guard: str = ""
    reason: str = ""


class GovernanceGuard:
    """Named guard with a check function."""

    def __init__(self, name: str, check_fn: Callable[[dict[str, Any]], GuardResult]) -> None:
        self.name = name
        self._check_fn = check_fn

    def check(self, context: dict[str, Any]) -> GuardResult:
        try:
            return self._check_fn(context)
        except Exception as exc:
            return GuardResult(
                allowed=False,
                guard_name=self.name,
                reason=_classify_guard_exception(exc),
                detail={"error_type": type(exc).__name__},
            )


class GovernanceGuardChain:
    """Ordered chain of governance guards.

    Guards run in registration order. First failure stops the chain.
    """

    def __init__(self) -> None:
        self._guards: list[GovernanceGuard] = []

    def add(self, guard: GovernanceGuard) -> None:
        self._guards.append(guard)

    def insert(self, index: int, guard: GovernanceGuard) -> None:
        """Insert a guard at a specific position in the chain."""
        self._guards.insert(index, guard)

    # Guards whose output (tenant_id, identity) is frozen after evaluation
    _AUTH_GUARD_NAMES = frozenset({"api_key", "jwt"})

    def evaluate(self, context: dict[str, Any]) -> GuardChainResult:
        """Run all guards in order. Stops on first failure.

        Auth guard outputs (tenant_id, identity) are frozen after auth
        guards complete — downstream guards cannot overwrite them.
        """
        results: list[GuardResult] = []
        auth_phase_complete = False
        frozen_keys: dict[str, Any] = {}

        for guard in self._guards:
            # Freeze auth fields after auth guards complete
            if not auth_phase_complete and guard.name not in self._AUTH_GUARD_NAMES and frozen_keys:
                auth_phase_complete = True

            result = guard.check(context)
            results.append(result)

            # Snapshot auth fields after auth guards
            if guard.name in self._AUTH_GUARD_NAMES and not auth_phase_complete:
                for key in ("tenant_id", "authenticated_subject", "authenticated_key_id", "authenticated_tenant_id"):
                    if key in context:
                        frozen_keys[key] = context[key]

            # Restore frozen auth fields if tampered by non-auth guard
            if auth_phase_complete:
                for key, value in frozen_keys.items():
                    if context.get(key) != value:
                        context[key] = value  # Restore original auth binding

            if not result.allowed:
                return GuardChainResult(
                    allowed=False,
                    results=tuple(results),
                    blocking_guard=guard.name,
                    reason=result.reason,
                )
        return GuardChainResult(allowed=True, results=tuple(results))

    @property
    def guard_count(self) -> int:
        return len(self._guards)

    def guard_names(self) -> list[str]:
        return [g.name for g in self._guards]


def create_rate_limit_guard(
    rate_limiter: Any,
) -> GovernanceGuard:
    """Create a rate-limiting guard.

    Uses both tenant-level and per-identity rate limiting when
    ``authenticated_subject`` or ``authenticated_key_id`` is present
    in the guard context (populated by auth guards upstream).
    """
    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "system")
        endpoint = ctx.get("endpoint", "/unknown")
        # Resolve identity from auth guards (JWT subject or API key ID)
        identity_id = ctx.get("authenticated_subject", "") or ctx.get("authenticated_key_id", "")
        result = rate_limiter.check(tenant_id, endpoint, identity_id=identity_id)
        if result.allowed:
            return GuardResult(allowed=True, guard_name="rate_limit")
        return GuardResult(
            allowed=False, guard_name="rate_limit",
            reason="rate limited",
        )
    return GovernanceGuard("rate_limit", check)


def create_budget_guard(
    budget_mgr: Any,
    *,
    require_tenant: bool = False,
) -> GovernanceGuard:
    """Create a budget-enforcement guard."""
    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "")
        if not tenant_id:
            if require_tenant:
                return GuardResult(
                    allowed=False, guard_name="budget",
                    reason="tenant_id is required",
                )
            return GuardResult(allowed=True, guard_name="budget")
        report = budget_mgr.report(tenant_id)
        if report.exhausted:
            return GuardResult(
                allowed=False, guard_name="budget",
                reason="budget exhausted",
            )
        if not report.enabled:
            return GuardResult(
                allowed=False, guard_name="budget",
                reason="tenant disabled",
            )
        return GuardResult(allowed=True, guard_name="budget")
    return GovernanceGuard("budget", check)


def create_tenant_guard() -> GovernanceGuard:
    """Create a tenant-validation guard."""
    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "")
        if tenant_id and len(tenant_id) > 128:
            return GuardResult(
                allowed=False, guard_name="tenant",
                reason="tenant_id exceeds 128 characters",
            )
        return GuardResult(allowed=True, guard_name="tenant")
    return GovernanceGuard("tenant", check)


def create_jwt_guard(
    jwt_authenticator: Any,
    *,
    require_auth: bool = False,
) -> GovernanceGuard:
    """Create a JWT authentication guard.

    Extracts Bearer token from the ``authorization`` context field and
    validates via the :class:`JWTAuthenticator`.  When a valid JWT is
    supplied, tenant_id and identity are propagated into context.
    """
    def check(ctx: dict[str, Any]) -> GuardResult:
        auth_header: str = ctx.get("authorization", "")
        if not auth_header:
            if require_auth:
                return GuardResult(
                    allowed=False, guard_name="jwt",
                    reason="missing Authorization header",
                )
            return GuardResult(allowed=True, guard_name="jwt")
        token = auth_header.removeprefix("Bearer ").strip()
        if not token or token == auth_header:
            # Not a Bearer token — skip JWT validation (may be API key)
            return GuardResult(allowed=True, guard_name="jwt")
        result = jwt_authenticator.validate(token)
        if not result.authenticated:
            return GuardResult(
                allowed=False, guard_name="jwt",
                reason=result.error or "JWT authentication failed",
            )
        # Bind tenant from JWT claims — prevents header spoofing.
        if result.tenant_id:
            request_tenant = ctx.get("tenant_id", "")
            if require_auth and request_tenant and request_tenant != result.tenant_id:
                return GuardResult(
                    allowed=False, guard_name="jwt",
                    reason=_bounded_tenant_mismatch_reason(),
                )
            ctx["tenant_id"] = result.tenant_id
        # Propagate identity for audit attribution
        ctx["authenticated_subject"] = result.subject
        ctx["authenticated_tenant_id"] = result.tenant_id
        ctx["jwt_scopes"] = result.scopes
        return GuardResult(allowed=True, guard_name="jwt")
    return GovernanceGuard("jwt", check)


def create_api_key_guard(
    api_key_mgr: Any,
    *,
    require_auth: bool = False,
    allow_jwt_passthrough: bool = False,
) -> GovernanceGuard:
    """Create an API-key authentication guard.

    Extracts Bearer token from the ``authorization`` context field and
    authenticates via the :class:`APIKeyManager`.  Requests without an
    ``Authorization`` header are allowed through (opt-in auth) so that
    health / public endpoints keep working.  When a key IS supplied it
    must be valid — invalid keys are hard-rejected.  When
    ``allow_jwt_passthrough`` is enabled, JWT-shaped bearer tokens are
    left for a downstream JWT guard to validate.
    """
    def check(ctx: dict[str, Any]) -> GuardResult:
        auth_header: str = ctx.get("authorization", "")
        if not auth_header:
            if require_auth:
                return GuardResult(
                    allowed=False, guard_name="api_key",
                    reason="missing Authorization header",
                )
            return GuardResult(allowed=True, guard_name="api_key")
        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            if require_auth:
                return GuardResult(
                    allowed=False, guard_name="api_key",
                    reason="missing bearer token",
                )
            return GuardResult(allowed=True, guard_name="api_key")
        if allow_jwt_passthrough and _looks_like_jwt_bearer(token):
            return GuardResult(allowed=True, guard_name="api_key")
        result = api_key_mgr.authenticate(token)
        if not result.authenticated:
            return GuardResult(
                allowed=False, guard_name="api_key",
                reason=result.error or "Authentication failed",
            )
        # Bind tenant from authenticated key — prevents header spoofing.
        # In require_auth mode, reject if request supplies a different tenant.
        if result.tenant_id:
            request_tenant = ctx.get("tenant_id", "")
            if require_auth and request_tenant and request_tenant != result.tenant_id:
                return GuardResult(
                    allowed=False, guard_name="api_key",
                    reason=_bounded_tenant_mismatch_reason(),
                )
            ctx["tenant_id"] = result.tenant_id
        # Propagate principal identity for audit attribution
        ctx["authenticated_key_id"] = result.key_id
        ctx["authenticated_tenant_id"] = result.tenant_id
        return GuardResult(allowed=True, guard_name="api_key")
    return GovernanceGuard("api_key", check)


def create_rbac_guard(
    access_runtime: Any,
    *,
    require_identity: bool = False,
) -> GovernanceGuard:
    """Create an RBAC access-control guard.

    Resolves identity from auth context (JWT subject or API key ID),
    evaluates access via AccessRuntimeEngine, and blocks if denied.
    Unknown/unauthenticated requests pass through when require_identity=False.
    """
    import hashlib as _hashlib

    def check(ctx: dict[str, Any]) -> GuardResult:
        # Resolve identity from auth guards
        identity_id = ctx.get("authenticated_subject", "") or ctx.get("authenticated_key_id", "")
        if not identity_id:
            if require_identity:
                return GuardResult(
                    allowed=False, guard_name="rbac",
                    reason="no authenticated identity for RBAC evaluation",
                )
            return GuardResult(allowed=True, guard_name="rbac")

        endpoint = ctx.get("endpoint", "/unknown")
        method = ctx.get("method", "GET")

        # Map endpoint to resource_type (e.g., "/api/v1/llm/complete" → "llm")
        parts = endpoint.strip("/").split("/")
        resource_type = parts[2] if len(parts) > 2 else "api"

        # Generate deterministic request_id
        req_hash = _hashlib.sha256(f"{identity_id}:{endpoint}:{method}".encode()).hexdigest()[:12]
        request_id = f"rbac-{req_hash}"

        try:
            from mcoi_runtime.contracts.access_runtime import AccessDecision
            evaluation = access_runtime.evaluate_access(
                request_id,
                identity_id,
                resource_type=resource_type,
                action=method,
                scope_ref_id=ctx.get("tenant_id", "*"),
            )

            if evaluation.decision == AccessDecision.DENIED:
                return GuardResult(
                    allowed=False, guard_name="rbac",
                    reason="access denied",
                )
            if evaluation.decision == AccessDecision.REQUIRES_APPROVAL:
                return GuardResult(
                    allowed=False, guard_name="rbac",
                    reason="approval required",
                )
        except Exception as _rbac_exc:
            # Once an identity is present, RBAC evaluation failures must
            # fail closed rather than silently bypassing authorization.
            import logging as _rbac_log
            _rbac_log.getLogger("mcoi_runtime.core.governance_guard").warning(
                "RBAC evaluation failed for %s on %s (%s) [fail-closed]",
                identity_id,
                endpoint,
                type(_rbac_exc).__name__,
            )
            return GuardResult(
                allowed=False, guard_name="rbac",
                reason="RBAC evaluation failed",
            )

        # Propagate resolved identity for downstream audit
        ctx["rbac_identity_id"] = identity_id
        ctx["rbac_resource_type"] = resource_type
        return GuardResult(allowed=True, guard_name="rbac")
    return GovernanceGuard("rbac", check)
