"""Purpose: verify the universal action kernel composes governed runtime planes.
Governance scope: goal, world-state, plan, simulation, capability admission,
    governed dispatch, terminal closure, learning admission, and app facade.
Dependencies: universal_action_kernel, governed_execution, governed_dispatcher,
    world_state, simulation, and governed capability fabric.
Invariants:
  - Dispatch requires world support, accepted capability admission, and
    non-blocking simulation.
  - Blocked paths do not call execution adapters.
  - Completed paths carry terminal closure and learning admission.
"""

from __future__ import annotations

import json
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from gateway.command_spine import CommandLedger, CommandState, InMemoryCommandLedgerStore
from mcoi_runtime.app.governed_execution import (
    build_universal_operator_kernel,
    universal_command_dispatch,
    universal_command_proof_view,
    universal_operator_dispatch,
)
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)
from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.simulation import RiskLevel, VerdictType
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.contracts.world_state import ContradictionRecord, ContradictionStrategy
from mcoi_runtime.core.closure_learning import ClosureLearningAdmissionGate
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.dispatcher import DispatchRequest, Dispatcher
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry
from mcoi_runtime.core.governed_dispatcher import GovernedDispatcher
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.system_stabilization import EquilibriumEngine
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.core.universal_action_kernel import (
    UniversalActionKernel,
    UniversalActionRequest,
    build_universal_action_orchestration_record,
)
from mcoi_runtime.core.world_state import WorldStateEngine


NOW = "2026-05-06T12:00:00+00:00"
REQUIRED_ROLE = "customer_ops_manager"
REPO_ROOT = Path(__file__).resolve().parents[2]
FABRIC_FIXTURE_DIR = REPO_ROOT / "integration" / "governed_capability_fabric" / "fixtures"
UAO_VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_universal_action_orchestration.py"
UAO_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_action_orchestration.schema.json"
VALID_TEMPLATE = {
    "template_id": "tpl-universal-1",
    "action_type": "shell_command",
    "command_argv": ("echo", "{msg}"),
    "required_parameters": ("msg",),
}


def _clock() -> str:
    return NOW


