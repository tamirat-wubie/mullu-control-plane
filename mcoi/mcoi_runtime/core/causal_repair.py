"""Purpose: causal repair engine for rollback, compensation, and reconciliation.
Governance scope: local admission, repair planning, durable receipts, and
    false-success blocking for state-changing action episodes.
Dependencies: Python standard library and runtime invariant helpers only.
Invariants:
  - No mutating action is admitted without bounded scope and repair knowledge.
  - No external effect is admitted without idempotency evidence.
  - Unknown commit state blocks blind retry until reconciliation.
  - Rollback never overwrites drifted state silently.
  - Closure never claims success without verification evidence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
import json
from typing import Any, Callable, Iterable, Mapping

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


State = Any
StateTransform = Callable[[State], State]
StateProbe = Callable[[State], bool]
StateReconciler = Callable[[State], "CommitState"]
CompensationJudge = Callable[[State], "CompensationAdequacyStatus"]


class CausalRepairError(RuntimeCoreInvariantError):
    """Raised when a causal repair contract violates a hard invariant."""


class UnknownCommitStateError(RuntimeCoreInvariantError):
    """Raised by an action when the engine cannot prove whether it committed."""


class RepairEngineCrash(RuntimeCoreInvariantError):
    """Raised by tests or adapters to simulate a crash after durable prepare."""


class EffectClass(StrEnum):
    """Externality class for a candidate action."""

    READ_ONLY = "read_only"
    INTERNAL_REVERSIBLE = "internal_reversible"
    INTERNAL_VERSIONED = "internal_versioned"
    EXTERNAL_MUTATION = "external_mutation"
    USER_VISIBLE = "user_visible"
    FINANCIAL_OR_LEGAL = "financial_or_legal"
    PUBLIC_IRREVERSIBLE = "public_irreversible"
    PHYSICAL_WORLD = "physical_world"


class ReversibilityClass(StrEnum):
    """Repair class for a candidate action."""

    READ_ONLY = "read_only"
    EXACT_ROLLBACK = "exact_rollback"
    VERSION_RESTORE = "version_restore"
    SEMANTIC_COMPENSATION = "semantic_compensation"
    RECONCILE_REQUIRED = "reconcile_required"
    HUMAN_ESCALATION = "human_escalation"
    FORBIDDEN = "forbidden"


class SnapshotQuality(IntEnum):
    """Quality of before-state evidence available for repair."""

    S0_NONE = 0
    S1_PARTIAL = 1
    S2_LOCAL = 2
    S3_VERSIONED = 3
    S4_CAUSAL_WITH_EXTERNAL_IDS = 4
    S5_REPLAYABLE = 5


class CommitState(StrEnum):
    """Observed or reconciled commit state for an action."""

    NOT_ATTEMPTED = "not_attempted"
    ATTEMPTED_NO_COMMIT_EVIDENCE = "attempted_no_commit_evidence"
    COMMITTED_CONFIRMED = "committed_confirmed"
    FAILED_CONFIRMED = "failed_confirmed"
    FAILED_BEFORE_COMMIT = "failed_before_commit"
    FAILED_AFTER_COMMIT = "failed_after_commit"
    UNKNOWN_COMMIT_STATE = "unknown_commit_state"
    PARTIAL_COMMIT = "partial_commit"
    DUPLICATE_DETECTED = "duplicate_detected"
    DUPLICATE_RISK = "duplicate_risk"
    RECONCILED_SAFE_TO_RETRY = "reconciled_safe_to_retry"
    RECONCILED_NEEDS_COMPENSATION = "reconciled_needs_compensation"
    ESCALATED_AMBIGUOUS = "escalated_ambiguous"


class RepairStrategy(StrEnum):
    """Repair strategy selected for a committed or ambiguous delta."""

    NONE_REQUIRED = "none_required"
    EXACT_ROLLBACK = "exact_rollback"
    VERSION_RESTORE = "version_restore"
    SEMANTIC_COMPENSATION = "semantic_compensation"
    RECONCILE_THEN_DECIDE = "reconcile_then_decide"
    QUARANTINE = "quarantine"
    ESCALATE = "escalate"
    FORBID = "forbid"


class AdmissionStatus(StrEnum):
    """Pre-mutation admission outcome."""

    ADMITTED = "admitted"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"


class RepairClosureStatus(StrEnum):
    """Truthful terminal closure status for a repair episode."""

    SUCCESS_VERIFIED = "success_verified"
    SUCCESS_WITH_COMPENSATION = "success_with_compensation"
    ROLLED_BACK_VERIFIED = "rolled_back_verified"
    VERSION_RESTORED_VERIFIED = "version_restored_verified"
    SEMANTICALLY_REPAIRED = "semantically_repaired"
    PARTIALLY_REPAIRED_ESCALATED = "partially_repaired_escalated"
    UNKNOWN_COMMIT_ESCALATED = "unknown_commit_escalated"
    BLOCKED_BEFORE_DAMAGE = "blocked_before_damage"
    FAILED_UNSAFE_TO_RETRY = "failed_unsafe_to_retry"
    FALSE_SUCCESS_BLOCKED = "false_success_blocked"
    ESCALATED_UNRESOLVED = "escalated_unresolved"


class CompensationAdequacyStatus(StrEnum):
    """Adequacy judgment for a compensation effect."""

    EXACTLY_NEUTRALIZED = "compensation_exactly_neutralized"
    SEMANTICALLY_ACCEPTABLE = "compensation_semantically_acceptable"
    PARTIAL = "compensation_partial"
    RISKIER_THAN_FAILURE = "compensation_riskier_than_failure"
    FAILED = "compensation_failed"
    FORBIDDEN = "compensation_forbidden"


class DurableEpisodeState(StrEnum):
    """Durable milestones that make crash recovery observable."""

    EPISODE_PREPARED = "episode_prepared"
    ACTION_PREPARED = "action_prepared"
    ACTION_ATTEMPTED = "action_attempted"
    ACTION_COMMITTED = "action_committed"
    REPAIR_REQUIRED = "repair_required"
    REPAIR_ATTEMPTED = "repair_attempted"
    REPAIR_VERIFIED = "repair_verified"
    EPISODE_CLOSED = "episode_closed"


_MUTATING_EFFECTS = frozenset(
    {
        EffectClass.INTERNAL_REVERSIBLE,
        EffectClass.INTERNAL_VERSIONED,
        EffectClass.EXTERNAL_MUTATION,
        EffectClass.USER_VISIBLE,
        EffectClass.FINANCIAL_OR_LEGAL,
        EffectClass.PUBLIC_IRREVERSIBLE,
        EffectClass.PHYSICAL_WORLD,
    }
)
_EXTERNAL_EFFECTS = frozenset(
    {
        EffectClass.EXTERNAL_MUTATION,
        EffectClass.USER_VISIBLE,
        EffectClass.FINANCIAL_OR_LEGAL,
        EffectClass.PUBLIC_IRREVERSIBLE,
        EffectClass.PHYSICAL_WORLD,
    }
)
_ACCEPTABLE_COMPENSATION = frozenset(
    {
        CompensationAdequacyStatus.EXACTLY_NEUTRALIZED,
        CompensationAdequacyStatus.SEMANTICALLY_ACCEPTABLE,
    }
)


@dataclass(frozen=True, slots=True)
class SnapshotReceipt:
    """Before-state evidence used to bound rollback claims."""

    snapshot_id: str
    action_id: str
    before_hash: str
    snapshot_quality: SnapshotQuality
    observed_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    version_id: str | None = None
    restore_pointer: str | None = None
    external_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("snapshot_id", "action_id", "before_hash"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "snapshot_quality",
            _coerce_snapshot_quality(self.snapshot_quality),
        )
        object.__setattr__(
            self,
            "observed_fields",
            _text_tuple(self.observed_fields, "observed_fields", allow_empty=True),
        )
        object.__setattr__(
            self,
            "missing_fields",
            _text_tuple(self.missing_fields, "missing_fields", allow_empty=True),
        )
        object.__setattr__(
            self,
            "external_reference_ids",
            _text_tuple(
                self.external_reference_ids,
                "external_reference_ids",
                allow_empty=True,
            ),
        )
        if self.version_id is not None:
            object.__setattr__(
                self,
                "version_id",
                ensure_non_empty_text("version_id", self.version_id),
            )
        if self.restore_pointer is not None:
            object.__setattr__(
                self,
                "restore_pointer",
                ensure_non_empty_text("restore_pointer", self.restore_pointer),
            )

    @property
    def rollback_claim_allowed(self) -> bool:
        return self.snapshot_quality >= SnapshotQuality.S2_LOCAL

    @property
    def version_restore_allowed(self) -> bool:
        return self.snapshot_quality >= SnapshotQuality.S3_VERSIONED


@dataclass(frozen=True, slots=True)
class CompensationContract:
    """Pre-registered compensation plan for a semantic repair path."""

    compensation_id: str
    original_action_id: str
    idempotency_key: str
    adequacy_criteria: tuple[str, ...]
    verification_rule: str
    escalation_rule: str
    max_attempts: int = 1
    compensation_deadline: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "compensation_id",
            "original_action_id",
            "idempotency_key",
            "verification_rule",
            "escalation_rule",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "adequacy_criteria",
            _text_tuple(self.adequacy_criteria, "adequacy_criteria"),
        )
        if isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise CausalRepairError("max_attempts must be a positive integer")
        if self.compensation_deadline is not None:
            object.__setattr__(
                self,
                "compensation_deadline",
                ensure_non_empty_text(
                    "compensation_deadline",
                    self.compensation_deadline,
                ),
            )


@dataclass(frozen=True, slots=True)
class ReconciliationContract:
    """Pre-registered unknown-commit reconciliation plan."""

    reconciliation_id: str
    action_id: str
    provider_lookup_ref: str
    idempotency_lookup_key: str
    safe_retry_condition: str
    escalation_condition: str

    def __post_init__(self) -> None:
        for field_name in (
            "reconciliation_id",
            "action_id",
            "provider_lookup_ref",
            "idempotency_lookup_key",
            "safe_retry_condition",
            "escalation_condition",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )


@dataclass(frozen=True, slots=True)
class CausalRepairAction:
    """Single action admitted by the causal repair engine."""

    action_id: str
    actor_id: str
    domain: str
    target_ref: str
    boundary_scope: tuple[str, ...]
    effect_class: EffectClass
    reversibility_class: ReversibilityClass
    execute: StateTransform
    verify_success: StateProbe
    rollback: StateTransform | None = None
    compensate: StateTransform | None = None
    reconcile: StateReconciler | None = None
    verify_repair: StateProbe | None = None
    compensation_adequacy: CompensationJudge | None = None
    drift_detector: StateProbe | None = None
    snapshot_receipt: SnapshotReceipt | None = None
    compensation_contract: CompensationContract | None = None
    reconciliation_contract: ReconciliationContract | None = None
    idempotency_key: str | None = None
    risk_score: float = 0.0
    requires_approval: bool = False
    approval_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("action_id", "actor_id", "domain", "target_ref"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "boundary_scope",
            _text_tuple(self.boundary_scope, "boundary_scope", allow_empty=True),
        )
        object.__setattr__(self, "effect_class", EffectClass(self.effect_class))
        object.__setattr__(
            self,
            "reversibility_class",
            ReversibilityClass(self.reversibility_class),
        )
        if not callable(self.execute):
            raise CausalRepairError("execute must be callable")
        if not callable(self.verify_success):
            raise CausalRepairError("verify_success must be callable")
        for field_name in (
            "rollback",
            "compensate",
            "reconcile",
            "verify_repair",
            "compensation_adequacy",
            "drift_detector",
        ):
            callback = getattr(self, field_name)
            if callback is not None and not callable(callback):
                raise CausalRepairError(f"{field_name} must be callable")
        if self.snapshot_receipt is not None and not isinstance(
            self.snapshot_receipt,
            SnapshotReceipt,
        ):
            raise CausalRepairError("snapshot_receipt must be a SnapshotReceipt")
        if self.compensation_contract is not None and not isinstance(
            self.compensation_contract,
            CompensationContract,
        ):
            raise CausalRepairError(
                "compensation_contract must be a CompensationContract"
            )
        if self.reconciliation_contract is not None and not isinstance(
            self.reconciliation_contract,
            ReconciliationContract,
        ):
            raise CausalRepairError(
                "reconciliation_contract must be a ReconciliationContract"
            )
        if self.idempotency_key is not None:
            object.__setattr__(
                self,
                "idempotency_key",
                ensure_non_empty_text("idempotency_key", self.idempotency_key),
            )
        if self.approval_ref is not None:
            object.__setattr__(
                self,
                "approval_ref",
                ensure_non_empty_text("approval_ref", self.approval_ref),
            )
        if not isinstance(self.requires_approval, bool):
            raise CausalRepairError("requires_approval must be a boolean")
        if isinstance(self.risk_score, bool) or not 0.0 <= float(self.risk_score) <= 1.0:
            raise CausalRepairError("risk_score must be a number in [0.0, 1.0]")
        object.__setattr__(self, "risk_score", float(self.risk_score))


@dataclass(frozen=True, slots=True)
class RepairAdmissionReceipt:
    """Admission result produced before mutation."""

    admission_id: str
    action_id: str
    status: AdmissionStatus
    reason: str
    repair_strategy: RepairStrategy
    evidence_refs: tuple[str, ...]


@dataclass(slots=True)
class ActionRepairReceipt:
    """Execution and repair receipt for one action."""

    action_id: str
    commit_state: CommitState
    before_hash: str | None = None
    after_hash: str | None = None
    admission_id: str | None = None
    repair_strategy: RepairStrategy = RepairStrategy.NONE_REQUIRED
    repair_status: str | None = None
    error: str | None = None
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DurableRepairReceipt:
    """Durable episode milestone."""

    receipt_id: str
    episode_id: str
    state: DurableEpisodeState
    action_id: str | None
    evidence_ref: str


@dataclass(slots=True)
class RepairEpisodeReceipt:
    """Terminal episode receipt returned by the engine."""

    episode_id: str
    goal: str
    admissions: list[RepairAdmissionReceipt] = field(default_factory=list)
    actions: list[ActionRepairReceipt] = field(default_factory=list)
    durable_receipts: list[DurableRepairReceipt] = field(default_factory=list)
    repaired_deltas: list[str] = field(default_factory=list)
    unresolved_deltas: list[str] = field(default_factory=list)
    final_status: RepairClosureStatus = RepairClosureStatus.ESCALATED_UNRESOLVED
    final_state: State | None = None
    ledger_hash: str = ""


class InMemoryRepairEpisodeStore:
    """Append-only in-memory durable receipt store for local repair episodes."""

    def __init__(self) -> None:
        self._receipts: dict[str, list[DurableRepairReceipt]] = {}

    def append(
        self,
        *,
        episode_id: str,
        state: DurableEpisodeState,
        action_id: str | None,
        evidence_ref: str,
    ) -> DurableRepairReceipt:
        receipt = DurableRepairReceipt(
            receipt_id=stable_identifier(
                "causal-repair-durable",
                {
                    "episode_id": episode_id,
                    "state": state.value,
                    "action_id": action_id or "",
                    "index": len(self._receipts.get(episode_id, ())),
                },
            ),
            episode_id=episode_id,
            state=state,
            action_id=action_id,
            evidence_ref=ensure_non_empty_text("evidence_ref", evidence_ref),
        )
        self._receipts.setdefault(episode_id, []).append(receipt)
        return receipt

    def list_episode(self, episode_id: str) -> tuple[DurableRepairReceipt, ...]:
        return tuple(self._receipts.get(episode_id, ()))

    def latest_state(self, episode_id: str) -> DurableEpisodeState | None:
        receipts = self._receipts.get(episode_id, ())
        if not receipts:
            return None
        return receipts[-1].state

    def recoverable_episode_ids(self) -> tuple[str, ...]:
        return tuple(
            episode_id
            for episode_id, receipts in sorted(self._receipts.items())
            if receipts and receipts[-1].state is not DurableEpisodeState.EPISODE_CLOSED
        )


class CausalRepairEngine:
    """Run repair-aware action episodes with admission and closure receipts."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        invariant_check: StateProbe | None = None,
        store: InMemoryRepairEpisodeStore | None = None,
    ) -> None:
        self._clock = clock
        self._invariant_check = invariant_check or (lambda _state: True)
        self._store = store or InMemoryRepairEpisodeStore()
        self._action_idempotency_keys: set[str] = set()
        self._compensation_idempotency_keys: set[str] = set()

    @property
    def store(self) -> InMemoryRepairEpisodeStore:
        return self._store

    def build_episode_id(
        self,
        *,
        goal: str,
        actions: Iterable[CausalRepairAction],
    ) -> str:
        action_ids = tuple(action.action_id for action in actions)
        return stable_identifier("causal-repair-episode", {"goal": goal, "actions": action_ids})

    def admit_action(self, action: CausalRepairAction) -> RepairAdmissionReceipt:
        """Classify whether an action can enter mutation."""
        evidence_refs = self._admission_evidence_refs(action)
        strategy = _strategy_for_reversibility(action.reversibility_class)
        status = AdmissionStatus.ADMITTED
        reason = "admitted"

        if action.reversibility_class is ReversibilityClass.FORBIDDEN:
            status = AdmissionStatus.BLOCKED
            reason = "action_forbidden"
        elif action.effect_class in _MUTATING_EFFECTS and not action.boundary_scope:
            status = AdmissionStatus.BLOCKED
            reason = "bounded_scope_missing"
        elif action.requires_approval and not action.approval_ref:
            status = AdmissionStatus.APPROVAL_REQUIRED
            reason = "approval_required"
        elif action.effect_class in _EXTERNAL_EFFECTS and not action.idempotency_key:
            status = AdmissionStatus.BLOCKED
            reason = "idempotency_key_missing"
        elif action.reversibility_class is ReversibilityClass.EXACT_ROLLBACK:
            if action.rollback is None:
                status = AdmissionStatus.BLOCKED
                reason = "rollback_contract_missing"
            elif (
                action.snapshot_receipt is None
                or not action.snapshot_receipt.rollback_claim_allowed
            ):
                status = AdmissionStatus.BLOCKED
                reason = "snapshot_insufficient_for_exact_rollback"
        elif action.reversibility_class is ReversibilityClass.VERSION_RESTORE:
            if action.rollback is None:
                status = AdmissionStatus.BLOCKED
                reason = "version_restore_contract_missing"
            elif (
                action.snapshot_receipt is None
                or not action.snapshot_receipt.version_restore_allowed
            ):
                status = AdmissionStatus.BLOCKED
                reason = "snapshot_insufficient_for_version_restore"
        elif action.reversibility_class is ReversibilityClass.SEMANTIC_COMPENSATION:
            if action.compensate is None or action.compensation_contract is None:
                status = AdmissionStatus.BLOCKED
                reason = "compensation_contract_missing"
            elif not action.compensation_contract.idempotency_key:
                status = AdmissionStatus.BLOCKED
                reason = "compensation_idempotency_missing"
        elif action.reversibility_class is ReversibilityClass.RECONCILE_REQUIRED:
            if action.reconcile is None or action.reconciliation_contract is None:
                status = AdmissionStatus.BLOCKED
                reason = "reconciliation_contract_missing"
        elif action.reversibility_class is ReversibilityClass.HUMAN_ESCALATION:
            status = AdmissionStatus.APPROVAL_REQUIRED
            reason = "human_escalation_required"
        elif (
            action.effect_class in _MUTATING_EFFECTS
            and action.reversibility_class is ReversibilityClass.READ_ONLY
        ):
            status = AdmissionStatus.BLOCKED
            reason = "mutating_action_marked_read_only"

        return RepairAdmissionReceipt(
            admission_id=stable_identifier(
                "causal-repair-admission",
                {
                    "action_id": action.action_id,
                    "status": status.value,
                    "reason": reason,
                    "strategy": strategy.value,
                },
            ),
            action_id=action.action_id,
            status=status,
            reason=reason,
            repair_strategy=strategy,
            evidence_refs=evidence_refs,
        )

    def run(
        self,
        *,
        goal: str,
        state: State,
        actions: tuple[CausalRepairAction, ...],
        episode_id: str | None = None,
    ) -> RepairEpisodeReceipt:
        """Execute actions in order and repair committed deltas on failure."""
        ensure_non_empty_text("goal", goal)
        if not actions:
            raise CausalRepairError("actions must contain at least one action")
        episode_id = episode_id or self.build_episode_id(goal=goal, actions=actions)
        episode = RepairEpisodeReceipt(episode_id=episode_id, goal=goal)
        episode.durable_receipts.append(
            self._persist(
                episode_id=episode_id,
                state=DurableEpisodeState.EPISODE_PREPARED,
                action_id=None,
                evidence_ref=f"goal://{stable_identifier('causal-repair-goal', {'goal': goal})}",
            )
        )
        committed: list[tuple[CausalRepairAction, ActionRepairReceipt]] = []
        current_state = deepcopy(state)

        for action in actions:
            admission = self.admit_action(action)
            episode.admissions.append(admission)
            if admission.status is not AdmissionStatus.ADMITTED:
                receipt = ActionRepairReceipt(
                    action_id=action.action_id,
                    commit_state=CommitState.FAILED_BEFORE_COMMIT,
                    admission_id=admission.admission_id,
                    error=admission.reason,
                    evidence_refs=list(admission.evidence_refs),
                )
                episode.actions.append(receipt)
                episode.final_status = RepairClosureStatus.BLOCKED_BEFORE_DAMAGE
                episode.final_state = current_state
                return self._close_episode(episode)

            before_hash = _state_hash(current_state)
            episode.durable_receipts.append(
                self._persist(
                    episode_id=episode_id,
                    state=DurableEpisodeState.ACTION_PREPARED,
                    action_id=action.action_id,
                    evidence_ref=admission.admission_id,
                )
            )
            if action.idempotency_key in self._action_idempotency_keys:
                receipt = ActionRepairReceipt(
                    action_id=action.action_id,
                    commit_state=CommitState.DUPLICATE_DETECTED,
                    before_hash=before_hash,
                    admission_id=admission.admission_id,
                    error="duplicate_action_idempotency_key",
                    evidence_refs=list(admission.evidence_refs),
                )
                episode.actions.append(receipt)
                episode.final_status = RepairClosureStatus.FAILED_UNSAFE_TO_RETRY
                episode.final_state = current_state
                return self._close_episode(episode)

            episode.durable_receipts.append(
                self._persist(
                    episode_id=episode_id,
                    state=DurableEpisodeState.ACTION_ATTEMPTED,
                    action_id=action.action_id,
                    evidence_ref=admission.admission_id,
                )
            )
            try:
                next_state = action.execute(deepcopy(current_state))
            except RepairEngineCrash:
                raise
            except UnknownCommitStateError as exc:
                receipt = ActionRepairReceipt(
                    action_id=action.action_id,
                    commit_state=CommitState.UNKNOWN_COMMIT_STATE,
                    before_hash=before_hash,
                    admission_id=admission.admission_id,
                    repair_strategy=RepairStrategy.RECONCILE_THEN_DECIDE,
                    error=_bounded_error(exc),
                    evidence_refs=list(admission.evidence_refs),
                )
                episode.actions.append(receipt)
                return self._handle_unknown_commit(
                    episode=episode,
                    state=current_state,
                    action=action,
                    receipt=receipt,
                )
            except Exception as exc:
                receipt = ActionRepairReceipt(
                    action_id=action.action_id,
                    commit_state=CommitState.FAILED_BEFORE_COMMIT,
                    before_hash=before_hash,
                    admission_id=admission.admission_id,
                    error=_bounded_error(exc),
                    evidence_refs=list(admission.evidence_refs),
                )
                episode.actions.append(receipt)
                return self._repair_committed(
                    episode=episode,
                    state=current_state,
                    committed=committed,
                )

            after_hash = _state_hash(next_state)
            if action.idempotency_key is not None:
                self._action_idempotency_keys.add(action.idempotency_key)
            receipt = ActionRepairReceipt(
                action_id=action.action_id,
                commit_state=CommitState.COMMITTED_CONFIRMED,
                before_hash=before_hash,
                after_hash=after_hash,
                admission_id=admission.admission_id,
                evidence_refs=list(admission.evidence_refs),
            )
            episode.durable_receipts.append(
                self._persist(
                    episode_id=episode_id,
                    state=DurableEpisodeState.ACTION_COMMITTED,
                    action_id=action.action_id,
                    evidence_ref=admission.admission_id,
                )
            )
            episode.actions.append(receipt)
            committed.append((action, receipt))

            if not action.verify_success(next_state) or not self._invariant_check(next_state):
                receipt.commit_state = CommitState.FAILED_AFTER_COMMIT
                receipt.error = "verification_or_invariant_failed"
                return self._repair_committed(
                    episode=episode,
                    state=next_state,
                    committed=committed,
                )

            current_state = next_state

        episode.final_status = RepairClosureStatus.SUCCESS_VERIFIED
        episode.final_state = current_state
        return self._close_episode(episode)

    def recoverable_episode_ids(self) -> tuple[str, ...]:
        """Return episode ids that have durable receipts but no closure receipt."""
        return self._store.recoverable_episode_ids()

    def _handle_unknown_commit(
        self,
        *,
        episode: RepairEpisodeReceipt,
        state: State,
        action: CausalRepairAction,
        receipt: ActionRepairReceipt,
    ) -> RepairEpisodeReceipt:
        episode.durable_receipts.append(
            self._persist(
                episode_id=episode.episode_id,
                state=DurableEpisodeState.REPAIR_REQUIRED,
                action_id=action.action_id,
                evidence_ref=receipt.admission_id or action.action_id,
            )
        )
        if action.reconcile is None:
            receipt.repair_status = "reconciliation_missing"
            episode.unresolved_deltas.append(action.action_id)
            episode.final_status = RepairClosureStatus.UNKNOWN_COMMIT_ESCALATED
            episode.final_state = state
            return self._close_episode(episode)

        reconciled = action.reconcile(deepcopy(state))
        receipt.evidence_refs.append(
            f"reconciliation://{action.reconciliation_contract.reconciliation_id}"
            if action.reconciliation_contract is not None
            else f"reconciliation://{action.action_id}"
        )
        if reconciled is CommitState.RECONCILED_SAFE_TO_RETRY:
            receipt.repair_status = "reconciled_safe_to_retry"
            episode.unresolved_deltas.append(action.action_id)
            episode.final_status = RepairClosureStatus.FAILED_UNSAFE_TO_RETRY
        elif reconciled is CommitState.RECONCILED_NEEDS_COMPENSATION:
            receipt.repair_status = "reconciled_needs_compensation"
            return self._repair_committed(
                episode=episode,
                state=state,
                committed=[(action, receipt)],
            )
        else:
            receipt.repair_status = reconciled.value
            episode.unresolved_deltas.append(action.action_id)
            episode.final_status = RepairClosureStatus.UNKNOWN_COMMIT_ESCALATED
        episode.final_state = state
        return self._close_episode(episode)

    def _repair_committed(
        self,
        *,
        episode: RepairEpisodeReceipt,
        state: State,
        committed: list[tuple[CausalRepairAction, ActionRepairReceipt]],
    ) -> RepairEpisodeReceipt:
        if not committed:
            episode.final_status = RepairClosureStatus.FALSE_SUCCESS_BLOCKED
            episode.final_state = state
            return self._close_episode(episode)
        episode.durable_receipts.append(
            self._persist(
                episode_id=episode.episode_id,
                state=DurableEpisodeState.REPAIR_REQUIRED,
                action_id=committed[-1][0].action_id,
                evidence_ref=committed[-1][1].admission_id or committed[-1][0].action_id,
            )
        )
        current_state = deepcopy(state)
        rollback_count = 0
        version_restore_count = 0
        compensation_count = 0

        for action, receipt in reversed(committed):
            strategy = _strategy_for_reversibility(action.reversibility_class)
            receipt.repair_strategy = strategy
            if strategy in {RepairStrategy.NONE_REQUIRED, RepairStrategy.FORBID}:
                continue
            episode.durable_receipts.append(
                self._persist(
                    episode_id=episode.episode_id,
                    state=DurableEpisodeState.REPAIR_ATTEMPTED,
                    action_id=action.action_id,
                    evidence_ref=receipt.admission_id or action.action_id,
                )
            )
            try:
                if strategy in {
                    RepairStrategy.EXACT_ROLLBACK,
                    RepairStrategy.VERSION_RESTORE,
                }:
                    if action.rollback is None:
                        raise CausalRepairError("rollback contract missing")
                    if self._has_drifted(action=action, receipt=receipt, state=current_state):
                        receipt.repair_status = "drift_detected_escalated"
                        episode.unresolved_deltas.append(action.action_id)
                        episode.final_status = (
                            RepairClosureStatus.PARTIALLY_REPAIRED_ESCALATED
                        )
                        episode.final_state = current_state
                        return self._close_episode(episode)
                    current_state = action.rollback(deepcopy(current_state))
                    if not self._verify_repair(action, current_state):
                        raise CausalRepairError("repair verification failed")
                    receipt.repair_status = strategy.value + "_verified"
                    episode.repaired_deltas.append(action.action_id)
                    if strategy is RepairStrategy.EXACT_ROLLBACK:
                        rollback_count += 1
                    else:
                        version_restore_count += 1
                elif strategy is RepairStrategy.SEMANTIC_COMPENSATION:
                    if action.compensate is None or action.compensation_contract is None:
                        raise CausalRepairError("compensation contract missing")
                    compensation_key = action.compensation_contract.idempotency_key
                    if compensation_key in self._compensation_idempotency_keys:
                        receipt.repair_status = "duplicate_compensation_suppressed"
                        episode.repaired_deltas.append(action.action_id)
                        compensation_count += 1
                        continue
                    current_state = action.compensate(deepcopy(current_state))
                    self._compensation_idempotency_keys.add(compensation_key)
                    adequacy = self._judge_compensation(action, current_state)
                    if adequacy not in _ACCEPTABLE_COMPENSATION:
                        receipt.repair_status = adequacy.value
                        episode.unresolved_deltas.append(action.action_id)
                        episode.final_status = (
                            RepairClosureStatus.PARTIALLY_REPAIRED_ESCALATED
                        )
                        episode.final_state = current_state
                        return self._close_episode(episode)
                    if not self._verify_repair(action, current_state):
                        raise CausalRepairError("compensation verification failed")
                    receipt.repair_status = adequacy.value
                    episode.repaired_deltas.append(action.action_id)
                    compensation_count += 1
                elif strategy is RepairStrategy.RECONCILE_THEN_DECIDE:
                    receipt.repair_status = "reconciliation_required"
                    episode.unresolved_deltas.append(action.action_id)
                else:
                    receipt.repair_status = "escalated"
                    episode.unresolved_deltas.append(action.action_id)
            except Exception as exc:
                receipt.repair_status = "repair_failed"
                receipt.error = _bounded_error(exc)
                episode.unresolved_deltas.append(action.action_id)
                episode.final_status = RepairClosureStatus.PARTIALLY_REPAIRED_ESCALATED
                episode.final_state = current_state
                return self._close_episode(episode)

        if episode.unresolved_deltas:
            episode.final_status = RepairClosureStatus.PARTIALLY_REPAIRED_ESCALATED
        elif compensation_count and (rollback_count or version_restore_count):
            episode.final_status = RepairClosureStatus.SUCCESS_WITH_COMPENSATION
        elif compensation_count:
            episode.final_status = RepairClosureStatus.SEMANTICALLY_REPAIRED
        elif version_restore_count:
            episode.final_status = RepairClosureStatus.VERSION_RESTORED_VERIFIED
        else:
            episode.final_status = RepairClosureStatus.ROLLED_BACK_VERIFIED
        episode.final_state = current_state
        episode.durable_receipts.append(
            self._persist(
                episode_id=episode.episode_id,
                state=DurableEpisodeState.REPAIR_VERIFIED,
                action_id=None,
                evidence_ref=stable_identifier(
                    "causal-repair-verification",
                    {
                        "episode_id": episode.episode_id,
                        "repaired": tuple(episode.repaired_deltas),
                        "unresolved": tuple(episode.unresolved_deltas),
                    },
                ),
            )
        )
        return self._close_episode(episode)

    def _admission_evidence_refs(self, action: CausalRepairAction) -> tuple[str, ...]:
        refs = [f"action://{action.action_id}"]
        if action.snapshot_receipt is not None:
            refs.append(f"snapshot://{action.snapshot_receipt.snapshot_id}")
        if action.compensation_contract is not None:
            refs.append(f"compensation://{action.compensation_contract.compensation_id}")
        if action.reconciliation_contract is not None:
            refs.append(f"reconciliation://{action.reconciliation_contract.reconciliation_id}")
        if action.approval_ref is not None:
            refs.append(f"approval://{action.approval_ref}")
        return tuple(refs)

    def _has_drifted(
        self,
        *,
        action: CausalRepairAction,
        receipt: ActionRepairReceipt,
        state: State,
    ) -> bool:
        if action.drift_detector is not None:
            return action.drift_detector(deepcopy(state))
        if receipt.after_hash is None:
            return False
        return _state_hash(state) != receipt.after_hash

    def _verify_repair(self, action: CausalRepairAction, state: State) -> bool:
        verifier = action.verify_repair or self._invariant_check
        return verifier(deepcopy(state)) and self._invariant_check(deepcopy(state))

    def _judge_compensation(
        self,
        action: CausalRepairAction,
        state: State,
    ) -> CompensationAdequacyStatus:
        if action.compensation_adequacy is None:
            return CompensationAdequacyStatus.SEMANTICALLY_ACCEPTABLE
        return CompensationAdequacyStatus(action.compensation_adequacy(deepcopy(state)))

    def _persist(
        self,
        *,
        episode_id: str,
        state: DurableEpisodeState,
        action_id: str | None,
        evidence_ref: str,
    ) -> DurableRepairReceipt:
        return self._store.append(
            episode_id=episode_id,
            state=state,
            action_id=action_id,
            evidence_ref=evidence_ref,
        )

    def _close_episode(self, episode: RepairEpisodeReceipt) -> RepairEpisodeReceipt:
        episode.ledger_hash = stable_identifier(
            "causal-repair-ledger",
            {
                "episode_id": episode.episode_id,
                "status": episode.final_status.value,
                "actions": tuple(
                    {
                        "action_id": receipt.action_id,
                        "commit_state": receipt.commit_state.value,
                        "repair_strategy": receipt.repair_strategy.value,
                        "repair_status": receipt.repair_status or "",
                    }
                    for receipt in episode.actions
                ),
                "repaired": tuple(episode.repaired_deltas),
                "unresolved": tuple(episode.unresolved_deltas),
            },
        )
        episode.durable_receipts.append(
            self._persist(
                episode_id=episode.episode_id,
                state=DurableEpisodeState.EPISODE_CLOSED,
                action_id=None,
                evidence_ref=episode.ledger_hash,
            )
        )
        return episode


