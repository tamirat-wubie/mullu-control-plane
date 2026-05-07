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
from dataclasses import dataclass
from pathlib import Path

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from gateway.command_spine import CommandLedger, CommandState, InMemoryCommandLedgerStore
from mcoi_runtime.app.governed_execution import (
    build_universal_operator_kernel,
    universal_command_dispatch,
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
from mcoi_runtime.core.universal_action_kernel import UniversalActionKernel, UniversalActionRequest
from mcoi_runtime.core.world_state import WorldStateEngine


NOW = "2026-05-06T12:00:00+00:00"
REPO_ROOT = Path(__file__).resolve().parents[2]
FABRIC_FIXTURE_DIR = REPO_ROOT / "integration" / "governed_capability_fabric" / "fixtures"
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
    assert result.terminal_certificate is not None
    assert result.terminal_certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert result.learning_decision is not None
    assert result.learning_decision.status is LearningAdmissionStatus.ADMIT
    assert executor.calls == 1
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
) -> UniversalActionRequest:
    return UniversalActionRequest(
        actor_id="actor-1",
        tenant_id="tenant-1",
        intent_id=intent_id,
        objective="Run a bounded shell command through the universal action kernel.",
        dispatch_request=_dispatch_request(),
        risk_level=risk_level,
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