@dataclass
class FakeExecutor:
    calls: int = 0
    last_request: ExecutionRequest | None = None

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.last_request = request
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(EffectRecord(name="process_completed", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at=NOW,
            finished_at=NOW,
            metadata={"adapter": "fake"},
        )


def test_universal_action_kernel_dispatches_after_all_certificates_pass() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(_action_request())

    assert result.blocked is False
    assert result.dispatched is True
    assert result.goal_certificate.goal.goal_id == "goal-1"
    assert result.world_certificate.allows_execution is True
    assert result.plan_certificate is not None
    assert result.plan_certificate.plan.state_hash == result.world_certificate.snapshot.state_hash
    assert result.simulation_certificate is not None
    assert result.simulation_certificate.verdict.verdict_type is VerdictType.PROCEED
    assert result.capability_decision is not None
    assert result.capability_decision.capability_id == "shell_command"
    assert result.governed_action is not None
    assert result.governed_action.typed_intent.intent_name == "shell_command"
    assert result.governed_action.capability_passport.capability_id == "shell_command"
    assert result.governed_action.authority_proof.actor_roles == (REQUIRED_ROLE,)
    assert result.terminal_certificate is not None
    assert result.terminal_certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert result.learning_decision is not None
    assert result.learning_decision.status is LearningAdmissionStatus.ADMIT
    assert executor.calls == 1
    assert result.action_envelope["actor"] == "actor-1"
    assert result.action_envelope["tenant"] == "tenant-1"
    assert result.action_envelope["intent"] == "intent-1"
    assert result.action_envelope["target"] == "shell_command"
    assert result.action_envelope["source"].startswith("action://universal-action-source-")
    assert result.action_envelope["risk"] == "low"
    assert result.action_envelope["approval_ref"] is None
    assert "approval_refs" not in result.action_envelope
    assert result.action_envelope["capability_refs"] == ("shell_command",)
    assert result.trace_ref.startswith("causal-decision-trace-")
    assert result.admission_receipt_ref.startswith("universal-action-admission-receipt-")
    assert result.execution_receipt_ref.startswith("universal-action-execution-receipt-")
    assert result.closure_state == "closed_allowed"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_result_exports_valid_allowed_uao_record() -> None:
    kernel, _executor = _kernel_with_capability()
    request = _action_request()

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record["uao_schema_version"] == "uao.v1"
    assert record["decision"]["status"] == "allow"
    assert record["execution_receipt_ref"] == result.execution_receipt_ref
    assert record["raw_reasoning_included"] is False
    assert record["lineage"]["accepted_deltas"]
    assert record["lineage"]["rejected_deltas"] == []


def test_universal_action_kernel_blocks_missing_authority_before_plan() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(
        _action_request(
            intent_id="intent-authority-block",
            metadata={"actor_roles": ("support_viewer",)},
        )
    )

    assert result.blocked is True
    assert result.block_reason == "governed_action_admission_rejected"
    assert result.capability_decision is not None
    assert result.governed_action is None
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.admission_receipt_ref.startswith("universal-action-admission-receipt-")
    assert result.execution_receipt_ref is None
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_open_world_contradictions_before_dispatch() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, executor = _kernel_with_capability(world_state=world_state)

    result = kernel.run(_action_request(intent_id="intent-world-block"))

    assert result.blocked is True
    assert result.block_reason == "open_world_contradictions"
    assert result.world_certificate.allows_execution is False
    assert len(result.world_certificate.snapshot.unresolved_contradictions) == 1
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_result_exports_valid_blocked_uao_record() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, _executor = _kernel_with_capability(world_state=world_state)
    request = _action_request(intent_id="intent-world-block-record")

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record["decision"]["status"] == "block"
    assert record["execution_receipt_ref"] is None
    assert record["closure_state"] == "closed_blocked"
    assert record["memory_update"]["learning_allowed"] is False
    assert record["lineage"]["accepted_deltas"] == []
    assert record["lineage"]["rejected_deltas"]


def test_universal_action_kernel_blocks_uninstalled_capability_before_plan() -> None:
    kernel, executor = _kernel_without_capability()

    result = kernel.run(_action_request(intent_id="intent-capability-block"))

    assert result.blocked is True
    assert result.block_reason == "capability_admission_rejected"
    assert result.capability_decision is not None
    assert result.capability_decision.reason == "no installed capability for typed intent"
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_escalating_simulation_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(_action_request(intent_id="intent-sim-block", risk_level=RiskLevel.HIGH))

    assert result.blocked is True
    assert result.block_reason == "simulation_escalate"
    assert result.plan_certificate is not None
    assert result.simulation_certificate is not None
    assert result.simulation_certificate.verdict.verdict_type is VerdictType.ESCALATE
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.action_envelope["risk"] == "H3"
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_operator_dispatch_exposes_kernel_entry_point() -> None:
    kernel, executor = _kernel_with_capability()

    result = universal_operator_dispatch(
        kernel,
        _dispatch_request(),
        actor_id="operator-1",
        tenant_id="tenant-1",
        intent_id="intent-operator-entry",
        objective="Exercise the app-layer universal action entry point.",
        actor_roles=(REQUIRED_ROLE,),
    )

    assert result.blocked is False
    assert result.dispatched is True
    assert result.goal_certificate.goal.description == "Exercise the app-layer universal action entry point."
    assert result.terminal_certificate is not None
    assert result.learning_decision is not None
    assert executor.calls == 1
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_operator_dispatch_derives_objective_and_intent_when_absent() -> None:
    kernel, executor = _kernel_with_capability()

    result = universal_operator_dispatch(
        kernel,
        _dispatch_request(goal_id="goal-auto"),
        actor_id="operator-auto",
        tenant_id="tenant-1",
        actor_roles=(REQUIRED_ROLE,),
    )

    assert result.blocked is False
    assert result.goal_certificate.goal.goal_id == "goal-auto"
    assert result.goal_certificate.goal.description == "Execute shell_command for goal goal-auto"
    assert result.capability_decision is not None
    assert result.capability_decision.intent_name == "shell_command"
    assert executor.calls == 1
    assert result.dispatch_result is not None
    assert result.dispatch_result.ledger_hash


def test_build_universal_operator_kernel_composes_bootstrapped_runtime() -> None:
    executor = FakeExecutor()
    runtime = bootstrap_runtime(clock=_clock, executors={"shell_command": executor})
    kernel = build_universal_operator_kernel(
        runtime,
        capability_admission_gate=_capability_admission_gate(),
    )

    result = universal_operator_dispatch(
        kernel,
        _dispatch_request(),
        actor_id="operator-bootstrap",
        tenant_id="tenant-1",
        intent_id="intent-bootstrap-kernel",
        actor_roles=(REQUIRED_ROLE,),
    )

    assert result.blocked is False
    assert result.dispatched is True
    assert result.terminal_certificate is not None
    assert result.learning_decision is not None
    assert executor.calls == 1
    assert result.proof_hash.startswith("universal-action-proof-")


def test_build_universal_operator_kernel_requires_runtime_dependencies() -> None:
    class MissingRuntime:
        pass

    try:
        build_universal_operator_kernel(
            MissingRuntime(),
            capability_admission_gate=_capability_admission_gate(),
        )
    except ValueError as exc:
        assert str(exc) == "runtime must expose world_state"
    else:
        raise AssertionError("missing runtime dependencies should fail closed")


def test_universal_command_dispatch_binds_command_spine_transitions() -> None:
    kernel, executor = _kernel_with_capability()
    ledger = CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-command",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
    )
    current = ledger.get(command.command_id)
    events = ledger.events_for(command.command_id)
    states = [event.next_state for event in events]

    assert result.blocked is False
    assert result.dispatched is True
    assert result.terminal_certificate is not None
    assert result.learning_decision is not None
    assert executor.calls == 1
    assert current is not None
    assert current.state is CommandState.LEARNING_DECIDED
    assert CommandState.GOVERNED_ACTION_BOUND in states
    assert CommandState.DISPATCHED in states
    assert CommandState.TERMINALLY_CERTIFIED in states
    assert CommandState.LEARNING_DECIDED in states
    assert events[-1].detail["learning_admission_id"] == result.learning_decision.admission_id
    assert events[-1].detail["proof_hash"] == result.proof_hash


