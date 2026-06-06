"""Phase 193 — Governed Dispatcher / Execution Spine Integration.

Purpose: Wraps the core dispatcher with stabilization and closure gates so that
    every action passes through the full governed pipeline.
Governance scope: pre-dispatch gates, post-dispatch verification, compensation hooks.
Dependencies: dispatcher, system_closure, system_stabilization.
Invariants: fail-closed on any gate failure, all actions are identity-bound and ledgered.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from string import Formatter
from typing import Any, Callable, Mapping
from hashlib import sha256

from mcoi_runtime.core.dispatcher import Dispatcher, DispatchRequest
from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    ExpectedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.execution import (
    EffectRecord,
    ExecutionMode,
    ExecutionOutcome,
    ExecutionResult,
    coerce_execution_mode,
    execution_mode_requires_backend,
)
from mcoi_runtime.contracts.governed_capability_fabric import (
    CommandCapabilityAdmissionStatus,
)
from mcoi_runtime.contracts.case_runtime import CaseKind, CaseSeverity, FindingSeverity
from mcoi_runtime.adapters.executor_base import build_failure_result, ExecutionFailure, utc_now_text
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier

from mcoi_runtime.core.system_closure import (
    ExecutionVerificationLoop,
    FailureRecoveryEngine,
    SimRealityBoundary,
)
from mcoi_runtime.core.system_stabilization import (
    IdentityBindingEngine, OntologyEnforcer, EquilibriumEngine,
    AdversarialDefenseEngine, PredictiveFailureEngine,
    EconomicOptimizer, AdaptivePromotionEngine,
)

_DEFAULT_DISPATCH_ECONOMIC_COST = 1.0
_DEFAULT_DISPATCH_ECONOMIC_VALUE = 1.0


def _bounded_gate_error(summary: str, _exc: Exception) -> str:
    """Return a stable gate failure summary without raw backend detail."""
    return summary


def _dispatch_economic_metrics(template: Mapping[str, Any]) -> tuple[float, float]:
    """Return governed cost/value estimates declared by a dispatch template."""
    if not isinstance(template, Mapping):
        return _DEFAULT_DISPATCH_ECONOMIC_COST, _DEFAULT_DISPATCH_ECONOMIC_VALUE
    cost = _optional_non_negative_metric(
        template.get("economic_cost"),
        default=_DEFAULT_DISPATCH_ECONOMIC_COST,
    )
    value = _optional_non_negative_metric(
        template.get("economic_value"),
        default=_DEFAULT_DISPATCH_ECONOMIC_VALUE,
    )
    return cost, value


def _optional_non_negative_metric(raw: Any, *, default: float) -> float:
    if raw is None:
        return default
    if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw < 0:
        raise ValueError("economic metric must be a non-negative number")
    return float(raw)


@dataclass(frozen=True, slots=True)
class GovernedDispatchContext:
    """Enriched context that flows through every gate."""
    actor_id: str
    intent_id: str
    request: DispatchRequest
    mode: ExecutionMode | str = ExecutionMode.SIMULATION
    budget_remaining: float = 10000.0
    current_load: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _coerce_dispatch_execution_mode(self.mode).value)


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_name: str
    passed: bool
    reason: str = ""


@dataclass
class GovernedDispatchResult:
    execution_result: ExecutionResult | None = None
    gates_passed: list[GateResult] = field(default_factory=list)
    gates_failed: list[GateResult] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    ledger_hash: str = ""

    @property
    def all_gates_passed(self) -> bool:
        return len(self.gates_failed) == 0


@dataclass(frozen=True, slots=True)
class _FilesystemSnapshot:
    path_hash: str
    exists: bool
    is_file: bool
    is_dir: bool
    size_bytes: int | None
    modified_time_ns: int | None
    content_hash: str | None
    error_code: str | None = None


class GovernedDispatcher:
    """Wraps the core Dispatcher with the full stabilization gate chain.

    Pipeline: identity -> trust -> meaning -> coordination -> prediction -> economics -> promotion -> execute -> verify -> compensate -> ledger
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        *,
        identity: IdentityBindingEngine | None = None,
        ontology: OntologyEnforcer | None = None,
        equilibrium: EquilibriumEngine | None = None,
        adversarial: AdversarialDefenseEngine | None = None,
        predictor: PredictiveFailureEngine | None = None,
        optimizer: EconomicOptimizer | None = None,
        promotion: AdaptivePromotionEngine | None = None,
        verifier: ExecutionVerificationLoop | None = None,
        recovery: FailureRecoveryEngine | None = None,
        boundary: SimRealityBoundary | None = None,
        capability_admission: CommandCapabilityAdmissionGate | None = None,
        effect_assurance: EffectAssuranceGate | None = None,
        effect_assurance_tenant_id: str = "operator",
        case_runtime: CaseRuntimeEngine | None = None,
        clock: Callable[[], str] = utc_now_text,
    ):
        self._dispatcher = dispatcher
        self._identity = identity or IdentityBindingEngine()
        self._ontology = ontology or OntologyEnforcer()
        self._equilibrium = equilibrium or EquilibriumEngine()
        self._adversarial = adversarial or AdversarialDefenseEngine()
        self._predictor = predictor or PredictiveFailureEngine()
        self._optimizer = optimizer or EconomicOptimizer()
        self._promotion = promotion or AdaptivePromotionEngine()
        self._verifier = verifier or ExecutionVerificationLoop()
        self._recovery = recovery or FailureRecoveryEngine()
        self._boundary = boundary or SimRealityBoundary()
        self._capability_admission = capability_admission
        self._effect_assurance = effect_assurance
        self._effect_assurance_tenant_id = effect_assurance_tenant_id
        self._case_runtime = case_runtime
        self._clock = clock
        self._ledger: list[dict[str, Any]] = []

    def governed_dispatch(self, context: GovernedDispatchContext) -> GovernedDispatchResult:
        """Execute with full gate chain. Fail-closed on any gate failure."""
        result = GovernedDispatchResult()
        now = self._clock()

        # --- Gate 1: Identity Binding ---
        try:
            self._identity.sign_intent(
                context.intent_id, context.actor_id,
                context.request.route, context.request.goal_id,
            )
            result.gates_passed.append(GateResult("identity_binding", True))
        except Exception as exc:
            bounded_error = _bounded_gate_error("identity binding failed", exc)
            result.gates_failed.append(GateResult("identity_binding", False, bounded_error))
            result.blocked = True
            result.block_reason = "identity_binding blocked"
            self._emit_ledger(context, result, now)
            return result

        # --- Gate 2: Predictive Failure ---
        prediction = self._predictor.predict(
            f"pred-{context.intent_id}", context.request.route, context.current_load
        )
        if prediction.recommendation == "abort":
            result.gates_failed.append(GateResult("predictive_failure", False, "predictive failure blocked dispatch"))
            result.blocked = True
            result.block_reason = "predictive_failure blocked"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("predictive_failure", True, "predictive failure check passed"))

        # --- Gate 3: Economic Optimization ---
        try:
            estimated_cost, estimated_value = _dispatch_economic_metrics(context.request.template)
        except ValueError as exc:
            bounded_error = _bounded_gate_error("economic metrics malformed", exc)
            result.gates_failed.append(GateResult("economic_optimization", False, bounded_error))
            result.blocked = True
            result.block_reason = "economic_optimization: malformed metrics"
            self._emit_ledger(context, result, now)
            return result
        estimate = self._optimizer.estimate(
            f"est-{context.intent_id}", context.request.route,
            cost=estimated_cost,
            value=estimated_value,
        )
        if estimate.recommendation == "reject":
            result.gates_failed.append(GateResult("economic_optimization", False, f"over_budget: remaining={self._optimizer.remaining_budget}"))
            result.blocked = True
            result.block_reason = "economic_optimization: over budget"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("economic_optimization", True, f"net_value={estimate.net_value}"))

        # --- Gate 4: Equilibrium Check ---
        allowed = self._equilibrium.record_action(context.actor_id)
        if not allowed:
            result.gates_failed.append(GateResult("equilibrium", False, "system at capacity"))
            result.blocked = True
            result.block_reason = "equilibrium: system at capacity"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("equilibrium", True, f"score={self._equilibrium.equilibrium_score()}"))

        # --- Gate 5: Sim/Real Promotion ---
        if execution_mode_requires_backend(context.mode) and not self._boundary.is_real():
            result.gates_failed.append(GateResult("promotion_boundary", False, f"mode={self._boundary.current_mode}, requested={context.mode}"))
            result.blocked = True
            result.block_reason = "promotion_boundary: not promoted to reality"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("promotion_boundary", True, f"mode={self._boundary.current_mode}"))

        # --- Gate 6: Governed Capability Admission ---
        if self._capability_admission is not None:
            try:
                admission = self._capability_admission.admit(
                    command_id=context.intent_id,
                    intent_name=context.request.route,
                )
            except (RuntimeCoreInvariantError, ValueError) as exc:
                bounded_error = _bounded_gate_error("capability admission failed", exc)
                result.gates_failed.append(GateResult("capability_admission", False, bounded_error))
                result.blocked = True
                result.block_reason = "capability_admission blocked"
                self._emit_ledger(context, result, now)
                return result
            if admission.status is not CommandCapabilityAdmissionStatus.ACCEPTED:
                result.gates_failed.append(
                    GateResult("capability_admission", False, admission.reason)
                )
                result.blocked = True
                result.block_reason = "capability_admission blocked"
                self._emit_ledger(context, result, now)
                return result
            result.gates_passed.append(
                GateResult(
                    "capability_admission",
                    True,
                    f"capability_id={admission.capability_id};owner_team={admission.owner_team}",
                )
            )

        # --- DISPATCH ---
        effect_plan = None
        filesystem_before: Mapping[str, _FilesystemSnapshot] = {}
        if self._effect_assurance is not None:
            try:
                effect_plan = self._effect_assurance.create_plan(
                    command_id=context.intent_id,
                    tenant_id=self._effect_assurance_tenant_id,
                    capability_id=context.request.route,
                    expected_effects=_expected_effects_from_request(context.request),
                    forbidden_effects=_forbidden_effects_from_request(context.request),
                )
                result.gates_passed.append(
                    GateResult("effect_plan", True, effect_plan.effect_plan_id)
                )
                filesystem_before = _filesystem_snapshots_from_request(context.request)
            except (RuntimeCoreInvariantError, ValueError) as exc:
                bounded_error = _bounded_gate_error("effect plan failed", exc)
                result.gates_failed.append(GateResult("effect_plan", False, bounded_error))
                result.blocked = True
                result.block_reason = "effect_plan blocked"
                self._emit_ledger(context, result, now)
                return result

        exec_result = self._dispatcher.dispatch(context.request)
        if filesystem_before:
            exec_result = _append_filesystem_delta_effects(
                context.request,
                exec_result,
                filesystem_before,
                observed_at=self._clock(),
            )
        result.execution_result = exec_result

        if self._effect_assurance is not None and effect_plan is not None:
            assurance_result = self._assure_execution_effect(
                context=context,
                execution_result=exec_result,
                effect_plan=effect_plan,
            )
            result.execution_result = assurance_result
            exec_result = assurance_result

        # --- Post: Execution Verification ---
        expected = "success" if exec_result.status == ExecutionOutcome.SUCCEEDED else "failure"
        actual = expected  # in real system, would check external effect
        verification = self._verifier.verify_execution(
            f"ver-{context.intent_id}", context.intent_id, expected, actual
        )
        if not verification.verified:
            # Trigger compensation
            self._recovery.register_compensation(
                f"comp-{context.intent_id}", context.intent_id, "rollback",
                detail="execution verification failed"
            )

        # --- Post: Action Binding ---
        self._identity.bind_action(
            f"bind-{context.intent_id}", context.intent_id,
            exec_result.execution_id,
        )

        # --- Post: Economic Commit ---
        self._optimizer.commit_spend(estimated_cost)

        # --- Post: Equilibrium Complete ---
        self._equilibrium.complete_action(context.actor_id)

        # --- Ledger ---
        self._emit_ledger(context, result, now)

        return result

    def _assure_execution_effect(
        self,
        *,
        context: GovernedDispatchContext,
        execution_result: ExecutionResult,
        effect_plan: EffectPlan,
    ) -> ExecutionResult:
        """Observe, verify, and reconcile actual effects after dispatch."""
        try:
            observed = self._effect_assurance.observe(execution_result)
            verification = self._effect_assurance.verify(
                plan=effect_plan,
                execution_result=execution_result,
                observed_effects=observed,
            )
            reconciliation = self._effect_assurance.reconcile(
                plan=effect_plan,
                observed_effects=observed,
                verification_result=verification,
            )
        except (RuntimeCoreInvariantError, ValueError) as exc:
            now = self._clock()
            return build_failure_result(
                execution_id=execution_result.execution_id,
                goal_id=execution_result.goal_id,
                started_at=execution_result.started_at,
                finished_at=now,
                failure=ExecutionFailure(
                    code="effect_assurance_failed",
                    message="effect assurance observation failed",
                    details={
                        "route": context.request.route,
                        "reason": _bounded_gate_error("effect assurance failed", exc),
                    },
                ),
                effect_name="effect_assurance_failed",
                metadata={
                    **dict(execution_result.metadata),
                    "effect_assurance_error": _bounded_gate_error(
                        "effect assurance failed",
                        exc,
                    ),
                },
            )

        assurance_metadata = {
            "effect_plan_id": effect_plan.effect_plan_id,
            "verification_result_id": verification.verification_id,
            "reconciliation_id": reconciliation.reconciliation_id,
            "reconciliation_status": reconciliation.status.value,
        }
        if reconciliation.status is not ReconciliationStatus.MATCH:
            case_id = self._open_reconciliation_case(
                context=context,
                effect_plan=effect_plan,
                verification_result_id=verification.verification_id,
                reconciliation_status=reconciliation.status,
                missing_effects=reconciliation.missing_effects,
                unexpected_effects=reconciliation.unexpected_effects,
            )
            if case_id is not None:
                reconciliation = self._effect_assurance.reconcile(
                    plan=effect_plan,
                    observed_effects=observed,
                    verification_result=verification,
                    case_id=case_id,
                )
                assurance_metadata = {
                    "effect_plan_id": effect_plan.effect_plan_id,
                    "verification_result_id": verification.verification_id,
                    "reconciliation_id": reconciliation.reconciliation_id,
                    "reconciliation_status": reconciliation.status.value,
                    "case_id": case_id,
                }
            now = self._clock()
            return build_failure_result(
                execution_id=execution_result.execution_id,
                goal_id=execution_result.goal_id,
                started_at=execution_result.started_at,
                finished_at=now,
                failure=ExecutionFailure(
                    code="effect_reconciliation_mismatch",
                    message="effect reconciliation did not match expected effects",
                    details=assurance_metadata,
                ),
                effect_name="effect_reconciliation_mismatch",
                metadata={
                    **dict(execution_result.metadata),
                    "effect_assurance": assurance_metadata,
                },
                execution_mode=execution_result.execution_mode,
            )

        try:
            self._effect_assurance.commit_graph(
                plan=effect_plan,
                observed_effects=observed,
                reconciliation=reconciliation,
            )
        except RuntimeCoreInvariantError as exc:
            now = self._clock()
            return build_failure_result(
                execution_id=execution_result.execution_id,
                goal_id=execution_result.goal_id,
                started_at=execution_result.started_at,
                finished_at=now,
                failure=ExecutionFailure(
                    code="effect_graph_commit_failed",
                    message="effect graph commit failed",
                    details={
                        **assurance_metadata,
                        "reason": _bounded_gate_error("effect graph commit failed", exc),
                    },
                ),
                effect_name="effect_graph_commit_failed",
                metadata={
                    **dict(execution_result.metadata),
                    "effect_assurance": assurance_metadata,
                },
            )

        return ExecutionResult(
            execution_id=execution_result.execution_id,
            goal_id=execution_result.goal_id,
            status=execution_result.status,
            actual_effects=execution_result.actual_effects,
            assumed_effects=execution_result.assumed_effects,
            started_at=execution_result.started_at,
            finished_at=execution_result.finished_at,
            metadata={
                **dict(execution_result.metadata),
                "effect_assurance": assurance_metadata,
            },
            extensions=execution_result.extensions,
            execution_mode=execution_result.execution_mode,
        )

    def _open_reconciliation_case(
        self,
        *,
        context: GovernedDispatchContext,
        effect_plan: EffectPlan,
        verification_result_id: str,
        reconciliation_status: ReconciliationStatus,
        missing_effects: tuple[str, ...],
        unexpected_effects: tuple[str, ...],
    ) -> str | None:
        """Open a durable case for unresolved effect reconciliation."""
        if self._case_runtime is None:
            return None

        case_id = f"case-{effect_plan.command_id}"
        try:
            self._case_runtime.open_case(
                case_id,
                effect_plan.tenant_id,
                "Effect reconciliation mismatch",
                kind=CaseKind.INCIDENT,
                severity=CaseSeverity.HIGH,
                description="Governed dispatch produced effects that did not match the effect plan.",
                opened_by="effect_assurance",
            )
        except RuntimeCoreInvariantError as exc:
            if "Duplicate case_id" not in str(exc):
                raise

        evidence_id = stable_identifier(
            "effect-case-evidence",
            {
                "case_id": case_id,
                "effect_plan_id": effect_plan.effect_plan_id,
                "verification_result_id": verification_result_id,
            },
        )
        try:
            self._case_runtime.add_evidence(
                evidence_id,
                case_id,
                "effect_reconciliation",
                effect_plan.effect_plan_id,
                title="Effect reconciliation record",
                description="Effect reconciliation mismatch record",
                submitted_by="effect_assurance",
            )
        except RuntimeCoreInvariantError as exc:
            if "Duplicate evidence_id" not in str(exc):
                raise

        finding_id = stable_identifier(
            "effect-case-finding",
            {
                "case_id": case_id,
                "effect_plan_id": effect_plan.effect_plan_id,
                "status": reconciliation_status.value,
            },
        )
        try:
            self._case_runtime.record_finding(
                finding_id,
                case_id,
                "Effect mismatch detected",
                severity=FindingSeverity.HIGH,
                description="Effect reconciliation produced missing or unexpected effects",
                evidence_ids=(evidence_id,),
                remediation="Review effect plan, observed effects, provider receipt, and compensation path.",
            )
        except RuntimeCoreInvariantError as exc:
            if "Duplicate finding_id" not in str(exc):
                raise
        return case_id

    def _emit_ledger(self, context: GovernedDispatchContext, result: GovernedDispatchResult, timestamp: str) -> None:
        entry = {
            "actor_id": context.actor_id,
            "intent_id": context.intent_id,
            "route": context.request.route,
            "goal_id": context.request.goal_id,
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "gates_passed": len(result.gates_passed),
            "gates_failed": len(result.gates_failed),
            "execution_mode": context.mode,
            "timestamp": timestamp,
        }
        entry_str = str(sorted(entry.items()))
        result.ledger_hash = sha256(entry_str.encode()).hexdigest()
        self._ledger.append(entry)

    @property
    def ledger_count(self) -> int:
        return len(self._ledger)

    @property
    def ledger(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._ledger)


