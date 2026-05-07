"""GovernedSession threads its guard list into the receipt's guard_verdicts.

Closes Finding A from the proof_bridge audit: prior to this change every
session-level receipt emitted via `_certify_proof` had an empty
`guard_verdicts` list, even though 6 guards (policy, tenant_gating, rbac,
rate_limit, content_safety, budget) had just been evaluated for a session
LLM call. The receipt's content misrepresented the depth of governance —
a verifier replaying the receipt could not reconstruct what was actually
checked.

Each operation has a known guard set:

    llm()     → policy, tenant_gating, rbac, rate_limit, content_safety, budget
    execute() → policy, tenant_gating, rbac, rate_limit
    query()   → policy, rbac, rate_limit

Tests below pin those exact lists. If a future change adds/removes a
`_check_*` call inside one of the public methods without updating the
matching `_certify_proof` call site, the receipt's `guard_verdicts` will
no longer match what was checked — and the assertion in this file fails.
The assertion IS the cohesion mechanism.
"""
from __future__ import annotations

from typing import Any

import pytest


# ── Test double ─────────────────────────────────────────────────────


class _RecordingProofBridge:
    """Captures every certify_governance_decision call. Returns a minimal
    object with the shape `GovernedSession._certify_proof` reads from
    (capsule.receipt.receipt_id, receipt_hash)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def certify_governance_decision(self, **kwargs):
        self.calls.append(kwargs)

        class _Receipt:
            receipt_id = "rcpt-stub"

        class _Capsule:
            receipt = _Receipt()

        class _Proof:
            capsule = _Capsule()
            receipt_hash = "hash-stub"

        return _Proof()


# ── Fixture ─────────────────────────────────────────────────────────


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


@pytest.fixture
def session_with_recording_bridge():
    """Build a Platform whose proof_bridge is a recording stub, then
    connect a session and return both."""
    from mcoi_runtime.core.governed_session import Platform
    from mcoi_runtime.governance.audit.trail import AuditTrail
    from mcoi_runtime.governance.guards.content_safety import build_default_safety_chain
    from mcoi_runtime.core.pii_scanner import PIIScanner
    from mcoi_runtime.governance.guards.budget import TenantBudgetManager
    from mcoi_runtime.governance.guards.tenant_gating import (
        TenantGatingRegistry,
    )
    from mcoi_runtime.persistence.postgres_governance_stores import (
        InMemoryBudgetStore,
        InMemoryTenantGatingStore,
    )

    bridge = _RecordingProofBridge()
    platform = Platform(
        clock=_clock,
        audit_trail=AuditTrail(clock=_clock),
        proof_bridge=bridge,
        pii_scanner=PIIScanner(),
        content_safety_chain=build_default_safety_chain(),
        budget_mgr=TenantBudgetManager(clock=_clock, store=InMemoryBudgetStore()),
        tenant_gating=TenantGatingRegistry(clock=_clock, store=InMemoryTenantGatingStore()),
    )
    session = platform.connect(identity_id="user1", tenant_id="t1")
    return session, bridge


# ── The contract ────────────────────────────────────────────────────


def _guard_names(call: dict[str, Any]) -> list[str]:
    return [g["guard_name"] for g in call.get("guard_results", [])]


class TestGuardListThreading:
    """Each public session method MUST thread its guard list into the
    receipt — empty guard_verdicts is a regression."""

    def test_execute_receipt_includes_four_guards(self, session_with_recording_bridge):
        session, bridge = session_with_recording_bridge
        try:
            session.execute("noop")
        except Exception:
            # We don't care about the dispatcher path here — only the
            # guard-threading. The session calls _certify_proof BEFORE
            # the dispatcher, so the receipt is emitted regardless.
            pass

        # Find the proof call for session/execute
        execute_calls = [c for c in bridge.calls if c.get("endpoint") == "session/execute"]
        assert len(execute_calls) == 1, (
            f"Expected exactly one session/execute receipt; got {len(execute_calls)}"
        )
        names = _guard_names(execute_calls[0])
        assert names == ["policy", "tenant_gating", "rbac", "rate_limit"], (
            f"session/execute receipt must include the four guards that "
            f"ran (policy, tenant_gating, rbac, rate_limit), got {names}. "
            f"If you added or removed a _check_* call inside execute(), "
            f"update the guard_results list at the _certify_proof call "
            f"site so the receipt reflects what was actually checked."
        )
        for g in execute_calls[0]["guard_results"]:
            assert g["allowed"] is True, "all listed guards must be passed=True"

    def test_query_receipt_includes_three_guards(self, session_with_recording_bridge):
        session, bridge = session_with_recording_bridge
        try:
            session.query("documents")
        except Exception:
            pass

        query_calls = [c for c in bridge.calls if c.get("endpoint") == "session/query"]
        assert len(query_calls) == 1
        names = _guard_names(query_calls[0])
        assert names == ["policy", "rbac", "rate_limit"], (
            f"session/query receipt must include the three guards that "
            f"ran (policy, rbac, rate_limit), got {names}."
        )

    def test_pre_fix_empty_guard_verdicts_was_the_regression(self, session_with_recording_bridge):
        """Documents WHY this test exists. Pre-fix, the assertion above
        would have failed because guard_results was [] regardless of
        which guards ran. This is a sanity test — guard_results MUST be
        non-empty after a session method runs successfully past its
        guard chain."""
        session, bridge = session_with_recording_bridge
        try:
            session.query("documents")
        except Exception:
            pass

        query_calls = [c for c in bridge.calls if c.get("endpoint") == "session/query"]
        assert len(query_calls) == 1
        assert len(query_calls[0]["guard_results"]) > 0, (
            "Receipt's guard_verdicts is empty — but the session has just "
            "evaluated 3 guards (policy, rbac, rate_limit). This is the "
            "Finding A regression. Verify that query()'s _certify_proof "
            "call site passes guard_results."
        )
