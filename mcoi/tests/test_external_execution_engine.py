"""Purpose: comprehensive tests for ExternalExecutionEngine.
Governance scope: governed execution of external tools and agents with
    sandboxing, retry, timeout, cancellation, and receipt tracking.
Dependencies: pytest, event_spine, external_execution, contracts.
Invariants:
  - Every execution references a tenant.
  - Duplicate IDs are rejected fail-closed.
  - Terminal states block further mutations.
  - Cross-tenant access is blocked fail-closed.
  - All outputs are frozen.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.external_execution import ExternalExecutionEngine
from mcoi_runtime.contracts.external_execution import (
    CredentialMode,
    ExecutionClosureReport,
    ExecutionFailure,
    ExecutionKind,
    ExecutionPolicy,
    ExecutionReceipt,
    ExecutionRequest,
    ExecutionResult,
    ExecutionRiskLevel,
    ExecutionSnapshot,
    ExecutionStatus,
    ExecutionTarget,
    ExecutionTrace,
    ExecutionViolation,
    RetryDisposition,
    SandboxDisposition,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(es: EventSpineEngine) -> ExternalExecutionEngine:
    return ExternalExecutionEngine(es)


@pytest.fixture
def seeded(engine: ExternalExecutionEngine) -> ExternalExecutionEngine:
    """Engine with one target registered for tenant T1."""
    engine.register_target("tgt-1", "T1", "Tool Alpha")
    return engine


@pytest.fixture
def seeded_with_policy(seeded: ExternalExecutionEngine) -> ExternalExecutionEngine:
    """Engine with target + policy (risk_threshold=HIGH)."""
    seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.HIGH)
    return seeded


@pytest.fixture
def seeded_with_request(seeded: ExternalExecutionEngine) -> ExternalExecutionEngine:
    """Engine with target + PENDING request."""
    seeded.request_execution("req-1", "T1", "tgt-1")
    return seeded


@pytest.fixture
def running_request(seeded_with_request: ExternalExecutionEngine) -> ExternalExecutionEngine:
    """Engine with target + RUNNING request."""
    seeded_with_request.start_execution("req-1")
    return seeded_with_request


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    def test_accepts_event_spine(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        assert eng.target_count == 0

    def test_rejects_none(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionEngine(None)  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionEngine("not-an-engine")  # type: ignore[arg-type]

    def test_rejects_dict(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionEngine({})  # type: ignore[arg-type]

    def test_rejects_int(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionEngine(42)  # type: ignore[arg-type]

    def test_rejects_list(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionEngine([])  # type: ignore[arg-type]


# ===================================================================
# 2. Initial property counts
# ===================================================================


class TestInitialCounts:
    def test_target_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.target_count == 0

    def test_request_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.request_count == 0

    def test_receipt_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.receipt_count == 0

    def test_result_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.result_count == 0

    def test_failure_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.failure_count == 0

    def test_trace_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.trace_count == 0

    def test_violation_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.violation_count == 0

    def test_policy_count_zero(self, engine: ExternalExecutionEngine) -> None:
        assert engine.policy_count == 0


# ===================================================================
# 3. register_target
# ===================================================================


class TestRegisterTarget:
    def test_basic_registration(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "My Tool")
        assert isinstance(t, ExecutionTarget)
        assert t.target_id == "tgt-1"
        assert t.tenant_id == "T1"
        assert t.display_name == "My Tool"

    def test_default_kind(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert t.kind == ExecutionKind.TOOL

    def test_agent_kind(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Agent", kind=ExecutionKind.AGENT)
        assert t.kind == ExecutionKind.AGENT

    def test_api_call_kind(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "API", kind=ExecutionKind.API_CALL)
        assert t.kind == ExecutionKind.API_CALL

    def test_script_kind(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Script", kind=ExecutionKind.SCRIPT)
        assert t.kind == ExecutionKind.SCRIPT

    def test_webhook_kind(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "WH", kind=ExecutionKind.WEBHOOK)
        assert t.kind == ExecutionKind.WEBHOOK

    def test_default_sandbox(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert t.sandbox_default == SandboxDisposition.SANDBOXED

    def test_privileged_sandbox(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", sandbox_default=SandboxDisposition.PRIVILEGED)
        assert t.sandbox_default == SandboxDisposition.PRIVILEGED

    def test_isolated_sandbox(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", sandbox_default=SandboxDisposition.ISOLATED)
        assert t.sandbox_default == SandboxDisposition.ISOLATED

    def test_restricted_sandbox(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", sandbox_default=SandboxDisposition.RESTRICTED)
        assert t.sandbox_default == SandboxDisposition.RESTRICTED

    def test_default_credential_mode(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert t.credential_mode == CredentialMode.NONE

    def test_token_credential(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", credential_mode=CredentialMode.TOKEN)
        assert t.credential_mode == CredentialMode.TOKEN

    def test_certificate_credential(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", credential_mode=CredentialMode.CERTIFICATE)
        assert t.credential_mode == CredentialMode.CERTIFICATE

    def test_delegated_credential(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", credential_mode=CredentialMode.DELEGATED)
        assert t.credential_mode == CredentialMode.DELEGATED

    def test_ephemeral_credential(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", credential_mode=CredentialMode.EPHEMERAL)
        assert t.credential_mode == CredentialMode.EPHEMERAL

    def test_default_max_retries(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert t.max_retries == 3

    def test_custom_max_retries(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", max_retries=5)
        assert t.max_retries == 5

    def test_default_timeout_ms(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert t.timeout_ms == 30000

    def test_custom_timeout_ms(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", timeout_ms=60000)
        assert t.timeout_ms == 60000

    def test_default_capability_ref(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert t.capability_ref == "default"

    def test_custom_capability_ref(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool", capability_ref="cap-xyz")
        assert t.capability_ref == "cap-xyz"

    def test_registered_at_populated(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        assert len(t.registered_at) > 0

    def test_target_count_increments(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "Tool1")
        engine.register_target("tgt-2", "T1", "Tool2")
        assert engine.target_count == 2

    def test_duplicate_target_raises(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "Tool")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate target_id"):
            engine.register_target("tgt-1", "T1", "Tool2")

    def test_emits_event(self, es: EventSpineEngine, engine: ExternalExecutionEngine) -> None:
        before = es.event_count
        engine.register_target("tgt-1", "T1", "Tool")
        assert es.event_count == before + 1

    def test_target_is_frozen(self, engine: ExternalExecutionEngine) -> None:
        t = engine.register_target("tgt-1", "T1", "Tool")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.display_name = "Changed"  # type: ignore[misc]

    def test_multiple_tenants(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "Tool A")
        engine.register_target("tgt-2", "T2", "Tool B")
        assert engine.target_count == 2


# ===================================================================
# 4. get_target
# ===================================================================


class TestGetTarget:
    def test_get_existing(self, seeded: ExternalExecutionEngine) -> None:
        t = seeded.get_target("tgt-1")
        assert t.target_id == "tgt-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown target_id"):
            engine.get_target("nope")

    def test_returns_frozen(self, seeded: ExternalExecutionEngine) -> None:
        t = seeded.get_target("tgt-1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.target_id = "x"  # type: ignore[misc]


# ===================================================================
# 5. targets_for_tenant
# ===================================================================


class TestTargetsForTenant:
    def test_returns_tuple(self, seeded: ExternalExecutionEngine) -> None:
        result = seeded.targets_for_tenant("T1")
        assert isinstance(result, tuple)

    def test_correct_count(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T1", "B")
        engine.register_target("tgt-3", "T2", "C")
        assert len(engine.targets_for_tenant("T1")) == 2
        assert len(engine.targets_for_tenant("T2")) == 1

    def test_empty_for_unknown_tenant(self, engine: ExternalExecutionEngine) -> None:
        assert engine.targets_for_tenant("unknown") == ()

    def test_isolates_tenants(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        t1 = engine.targets_for_tenant("T1")
        assert all(t.tenant_id == "T1" for t in t1)


# ===================================================================
# 6. register_policy
# ===================================================================


class TestRegisterPolicy:
    def test_basic_policy(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert isinstance(p, ExecutionPolicy)
        assert p.policy_id == "pol-1"
        assert p.tenant_id == "T1"
        assert p.target_id == "tgt-1"

    def test_default_risk_threshold(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert p.risk_threshold == ExecutionRiskLevel.HIGH

    def test_custom_risk_threshold_low(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        assert p.risk_threshold == ExecutionRiskLevel.LOW

    def test_custom_risk_threshold_medium(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.MEDIUM)
        assert p.risk_threshold == ExecutionRiskLevel.MEDIUM

    def test_custom_risk_threshold_critical(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.CRITICAL)
        assert p.risk_threshold == ExecutionRiskLevel.CRITICAL

    def test_default_max_retries(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert p.max_retries == 3

    def test_custom_max_retries(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1", max_retries=10)
        assert p.max_retries == 10

    def test_default_timeout_ms(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert p.timeout_ms == 30000

    def test_default_sandbox_required(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert p.sandbox_required == SandboxDisposition.SANDBOXED

    def test_default_credential_mode(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert p.credential_mode == CredentialMode.NONE

    def test_duplicate_policy_raises(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate policy_id"):
            seeded.register_policy("pol-1", "T1", "tgt-1")

    def test_unknown_target_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown target_id"):
            engine.register_policy("pol-1", "T1", "nonexistent")

    def test_policy_count_increments(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1")
        assert seeded.policy_count == 1

    def test_emits_event(self, es: EventSpineEngine, seeded: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded.register_policy("pol-1", "T1", "tgt-1")
        assert es.event_count == before + 1

    def test_policy_is_frozen(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.policy_id = "changed"  # type: ignore[misc]

    def test_created_at_populated(self, seeded: ExternalExecutionEngine) -> None:
        p = seeded.register_policy("pol-1", "T1", "tgt-1")
        assert len(p.created_at) > 0


# ===================================================================
# 7. get_policy
# ===================================================================


class TestGetPolicy:
    def test_get_existing(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1")
        p = seeded.get_policy("pol-1")
        assert p.policy_id == "pol-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown policy_id"):
            engine.get_policy("nope")


# ===================================================================
# 8. policies_for_target
# ===================================================================


class TestPoliciesForTarget:
    def test_returns_tuple(self, seeded: ExternalExecutionEngine) -> None:
        assert isinstance(seeded.policies_for_target("tgt-1"), tuple)

    def test_finds_policies(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1")
        seeded.register_policy("pol-2", "T1", "tgt-1")
        assert len(seeded.policies_for_target("tgt-1")) == 2

    def test_empty_for_no_policies(self, seeded: ExternalExecutionEngine) -> None:
        assert seeded.policies_for_target("tgt-1") == ()


# ===================================================================
# 9. request_execution — happy path
# ===================================================================


class TestRequestExecution:
    def test_basic_request(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        assert isinstance(req, ExecutionRequest)
        assert req.request_id == "req-1"
        assert req.tenant_id == "T1"
        assert req.target_id == "tgt-1"
        assert req.status == ExecutionStatus.PENDING

    def test_default_kind(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        assert req.kind == ExecutionKind.TOOL

    def test_custom_kind_agent(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1", kind=ExecutionKind.AGENT)
        assert req.kind == ExecutionKind.AGENT

    def test_default_sandbox(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        assert req.sandbox == SandboxDisposition.SANDBOXED

    def test_custom_sandbox(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1", sandbox=SandboxDisposition.PRIVILEGED)
        assert req.sandbox == SandboxDisposition.PRIVILEGED

    def test_default_credential_mode(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        assert req.credential_mode == CredentialMode.NONE

    def test_default_risk_level(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        assert req.risk_level == ExecutionRiskLevel.LOW

    def test_request_count_increments(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T1", "tgt-1")
        assert seeded.request_count == 1

    def test_duplicate_request_raises(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T1", "tgt-1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate request_id"):
            seeded.request_execution("req-1", "T1", "tgt-1")

    def test_unknown_target_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown target_id"):
            engine.request_execution("req-1", "T1", "nonexistent")

    def test_emits_event(self, es: EventSpineEngine, seeded: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded.request_execution("req-1", "T1", "tgt-1")
        assert es.event_count == before + 1

    def test_request_is_frozen(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.status = ExecutionStatus.RUNNING  # type: ignore[misc]

    def test_requested_at_populated(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1")
        assert len(req.requested_at) > 0


# ===================================================================
# 10. Cross-tenant blocking
# ===================================================================


class TestCrossTenantBlocking:
    def test_cross_tenant_returns_cancelled(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T2", "tgt-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_cross_tenant_creates_violation(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T2", "tgt-1")
        assert seeded.violation_count == 1

    def test_cross_tenant_violation_operation(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T2", "tgt-1")
        viols = seeded.violations_for_tenant("T2")
        assert len(viols) == 1
        assert viols[0].operation == "cross_tenant_blocked"

    def test_cross_tenant_violation_reason_mentions_owner(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T2", "tgt-1")
        viols = seeded.violations_for_tenant("T2")
        assert "T1" in viols[0].reason

    def test_cross_tenant_request_still_stored(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T2", "tgt-1")
        assert seeded.request_count == 1

    def test_cross_tenant_emits_event(self, es: EventSpineEngine, seeded: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded.request_execution("req-1", "T2", "tgt-1")
        assert es.event_count > before

    def test_cross_tenant_preserves_risk_level(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T2", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert req.risk_level == ExecutionRiskLevel.CRITICAL

    def test_cross_tenant_preserves_kind(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T2", "tgt-1", kind=ExecutionKind.AGENT)
        assert req.kind == ExecutionKind.AGENT


# ===================================================================
# 11. Risk policy blocking
# ===================================================================


class TestRiskPolicyBlocking:
    def test_risk_exceeds_returns_cancelled(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        req = seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert req.status == ExecutionStatus.CANCELLED

    def test_risk_exceeds_creates_violation(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert seeded_with_policy.violation_count == 1

    def test_risk_exceeds_violation_operation(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        viols = seeded_with_policy.violations_for_tenant("T1")
        assert viols[0].operation == "risk_exceeded"

    def test_risk_exceeds_violation_reason(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        viols = seeded_with_policy.violations_for_tenant("T1")
        assert "critical" in viols[0].reason
        assert "high" in viols[0].reason

    def test_risk_equal_threshold_allowed(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        req = seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.HIGH)
        assert req.status == ExecutionStatus.PENDING

    def test_risk_below_threshold_allowed(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        req = seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.LOW)
        assert req.status == ExecutionStatus.PENDING

    def test_risk_medium_below_high_allowed(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        req = seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.MEDIUM)
        assert req.status == ExecutionStatus.PENDING

    def test_risk_low_threshold_blocks_medium(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        req = seeded.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.MEDIUM)
        assert req.status == ExecutionStatus.CANCELLED

    def test_risk_low_threshold_blocks_high(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        req = seeded.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.HIGH)
        assert req.status == ExecutionStatus.CANCELLED

    def test_risk_low_threshold_blocks_critical(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        req = seeded.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert req.status == ExecutionStatus.CANCELLED

    def test_risk_low_threshold_allows_low(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        req = seeded.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.LOW)
        assert req.status == ExecutionStatus.PENDING

    def test_critical_threshold_allows_all(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.CRITICAL)
        for i, rl in enumerate(ExecutionRiskLevel):
            req = seeded.request_execution(f"req-{i}", "T1", "tgt-1", risk_level=rl)
            assert req.status == ExecutionStatus.PENDING

    def test_no_policy_allows_any_risk(self, seeded: ExternalExecutionEngine) -> None:
        req = seeded.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert req.status == ExecutionStatus.PENDING

    def test_risk_emits_event(self, es: EventSpineEngine, seeded_with_policy: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert es.event_count > before


# ===================================================================
# 12. get_request
# ===================================================================


class TestGetRequest:
    def test_get_existing(self, seeded_with_request: ExternalExecutionEngine) -> None:
        req = seeded_with_request.get_request("req-1")
        assert req.request_id == "req-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.get_request("nope")


# ===================================================================
# 13. requests_for_tenant
# ===================================================================


class TestRequestsForTenant:
    def test_returns_tuple(self, seeded: ExternalExecutionEngine) -> None:
        assert isinstance(seeded.requests_for_tenant("T1"), tuple)

    def test_correct_count(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T1", "tgt-1")
        seeded.request_execution("req-2", "T1", "tgt-1")
        assert len(seeded.requests_for_tenant("T1")) == 2

    def test_empty_for_unknown_tenant(self, engine: ExternalExecutionEngine) -> None:
        assert engine.requests_for_tenant("unknown") == ()

    def test_isolates_tenants(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.request_execution("req-2", "T2", "tgt-2")
        assert len(engine.requests_for_tenant("T1")) == 1
        assert len(engine.requests_for_tenant("T2")) == 1


# ===================================================================
# 14. approve_execution
# ===================================================================


class TestApproveExecution:
    def test_approve_pending(self, seeded_with_request: ExternalExecutionEngine) -> None:
        req = seeded_with_request.approve_execution("req-1")
        assert req.status == ExecutionStatus.APPROVED

    def test_approve_updates_store(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        assert seeded_with_request.get_request("req-1").status == ExecutionStatus.APPROVED

    def test_approve_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.approve_execution("req-1")
        assert es.event_count == before + 1

    def test_approve_returns_frozen(self, seeded_with_request: ExternalExecutionEngine) -> None:
        req = seeded_with_request.approve_execution("req-1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.status = ExecutionStatus.RUNNING  # type: ignore[misc]

    def test_approve_completed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.approve_execution("req-1")

    def test_approve_failed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.approve_execution("req-1")

    def test_approve_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded_with_request.approve_execution("req-1")

    def test_approve_timed_out_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.approve_execution("req-1")

    def test_approve_running_raises(self, running_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="PENDING to approve"):
            running_request.approve_execution("req-1")

    def test_approve_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.approve_execution("nope")


# ===================================================================
# 15. start_execution
# ===================================================================


class TestStartExecution:
    def test_start_pending(self, seeded_with_request: ExternalExecutionEngine) -> None:
        req = seeded_with_request.start_execution("req-1")
        assert req.status == ExecutionStatus.RUNNING

    def test_start_approved(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        req = seeded_with_request.start_execution("req-1")
        assert req.status == ExecutionStatus.RUNNING

    def test_start_updates_store(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.start_execution("req-1")
        assert seeded_with_request.get_request("req-1").status == ExecutionStatus.RUNNING

    def test_start_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.start_execution("req-1")
        assert es.event_count == before + 1

    def test_start_completed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.start_execution("req-1")

    def test_start_failed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.start_execution("req-1")

    def test_start_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded_with_request.start_execution("req-1")

    def test_start_timed_out_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.start_execution("req-1")

    def test_start_running_raises(self, running_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="PENDING or APPROVED"):
            running_request.start_execution("req-1")

    def test_start_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.start_execution("nope")


# ===================================================================
# 16. cancel_execution
# ===================================================================


class TestCancelExecution:
    def test_cancel_pending(self, seeded_with_request: ExternalExecutionEngine) -> None:
        req = seeded_with_request.cancel_execution("req-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_cancel_approved(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        req = seeded_with_request.cancel_execution("req-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_cancel_running(self, running_request: ExternalExecutionEngine) -> None:
        req = running_request.cancel_execution("req-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_cancel_updates_store(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        assert seeded_with_request.get_request("req-1").status == ExecutionStatus.CANCELLED

    def test_cancel_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.cancel_execution("req-1")
        assert es.event_count == before + 1

    def test_cancel_completed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.cancel_execution("req-1")

    def test_cancel_failed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.cancel_execution("req-1")

    def test_cancel_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded_with_request.cancel_execution("req-1")

    def test_cancel_timed_out_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            running_request.cancel_execution("req-1")

    def test_cancel_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.cancel_execution("nope")


# ===================================================================
# 17. timeout_execution
# ===================================================================


class TestTimeoutExecution:
    def test_timeout_running(self, running_request: ExternalExecutionEngine) -> None:
        req = running_request.timeout_execution("req-1")
        assert req.status == ExecutionStatus.TIMED_OUT

    def test_timeout_updates_store(self, running_request: ExternalExecutionEngine) -> None:
        running_request.timeout_execution("req-1")
        assert running_request.get_request("req-1").status == ExecutionStatus.TIMED_OUT

    def test_timeout_emits_event(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        running_request.timeout_execution("req-1")
        assert es.event_count == before + 1

    def test_timeout_pending_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to timeout"):
            seeded_with_request.timeout_execution("req-1")

    def test_timeout_approved_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to timeout"):
            seeded_with_request.timeout_execution("req-1")

    def test_timeout_completed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to timeout"):
            running_request.timeout_execution("req-1")

    def test_timeout_failed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to timeout"):
            running_request.timeout_execution("req-1")

    def test_timeout_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to timeout"):
            seeded_with_request.timeout_execution("req-1")

    def test_timeout_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.timeout_execution("nope")


# ===================================================================
# 18. complete_execution
# ===================================================================


class TestCompleteExecution:
    def test_complete_running(self, running_request: ExternalExecutionEngine) -> None:
        req = running_request.complete_execution("req-1")
        assert req.status == ExecutionStatus.COMPLETED

    def test_complete_updates_store(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        assert running_request.get_request("req-1").status == ExecutionStatus.COMPLETED

    def test_complete_emits_event(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        running_request.complete_execution("req-1")
        assert es.event_count == before + 1

    def test_complete_pending_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to complete"):
            seeded_with_request.complete_execution("req-1")

    def test_complete_approved_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to complete"):
            seeded_with_request.complete_execution("req-1")

    def test_complete_failed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to complete"):
            running_request.complete_execution("req-1")

    def test_complete_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to complete"):
            seeded_with_request.complete_execution("req-1")

    def test_complete_timed_out_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to complete"):
            running_request.complete_execution("req-1")

    def test_complete_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.complete_execution("nope")


# ===================================================================
# 19. fail_execution
# ===================================================================


class TestFailExecution:
    def test_fail_running(self, running_request: ExternalExecutionEngine) -> None:
        req = running_request.fail_execution("req-1")
        assert req.status == ExecutionStatus.FAILED

    def test_fail_updates_store(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        assert running_request.get_request("req-1").status == ExecutionStatus.FAILED

    def test_fail_emits_event(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        running_request.fail_execution("req-1")
        assert es.event_count == before + 1

    def test_fail_pending_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to fail"):
            seeded_with_request.fail_execution("req-1")

    def test_fail_approved_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to fail"):
            seeded_with_request.fail_execution("req-1")

    def test_fail_completed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to fail"):
            running_request.fail_execution("req-1")

    def test_fail_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING to fail"):
            seeded_with_request.fail_execution("req-1")

    def test_fail_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.fail_execution("nope")


# ===================================================================
# 20. record_receipt
# ===================================================================


class TestRecordReceipt:
    def test_basic_receipt(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert isinstance(r, ExecutionReceipt)
        assert r.receipt_id == "rcpt-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "T1"

    def test_default_status(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert r.status == ExecutionStatus.COMPLETED

    def test_custom_status(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1", status=ExecutionStatus.FAILED)
        assert r.status == ExecutionStatus.FAILED

    def test_default_duration_ms(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert r.duration_ms == 0.0

    def test_custom_duration_ms(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1", duration_ms=150.5)
        assert r.duration_ms == 150.5

    def test_default_output_ref(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert r.output_ref == "none"

    def test_custom_output_ref(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1", output_ref="s3://bucket/key")
        assert r.output_ref == "s3://bucket/key"

    def test_duplicate_receipt_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate receipt_id"):
            seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")

    def test_unknown_request_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.record_receipt("rcpt-1", "nonexistent", "T1")

    def test_receipt_count_increments(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert seeded_with_request.receipt_count == 1

    def test_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_receipt_is_frozen(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.receipt_id = "changed"  # type: ignore[misc]

    def test_completed_at_populated(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert len(r.completed_at) > 0


# ===================================================================
# 21. get_receipt
# ===================================================================


class TestGetReceipt:
    def test_get_existing(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        r = seeded_with_request.get_receipt("rcpt-1")
        assert r.receipt_id == "rcpt-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown receipt_id"):
            engine.get_receipt("nope")


# ===================================================================
# 22. receipts_for_request
# ===================================================================


class TestReceiptsForRequest:
    def test_returns_tuple(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert isinstance(seeded_with_request.receipts_for_request("req-1"), tuple)

    def test_finds_receipts(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        seeded_with_request.record_receipt("rcpt-2", "req-1", "T1")
        assert len(seeded_with_request.receipts_for_request("req-1")) == 2

    def test_empty_for_no_receipts(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert seeded_with_request.receipts_for_request("req-1") == ()


# ===================================================================
# 23. record_result
# ===================================================================


class TestRecordResult:
    def test_basic_result(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1")
        assert isinstance(r, ExecutionResult)
        assert r.result_id == "res-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "T1"

    def test_default_success(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1")
        assert r.success is True

    def test_success_false(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1", success=False)
        assert r.success is False

    def test_default_output_summary(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1")
        assert r.output_summary == "completed"

    def test_custom_output_summary(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1", output_summary="done with warnings")
        assert r.output_summary == "done with warnings"

    def test_default_confidence(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1")
        assert r.confidence == 1.0

    def test_custom_confidence(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1", confidence=0.85)
        assert r.confidence == 0.85

    def test_duplicate_result_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_result("res-1", "req-1", "T1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate result_id"):
            seeded_with_request.record_result("res-1", "req-1", "T1")

    def test_unknown_request_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.record_result("res-1", "nonexistent", "T1")

    def test_result_count_increments(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_result("res-1", "req-1", "T1")
        assert seeded_with_request.result_count == 1

    def test_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_result("res-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_result_is_frozen(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.result_id = "changed"  # type: ignore[misc]

    def test_created_at_populated(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1")
        assert len(r.created_at) > 0


# ===================================================================
# 24. get_result
# ===================================================================


class TestGetResult:
    def test_get_existing(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_result("res-1", "req-1", "T1")
        r = seeded_with_request.get_result("res-1")
        assert r.result_id == "res-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown result_id"):
            engine.get_result("nope")


# ===================================================================
# 25. results_for_request
# ===================================================================


class TestResultsForRequest:
    def test_returns_tuple(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert isinstance(seeded_with_request.results_for_request("req-1"), tuple)

    def test_finds_results(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_result("res-1", "req-1", "T1")
        seeded_with_request.record_result("res-2", "req-1", "T1")
        assert len(seeded_with_request.results_for_request("req-1")) == 2

    def test_empty_for_no_results(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert seeded_with_request.results_for_request("req-1") == ()


# ===================================================================
# 26. record_failure
# ===================================================================


class TestRecordFailure:
    def test_basic_failure(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert isinstance(f, ExecutionFailure)
        assert f.failure_id == "fail-1"
        assert f.request_id == "req-1"
        assert f.tenant_id == "T1"

    def test_default_reason(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert f.reason == "unknown"

    def test_custom_reason(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1", reason="timeout")
        assert f.reason == "timeout"

    def test_default_retry_disposition(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert f.retry_disposition == RetryDisposition.NO_RETRY

    def test_custom_retry_disposition(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure(
            "fail-1", "req-1", "T1", retry_disposition=RetryDisposition.RETRY_PENDING
        )
        assert f.retry_disposition == RetryDisposition.RETRY_PENDING

    def test_retried_disposition(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure(
            "fail-1", "req-1", "T1", retry_disposition=RetryDisposition.RETRIED
        )
        assert f.retry_disposition == RetryDisposition.RETRIED

    def test_exhausted_disposition(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure(
            "fail-1", "req-1", "T1", retry_disposition=RetryDisposition.EXHAUSTED
        )
        assert f.retry_disposition == RetryDisposition.EXHAUSTED

    def test_default_retry_count(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert f.retry_count == 0

    def test_custom_retry_count(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1", retry_count=3)
        assert f.retry_count == 3

    def test_duplicate_failure_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_failure("fail-1", "req-1", "T1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate failure_id"):
            seeded_with_request.record_failure("fail-1", "req-1", "T1")

    def test_unknown_request_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.record_failure("fail-1", "nonexistent", "T1")

    def test_failure_count_increments(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert seeded_with_request.failure_count == 1

    def test_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_failure_is_frozen(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.reason = "changed"  # type: ignore[misc]

    def test_failed_at_populated(self, seeded_with_request: ExternalExecutionEngine) -> None:
        f = seeded_with_request.record_failure("fail-1", "req-1", "T1")
        assert len(f.failed_at) > 0


# ===================================================================
# 27. get_failure
# ===================================================================


class TestGetFailure:
    def test_get_existing(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_failure("fail-1", "req-1", "T1")
        f = seeded_with_request.get_failure("fail-1")
        assert f.failure_id == "fail-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown failure_id"):
            engine.get_failure("nope")


# ===================================================================
# 28. failures_for_request
# ===================================================================


class TestFailuresForRequest:
    def test_returns_tuple(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert isinstance(seeded_with_request.failures_for_request("req-1"), tuple)

    def test_finds_failures(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_failure("fail-1", "req-1", "T1")
        seeded_with_request.record_failure("fail-2", "req-1", "T1")
        assert len(seeded_with_request.failures_for_request("req-1")) == 2

    def test_empty_for_no_failures(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert seeded_with_request.failures_for_request("req-1") == ()


# ===================================================================
# 29. record_trace
# ===================================================================


class TestRecordTrace:
    def test_basic_trace(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert isinstance(t, ExecutionTrace)
        assert t.trace_id == "tr-1"
        assert t.request_id == "req-1"
        assert t.tenant_id == "T1"

    def test_default_step_name(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert t.step_name == "execute"

    def test_custom_step_name(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1", step_name="validate")
        assert t.step_name == "validate"

    def test_default_duration_ms(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert t.duration_ms == 0.0

    def test_custom_duration_ms(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1", duration_ms=250.0)
        assert t.duration_ms == 250.0

    def test_default_status(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert t.status == ExecutionStatus.COMPLETED

    def test_custom_status(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1", status=ExecutionStatus.FAILED)
        assert t.status == ExecutionStatus.FAILED

    def test_duplicate_trace_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate trace_id"):
            seeded_with_request.record_trace("tr-1", "req-1", "T1")

    def test_unknown_request_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.record_trace("tr-1", "nonexistent", "T1")

    def test_trace_count_increments(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert seeded_with_request.trace_count == 1

    def test_emits_event(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_trace_is_frozen(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.trace_id = "changed"  # type: ignore[misc]

    def test_created_at_populated(self, seeded_with_request: ExternalExecutionEngine) -> None:
        t = seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert len(t.created_at) > 0


# ===================================================================
# 30. get_trace
# ===================================================================


class TestGetTrace:
    def test_get_existing(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        t = seeded_with_request.get_trace("tr-1")
        assert t.trace_id == "tr-1"

    def test_get_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown trace_id"):
            engine.get_trace("nope")


# ===================================================================
# 31. traces_for_request
# ===================================================================


class TestTracesForRequest:
    def test_returns_tuple(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert isinstance(seeded_with_request.traces_for_request("req-1"), tuple)

    def test_finds_traces(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        seeded_with_request.record_trace("tr-2", "req-1", "T1")
        assert len(seeded_with_request.traces_for_request("req-1")) == 2

    def test_empty_for_no_traces(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert seeded_with_request.traces_for_request("req-1") == ()


# ===================================================================
# 32. retry_execution
# ===================================================================


class TestRetryExecution:
    def test_retry_failed_resets_to_pending(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        req = running_request.retry_execution("req-1")
        assert req.status == ExecutionStatus.PENDING

    def test_retry_timed_out_resets_to_pending(self, running_request: ExternalExecutionEngine) -> None:
        running_request.timeout_execution("req-1")
        req = running_request.retry_execution("req-1")
        assert req.status == ExecutionStatus.PENDING

    def test_retry_updates_store(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        running_request.retry_execution("req-1")
        assert running_request.get_request("req-1").status == ExecutionStatus.PENDING

    def test_retry_emits_event(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        before = es.event_count
        running_request.retry_execution("req-1")
        assert es.event_count > before

    def test_retry_pending_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="FAILED or TIMED_OUT"):
            seeded_with_request.retry_execution("req-1")

    def test_retry_approved_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.approve_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="FAILED or TIMED_OUT"):
            seeded_with_request.retry_execution("req-1")

    def test_retry_running_raises(self, running_request: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="FAILED or TIMED_OUT"):
            running_request.retry_execution("req-1")

    def test_retry_completed_raises(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="FAILED or TIMED_OUT"):
            running_request.retry_execution("req-1")

    def test_retry_cancelled_raises(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="FAILED or TIMED_OUT"):
            seeded_with_request.retry_execution("req-1")

    def test_retry_unknown_raises(self, engine: ExternalExecutionEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.retry_execution("nope")

    def test_retry_exhausted_by_failures(self, running_request: ExternalExecutionEngine) -> None:
        """max_retries=3 on target; record 3 failures -> retry returns original (terminal)."""
        running_request.fail_execution("req-1")
        running_request.record_failure("f1", "req-1", "T1")
        running_request.record_failure("f2", "req-1", "T1")
        running_request.record_failure("f3", "req-1", "T1")
        req = running_request.retry_execution("req-1")
        # Should still be FAILED — exhausted
        assert req.status == ExecutionStatus.FAILED

    def test_retry_exhausted_records_failure(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        running_request.record_failure("f1", "req-1", "T1")
        running_request.record_failure("f2", "req-1", "T1")
        running_request.record_failure("f3", "req-1", "T1")
        before_failures = running_request.failure_count
        running_request.retry_execution("req-1")
        assert running_request.failure_count == before_failures + 1

    def test_retry_exhausted_failure_has_exhausted_disposition(
        self, running_request: ExternalExecutionEngine
    ) -> None:
        running_request.fail_execution("req-1")
        running_request.record_failure("f1", "req-1", "T1")
        running_request.record_failure("f2", "req-1", "T1")
        running_request.record_failure("f3", "req-1", "T1")
        running_request.retry_execution("req-1")
        all_failures = running_request.failures_for_request("req-1")
        exhausted = [f for f in all_failures if f.retry_disposition == RetryDisposition.EXHAUSTED]
        assert len(exhausted) >= 1

    def test_retry_below_max_succeeds(self, running_request: ExternalExecutionEngine) -> None:
        """2 failures < max_retries=3 -> retry resets to PENDING."""
        running_request.fail_execution("req-1")
        running_request.record_failure("f1", "req-1", "T1")
        running_request.record_failure("f2", "req-1", "T1")
        req = running_request.retry_execution("req-1")
        assert req.status == ExecutionStatus.PENDING

    def test_retry_with_zero_max_retries(self, engine: ExternalExecutionEngine, es: EventSpineEngine) -> None:
        """Target with max_retries=0 => first retry exhausts."""
        engine.register_target("tgt-z", "T1", "Zero Retry Tool", max_retries=0)
        engine.request_execution("req-z", "T1", "tgt-z")
        engine.start_execution("req-z")
        engine.fail_execution("req-z")
        req = engine.retry_execution("req-z")
        assert req.status == ExecutionStatus.FAILED

    def test_retry_preserves_fields(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        req = running_request.retry_execution("req-1")
        assert req.request_id == "req-1"
        assert req.tenant_id == "T1"
        assert req.target_id == "tgt-1"
        assert req.kind == ExecutionKind.TOOL
        assert req.sandbox == SandboxDisposition.SANDBOXED


# ===================================================================
# 33. detect_execution_violations
# ===================================================================


class TestDetectExecutionViolations:
    def test_no_violations_returns_empty(self, seeded: ExternalExecutionEngine) -> None:
        result = seeded.detect_execution_violations("T1")
        assert result == ()

    def test_running_no_trace(self, running_request: ExternalExecutionEngine) -> None:
        viols = running_request.detect_execution_violations("T1")
        assert len(viols) == 1
        assert viols[0].operation == "running_no_trace"

    def test_running_with_trace_no_violation(self, running_request: ExternalExecutionEngine) -> None:
        running_request.record_trace("tr-1", "req-1", "T1")
        viols = running_request.detect_execution_violations("T1")
        assert len(viols) == 0

    def test_failed_no_failure_record(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        viols = running_request.detect_execution_violations("T1")
        assert len(viols) == 1
        assert viols[0].operation == "failed_no_failure_record"

    def test_failed_with_failure_record_no_violation(self, running_request: ExternalExecutionEngine) -> None:
        running_request.fail_execution("req-1")
        running_request.record_failure("f1", "req-1", "T1")
        viols = running_request.detect_execution_violations("T1")
        assert len(viols) == 0

    def test_completed_no_result(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        viols = running_request.detect_execution_violations("T1")
        assert len(viols) == 1
        assert viols[0].operation == "completed_no_result"

    def test_completed_with_result_no_violation(self, running_request: ExternalExecutionEngine) -> None:
        running_request.complete_execution("req-1")
        running_request.record_result("res-1", "req-1", "T1")
        viols = running_request.detect_execution_violations("T1")
        assert len(viols) == 0

    def test_idempotent_second_call_empty(self, running_request: ExternalExecutionEngine) -> None:
        viols1 = running_request.detect_execution_violations("T1")
        assert len(viols1) == 1
        viols2 = running_request.detect_execution_violations("T1")
        assert len(viols2) == 0

    def test_idempotent_violation_count_unchanged(self, running_request: ExternalExecutionEngine) -> None:
        running_request.detect_execution_violations("T1")
        count_after_first = running_request.violation_count
        running_request.detect_execution_violations("T1")
        assert running_request.violation_count == count_after_first

    def test_violations_tenant_isolation(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        engine.request_execution("req-2", "T2", "tgt-2")
        engine.start_execution("req-2")
        viols_t1 = engine.detect_execution_violations("T1")
        viols_t2 = engine.detect_execution_violations("T2")
        assert len(viols_t1) == 1
        assert len(viols_t2) == 1
        assert viols_t1[0].tenant_id == "T1"
        assert viols_t2[0].tenant_id == "T2"

    def test_returns_tuple_type(self, seeded: ExternalExecutionEngine) -> None:
        result = seeded.detect_execution_violations("T1")
        assert isinstance(result, tuple)

    def test_violation_is_frozen(self, running_request: ExternalExecutionEngine) -> None:
        viols = running_request.detect_execution_violations("T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            viols[0].operation = "changed"  # type: ignore[misc]

    def test_violation_reason_mentions_request(self, running_request: ExternalExecutionEngine) -> None:
        viols = running_request.detect_execution_violations("T1")
        assert "req-1" in viols[0].reason

    def test_emits_event_on_new_violations(
        self, es: EventSpineEngine, running_request: ExternalExecutionEngine
    ) -> None:
        before = es.event_count
        running_request.detect_execution_violations("T1")
        assert es.event_count > before

    def test_no_event_on_no_new_violations(
        self, es: EventSpineEngine, seeded: ExternalExecutionEngine
    ) -> None:
        before = es.event_count
        seeded.detect_execution_violations("T1")
        assert es.event_count == before

    def test_multiple_violations_in_one_call(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        # running + no trace
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        # failed + no failure
        engine.request_execution("req-2", "T1", "tgt-1")
        engine.start_execution("req-2")
        engine.fail_execution("req-2")
        # completed + no result
        engine.request_execution("req-3", "T1", "tgt-1")
        engine.start_execution("req-3")
        engine.complete_execution("req-3")
        viols = engine.detect_execution_violations("T1")
        assert len(viols) == 3
        ops = {v.operation for v in viols}
        assert ops == {"running_no_trace", "failed_no_failure_record", "completed_no_result"}


# ===================================================================
# 34. violations_for_tenant
# ===================================================================


class TestViolationsForTenant:
    def test_returns_tuple(self, engine: ExternalExecutionEngine) -> None:
        assert isinstance(engine.violations_for_tenant("T1"), tuple)

    def test_finds_violations(self, running_request: ExternalExecutionEngine) -> None:
        running_request.detect_execution_violations("T1")
        assert len(running_request.violations_for_tenant("T1")) == 1

    def test_empty_for_no_violations(self, engine: ExternalExecutionEngine) -> None:
        assert engine.violations_for_tenant("T1") == ()

    def test_includes_cross_tenant_violations(self, seeded: ExternalExecutionEngine) -> None:
        seeded.request_execution("req-1", "T2", "tgt-1")
        viols = seeded.violations_for_tenant("T2")
        assert len(viols) == 1

    def test_includes_risk_violations(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        viols = seeded_with_policy.violations_for_tenant("T1")
        assert len(viols) == 1


# ===================================================================
# 35. execution_snapshot
# ===================================================================


class TestExecutionSnapshot:
    def test_empty_snapshot(self, engine: ExternalExecutionEngine) -> None:
        snap = engine.execution_snapshot("snap-1", "T1")
        assert isinstance(snap, ExecutionSnapshot)
        assert snap.snapshot_id == "snap-1"
        assert snap.tenant_id == "T1"
        assert snap.total_targets == 0
        assert snap.total_requests == 0
        assert snap.total_receipts == 0
        assert snap.total_failures == 0
        assert snap.total_results == 0
        assert snap.total_traces == 0
        assert snap.total_violations == 0

    def test_snapshot_counts_targets(self, seeded: ExternalExecutionEngine) -> None:
        snap = seeded.execution_snapshot("snap-1", "T1")
        assert snap.total_targets == 1

    def test_snapshot_counts_requests(self, seeded_with_request: ExternalExecutionEngine) -> None:
        snap = seeded_with_request.execution_snapshot("snap-1", "T1")
        assert snap.total_requests == 1

    def test_snapshot_counts_receipts(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        snap = seeded_with_request.execution_snapshot("snap-1", "T1")
        assert snap.total_receipts == 1

    def test_snapshot_counts_failures(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_failure("f1", "req-1", "T1")
        snap = seeded_with_request.execution_snapshot("snap-1", "T1")
        assert snap.total_failures == 1

    def test_snapshot_counts_results(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_result("res-1", "req-1", "T1")
        snap = seeded_with_request.execution_snapshot("snap-1", "T1")
        assert snap.total_results == 1

    def test_snapshot_counts_traces(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        snap = seeded_with_request.execution_snapshot("snap-1", "T1")
        assert snap.total_traces == 1

    def test_snapshot_counts_violations(self, running_request: ExternalExecutionEngine) -> None:
        running_request.detect_execution_violations("T1")
        snap = running_request.execution_snapshot("snap-1", "T1")
        assert snap.total_violations == 1

    def test_snapshot_tenant_isolation(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        snap1 = engine.execution_snapshot("snap-1", "T1")
        snap2 = engine.execution_snapshot("snap-2", "T2")
        assert snap1.total_targets == 1
        assert snap2.total_targets == 1

    def test_snapshot_is_frozen(self, engine: ExternalExecutionEngine) -> None:
        snap = engine.execution_snapshot("snap-1", "T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.total_targets = 99  # type: ignore[misc]

    def test_snapshot_emits_event(self, es: EventSpineEngine, engine: ExternalExecutionEngine) -> None:
        before = es.event_count
        engine.execution_snapshot("snap-1", "T1")
        assert es.event_count == before + 1

    def test_captured_at_populated(self, engine: ExternalExecutionEngine) -> None:
        snap = engine.execution_snapshot("snap-1", "T1")
        assert len(snap.captured_at) > 0


# ===================================================================
# 36. closure_report
# ===================================================================


class TestClosureReport:
    def test_empty_report(self, engine: ExternalExecutionEngine) -> None:
        rpt = engine.closure_report("rpt-1", "T1")
        assert isinstance(rpt, ExecutionClosureReport)
        assert rpt.report_id == "rpt-1"
        assert rpt.tenant_id == "T1"
        assert rpt.total_targets == 0
        assert rpt.total_requests == 0
        assert rpt.total_receipts == 0
        assert rpt.total_failures == 0
        assert rpt.total_results == 0
        assert rpt.total_violations == 0

    def test_report_counts_targets(self, seeded: ExternalExecutionEngine) -> None:
        rpt = seeded.closure_report("rpt-1", "T1")
        assert rpt.total_targets == 1

    def test_report_counts_requests(self, seeded_with_request: ExternalExecutionEngine) -> None:
        rpt = seeded_with_request.closure_report("rpt-1", "T1")
        assert rpt.total_requests == 1

    def test_report_counts_receipts(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        rpt = seeded_with_request.closure_report("rpt-1", "T1")
        assert rpt.total_receipts == 1

    def test_report_counts_failures(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_failure("f1", "req-1", "T1")
        rpt = seeded_with_request.closure_report("rpt-1", "T1")
        assert rpt.total_failures == 1

    def test_report_counts_results(self, seeded_with_request: ExternalExecutionEngine) -> None:
        seeded_with_request.record_result("res-1", "req-1", "T1")
        rpt = seeded_with_request.closure_report("rpt-1", "T1")
        assert rpt.total_results == 1

    def test_report_counts_violations(self, running_request: ExternalExecutionEngine) -> None:
        running_request.detect_execution_violations("T1")
        rpt = running_request.closure_report("rpt-1", "T1")
        assert rpt.total_violations == 1

    def test_report_tenant_isolation(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        rpt1 = engine.closure_report("rpt-1", "T1")
        rpt2 = engine.closure_report("rpt-2", "T2")
        assert rpt1.total_targets == 1
        assert rpt2.total_targets == 1

    def test_report_is_frozen(self, engine: ExternalExecutionEngine) -> None:
        rpt = engine.closure_report("rpt-1", "T1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            rpt.total_targets = 99  # type: ignore[misc]

    def test_report_emits_event(self, es: EventSpineEngine, engine: ExternalExecutionEngine) -> None:
        before = es.event_count
        engine.closure_report("rpt-1", "T1")
        assert es.event_count == before + 1

    def test_created_at_populated(self, engine: ExternalExecutionEngine) -> None:
        rpt = engine.closure_report("rpt-1", "T1")
        assert len(rpt.created_at) > 0


# ===================================================================
# 37. state_hash
# ===================================================================


class TestStateHash:
    def test_empty_hash_is_sha256(self, engine: ExternalExecutionEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", h)

    def test_deterministic(self, engine: ExternalExecutionEngine) -> None:
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_target(self, engine: ExternalExecutionEngine) -> None:
        h1 = engine.state_hash()
        engine.register_target("tgt-1", "T1", "Tool")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_request(self, seeded: ExternalExecutionEngine) -> None:
        h1 = seeded.state_hash()
        seeded.request_execution("req-1", "T1", "tgt-1")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_after_receipt(self, seeded_with_request: ExternalExecutionEngine) -> None:
        h1 = seeded_with_request.state_hash()
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        h2 = seeded_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_result(self, seeded_with_request: ExternalExecutionEngine) -> None:
        h1 = seeded_with_request.state_hash()
        seeded_with_request.record_result("res-1", "req-1", "T1")
        h2 = seeded_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_failure(self, seeded_with_request: ExternalExecutionEngine) -> None:
        h1 = seeded_with_request.state_hash()
        seeded_with_request.record_failure("f1", "req-1", "T1")
        h2 = seeded_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_trace(self, seeded_with_request: ExternalExecutionEngine) -> None:
        h1 = seeded_with_request.state_hash()
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        h2 = seeded_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self, running_request: ExternalExecutionEngine) -> None:
        h1 = running_request.state_hash()
        running_request.detect_execution_violations("T1")
        h2 = running_request.state_hash()
        assert h1 != h2

    def test_changes_after_status_change(self, seeded_with_request: ExternalExecutionEngine) -> None:
        h1 = seeded_with_request.state_hash()
        seeded_with_request.start_execution("req-1")
        h2 = seeded_with_request.state_hash()
        assert h1 != h2

    def test_same_ops_same_hash(self) -> None:
        """Two engines with identical operations produce the same hash."""
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        e1 = ExternalExecutionEngine(es1)
        e2 = ExternalExecutionEngine(es2)
        e1.register_target("tgt-1", "T1", "Tool")
        e2.register_target("tgt-1", "T1", "Tool")
        e1.request_execution("req-1", "T1", "tgt-1")
        e2.request_execution("req-1", "T1", "tgt-1")
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# 38. Golden scenario 1: service request -> sandboxed tool execution
# ===================================================================


class TestGoldenScenario1:
    def test_full_happy_path(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        # Register target
        tgt = eng.register_target("tgt-tool", "T1", "Calculator Tool", sandbox_default=SandboxDisposition.SANDBOXED)
        assert tgt.sandbox_default == SandboxDisposition.SANDBOXED

        # Request execution
        req = eng.request_execution("req-calc", "T1", "tgt-tool", sandbox=SandboxDisposition.SANDBOXED)
        assert req.status == ExecutionStatus.PENDING

        # Approve
        req = eng.approve_execution("req-calc")
        assert req.status == ExecutionStatus.APPROVED

        # Start
        req = eng.start_execution("req-calc")
        assert req.status == ExecutionStatus.RUNNING

        # Record trace
        eng.record_trace("tr-calc", "req-calc", "T1", step_name="compute", duration_ms=50.0)

        # Complete
        req = eng.complete_execution("req-calc")
        assert req.status == ExecutionStatus.COMPLETED

        # Record receipt
        rcpt = eng.record_receipt("rcpt-calc", "req-calc", "T1", duration_ms=55.0, output_ref="result-ref-1")
        assert rcpt.status == ExecutionStatus.COMPLETED

        # Record result
        result = eng.record_result("res-calc", "req-calc", "T1", success=True, output_summary="42", confidence=0.99)
        assert result.success is True
        assert result.confidence == 0.99

        # No violations
        viols = eng.detect_execution_violations("T1")
        assert len(viols) == 0

        # Snapshot
        snap = eng.execution_snapshot("snap-1", "T1")
        assert snap.total_targets == 1
        assert snap.total_requests == 1
        assert snap.total_receipts == 1
        assert snap.total_results == 1
        assert snap.total_traces == 1
        assert snap.total_violations == 0

    def test_full_happy_path_events_emitted(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.approve_execution("req-1")
        eng.start_execution("req-1")
        eng.record_trace("tr-1", "req-1", "T1")
        eng.complete_execution("req-1")
        eng.record_receipt("rcpt-1", "req-1", "T1")
        eng.record_result("res-1", "req-1", "T1")
        # Each step emits an event: register_target + request + approve + start + trace + complete + receipt + result = 8
        assert es.event_count == 8


# ===================================================================
# 39. Golden scenario 2: forbidden capability blocked by risk
# ===================================================================


class TestGoldenScenario2:
    def test_forbidden_capability_blocked(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-admin", "T1", "Admin Panel", capability_ref="admin_write")
        eng.register_policy("pol-strict", "T1", "tgt-admin", risk_threshold=ExecutionRiskLevel.LOW)

        req = eng.request_execution("req-danger", "T1", "tgt-admin", risk_level=ExecutionRiskLevel.HIGH)
        assert req.status == ExecutionStatus.CANCELLED

        viols = eng.violations_for_tenant("T1")
        assert len(viols) == 1
        assert viols[0].operation == "risk_exceeded"

    def test_forbidden_medium_blocked_by_low(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        req = eng.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.MEDIUM)
        assert req.status == ExecutionStatus.CANCELLED

    def test_forbidden_critical_blocked_by_medium(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.MEDIUM)
        req = eng.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert req.status == ExecutionStatus.CANCELLED


# ===================================================================
# 40. Golden scenario 3: timeout -> retry -> retry -> exhausted
# ===================================================================


class TestGoldenScenario3:
    def test_timeout_retry_exhausted(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-slow", "T1", "Slow Service", max_retries=2)

        # Attempt 1: timeout
        eng.request_execution("req-slow", "T1", "tgt-slow")
        eng.start_execution("req-slow")
        eng.timeout_execution("req-slow")
        assert eng.get_request("req-slow").status == ExecutionStatus.TIMED_OUT

        # Retry 1 (0 failures so far -> under max_retries=2)
        eng.retry_execution("req-slow")
        assert eng.get_request("req-slow").status == ExecutionStatus.PENDING

        # Attempt 2: fail
        eng.start_execution("req-slow")
        eng.fail_execution("req-slow")
        eng.record_failure("f1", "req-slow", "T1", reason="second_attempt_fail")

        # Retry 2 (1 failure < 2 -> allowed)
        eng.retry_execution("req-slow")
        assert eng.get_request("req-slow").status == ExecutionStatus.PENDING

        # Attempt 3: timeout again
        eng.start_execution("req-slow")
        eng.timeout_execution("req-slow")
        eng.record_failure("f2", "req-slow", "T1", reason="third_attempt_timeout")

        # Retry 3 (2 failures >= max_retries=2 -> exhausted)
        req = eng.retry_execution("req-slow")
        assert req.status == ExecutionStatus.TIMED_OUT  # stays terminal
        # Exhausted failure recorded
        exhausted = [f for f in eng.failures_for_request("req-slow")
                     if f.retry_disposition == RetryDisposition.EXHAUSTED]
        assert len(exhausted) == 1


# ===================================================================
# 41. Golden scenario 4: operator cancellation
# ===================================================================


class TestGoldenScenario4:
    def test_operator_cancels_pending(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.request_execution("req-1", "T1", "tgt-1")
        req = eng.cancel_execution("req-1")
        assert req.status == ExecutionStatus.CANCELLED

        # Record receipt for cancelled
        rcpt = eng.record_receipt("rcpt-cancel", "req-1", "T1", status=ExecutionStatus.CANCELLED)
        assert rcpt.status == ExecutionStatus.CANCELLED

        # Cannot modify further
        with pytest.raises(RuntimeCoreInvariantError):
            eng.start_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.approve_execution("req-1")

    def test_operator_cancels_running(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.start_execution("req-1")
        req = eng.cancel_execution("req-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_cancel_is_terminal(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.cancel_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.cancel_execution("req-1")


# ===================================================================
# 42. Golden scenario 5: orchestration step consumes result
# ===================================================================


class TestGoldenScenario5:
    def test_orchestration_step(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Code Runner")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.start_execution("req-1")
        eng.record_trace("tr-exec", "req-1", "T1", step_name="run_code", duration_ms=100.0)
        eng.complete_execution("req-1")
        eng.record_result("res-1", "req-1", "T1", success=True, output_summary="exit_code=0")

        # Orchestrator queries result
        results = eng.results_for_request("req-1")
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output_summary == "exit_code=0"

        # Record receipt referencing the result
        eng.record_receipt("rcpt-1", "req-1", "T1", duration_ms=110.0, output_ref="res-1")
        rcpt = eng.get_receipt("rcpt-1")
        assert rcpt.output_ref == "res-1"

    def test_multiple_results_for_one_request(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Multi-step")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.record_result("res-1", "req-1", "T1", output_summary="step1")
        eng.record_result("res-2", "req-1", "T1", output_summary="step2")
        assert len(eng.results_for_request("req-1")) == 2


# ===================================================================
# 43. Golden scenario 6: replay/restore determinism
# ===================================================================


class TestGoldenScenario6:
    def test_same_ops_same_state_hash(self) -> None:
        """Two engines with same operations produce same state_hash."""
        es1, es2 = EventSpineEngine(), EventSpineEngine()
        e1, e2 = ExternalExecutionEngine(es1), ExternalExecutionEngine(es2)

        for eng in (e1, e2):
            eng.register_target("tgt-1", "T1", "Tool")
            eng.request_execution("req-1", "T1", "tgt-1")
            eng.start_execution("req-1")
            eng.record_trace("tr-1", "req-1", "T1")
            eng.complete_execution("req-1")
            eng.record_result("res-1", "req-1", "T1")
            eng.record_receipt("rcpt-1", "req-1", "T1")
            eng.record_failure("f1", "req-1", "T1")

        assert e1.state_hash() == e2.state_hash()

    def test_different_ids_different_hash(self) -> None:
        es1, es2 = EventSpineEngine(), EventSpineEngine()
        e1, e2 = ExternalExecutionEngine(es1), ExternalExecutionEngine(es2)
        e1.register_target("tgt-1", "T1", "Tool")
        e2.register_target("tgt-2", "T1", "Tool")
        assert e1.state_hash() != e2.state_hash()

    def test_hash_includes_all_collections(self) -> None:
        """Adding to each collection changes the hash."""
        es = EventSpineEngine()
        eng = ExternalExecutionEngine(es)
        hashes = [eng.state_hash()]

        eng.register_target("tgt-1", "T1", "Tool")
        hashes.append(eng.state_hash())

        eng.request_execution("req-1", "T1", "tgt-1")
        hashes.append(eng.state_hash())

        eng.start_execution("req-1")
        hashes.append(eng.state_hash())

        eng.record_trace("tr-1", "req-1", "T1")
        hashes.append(eng.state_hash())

        eng.complete_execution("req-1")
        hashes.append(eng.state_hash())

        eng.record_result("res-1", "req-1", "T1")
        hashes.append(eng.state_hash())

        eng.record_receipt("rcpt-1", "req-1", "T1")
        hashes.append(eng.state_hash())

        eng.record_failure("f1", "req-1", "T1")
        hashes.append(eng.state_hash())

        eng.detect_execution_violations("T1")
        hashes.append(eng.state_hash())

        # At least 9 unique hashes (violations may not change if none detected)
        assert len(set(hashes)) >= len(hashes) - 1


# ===================================================================
# 44. Terminal state blocking — exhaustive matrix
# ===================================================================


class TestTerminalStateBlocking:
    """Ensure all four terminal states block approve, start, cancel."""

    @pytest.mark.parametrize("terminal", [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    ])
    def test_approve_blocked(self, engine: ExternalExecutionEngine, es: EventSpineEngine, terminal: ExecutionStatus) -> None:
        engine.register_target("tgt-1", "T1", "Tool")
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        if terminal == ExecutionStatus.COMPLETED:
            engine.complete_execution("req-1")
        elif terminal == ExecutionStatus.FAILED:
            engine.fail_execution("req-1")
        elif terminal == ExecutionStatus.CANCELLED:
            engine.cancel_execution("req-1")
        elif terminal == ExecutionStatus.TIMED_OUT:
            engine.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.approve_execution("req-1")

    @pytest.mark.parametrize("terminal", [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    ])
    def test_start_blocked(self, engine: ExternalExecutionEngine, es: EventSpineEngine, terminal: ExecutionStatus) -> None:
        engine.register_target("tgt-1", "T1", "Tool")
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        if terminal == ExecutionStatus.COMPLETED:
            engine.complete_execution("req-1")
        elif terminal == ExecutionStatus.FAILED:
            engine.fail_execution("req-1")
        elif terminal == ExecutionStatus.CANCELLED:
            engine.cancel_execution("req-1")
        elif terminal == ExecutionStatus.TIMED_OUT:
            engine.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_execution("req-1")

    @pytest.mark.parametrize("terminal", [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    ])
    def test_cancel_blocked(self, engine: ExternalExecutionEngine, es: EventSpineEngine, terminal: ExecutionStatus) -> None:
        engine.register_target("tgt-1", "T1", "Tool")
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        if terminal == ExecutionStatus.COMPLETED:
            engine.complete_execution("req-1")
        elif terminal == ExecutionStatus.FAILED:
            engine.fail_execution("req-1")
        elif terminal == ExecutionStatus.CANCELLED:
            engine.cancel_execution("req-1")
        elif terminal == ExecutionStatus.TIMED_OUT:
            engine.timeout_execution("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cancel_execution("req-1")


# ===================================================================
# 45. Multiple targets per tenant
# ===================================================================


class TestMultipleTargetsPerTenant:
    def test_three_targets_same_tenant(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-a", "T1", "A")
        engine.register_target("tgt-b", "T1", "B")
        engine.register_target("tgt-c", "T1", "C")
        assert engine.target_count == 3
        assert len(engine.targets_for_tenant("T1")) == 3

    def test_independent_requests(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-a", "T1", "A")
        engine.register_target("tgt-b", "T1", "B")
        engine.request_execution("req-a", "T1", "tgt-a")
        engine.request_execution("req-b", "T1", "tgt-b")
        assert engine.request_count == 2

    def test_each_request_has_correct_target(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-a", "T1", "A")
        engine.register_target("tgt-b", "T1", "B")
        ra = engine.request_execution("req-a", "T1", "tgt-a")
        rb = engine.request_execution("req-b", "T1", "tgt-b")
        assert ra.target_id == "tgt-a"
        assert rb.target_id == "tgt-b"


# ===================================================================
# 46. Multiple policies per target
# ===================================================================


class TestMultiplePoliciesPerTarget:
    def test_multiple_policies(self, seeded: ExternalExecutionEngine) -> None:
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.HIGH)
        seeded.register_policy("pol-2", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.MEDIUM)
        assert seeded.policy_count == 2

    def test_strictest_policy_wins(self, seeded: ExternalExecutionEngine) -> None:
        """When one policy has LOW threshold, MEDIUM request gets blocked."""
        seeded.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.CRITICAL)
        seeded.register_policy("pol-2", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.LOW)
        req = seeded.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.MEDIUM)
        assert req.status == ExecutionStatus.CANCELLED


# ===================================================================
# 47. Event emission counting
# ===================================================================


class TestEventEmissionCounting:
    def test_register_target_emits_one(self, es: EventSpineEngine, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "Tool")
        assert es.event_count == 1

    def test_register_policy_emits_one(self, es: EventSpineEngine, seeded: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded.register_policy("pol-1", "T1", "tgt-1")
        assert es.event_count == before + 1

    def test_request_execution_emits_one(self, es: EventSpineEngine, seeded: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded.request_execution("req-1", "T1", "tgt-1")
        assert es.event_count == before + 1

    def test_approve_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.approve_execution("req-1")
        assert es.event_count == before + 1

    def test_start_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.start_execution("req-1")
        assert es.event_count == before + 1

    def test_cancel_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.cancel_execution("req-1")
        assert es.event_count == before + 1

    def test_timeout_emits_one(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        running_request.timeout_execution("req-1")
        assert es.event_count == before + 1

    def test_complete_emits_one(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        running_request.complete_execution("req-1")
        assert es.event_count == before + 1

    def test_fail_emits_one(self, es: EventSpineEngine, running_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        running_request.fail_execution("req-1")
        assert es.event_count == before + 1

    def test_record_receipt_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_receipt("rcpt-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_record_result_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_result("res-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_record_failure_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_failure("f1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_record_trace_emits_one(self, es: EventSpineEngine, seeded_with_request: ExternalExecutionEngine) -> None:
        before = es.event_count
        seeded_with_request.record_trace("tr-1", "req-1", "T1")
        assert es.event_count == before + 1

    def test_snapshot_emits_one(self, es: EventSpineEngine, engine: ExternalExecutionEngine) -> None:
        before = es.event_count
        engine.execution_snapshot("snap-1", "T1")
        assert es.event_count == before + 1

    def test_closure_report_emits_one(self, es: EventSpineEngine, engine: ExternalExecutionEngine) -> None:
        before = es.event_count
        engine.closure_report("rpt-1", "T1")
        assert es.event_count == before + 1


# ===================================================================
# 48. Execution kind matrix
# ===================================================================


class TestExecutionKindMatrix:
    @pytest.mark.parametrize("kind", list(ExecutionKind))
    def test_register_target_with_kind(self, engine: ExternalExecutionEngine, kind: ExecutionKind) -> None:
        t = engine.register_target(f"tgt-{kind.value}", "T1", f"Tool {kind.value}", kind=kind)
        assert t.kind == kind

    @pytest.mark.parametrize("kind", list(ExecutionKind))
    def test_request_with_kind(self, seeded: ExternalExecutionEngine, kind: ExecutionKind) -> None:
        req = seeded.request_execution(f"req-{kind.value}", "T1", "tgt-1", kind=kind)
        assert req.kind == kind


# ===================================================================
# 49. SandboxDisposition matrix
# ===================================================================


class TestSandboxDispositionMatrix:
    @pytest.mark.parametrize("sd", list(SandboxDisposition))
    def test_target_sandbox(self, engine: ExternalExecutionEngine, sd: SandboxDisposition) -> None:
        t = engine.register_target(f"tgt-{sd.value}", "T1", "Tool", sandbox_default=sd)
        assert t.sandbox_default == sd

    @pytest.mark.parametrize("sd", list(SandboxDisposition))
    def test_request_sandbox(self, seeded: ExternalExecutionEngine, sd: SandboxDisposition) -> None:
        req = seeded.request_execution(f"req-{sd.value}", "T1", "tgt-1", sandbox=sd)
        assert req.sandbox == sd

    @pytest.mark.parametrize("sd", list(SandboxDisposition))
    def test_policy_sandbox(self, seeded: ExternalExecutionEngine, sd: SandboxDisposition) -> None:
        p = seeded.register_policy(f"pol-{sd.value}", "T1", "tgt-1", sandbox_required=sd)
        assert p.sandbox_required == sd


# ===================================================================
# 50. CredentialMode matrix
# ===================================================================


class TestCredentialModeMatrix:
    @pytest.mark.parametrize("cm", list(CredentialMode))
    def test_target_credential(self, engine: ExternalExecutionEngine, cm: CredentialMode) -> None:
        t = engine.register_target(f"tgt-{cm.value}", "T1", "Tool", credential_mode=cm)
        assert t.credential_mode == cm

    @pytest.mark.parametrize("cm", list(CredentialMode))
    def test_request_credential(self, seeded: ExternalExecutionEngine, cm: CredentialMode) -> None:
        req = seeded.request_execution(f"req-{cm.value}", "T1", "tgt-1", credential_mode=cm)
        assert req.credential_mode == cm

    @pytest.mark.parametrize("cm", list(CredentialMode))
    def test_policy_credential(self, seeded: ExternalExecutionEngine, cm: CredentialMode) -> None:
        p = seeded.register_policy(f"pol-{cm.value}", "T1", "tgt-1", credential_mode=cm)
        assert p.credential_mode == cm


# ===================================================================
# 51. Risk level matrix
# ===================================================================


class TestRiskLevelMatrix:
    @pytest.mark.parametrize("rl", list(ExecutionRiskLevel))
    def test_request_risk_level(self, seeded: ExternalExecutionEngine, rl: ExecutionRiskLevel) -> None:
        req = seeded.request_execution(f"req-{rl.value}", "T1", "tgt-1", risk_level=rl)
        assert req.risk_level == rl

    @pytest.mark.parametrize("rl", list(ExecutionRiskLevel))
    def test_policy_risk_threshold(self, seeded: ExternalExecutionEngine, rl: ExecutionRiskLevel) -> None:
        p = seeded.register_policy(f"pol-{rl.value}", "T1", "tgt-1", risk_threshold=rl)
        assert p.risk_threshold == rl


# ===================================================================
# 52. RetryDisposition matrix
# ===================================================================


class TestRetryDispositionMatrix:
    @pytest.mark.parametrize("rd", list(RetryDisposition))
    def test_failure_retry_disposition(self, seeded_with_request: ExternalExecutionEngine, rd: RetryDisposition) -> None:
        f = seeded_with_request.record_failure(f"fail-{rd.value}", "req-1", "T1", retry_disposition=rd)
        assert f.retry_disposition == rd


# ===================================================================
# 53. Status lifecycle through trace
# ===================================================================


class TestStatusLifecycleTrace:
    @pytest.mark.parametrize("status", list(ExecutionStatus))
    def test_trace_with_each_status(self, seeded_with_request: ExternalExecutionEngine, status: ExecutionStatus) -> None:
        t = seeded_with_request.record_trace(f"tr-{status.value}", "req-1", "T1", status=status)
        assert t.status == status


# ===================================================================
# 54. Snapshot vs closure report comparison
# ===================================================================


class TestSnapshotVsClosureComparison:
    def test_snapshot_and_closure_agree(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.start_execution("req-1")
        eng.complete_execution("req-1")
        eng.record_receipt("rcpt-1", "req-1", "T1")
        eng.record_result("res-1", "req-1", "T1")
        eng.record_failure("f1", "req-1", "T1")

        snap = eng.execution_snapshot("snap-1", "T1")
        rpt = eng.closure_report("rpt-1", "T1")

        assert snap.total_targets == rpt.total_targets
        assert snap.total_requests == rpt.total_requests
        assert snap.total_receipts == rpt.total_receipts
        assert snap.total_failures == rpt.total_failures
        assert snap.total_results == rpt.total_results

    def test_snapshot_has_traces_closure_does_not(self, es: EventSpineEngine) -> None:
        """Closure report doesn't include traces count."""
        eng = ExternalExecutionEngine(es)
        eng.register_target("tgt-1", "T1", "Tool")
        eng.request_execution("req-1", "T1", "tgt-1")
        eng.record_trace("tr-1", "req-1", "T1")
        snap = eng.execution_snapshot("snap-1", "T1")
        assert snap.total_traces == 1
        # Closure report doesn't have total_traces field
        rpt = eng.closure_report("rpt-1", "T1")
        assert not hasattr(rpt, "total_traces")