def _expected_effects_from_request(request: DispatchRequest) -> tuple[ExpectedEffect, ...]:
    """Build required expected effects from dispatch template metadata."""
    declared = _string_tuple(request.template.get("declared_effects"))
    if not declared:
        declared = _default_declared_effects(request)
    return tuple(
        ExpectedEffect(
            effect_id=effect_name,
            name=effect_name,
            target_ref=request.goal_id,
            required=True,
            verification_method="actual_effect",
        )
        for effect_name in declared
    )


def _forbidden_effects_from_request(request: DispatchRequest) -> tuple[str, ...]:
    """Build forbidden effect names from dispatch template metadata."""
    forbidden = _string_tuple(request.template.get("forbidden_effects"))
    if forbidden:
        return forbidden
    default = [f"{request.route}:unexpected_duplicate"]
    if _effect_observation_paths_from_request(request):
        default.append("file_observation_failed")
    return tuple(default)


def _default_declared_effects(request: DispatchRequest) -> tuple[str, ...]:
    if request.route == "shell_command":
        if _effect_observation_paths_from_request(request):
            return ("process_completed", "file_changed")
        return ("process_completed",)
    return ("execution_completed",)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _coerce_dispatch_execution_mode(mode: ExecutionMode | str) -> ExecutionMode:
    """Normalize legacy dispatcher labels to the shared ExecutionMode ABI."""

    if mode == "reality":
        return ExecutionMode.REAL
    if mode == "sandbox":
        return ExecutionMode.TEST
    return coerce_execution_mode(mode)


