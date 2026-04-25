"""Authority-obligation mesh tests.

Tests: ownership binding, approval chains, separation of duty, post-closure
    obligations, escalation, and runtime responsibility witness counters.
"""

import sys
import threading
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gateway.authority_obligation_mesh as authority_mesh_module  # noqa: E402
from gateway.authority_obligation_mesh import (  # noqa: E402
    ApprovalChainStatus,
    ApprovalPolicy,
    AuthorityObligationMesh,
    AuthorityObligationMeshConfigurationError,
    EscalationPolicy,
    InMemoryAuthorityObligationMeshStore,
    ObligationStatus,
    PostgresAuthorityObligationMeshStore,
    TeamOwnership,
    build_authority_obligation_mesh_store_from_env,
)
from gateway.command_spine import (  # noqa: E402
    ClosureDisposition,
    CommandLedger,
    CommandState,
    InMemoryCommandLedgerStore,
)


def _ledger(clock=lambda: "2026-04-24T12:00:00+00:00") -> CommandLedger:
    return CommandLedger(clock=clock, store=InMemoryCommandLedgerStore())


def _payment_command(ledger: CommandLedger):
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="requester-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-authority-mesh",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )
    ledger.transition(command.command_id, CommandState.TENANT_BOUND)
    ledger.bind_governed_action(command.command_id)
    return command


def _register_payment_owner(mesh: AuthorityObligationMesh) -> None:
    mesh.register_ownership(TeamOwnership(
        tenant_id="tenant-1",
        resource_ref="financial.send_payment",
        owner_team="finance_ops",
        primary_owner_id="finance-manager-1",
        fallback_owner_id="tenant-owner-1",
        escalation_team="executive_ops",
    ))


class _CountingCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return (0,)


class _RollbackFailingConnection:
    def __init__(self):
        self.rollback_attempts = 0

    def rollback(self):
        self.rollback_attempts += 1
        raise RuntimeError("rollback failed")

    def cursor(self):
        return _CountingCursor()

    def close(self):
        return None


class _CloseFailingConnection:
    def close(self):
        raise RuntimeError("close failed")


def _postgres_mesh_store_for_fault_tests(conn):
    store = PostgresAuthorityObligationMeshStore.__new__(PostgresAuthorityObligationMeshStore)
    store._connection_string = "postgresql://example/mullu"
    store._conn = conn
    store._lock = threading.Lock()
    store._available = True
    store._operation_failures = 0
    store._rollback_failures = 0
    store._close_failures = 0
    return store


def test_prepare_authority_binds_ownership_and_pending_approval_chain():
    ledger = _ledger()
    command = _payment_command(ledger)
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)

    chain = mesh.prepare_authority(command.command_id)
    events = ledger.events_for(command.command_id)
    witness = mesh.responsibility_witness()

    assert chain.status is ApprovalChainStatus.PENDING
    assert chain.required_roles == ("financial_admin",)
    assert chain.required_approver_count == 1
    assert events[-3].next_state is CommandState.OWNERSHIP_BOUND
    assert events[-2].next_state is CommandState.AUTHORITY_PATH_BUILT
    assert events[-1].next_state is CommandState.APPROVAL_CHAIN_PENDING
    assert witness.pending_approval_chain_count == 1


def test_strict_mesh_rejects_high_risk_capability_without_owner():
    ledger = _ledger()
    command = _payment_command(ledger)
    mesh = AuthorityObligationMesh(
        commands=ledger,
        clock=ledger._clock,
        strict_high_risk_ownership=True,
    )

    with pytest.raises(ValueError, match="^high-risk capability requires ownership binding$"):
        mesh.prepare_authority(command.command_id)

    witness = mesh.responsibility_witness()

    assert witness.unowned_high_risk_capability_count == 1
    assert witness.pending_approval_chain_count == 0
    assert mesh.approval_chain_for(command.command_id) is None