# ===================================================================
# 55. Large-scale batch operations
# ===================================================================


class TestBatchOperations:
    def test_many_targets(self, engine: ExternalExecutionEngine) -> None:
        for i in range(20):
            engine.register_target(f"tgt-{i}", "T1", f"Tool {i}")
        assert engine.target_count == 20

    def test_many_requests(self, seeded: ExternalExecutionEngine) -> None:
        for i in range(20):
            seeded.request_execution(f"req-{i}", "T1", "tgt-1")
        assert seeded.request_count == 20

    def test_many_receipts(self, seeded_with_request: ExternalExecutionEngine) -> None:
        for i in range(10):
            seeded_with_request.record_receipt(f"rcpt-{i}", "req-1", "T1")
        assert seeded_with_request.receipt_count == 10

    def test_many_results(self, seeded_with_request: ExternalExecutionEngine) -> None:
        for i in range(10):
            seeded_with_request.record_result(f"res-{i}", "req-1", "T1")
        assert seeded_with_request.result_count == 10

    def test_many_failures(self, seeded_with_request: ExternalExecutionEngine) -> None:
        for i in range(10):
            seeded_with_request.record_failure(f"fail-{i}", "req-1", "T1")
        assert seeded_with_request.failure_count == 10

    def test_many_traces(self, seeded_with_request: ExternalExecutionEngine) -> None:
        for i in range(10):
            seeded_with_request.record_trace(f"tr-{i}", "req-1", "T1")
        assert seeded_with_request.trace_count == 10

    def test_many_policies(self, seeded: ExternalExecutionEngine) -> None:
        for i in range(10):
            seeded.register_policy(f"pol-{i}", "T1", "tgt-1")
        assert seeded.policy_count == 10


