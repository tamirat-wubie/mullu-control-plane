"""Purpose: verify governance guard-chain bounded error invariants.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, PRS.
Dependencies: mcoi_runtime.governance.guards.chain.
Invariants:
  - Guard exceptions surface only bounded type-level reasons.
  - Tenant mismatch rejects with a constant reason.
  - Sensitive tenant and backend details do not escape through denial reasons.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.governance.guards.chain import (
    GovernanceGuard,
    GovernanceGuardChain,
    GuardResult,
    create_jwt_guard,
)


SENSITIVE_TENANT = "tenant-secret-alpha"
SENSITIVE_BACKEND_DETAIL = "postgres://operator:secret@example.internal/db"


def test_guard_exception_reason_is_bounded_to_exception_type() -> None:
    def exploding_guard(_: dict[str, object]) -> GuardResult:
        raise RuntimeError(f"backend unavailable at {SENSITIVE_BACKEND_DETAIL}")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("store", exploding_guard))

    result = chain.evaluate({"tenant_id": SENSITIVE_TENANT, "endpoint": "/api/private"})

    assert result.allowed is False
    assert result.blocking_guard == "store"
    assert result.reason == "guard error (RuntimeError)"
    assert SENSITIVE_BACKEND_DETAIL not in result.reason
    assert SENSITIVE_TENANT not in result.reason
    assert result.results[0].detail == {"error_type": "RuntimeError"}


def test_guard_timeout_reason_is_bounded_to_exception_type() -> None:
    def timeout_guard(_: dict[str, object]) -> GuardResult:
        raise TimeoutError(f"timed out while loading {SENSITIVE_TENANT}")

    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("budget", timeout_guard))

    result = chain.evaluate({"tenant_id": SENSITIVE_TENANT, "endpoint": "/api/private"})

    assert result.allowed is False
    assert result.blocking_guard == "budget"
    assert result.reason == "guard timeout (TimeoutError)"
    assert SENSITIVE_TENANT not in result.reason
    assert result.results[0].detail == {"error_type": "TimeoutError"}


@dataclass(frozen=True, slots=True)
class _JWTResult:
    authenticated: bool
    tenant_id: str
    subject: str = "subject-secret"
    scopes: frozenset[str] = frozenset()
    error: str = ""


class _JWTAuthenticator:
    def validate(self, token: str) -> _JWTResult:
        assert token == "header.payload.signature"
        return _JWTResult(authenticated=True, tenant_id="tenant-from-token")


def test_jwt_tenant_mismatch_reason_is_constant_and_bounded() -> None:
    guard = create_jwt_guard(_JWTAuthenticator(), require_auth=True)
    context = {
        "authorization": "Bearer header.payload.signature",
        "tenant_id": SENSITIVE_TENANT,
        "tenant_id_explicit": True,
    }

    result = guard.check(context)

    assert result.allowed is False
    assert result.guard_name == "jwt"
    assert result.reason == "tenant mismatch"
    assert SENSITIVE_TENANT not in result.reason
    assert "tenant-from-token" not in result.reason
    assert "subject-secret" not in result.reason