def _strategy_for_reversibility(reversibility: ReversibilityClass) -> RepairStrategy:
    if reversibility is ReversibilityClass.READ_ONLY:
        return RepairStrategy.NONE_REQUIRED
    if reversibility is ReversibilityClass.EXACT_ROLLBACK:
        return RepairStrategy.EXACT_ROLLBACK
    if reversibility is ReversibilityClass.VERSION_RESTORE:
        return RepairStrategy.VERSION_RESTORE
    if reversibility is ReversibilityClass.SEMANTIC_COMPENSATION:
        return RepairStrategy.SEMANTIC_COMPENSATION
    if reversibility is ReversibilityClass.RECONCILE_REQUIRED:
        return RepairStrategy.RECONCILE_THEN_DECIDE
    if reversibility is ReversibilityClass.HUMAN_ESCALATION:
        return RepairStrategy.ESCALATE
    return RepairStrategy.FORBID


def _coerce_snapshot_quality(value: SnapshotQuality | int) -> SnapshotQuality:
    if isinstance(value, SnapshotQuality):
        return value
    try:
        return SnapshotQuality(value)
    except ValueError as exc:
        raise CausalRepairError("snapshot_quality must be S0 through S5") from exc


def _text_tuple(
    values: Iterable[str],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise CausalRepairError(f"{field_name} must be an array")
    result = tuple(ensure_non_empty_text(field_name, value) for value in values)
    if not result and not allow_empty:
        raise CausalRepairError(f"{field_name} must contain at least one item")
    return result


def _state_hash(state: State) -> str:
    try:
        encoded = json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise CausalRepairError("state must be deterministic JSON") from exc
    return stable_identifier("state", {"encoded": encoded})


def _bounded_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"