# ===================================================================
# 56. Cross-tenant isolation with multiple tenants
# ===================================================================


class TestMultiTenantIsolation:
    def test_three_tenants(self, engine: ExternalExecutionEngine) -> None:
        for tid in ("T1", "T2", "T3"):
            engine.register_target(f"tgt-{tid}", tid, f"Tool for {tid}")
        for tid in ("T1", "T2", "T3"):
            engine.request_execution(f"req-{tid}", tid, f"tgt-{tid}")
        assert len(engine.targets_for_tenant("T1")) == 1
        assert len(engine.targets_for_tenant("T2")) == 1
        assert len(engine.targets_for_tenant("T3")) == 1
        assert len(engine.requests_for_tenant("T1")) == 1
        assert len(engine.requests_for_tenant("T2")) == 1
        assert len(engine.requests_for_tenant("T3")) == 1

    def test_cross_tenant_t2_to_t1(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        req = engine.request_execution("req-1", "T2", "tgt-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_cross_tenant_t3_to_t1(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        req = engine.request_execution("req-1", "T3", "tgt-1")
        assert req.status == ExecutionStatus.CANCELLED

    def test_snapshot_isolation(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        snap1 = engine.execution_snapshot("snap-1", "T1")
        snap2 = engine.execution_snapshot("snap-2", "T2")
        assert snap1.total_targets == 1
        assert snap2.total_targets == 1

    def test_closure_isolation(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.register_target("tgt-2", "T2", "B")
        rpt1 = engine.closure_report("rpt-1", "T1")
        rpt2 = engine.closure_report("rpt-2", "T2")
        assert rpt1.total_targets == 1
        assert rpt2.total_targets == 1

    def test_violation_isolation(self, engine: ExternalExecutionEngine) -> None:
        engine.register_target("tgt-1", "T1", "A")
        engine.request_execution("req-ct-1", "T2", "tgt-1")
        engine.request_execution("req-ct-2", "T3", "tgt-1")
        assert len(engine.violations_for_tenant("T2")) == 1
        assert len(engine.violations_for_tenant("T3")) == 1
        assert len(engine.violations_for_tenant("T1")) == 0


# ===================================================================
# 57. Retry with various max_retries settings
# ===================================================================


class TestRetryVariousMaxRetries:
    def test_max_retries_1(self, engine: ExternalExecutionEngine, es: EventSpineEngine) -> None:
        engine.register_target("tgt-1", "T1", "Tool", max_retries=1)
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        engine.fail_execution("req-1")
        # 0 failures => retry OK
        req = engine.retry_execution("req-1")
        assert req.status == ExecutionStatus.PENDING
        # Fail again, record failure
        engine.start_execution("req-1")
        engine.fail_execution("req-1")
        engine.record_failure("f1", "req-1", "T1")
        # 1 failure >= max_retries=1 => exhausted
        req = engine.retry_execution("req-1")
        assert req.status == ExecutionStatus.FAILED

    def test_max_retries_5(self, engine: ExternalExecutionEngine, es: EventSpineEngine) -> None:
        engine.register_target("tgt-1", "T1", "Tool", max_retries=5)
        engine.request_execution("req-1", "T1", "tgt-1")
        engine.start_execution("req-1")
        engine.fail_execution("req-1")
        # Record 4 failures
        for i in range(4):
            engine.record_failure(f"f{i}", "req-1", "T1")
        # 4 failures < 5 => retry OK
        req = engine.retry_execution("req-1")
        assert req.status == ExecutionStatus.PENDING
        # Record 5th failure
        engine.start_execution("req-1")
        engine.fail_execution("req-1")
        engine.record_failure("f4", "req-1", "T1")
        # 5 failures >= 5 => exhausted
        req = engine.retry_execution("req-1")
        assert req.status == ExecutionStatus.FAILED


# ===================================================================
# 58. Edge cases for state_hash
# ===================================================================


class TestStateHashEdgeCases:
    def test_empty_engine_hash(self, engine: ExternalExecutionEngine) -> None:
        h = engine.state_hash()
        assert len(h) == 64

    def test_hash_length_always_64(self, seeded_with_request: ExternalExecutionEngine) -> None:
        assert len(seeded_with_request.state_hash()) == 64

    def test_hash_is_hex(self, seeded_with_request: ExternalExecutionEngine) -> None:
        h = seeded_with_request.state_hash()
        assert re.fullmatch(r"[0-9a-f]+", h)

    def test_hash_after_cross_tenant_violation(self, seeded: ExternalExecutionEngine) -> None:
        h1 = seeded.state_hash()
        seeded.request_execution("req-1", "T2", "tgt-1")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_hash_after_risk_violation(self, seeded_with_policy: ExternalExecutionEngine) -> None:
        h1 = seeded_with_policy.state_hash()
        seeded_with_policy.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        h2 = seeded_with_policy.state_hash()
        assert h1 != h2


# ===================================================================
# 59. Receipt status values
# ===================================================================


class TestReceiptStatusValues:
    @pytest.mark.parametrize("status", list(ExecutionStatus))
    def test_receipt_with_each_status(self, seeded_with_request: ExternalExecutionEngine, status: ExecutionStatus) -> None:
        r = seeded_with_request.record_receipt(f"rcpt-{status.value}", "req-1", "T1", status=status)
        assert r.status == status


# ===================================================================
# 60. Result confidence range
# ===================================================================


class TestResultConfidenceRange:
    def test_confidence_zero(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1", confidence=0.0)
        assert r.confidence == 0.0

    def test_confidence_one(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1", confidence=1.0)
        assert r.confidence == 1.0

    def test_confidence_half(self, seeded_with_request: ExternalExecutionEngine) -> None:
        r = seeded_with_request.record_result("res-1", "req-1", "T1", confidence=0.5)
        assert r.confidence == 0.5


# ===================================================================
# 61. Trace step_name variations
# ===================================================================


class TestTraceStepNameVariations:
    @pytest.mark.parametrize("step", ["init", "validate", "execute", "finalize", "cleanup"])
    def test_various_step_names(self, seeded_with_request: ExternalExecutionEngine, step: str) -> None:
        t = seeded_with_request.record_trace(f"tr-{step}", "req-1", "T1", step_name=step)
        assert t.step_name == step


# ===================================================================
# 62. Comprehensive end-to-end with all engine operations
# ===================================================================


class TestComprehensiveEndToEnd:
    def test_all_operations(self, es: EventSpineEngine) -> None:
        eng = ExternalExecutionEngine(es)

        # Setup
        eng.register_target("tgt-1", "T1", "Calculator", kind=ExecutionKind.TOOL, max_retries=2)
        eng.register_policy("pol-1", "T1", "tgt-1", risk_threshold=ExecutionRiskLevel.HIGH)

        # Execute successfully
        eng.request_execution("req-1", "T1", "tgt-1", risk_level=ExecutionRiskLevel.LOW)
        eng.approve_execution("req-1")
        eng.start_execution("req-1")
        eng.record_trace("tr-1", "req-1", "T1", step_name="compute")
        eng.complete_execution("req-1")
        eng.record_result("res-1", "req-1", "T1", success=True, output_summary="42")
        eng.record_receipt("rcpt-1", "req-1", "T1", duration_ms=100.0, output_ref="res-1")

        # Execute and fail
        eng.request_execution("req-2", "T1", "tgt-1")
        eng.start_execution("req-2")
        eng.fail_execution("req-2")
        eng.record_failure("f1", "req-2", "T1", reason="connection_timeout")

        # Blocked by risk
        eng.request_execution("req-3", "T1", "tgt-1", risk_level=ExecutionRiskLevel.CRITICAL)
        assert eng.get_request("req-3").status == ExecutionStatus.CANCELLED

        # Cross-tenant blocked
        eng.request_execution("req-4", "T2", "tgt-1")
        assert eng.get_request("req-4").status == ExecutionStatus.CANCELLED

        # Snapshot
        snap = eng.execution_snapshot("snap-1", "T1")
        assert snap.total_targets == 1
        assert snap.total_requests == 3  # req-1, req-2, req-3

        # Detect violations
        viols = eng.detect_execution_violations("T1")
        # req-1: completed + has result -> OK
        # req-2: failed + has failure -> OK
        # req-3: cancelled -> no check needed
        assert len(viols) == 0

        # Closure report
        rpt = eng.closure_report("rpt-1", "T1")
        assert rpt.total_targets == 1
        assert rpt.total_violations >= 1  # risk violation from req-3

        # State hash
        h = eng.state_hash()
        assert len(h) == 64
