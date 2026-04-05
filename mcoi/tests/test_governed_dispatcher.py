"""Purpose: verify the governed dispatch pipeline wires all stabilization engines into the execution hot path.
Governance scope: integration tests for identity, prediction, economics, equilibrium, promotion, verification, compensation, and ledger gates.
Dependencies: governed_dispatcher, dispatcher, system_closure, system_stabilization, executor_base, template_validator.
Invariants: fail-closed on any gate failure, all actions identity-bound and ledgered, blocked dispatches still emit ledger entries.
"""
from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.core.dispatcher import DispatchRequest, Dispatcher
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatchContext,
    GovernedDispatcher,
    GovernedDispatchResult,
)
from mcoi_runtime.core.system_closure import (
    ExecutionVerificationLoop,
    FailureRecoveryEngine,
    SimRealityBoundary,
)
from mcoi_runtime.core.system_stabilization import (
    EconomicOptimizer,
    EquilibriumEngine,
    IdentityBindingEngine,
    PredictiveFailureEngine,
)
from mcoi_runtime.core.template_validator import TemplateValidator


FIXED_CLOCK = lambda: "2026-03-26T12:00:00+00:00"

VALID_TEMPLATE = {
    "template_id": "tpl-gov-1",
    "action_type": "shell_command",
    "command_argv": ("echo", "{msg}"),
    "required_parameters": ("msg",),
}


@dataclass
class FakeExecutor:
    calls: int = 0
    last_request: ExecutionRequest | None = None
    should_fail: bool = False

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.last_request = request
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(EffectRecord(name="process_completed", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at="2026-03-26T12:00:00+00:00",
            finished_at="2026-03-26T12:00:01+00:00",
            metadata={"adapter": "fake"},
        )


def _make_request(goal_id: str = "goal-1", msg: str = "hello") -> DispatchRequest:
    return DispatchRequest(
        goal_id=goal_id,
        route="shell_command",
        template=VALID_TEMPLATE,
        bindings={"msg": msg},
    )


def _make_governed(
    executor: FakeExecutor | None = None,
    *,
    identity: IdentityBindingEngine | None = None,
    predictor: PredictiveFailureEngine | None = None,
    optimizer: EconomicOptimizer | None = None,
    equilibrium: EquilibriumEngine | None = None,
    boundary: SimRealityBoundary | None = None,
    verifier: ExecutionVerificationLoop | None = None,
    recovery: FailureRecoveryEngine | None = None,
) -> tuple[GovernedDispatcher, FakeExecutor]:
    exe = executor or FakeExecutor()
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"shell_command": exe},
        clock=FIXED_CLOCK,
    )
    eq = equilibrium or EquilibriumEngine()
    governed = GovernedDispatcher(
        dispatcher,
        identity=identity,
        equilibrium=eq,
        predictor=predictor,
        optimizer=optimizer,
        boundary=boundary,
        verifier=verifier,
        recovery=recovery,
        clock=FIXED_CLOCK,
    )
    return governed, exe


def _make_context(
    intent_id: str = "intent-1",
    actor_id: str = "actor-1",
    mode: str = "simulation",
    current_load: float = 0.0,
) -> GovernedDispatchContext:
    return GovernedDispatchContext(
        actor_id=actor_id,
        intent_id=intent_id,
        request=_make_request(),
        mode=mode,
        current_load=current_load,
    )


# ── 1. Happy path ──

def test_happy_path_all_gates_pass() -> None:
    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(equilibrium=eq)
    ctx = _make_context()

    result = governed.governed_dispatch(ctx)

    assert result.all_gates_passed
    assert not result.blocked
    assert result.execution_result is not None
    assert result.execution_result.status == ExecutionOutcome.SUCCEEDED
    assert exe.calls == 1
    assert result.ledger_hash != ""
    assert governed.ledger_count == 1
    assert len(result.gates_passed) >= 5  # identity, prediction, economics, equilibrium, promotion
    predictive_gate = next(g for g in result.gates_passed if g.gate_name == "predictive_failure")
    assert predictive_gate.reason == "predictive failure check passed"


# ── 2. Identity binding required ──

def test_identity_binding_required() -> None:
    identity = IdentityBindingEngine()
    # Pre-register the intent so the governed dispatch hits a duplicate
    identity.sign_intent("intent-dup", "actor-1", "shell_command", "goal-1")

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(identity=identity, equilibrium=eq)
    ctx = _make_context(intent_id="intent-dup")

    result = governed.governed_dispatch(ctx)

    assert result.blocked
    assert "identity_binding" in result.block_reason
    assert exe.calls == 0
    assert governed.ledger_count == 1  # ledger still emitted