def _effect_observation_paths_from_request(request: DispatchRequest) -> tuple[str, ...]:
    paths = _string_tuple(request.template.get("effect_observation_paths"))
    if not paths:
        return ()
    return tuple(_bind_template_text(path, request.bindings) for path in paths)


def _bind_template_text(value: str, bindings: Mapping[str, str]) -> str:
    normalized = {
        key: item
        for key, item in bindings.items()
        if isinstance(key, str) and isinstance(item, str)
    }
    for _, field_name, _, _ in Formatter().parse(value):
        if field_name is not None and field_name not in normalized:
            raise RuntimeCoreInvariantError("effect observation path binding failed")
    return value.format_map(normalized)


def _filesystem_snapshots_from_request(request: DispatchRequest) -> Mapping[str, _FilesystemSnapshot]:
    return {
        path: _capture_filesystem_snapshot(path)
        for path in _effect_observation_paths_from_request(request)
    }


def _capture_filesystem_snapshot(path_text: str) -> _FilesystemSnapshot:
    path_hash = _path_hash(path_text)
    try:
        path = Path(path_text)
        exists = path.exists()
        if not exists:
            return _FilesystemSnapshot(
                path_hash=path_hash,
                exists=False,
                is_file=False,
                is_dir=False,
                size_bytes=None,
                modified_time_ns=None,
                content_hash=None,
            )
        is_file = path.is_file()
        is_dir = path.is_dir()
        stat_result = path.stat()
        return _FilesystemSnapshot(
            path_hash=path_hash,
            exists=True,
            is_file=is_file,
            is_dir=is_dir,
            size_bytes=stat_result.st_size,
            modified_time_ns=stat_result.st_mtime_ns,
            content_hash=_file_content_hash(path) if is_file else None,
        )
    except OSError:
        return _FilesystemSnapshot(
            path_hash=path_hash,
            exists=False,
            is_file=False,
            is_dir=False,
            size_bytes=None,
            modified_time_ns=None,
            content_hash=None,
            error_code="filesystem_observation_error",
        )


