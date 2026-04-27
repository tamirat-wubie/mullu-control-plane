"""
MUSIA tenant resolution + scope enforcement.

Two authenticators supported, evaluated in priority order:

1. **APIKeyManager** (since v4.3.1) — `Authorization: Bearer <api-key>`
2. **JWTAuthenticator** (added in v4.5.0) — `Authorization: Bearer <jwt>`

When both are configured, API-key is tried first; on failure (invalid /
not a recognized key), JWT is tried. This lets a deployment migrate
between auth schemes without a flag day.

Three modes:

- **Dev** — neither configured. `X-Tenant-ID` header trusted, defaults to `default`. No scope checks.
- **Auth** — at least one configured. `Authorization` required. Tenant comes from authenticated subject. `X-Tenant-ID` must match if supplied; mismatch → 403. Scope checks active via `require_scope(...)`.

Scopes:
- `musia.read` — list/get/snapshot summaries
- `musia.write` — create/delete constructs, run cycles
- `musia.admin` — tenant lifecycle, persistence administration
- `*` — wildcard: grants all (matches existing api_key_auth semantics)

Auth context flows via dependency return values (not ContextVar) because
FastAPI evaluates each Depends() in its own task context, which would
break ContextVar propagation between resolver and scope check.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, Header, HTTPException

from mcoi_runtime.core.api_key_auth import APIKeyManager
from mcoi_runtime.core.jwt_auth import JWTAuthenticator
from mcoi_runtime.substrate.registry_store import DEFAULT_TENANT


_log = logging.getLogger(__name__)


# Module-level state. configure_musia_*() install/uninstall.
_AUTH_MANAGER: Optional[APIKeyManager] = None
# A list of JWT authenticators rather than a single one, to support
# secret/key rotation: during a rotation window, both old and new
# authenticators are active; tokens signed with either pass. After
# rotation, the old authenticator is removed without a flag day.
_JWT_AUTHENTICATORS: list[JWTAuthenticator] = []

# v4.26.0: explicit dev-mode opt-in flag. When False (default), an
# unconfigured resolver call raises 503 instead of degrading to dev
# wildcard. The bootstrap path sets this based on MULLU_ENV; tests
# call ``configure_musia_dev_mode(True)`` to keep the historical
# wildcard behavior in unit tests.
#
# This is the F16 fix: pre-v4.26 the resolver short-circuited to
# wildcard whenever ``is_auth_configured()`` returned False, which
# happened in every default-bootstrap deployment because nobody called
# ``configure_musia_auth(...)`` from production wiring. Now production
# fails closed.
_DEV_MODE_ALLOWED: bool = False


# ---- Auth context ----


@dataclass(frozen=True)
class MusiaAuthContext:
    """Per-request auth context. Returned by resolve_musia_auth.

    In dev mode, ``auth_kind="dev"`` and ``scopes`` is treated as a
    wildcard (no scope enforcement happens).
    """

    tenant_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    subject: str = ""
    auth_kind: str = "dev"  # dev | api_key | jwt


# ---- Configuration ----


def configure_musia_auth(manager: APIKeyManager | None) -> None:
    """Install or uninstall the API-key manager. Pass None for dev mode."""
    global _AUTH_MANAGER
    _AUTH_MANAGER = manager


def configure_musia_jwt(
    authenticators: JWTAuthenticator | list[JWTAuthenticator] | None,
) -> None:
    """Install JWT authenticators. Accepts:

    - ``None`` — disable JWT auth
    - A single ``JWTAuthenticator`` — back-compat with v4.5.0 callers
    - A list of authenticators — rotation: tokens signed by any active
      key pass. Order matters: cheapest/most-likely-to-match first.
    """
    global _JWT_AUTHENTICATORS
    if authenticators is None:
        _JWT_AUTHENTICATORS = []
    elif isinstance(authenticators, JWTAuthenticator):
        _JWT_AUTHENTICATORS = [authenticators]
    else:
        # Accept any iterable of JWTAuthenticator
        _JWT_AUTHENTICATORS = list(authenticators)


def configured_jwt_authenticators() -> list[JWTAuthenticator]:
    """Inspect the current JWT authenticator list. Returns a copy."""
    return list(_JWT_AUTHENTICATORS)


def is_auth_configured() -> bool:
    """True if any authenticator is configured."""
    return _AUTH_MANAGER is not None or len(_JWT_AUTHENTICATORS) > 0


def configure_musia_dev_mode(allowed: bool) -> None:
    """Allow / disallow the dev-wildcard branch in ``resolve_musia_auth``.

    v4.26.0+. The bootstrap path calls ``configure_musia_dev_mode(True)``
    only when ``MULLU_ENV == "local_dev"`` and no real authenticator was
    wired. Tests also call this. In ``pilot``/``production`` it stays
    False, so a missing ``configure_musia_auth(...)`` produces a 503
    instead of a wildcard pass-through.
    """
    global _DEV_MODE_ALLOWED
    _DEV_MODE_ALLOWED = bool(allowed)


def dev_mode_allowed() -> bool:
    """Inspect the current dev-mode flag. Test-only."""
    return _DEV_MODE_ALLOWED


# ---- Helpers ----


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, value = parts
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def _try_api_key(token: str) -> MusiaAuthContext | None:
    if _AUTH_MANAGER is None:
        return None
    res = _AUTH_MANAGER.authenticate(token)
    if not res.authenticated:
        return None
    if not res.tenant_id:
        _log.error("MUSIA auth: API-key %s has no tenant_id", res.key_id)
        return None
    return MusiaAuthContext(
        tenant_id=res.tenant_id,
        scopes=frozenset(res.scopes),
        subject=res.key_id,
        auth_kind="api_key",
    )


def _try_jwt(token: str) -> MusiaAuthContext | None:
    """Try each configured JWT authenticator in order. First match wins.

    During a key rotation window, two (or more) authenticators are active.
    A token signed by any of them passes — operators rotate by adding a
    new authenticator, waiting for old tokens to expire, then removing
    the old authenticator.
    """
    for authenticator in _JWT_AUTHENTICATORS:
        res = authenticator.validate(token)
        if not res.authenticated:
            continue
        if not res.tenant_id:
            _log.error(
                "MUSIA auth: JWT subject %s has no tenant_id claim",
                res.subject,
            )
            continue
        return MusiaAuthContext(
            tenant_id=res.tenant_id,
            scopes=frozenset(res.scopes),
            subject=res.subject,
            auth_kind="jwt",
        )
    return None


# ---- Resolver ----


def resolve_musia_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> MusiaAuthContext:
    """Full auth resolver. Returns the request's MusiaAuthContext.

    Used by ``resolve_musia_tenant`` and ``require_scope``. Routes that
    only need the tenant_id should depend on ``resolve_musia_tenant``
    instead.
    """
    # No authenticators configured.
    if not is_auth_configured():
        # v4.26.0: fail-closed unless dev mode was explicitly allowed.
        # Pre-v4.26 this branch always activated, which is the F16 bug:
        # the bootstrap path never called ``configure_musia_auth(...)``,
        # so every MUSIA endpoint accepted unauthenticated wildcard
        # requests in production. Now production must opt in to dev
        # mode (it shouldn't), tests can still call
        # ``configure_musia_dev_mode(True)``.
        if not _DEV_MODE_ALLOWED:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "musia_auth_not_configured",
                    "remedy": (
                        "Wire configure_musia_auth(api_key_mgr) and/or "
                        "configure_musia_jwt(jwt_authenticator) at startup, "
                        "or set MULLU_ENV=local_dev to enable dev mode."
                    ),
                },
            )
        tid = (x_tenant_id or DEFAULT_TENANT).strip()
        if not tid:
            raise HTTPException(status_code=400, detail="X-Tenant-ID is empty")
        # Dev: pretend wildcard scope so scope checks become no-ops
        return MusiaAuthContext(
            tenant_id=tid,
            scopes=frozenset({"*"}),
            auth_kind="dev",
        )

    # Auth mode — Authorization required
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization: Bearer <api-key|jwt> required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try API-key first, then JWT.
    ctx = _try_api_key(token) or _try_jwt(token)
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail="authentication failed: invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # X-Tenant-ID must match if supplied
    if x_tenant_id is not None:
        claimed = x_tenant_id.strip()
        if claimed and claimed != ctx.tenant_id:
            _log.warning(
                "MUSIA auth: X-Tenant-ID spoof — auth_kind=%s subject=%s "
                "authenticated_tenant=%s claimed_tenant=%s",
                ctx.auth_kind,
                ctx.subject,
                ctx.tenant_id,
                claimed,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "X-Tenant-ID does not match authenticated tenant",
                    "authenticated_tenant": ctx.tenant_id,
                    "claimed_tenant": claimed,
                },
            )

    return ctx


def resolve_musia_tenant(
    ctx: MusiaAuthContext = Depends(resolve_musia_auth),
) -> str:
    """Compatibility shim: routes that don't need scope just want tenant_id."""
    return ctx.tenant_id


# ---- Scope enforcement ----


def _scope_allows(granted: frozenset[str], required: str) -> bool:
    """Wildcard `*` grants all. Otherwise exact match is required."""
    return "*" in granted or required in granted


def require_scope(scope: str):
    """Build a FastAPI dependency that enforces a scope.

    In dev mode (no auth configured), `auth_kind="dev"` and the resolver
    grants wildcard scopes — checks are no-ops. In auth mode, the request
    must carry a token whose scopes include either ``scope`` exactly or
    ``*`` (wildcard).

    Returns a dependency that yields ``tenant_id`` on success.
    """

    def _enforcer(
        ctx: MusiaAuthContext = Depends(resolve_musia_auth),
    ) -> str:
        if not _scope_allows(ctx.scopes, scope):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": f"missing scope: {scope}",
                    "subject": ctx.subject,
                    "granted_scopes": sorted(ctx.scopes),
                },
            )
        return ctx.tenant_id

    return _enforcer


# Pre-built scope dependencies for common cases.
require_read = require_scope("musia.read")
require_write = require_scope("musia.write")
require_admin = require_scope("musia.admin")