# ── 3. Predictive failure blocks abort ──

def test_identity_binding_failure_is_bounded() -> None:
    class CrashingIdentity:
        def sign_intent(self, intent_id: str, actor_id: str, action: str, target: str):
            raise RuntimeError("secret identity failure")

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(identity=CrashingIdentity(), equilibrium=eq)

    result = governed.governed_dispatch(_make_context(intent_id="intent-crash"))

    assert result.blocked
    assert result.gates_failed[0].reason == "identity binding failed"
    assert result.block_reason == "identity_binding blocked"
    assert "RuntimeError" not in result.gates_failed[0].reason
    assert "secret identity failure" not in result.block_reason
    assert exe.calls == 0


def test_predictive_failure_blocks_abort() -> None:
    predictor = PredictiveFailureEngine()
    # Record enough failures to push risk above abort threshold (0.8)
    for _ in range(5):
        predictor.record_failure("shell_command")

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(predictor=predictor, equilibrium=eq)
    ctx = _make_context()

    result = governed.governed_dispatch(ctx)

    assert result.blocked
    assert result.gates_failed[0].reason == "predictive failure blocked dispatch"
    assert result.block_reason == "predictive_failure blocked"
    assert "0." not in result.gates_failed[0].reason
    assert exe.calls == 0


# ── 4. Economic gate blocks over budget ──

def test_economic_gate_blocks_over_budget() -> None:
    optimizer = EconomicOptimizer(budget=50.0)  # budget < cost (100)

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(optimizer=optimizer, equilibrium=eq)
    ctx = _make_context()

    result = governed.governed_dispatch(ctx)

    assert result.blocked
    assert "economic_optimization" in result.block_reason
    assert exe.calls == 0


# ── 5. Equilibrium blocks at capacity ──

def test_equilibrium_blocks_at_capacity() -> None:
    eq = EquilibriumEngine(max_total_pending=1)
    eq.register_agent("actor-1")
    eq.record_action("actor-1")  # fill the single slot

    governed, exe = _make_governed(equilibrium=eq)

    # Use a fresh identity intent for this call
    ctx = _make_context(intent_id="intent-eq-block")

    result = governed.governed_dispatch(ctx)

    assert result.blocked
    assert "equilibrium" in result.block_reason
    assert exe.calls == 0


# ── 6. Promotion boundary blocks reality in sim ──

def test_promotion_boundary_blocks_reality_in_sim() -> None:
    boundary = SimRealityBoundary()  # defaults to simulation mode

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(boundary=boundary, equilibrium=eq)
    ctx = _make_context(mode="reality")

    result = governed.governed_dispatch(ctx)

    assert result.blocked
    assert "promotion_boundary" in result.block_reason
    assert exe.calls == 0


# ── 7. Verification triggers compensation ──

def test_verification_triggers_compensation() -> None:
    verifier = ExecutionVerificationLoop()
    recovery = FailureRecoveryEngine()

    # Create a verifier that will produce a mismatch by pre-registering the verification ID
    # so the governed dispatch's verify call uses a different ID pattern.
    # Actually, we need a different approach: we make expected != actual.
    # The governed dispatcher sets actual = expected, so verification always passes.
    # To test compensation, we need to intercept. Let's subclass.

    class ForcedMismatchVerifier(ExecutionVerificationLoop):
        """Forces a mismatch to trigger compensation."""
        def verify_execution(self, verification_id, action_id, expected, actual):
            # Force actual to differ from expected
            return super().verify_execution(verification_id, action_id, expected, "FORCED_MISMATCH")

    verifier = ForcedMismatchVerifier()

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(verifier=verifier, recovery=recovery, equilibrium=eq)
    ctx = _make_context()

    result = governed.governed_dispatch(ctx)

    # Dispatch itself succeeds (verification is post-dispatch)
    assert not result.blocked
    assert result.execution_result is not None
    assert result.execution_result.status == ExecutionOutcome.SUCCEEDED
    # Compensation was registered
    assert recovery.count == 1
    assert recovery.pending_count() == 1
    assert recovery._compensations["comp-intent-1"].detail == "execution verification failed"
    assert "expected=" not in recovery._compensations["comp-intent-1"].detail