def test_approval_chain_requires_separate_authorized_resolver():
    ledger = _ledger()
    command = _payment_command(ledger)
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)
    mesh.prepare_authority(command.command_id)

    self_attempt = mesh.record_approval(
        command_id=command.command_id,
        approver_id="requester-1",
        approver_roles=("financial_admin",),
        approved=True,
    )
    authorized = mesh.record_approval(
        command_id=command.command_id,
        approver_id="finance-manager-1",
        approver_roles=("financial_admin",),
        approved=True,
    )
    events = ledger.events_for(command.command_id)

    assert self_attempt is not None
    assert self_attempt.status is ApprovalChainStatus.PENDING
    assert authorized is not None
    assert authorized.status is ApprovalChainStatus.SATISFIED
    assert authorized.approvals_received == ("finance-manager-1",)
    assert events[-1].next_state is CommandState.APPROVAL_CHAIN_SATISFIED


def test_quorum_policy_requires_two_approvers():
    ledger = _ledger()
    command = _payment_command(ledger)
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)
    mesh.register_approval_policy(ApprovalPolicy(
        policy_id="payment-quorum",
        tenant_id="tenant-1",
        capability="financial.send_payment",
        risk_tier="high",
        required_roles=("financial_admin",),
        required_approver_count=2,
        separation_of_duty=True,
        timeout_seconds=600,
        escalation_policy_id="finance-escalation",
    ))
    chain = mesh.prepare_authority(command.command_id)

    first = mesh.record_approval(
        command_id=command.command_id,
        approver_id="finance-manager-1",
        approver_roles=("financial_admin",),
        approved=True,
    )
    second = mesh.record_approval(
        command_id=command.command_id,
        approver_id="tenant-owner-1",
        approver_roles=("financial_admin",),
        approved=True,
    )

    assert chain.required_approver_count == 2
    assert first is not None
    assert first.status is ApprovalChainStatus.PENDING
    assert second is not None
    assert second.status is ApprovalChainStatus.SATISFIED
    assert second.approvals_received == ("finance-manager-1", "tenant-owner-1")


def test_mesh_store_reloads_ownership_policies_and_approval_chain_across_instances():
    ledger = _ledger()
    command = _payment_command(ledger)
    store = InMemoryAuthorityObligationMeshStore()
    first_mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock, store=store)
    _register_payment_owner(first_mesh)
    first_mesh.register_escalation_policy(EscalationPolicy(
        policy_id="finance-escalation",
        tenant_id="tenant-1",
        notify_after_seconds=1800,
        escalate_after_seconds=7200,
        incident_after_seconds=86400,
        fallback_owner_id="tenant-owner-1",
        escalation_team="executive_ops",
    ))

    chain = first_mesh.prepare_authority(command.command_id)
    second_mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock, store=store)
    reloaded_chain = second_mesh.approval_chain_for(command.command_id)
    summary = second_mesh.summary()

    assert reloaded_chain == chain
    assert summary["ownership_bindings"] == 1
    assert summary["approval_chains"] == 1
    assert summary["escalation_policies"] == 1
    assert summary["store"]["backend"] == "memory"
    assert store.load_ownership("tenant-1", "financial.send_payment") is not None
    assert store.load_escalation_policy("tenant-1", "finance-escalation") is not None


def test_review_terminal_certificate_opens_owned_obligation_and_escalates_when_overdue():
    current_time = {"value": "2026-04-24T12:00:00+00:00"}

    def clock() -> str:
        return current_time["value"]

    ledger = _ledger(clock=clock)
    command = _payment_command(ledger)
    ledger.record_operational_claim(
        command.command_id,
        text="Command requires review.",
        verified=False,
        confidence=0.0,
    )
    certificate = ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.REQUIRES_REVIEW,
        case_id="case-authority-mesh",
    )
    mesh = AuthorityObligationMesh(commands=ledger, clock=clock)
    _register_payment_owner(mesh)

    obligations = mesh.open_post_closure_obligations(
        command_id=command.command_id,
        certificate=certificate,
    )
    witness_before = mesh.responsibility_witness()
    current_time["value"] = "2026-04-25T12:00:01+00:00"
    escalated = mesh.escalate_overdue()
    witness_after = mesh.responsibility_witness()

    assert len(obligations) == 1
    assert obligations[0].owner_team == "finance_ops"
    assert obligations[0].obligation_type == "case_review"
    assert obligations[0].evidence_required == ("case_disposition",)
    assert witness_before.open_obligation_count == 1
    assert len(escalated) == 1
    assert escalated[0].status is ObligationStatus.ESCALATED
    assert witness_after.escalated_obligation_count == 1
    assert mesh.escalation_events()[0]["obligation_id"] == escalated[0].obligation_id