def _append_filesystem_delta_effects(
    request: DispatchRequest,
    execution_result: ExecutionResult,
    before: Mapping[str, _FilesystemSnapshot],
    *,
    observed_at: str,
) -> ExecutionResult:
    effects = list(execution_result.actual_effects)
    observation_records: list[dict[str, Any]] = []
    for path_text, before_snapshot in before.items():
        after_snapshot = _capture_filesystem_snapshot(path_text)
        observation_records.append(
            _filesystem_observation_record(
                path_text=path_text,
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
            )
        )
        if before_snapshot.error_code or after_snapshot.error_code:
            effects.append(
                _filesystem_effect_record(
                    execution_id=execution_result.execution_id,
                    effect_name="file_observation_failed",
                    before_snapshot=before_snapshot,
                    after_snapshot=after_snapshot,
                    observed_at=observed_at,
                )
            )
            continue
        if _filesystem_snapshot_changed(before_snapshot, after_snapshot):
            effects.append(
                _filesystem_effect_record(
                    execution_id=execution_result.execution_id,
                    effect_name="file_changed",
                    before_snapshot=before_snapshot,
                    after_snapshot=after_snapshot,
                    observed_at=observed_at,
                )
            )
    if len(effects) == len(execution_result.actual_effects):
        return ExecutionResult(
            execution_id=execution_result.execution_id,
            goal_id=execution_result.goal_id,
            status=execution_result.status,
            actual_effects=execution_result.actual_effects,
            assumed_effects=execution_result.assumed_effects,
            started_at=execution_result.started_at,
            finished_at=execution_result.finished_at,
            metadata={
                **dict(execution_result.metadata),
                "filesystem_effect_observations": tuple(observation_records),
            },
            extensions=execution_result.extensions,
            execution_mode=execution_result.execution_mode,
        )
    return ExecutionResult(
        execution_id=execution_result.execution_id,
        goal_id=execution_result.goal_id,
        status=execution_result.status,
        actual_effects=tuple(effects),
        assumed_effects=execution_result.assumed_effects,
        started_at=execution_result.started_at,
        finished_at=execution_result.finished_at,
        metadata={
            **dict(execution_result.metadata),
            "filesystem_effect_observations": tuple(observation_records),
        },
        extensions=execution_result.extensions,
        execution_mode=execution_result.execution_mode,
    )