# ── 8. Action binding creates non-repudiable record ──

def test_action_binding_creates_non_repudiable_record() -> None:
    identity = IdentityBindingEngine()

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(identity=identity, equilibrium=eq)
    ctx = _make_context(intent_id="intent-bind")

    result = governed.governed_dispatch(ctx)

    assert not result.blocked
    assert identity.binding_count == 1
    assert identity.intent_count == 1

    # Verify the binding is cryptographically valid
    assert identity.verify_binding("bind-intent-bind")


# ── 9. Ledger emitted on success ──

def test_ledger_emitted_on_success() -> None:
    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(equilibrium=eq)
    ctx = _make_context()

    result = governed.governed_dispatch(ctx)

    assert governed.ledger_count == 1
    entry = governed.ledger[0]
    assert entry["actor_id"] == "actor-1"
    assert entry["intent_id"] == "intent-1"
    assert entry["route"] == "shell_command"
    assert entry["goal_id"] == "goal-1"
    assert entry["blocked"] is False
    assert entry["block_reason"] == ""
    assert entry["gates_passed"] >= 5
    assert entry["gates_failed"] == 0
    assert entry["timestamp"] == "2026-03-26T12:00:00+00:00"
    assert result.ledger_hash != ""


# ── 10. Ledger emitted on block ──

def test_ledger_emitted_on_block() -> None:
    predictor = PredictiveFailureEngine()
    for _ in range(5):
        predictor.record_failure("shell_command")

    eq = EquilibriumEngine()
    eq.register_agent("actor-1")
    governed, exe = _make_governed(predictor=predictor, equilibrium=eq)
    ctx = _make_context(intent_id="intent-blocked")

    result = governed.governed_dispatch(ctx)

    assert result.blocked
    assert governed.ledger_count == 1
    entry = governed.ledger[0]
    assert entry["blocked"] is True
    assert entry["block_reason"] != ""
    assert entry["gates_failed"] >= 1
    assert result.ledger_hash != ""


# ── 11. Full pipeline integration ──

def test_full_pipeline_integration() -> None:
    """Complete: sign -> predict -> budget -> equilibrium -> promote -> dispatch -> verify -> bind -> ledger."""
    identity = IdentityBindingEngine()
    predictor = PredictiveFailureEngine()
    optimizer = EconomicOptimizer(budget=10000.0)
    eq = EquilibriumEngine(max_total_pending=10)
    eq.register_agent("actor-full")
    boundary = SimRealityBoundary()
    verifier = ExecutionVerificationLoop()
    recovery = FailureRecoveryEngine()

    exe = FakeExecutor()
    governed, _ = _make_governed(
        executor=exe,
        identity=identity,
        predictor=predictor,
        optimizer=optimizer,
        equilibrium=eq,
        boundary=boundary,
        verifier=verifier,
        recovery=recovery,
    )

    ctx = GovernedDispatchContext(
        actor_id="actor-full",
        intent_id="intent-full-pipeline",
        request=_make_request(goal_id="goal-full", msg="integration"),
        mode="simulation",
        current_load=0.1,
    )

    result = governed.governed_dispatch(ctx)

    # All gates passed
    assert result.all_gates_passed
    assert not result.blocked
    assert len(result.gates_passed) == 5  # identity, prediction, economics, equilibrium, promotion

    # Dispatch executed
    assert result.execution_result is not None
    assert result.execution_result.status == ExecutionOutcome.SUCCEEDED
    assert exe.calls == 1

    # Identity: intent signed and action bound
    assert identity.intent_count == 1
    assert identity.binding_count == 1
    assert identity.verify_binding("bind-intent-full-pipeline")

    # Prediction: recorded (low risk, proceed)
    assert predictor.prediction_count == 1

    # Economics: budget committed
    assert optimizer.remaining_budget == 9900.0

    # Equilibrium: action completed (pending back to 0)
    agent_load = eq._agents["actor-full"]
    assert agent_load.actions_completed == 1
    assert agent_load.actions_pending == 0

    # Verification: verified (expected == actual)
    assert verifier.count == 1
    assert verifier.failed_count() == 0

    # No compensation needed
    assert recovery.count == 0

    # Ledger: one entry with hash
    assert governed.ledger_count == 1
    assert result.ledger_hash != ""
    entry = governed.ledger[0]
    assert entry["actor_id"] == "actor-full"
    assert entry["goal_id"] == "goal-full"
    assert entry["blocked"] is False