def test_satisfy_obligation_requires_evidence_and_active_status():
    ledger = _ledger()
    command = _payment_command(ledger)
    ledger.record_operational_claim(
        command.command_id,
        text="Command requires review.",
        verified=False,
        confidence=0.0,
    )
    certificate = ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.REQUIRES_REVIEW,
        case_id="case-authority-mesh",
    )
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)
    obligation = mesh.open_post_closure_obligations(
        command_id=command.command_id,
        certificate=certificate,
    )[0]

    with pytest.raises(ValueError, match="requires evidence_refs"):
        mesh.satisfy_obligation(obligation.obligation_id, evidence_refs=())

    satisfied = mesh.satisfy_obligation(
        obligation.obligation_id,
        evidence_refs=("case:authority-review-closed",),
    )
    events = ledger.events_for(command.command_id)
    witness = mesh.responsibility_witness()

    assert satisfied.status is ObligationStatus.SATISFIED
    assert events[-1].next_state is CommandState.OBLIGATIONS_SATISFIED
    assert events[-1].detail["evidence_refs"] == ("case:authority-review-closed",)
    assert witness.open_obligation_count == 0
    assert witness.requires_review_count == 0

    with pytest.raises(ValueError, match="open or escalated"):
        mesh.satisfy_obligation(
            obligation.obligation_id,
            evidence_refs=("case:duplicate-authority-review-closed",),
        )


def test_postgres_mesh_store_counts_operation_and_rollback_failure():
    conn = _RollbackFailingConnection()
    store = _postgres_mesh_store_for_fault_tests(conn)

    result = store._safe_execute(lambda: (_ for _ in ()).throw(RuntimeError("write failed")))
    status = store.status()

    assert result is None
    assert conn.rollback_attempts == 1
    assert status["operation_failures"] == 1
    assert status["rollback_failures"] == 1
    assert status["available"] is True


def test_postgres_mesh_store_counts_close_failure_and_clears_connection():
    store = _postgres_mesh_store_for_fault_tests(_CloseFailingConnection())

    store.close()
    status = store.status()

    assert store._conn is None
    assert status["available"] is False
    assert status["close_failures"] == 1


def test_build_authority_mesh_store_from_env_uses_memory_backend(monkeypatch):
    monkeypatch.setenv("MULLU_AUTHORITY_MESH_BACKEND", "memory")
    monkeypatch.delenv("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", raising=False)
    monkeypatch.setenv("MULLU_ENV", "local_dev")

    store = build_authority_obligation_mesh_store_from_env()

    assert store.status()["backend"] == "memory"
    assert store.status()["available"] is True
    assert store.list_obligations() == ()


def test_build_authority_mesh_store_rejects_memory_when_persistent_required(monkeypatch):
    monkeypatch.setenv("MULLU_AUTHORITY_MESH_BACKEND", "memory")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", "true")
    monkeypatch.setenv("MULLU_ENV", "local_dev")

    with pytest.raises(
        AuthorityObligationMeshConfigurationError,
        match="^persistent authority-obligation mesh store required$",
    ):
        build_authority_obligation_mesh_store_from_env()


def test_build_authority_mesh_store_rejects_unavailable_postgres_when_required(monkeypatch):
    class UnavailablePostgresStore:
        def __init__(self, *_args, **_kwargs):
            self.closed = False

        def status(self):
            return {
                "backend": "postgresql",
                "persistent": True,
                "available": False,
            }

        def close(self):
            self.closed = True

    monkeypatch.setenv("MULLU_AUTHORITY_MESH_BACKEND", "postgresql")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", "true")
    monkeypatch.setenv("MULLU_AUTHORITY_MESH_DB_URL", "postgresql://example/mullu")
    monkeypatch.setattr(
        authority_mesh_module,
        "PostgresAuthorityObligationMeshStore",
        UnavailablePostgresStore,
    )

    with pytest.raises(
        AuthorityObligationMeshConfigurationError,
        match="^persistent authority-obligation mesh store unavailable$",
    ):
        build_authority_obligation_mesh_store_from_env()