def test_universal_command_proof_view_replays_persisted_success_events() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-view",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    proof = universal_command_proof_view(reloaded_ledger, command.command_id)

    assert proof is not None
    assert proof.command_id == command.command_id
    assert proof.blocked is False
    assert proof.action_envelope["actor"] == "actor-1"
    assert proof.action_envelope["tenant"] == "tenant-1"
    assert proof.trace_ref == result.trace_ref
    assert proof.admission_receipt_ref == result.admission_receipt_ref
    assert proof.execution_receipt_ref == result.execution_receipt_ref
    assert proof.closure_state == "closed_allowed"
    assert proof.proof_hash == result.proof_hash
    assert proof.capability_id == "shell_command"
    assert proof.dispatch_ledger_hash == result.dispatch_result.ledger_hash
    assert proof.terminal_certificate_id == result.terminal_certificate.certificate_id
    assert proof.terminal_disposition == TerminalClosureDisposition.COMMITTED.value
    assert proof.learning_admission_id == result.learning_decision.admission_id
    assert proof.learning_status == LearningAdmissionStatus.ADMIT.value
    assert CommandState.DISPATCHED.value in proof.state_sequence
    assert CommandState.LEARNING_DECIDED.value in proof.state_sequence
    assert len(proof.event_hashes) >= 5


def test_universal_command_dispatch_records_blocked_kernel_result() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, executor = _kernel_with_capability(world_state=world_state)
    ledger = CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-block",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
    )
    current = ledger.get(command.command_id)
    events = ledger.events_for(command.command_id)

    assert result.blocked is True
    assert result.block_reason == "open_world_contradictions"
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert current is not None
    assert current.state is CommandState.REQUIRES_REVIEW
    assert events[-1].detail["cause"] == "universal_action_kernel_blocked"
    assert events[-1].detail["universal_action"]["block_reason"] == "open_world_contradictions"
    assert events[-1].detail["universal_action"]["proof_hash"] == result.proof_hash


def test_universal_command_proof_view_replays_blocked_result() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, _executor = _kernel_with_capability(world_state=world_state)
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-block",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    proof = universal_command_proof_view(reloaded_ledger, command.command_id)

    assert proof is not None
    assert proof.blocked is True
    assert proof.block_reason == "open_world_contradictions"
    assert proof.action_envelope["tenant"] == "tenant-1"
    assert proof.trace_ref == result.trace_ref
    assert proof.admission_receipt_ref == result.admission_receipt_ref
    assert proof.execution_receipt_ref is None
    assert proof.closure_state == "closed_blocked"
    assert proof.proof_hash == result.proof_hash
    assert proof.dispatch_ledger_hash == ""
    assert proof.terminal_certificate_id == ""
    assert proof.learning_admission_id == ""
    assert CommandState.REQUIRES_REVIEW.value in proof.state_sequence
    assert CommandState.TERMINALLY_CERTIFIED.value not in proof.state_sequence
    assert len(proof.event_hashes) >= 4


def _kernel_with_capability(
    *,
    world_state: WorldStateEngine | None = None,
) -> tuple[UniversalActionKernel, FakeExecutor]:
    return _kernel(gate=_capability_admission_gate(), world_state=world_state)


def _kernel_without_capability() -> tuple[UniversalActionKernel, FakeExecutor]:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = CommandCapabilityAdmissionGate(registry=registry, clock=_clock)
    return _kernel(gate=gate)