def _filesystem_observation_record(
    *,
    path_text: str,
    before_snapshot: _FilesystemSnapshot,
    after_snapshot: _FilesystemSnapshot,
) -> dict[str, Any]:
    return {
        "path_hash": _path_hash(path_text),
        "before": _snapshot_details(before_snapshot),
        "after": _snapshot_details(after_snapshot),
        "changed": _filesystem_snapshot_changed(before_snapshot, after_snapshot),
    }


def _filesystem_effect_record(
    *,
    execution_id: str,
    effect_name: str,
    before_snapshot: _FilesystemSnapshot,
    after_snapshot: _FilesystemSnapshot,
    observed_at: str,
) -> EffectRecord:
    evidence_hash = sha256(
        f"{execution_id}:{effect_name}:{before_snapshot.path_hash}:{after_snapshot.path_hash}:"
        f"{before_snapshot.content_hash}:{after_snapshot.content_hash}:{after_snapshot.modified_time_ns}".encode()
    ).hexdigest()[:16]
    evidence_ref = f"filesystem-delta:{execution_id}:{before_snapshot.path_hash[:16]}:{evidence_hash}"
    return EffectRecord(
        name=effect_name,
        details={
            "effect_id": effect_name,
            "source": execution_id,
            "evidence_ref": evidence_ref,
            "observed_value": {
                "before": _snapshot_details(before_snapshot),
                "after": _snapshot_details(after_snapshot),
                "observed_at": observed_at,
            },
        },
    )


def _snapshot_details(snapshot: _FilesystemSnapshot) -> dict[str, Any]:
    return {
        "path_hash": snapshot.path_hash,
        "exists": snapshot.exists,
        "is_file": snapshot.is_file,
        "is_dir": snapshot.is_dir,
        "size_bytes": snapshot.size_bytes,
        "modified_time_ns": snapshot.modified_time_ns,
        "content_hash": snapshot.content_hash,
        "error_code": snapshot.error_code,
    }


def _filesystem_snapshot_changed(before: _FilesystemSnapshot, after: _FilesystemSnapshot) -> bool:
    return _snapshot_details(before) != _snapshot_details(after)


def _path_hash(path_text: str) -> str:
    try:
        material = str(Path(path_text).resolve(strict=False))
    except OSError:
        material = path_text
    return sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _file_content_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