def _kernel(
    *,
    gate: CommandCapabilityAdmissionGate,
    world_state: WorldStateEngine | None = None,
) -> tuple[UniversalActionKernel, FakeExecutor]:
    executor = FakeExecutor()
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"shell_command": executor},
        clock=_clock,
    )
    equilibrium = EquilibriumEngine()
    equilibrium.register_agent("actor-1")
    governed = GovernedDispatcher(
        dispatcher,
        equilibrium=equilibrium,
        capability_admission=gate,
        clock=_clock,
    )
    graph = OperationalGraph(clock=_clock)
    simulator = SimulationEngine(graph=graph, clock=_clock)
    kernel = UniversalActionKernel(
        world_state=world_state or WorldStateEngine(clock=_clock),
        simulator=simulator,
        capability_admission=gate,
        governed_dispatcher=governed,
        terminal_closure=TerminalClosureCertifier(clock=_clock),
        learning_admission=ClosureLearningAdmissionGate(clock=_clock),
        clock=_clock,
    )
    return kernel, executor


def _action_request(
    *,
    intent_id: str = "intent-1",
    risk_level: RiskLevel = RiskLevel.LOW,
    metadata: dict | None = None,
) -> UniversalActionRequest:
    request_metadata = {"actor_roles": (REQUIRED_ROLE,)}
    if metadata is not None:
        request_metadata.update(metadata)
    return UniversalActionRequest(
        actor_id="actor-1",
        tenant_id="tenant-1",
        intent_id=intent_id,
        objective="Run a bounded shell command through the universal action kernel.",
        dispatch_request=_dispatch_request(),
        risk_level=risk_level,
        metadata=request_metadata,
    )


def _dispatch_request(goal_id: str = "goal-1") -> DispatchRequest:
    return DispatchRequest(
        goal_id=goal_id,
        route="shell_command",
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
    )


def _capability_admission_gate() -> CommandCapabilityAdmissionGate:
    registry = GovernedCapabilityRegistry(clock=_clock)
    compiler = DomainCapsuleCompiler(clock=_clock)
    entry = _certified_entry("shell_command")
    capsule = _certified_capsule("shell_command")
    compilation = compiler.compile(capsule=capsule, registry_entries=(entry,))
    installation = registry.install(compilation, (entry,))
    assert installation.errors == ()
    return CommandCapabilityAdmissionGate(registry=registry, clock=_clock)


def _certified_entry(capability_id: str) -> CapabilityRegistryEntry:
    entry = CapabilityRegistryEntry.from_mapping(_fixture("capability_registry_entry.json"))
    return CapabilityRegistryEntry(
        capability_id=capability_id,
        domain=entry.domain,
        version=entry.version,
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        effect_model=entry.effect_model,
        evidence_model=entry.evidence_model,
        authority_policy=entry.authority_policy,
        isolation_profile=entry.isolation_profile,
        recovery_plan=entry.recovery_plan,
        cost_model=entry.cost_model,
        obligation_model=entry.obligation_model,
        certification_status=CapabilityCertificationStatus.CERTIFIED,
        metadata=entry.metadata,
        extensions=entry.extensions,
    )


def _certified_capsule(capability_id: str) -> DomainCapsule:
    capsule = DomainCapsule.from_mapping(_fixture("domain_capsule.json"))
    return DomainCapsule(
        capsule_id=capsule.capsule_id,
        domain=capsule.domain,
        version=capsule.version,
        ontology_refs=capsule.ontology_refs,
        capability_refs=(capability_id,),
        policy_refs=capsule.policy_refs,
        evidence_rules=capsule.evidence_rules,
        approval_rules=capsule.approval_rules,
        recovery_rules=capsule.recovery_rules,
        test_fixture_refs=capsule.test_fixture_refs,
        read_model_refs=capsule.read_model_refs,
        operator_view_refs=capsule.operator_view_refs,
        owner_team=capsule.owner_team,
        certification_status=DomainCapsuleCertificationStatus.CERTIFIED,
        metadata=capsule.metadata,
        extensions=capsule.extensions,
    )


def _fixture(name: str) -> dict:
    with open(FABRIC_FIXTURE_DIR / name, encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def _validate_uao_record(record: dict) -> list[str]:
    schema = json.loads(UAO_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(record)
    spec = importlib.util.spec_from_file_location("validate_universal_action_orchestration", UAO_VALIDATOR_PATH)
    assert spec is not None
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)
    errors = validator.validate_orchestration(record)
    assert isinstance(errors, list)
    return errors
