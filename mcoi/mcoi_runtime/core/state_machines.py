"""Purpose: canonical state machine definitions for supervisor, obligation, reaction,
and checkpoint lifecycles, plus transition guard infrastructure and audit integration.
Governance scope: formal transition tables with enforcement, callable guards, audit trail.
Dependencies: state machine contracts, supervisor/obligation/reaction enums.
Invariants:
  - Transition tables are exhaustive — every legal edge is declared, nothing else is permitted.
  - Terminal states have zero outgoing edges.
  - Enforcement methods raise on illegal transitions.
  - All machines are versioned for replay compatibility.
  - Guards are callable and registered by label — declarative tables, runtime evaluation.
  - Every transition produces an immutable audit record.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.contracts.reaction import ReactionVerdict
from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec,
    TransitionAuditRecord,
    TransitionRule,
    TransitionVerdict,
)
from mcoi_runtime.contracts.supervisor import SupervisorPhase, TickOutcome
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Obligation lifecycle state machine
# ---------------------------------------------------------------------------

OBLIGATION_MACHINE = StateMachineSpec(
    machine_id="obligation-lifecycle",
    name="Obligation Lifecycle",
    version="2.0.0",
    states=(
        ObligationState.PENDING.value,
        ObligationState.ACTIVE.value,
        ObligationState.ESCALATED.value,
        ObligationState.COMPLETED.value,
        ObligationState.EXPIRED.value,
        ObligationState.CANCELLED.value,
    ),
    initial_state=ObligationState.PENDING.value,
    terminal_states=(
        ObligationState.COMPLETED.value,
        ObligationState.EXPIRED.value,
        ObligationState.CANCELLED.value,
    ),
    transitions=(
        # From PENDING
        TransitionRule(
            from_state="pending", to_state="active",
            action="activate",
            emits="obligation_activated",
        ),
        TransitionRule(
            from_state="pending", to_state="completed",
            action="close",
            guard_label="final_state=completed",
            emits="obligation_closed",
        ),
        TransitionRule(
            from_state="pending", to_state="expired",
            action="close",
            guard_label="final_state=expired",
            emits="obligation_expired",
        ),
        TransitionRule(
            from_state="pending", to_state="cancelled",
            action="close",
            guard_label="final_state=cancelled",
            emits="obligation_cancelled",
        ),
        TransitionRule(
            from_state="pending", to_state="escalated",
            action="escalate",
            emits="obligation_escalated",
        ),
        TransitionRule(
            from_state="pending", to_state="pending",
            action="transfer",
            guard_label="owner_changes",
            emits="obligation_transferred",
        ),
        # From ACTIVE
        TransitionRule(
            from_state="active", to_state="completed",
            action="close",
            guard_label="final_state=completed",
            emits="obligation_closed",
        ),
        TransitionRule(
            from_state="active", to_state="expired",
            action="close",
            guard_label="final_state=expired",
            emits="obligation_expired",
        ),
        TransitionRule(
            from_state="active", to_state="cancelled",
            action="close",
            guard_label="final_state=cancelled",
            emits="obligation_cancelled",
        ),
        TransitionRule(
            from_state="active", to_state="escalated",
            action="escalate",
            emits="obligation_escalated",
        ),
        TransitionRule(
            from_state="active", to_state="active",
            action="transfer",
            guard_label="owner_changes",
            emits="obligation_transferred",
        ),
        # From ESCALATED
        TransitionRule(
            from_state="escalated", to_state="completed",
            action="close",
            guard_label="final_state=completed",
            emits="obligation_closed",
        ),
        TransitionRule(
            from_state="escalated", to_state="expired",
            action="close",
            guard_label="final_state=expired",
            emits="obligation_expired",
        ),
        TransitionRule(
            from_state="escalated", to_state="cancelled",
            action="close",
            guard_label="final_state=cancelled",
            emits="obligation_cancelled",
        ),
        TransitionRule(
            from_state="escalated", to_state="escalated",
            action="escalate",
            guard_label="re-escalation to higher authority",
            emits="obligation_escalated",
        ),
        TransitionRule(
            from_state="escalated", to_state="escalated",
            action="transfer",
            guard_label="owner_changes",
            emits="obligation_transferred",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Supervisor tick state machine (expanded)
# ---------------------------------------------------------------------------

SUPERVISOR_MACHINE = StateMachineSpec(
    machine_id="supervisor-tick-lifecycle",
    name="Supervisor Tick Lifecycle",
    version="2.0.0",
    states=(
        SupervisorPhase.IDLE.value,
        SupervisorPhase.POLLING.value,
        SupervisorPhase.EVALUATING_OBLIGATIONS.value,
        SupervisorPhase.EVALUATING_DEADLINES.value,
        SupervisorPhase.WAKING_WORK.value,
        SupervisorPhase.RUNNING_REACTIONS.value,
        SupervisorPhase.REASONING.value,
        SupervisorPhase.ACTING.value,
        SupervisorPhase.CHECKPOINTING.value,
        SupervisorPhase.EMITTING_HEARTBEAT.value,
        SupervisorPhase.PAUSED.value,
        SupervisorPhase.DEGRADED.value,
        SupervisorPhase.HALTED.value,
    ),
    initial_state=SupervisorPhase.IDLE.value,
    terminal_states=(SupervisorPhase.HALTED.value,),
    transitions=(
        # Normal tick flow: idle → polling → evaluating → reacting → reasoning → acting → checkpoint → heartbeat → idle
        TransitionRule(from_state="idle", to_state="polling", action="tick_start",
                       emits="supervisor_tick_started"),
        TransitionRule(from_state="polling", to_state="evaluating_obligations", action="poll_complete",
                       emits="supervisor_poll_complete"),
        TransitionRule(from_state="polling", to_state="degraded", action="backpressure_triggered",
                       emits="supervisor_backpressure"),
        TransitionRule(from_state="evaluating_obligations", to_state="evaluating_deadlines", action="obligations_evaluated"),
        TransitionRule(from_state="evaluating_deadlines", to_state="waking_work", action="deadlines_evaluated"),
        TransitionRule(from_state="waking_work", to_state="running_reactions", action="work_woken"),
        TransitionRule(from_state="running_reactions", to_state="reasoning", action="reactions_complete"),
        TransitionRule(from_state="reasoning", to_state="acting", action="reasoning_complete"),
        TransitionRule(from_state="acting", to_state="checkpointing", action="actions_complete",
                       guard_label="checkpoint_interval_reached",
                       emits="supervisor_checkpointing"),
        TransitionRule(from_state="acting", to_state="emitting_heartbeat", action="actions_complete_no_checkpoint",
                       guard_label="checkpoint_interval_not_reached"),
        TransitionRule(from_state="acting", to_state="idle", action="tick_complete",
                       emits="supervisor_tick_complete"),
        TransitionRule(from_state="checkpointing", to_state="emitting_heartbeat", action="checkpoint_complete",
                       guard_label="heartbeat_interval_reached",
                       emits="supervisor_checkpoint_complete"),
        TransitionRule(from_state="checkpointing", to_state="idle", action="checkpoint_complete_no_heartbeat",
                       guard_label="heartbeat_interval_not_reached",
                       emits="supervisor_checkpoint_complete"),
        TransitionRule(from_state="emitting_heartbeat", to_state="idle", action="heartbeat_complete",
                       emits="supervisor_heartbeat_emitted"),
        # Pause/resume — operator-initiated
        TransitionRule(from_state="idle", to_state="paused", action="pause",
                       emits="supervisor_paused"),
        TransitionRule(from_state="paused", to_state="idle", action="resume",
                       emits="supervisor_resumed"),
        TransitionRule(from_state="paused", to_state="halted", action="halt",
                       guard_label="operator_halt_while_paused",
                       emits="supervisor_halted"),
        TransitionRule(from_state="paused", to_state="degraded", action="error",
                       emits="supervisor_error"),
        # Degraded paths
        TransitionRule(from_state="degraded", to_state="idle", action="tick_complete",
                       guard_label="backpressure/livelock resolved"),
        TransitionRule(from_state="degraded", to_state="halted", action="halt",
                       guard_label="livelock strategy=HALT or max_errors exceeded",
                       emits="supervisor_halted"),
        TransitionRule(from_state="degraded", to_state="paused", action="pause",
                       guard_label="operator_pause_in_degraded",
                       emits="supervisor_paused"),
        # Livelock from acting phase
        TransitionRule(from_state="acting", to_state="degraded", action="livelock_detected",
                       emits="supervisor_livelock"),
        # Error from any working phase → degraded
        TransitionRule(from_state="idle", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="polling", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="evaluating_obligations", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="evaluating_deadlines", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="waking_work", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="running_reactions", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="reasoning", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="acting", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="checkpointing", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="emitting_heartbeat", to_state="degraded", action="error",
                       emits="supervisor_error"),
        TransitionRule(from_state="degraded", to_state="degraded", action="error",
                       emits="supervisor_error"),
    ),
)


# ---------------------------------------------------------------------------
# Reaction pipeline state machine (expanded)
# ---------------------------------------------------------------------------

REACTION_PIPELINE_MACHINE = StateMachineSpec(
    machine_id="reaction-pipeline",
    name="Reaction Pipeline",
    version="2.0.0",
    states=(
        "received",
        "matching",
        "idempotency_check",
        "backpressure_check",
        "gating",
        "executed",
        "emitted",
        "deferred",
        "rejected",
        "recorded",
    ),
    initial_state="received",
    terminal_states=("recorded",),
    transitions=(
        TransitionRule(from_state="received", to_state="matching", action="begin_react"),
        TransitionRule(from_state="matching", to_state="idempotency_check", action="rules_matched"),
        TransitionRule(from_state="matching", to_state="recorded", action="no_rules_matched",
                       guard_label="zero matched rules"),
        TransitionRule(from_state="idempotency_check", to_state="rejected", action="duplicate_detected",
                       emits="reaction_rejected"),
        TransitionRule(from_state="idempotency_check", to_state="backpressure_check", action="not_duplicate"),
        TransitionRule(from_state="backpressure_check", to_state="deferred", action="backpressure_limit",
                       emits="reaction_deferred"),
        TransitionRule(from_state="backpressure_check", to_state="gating", action="backpressure_ok"),
        TransitionRule(from_state="gating", to_state="executed", action="verdict_proceed",
                       emits="reaction_executed"),
        TransitionRule(from_state="gating", to_state="deferred", action="verdict_defer",
                       emits="reaction_deferred"),
        TransitionRule(from_state="gating", to_state="rejected", action="verdict_reject",
                       emits="reaction_rejected"),
        TransitionRule(from_state="gating", to_state="rejected", action="verdict_escalate",
                       emits="reaction_rejected"),
        TransitionRule(from_state="gating", to_state="rejected", action="verdict_requires_approval",
                       emits="reaction_rejected"),
        # Executed → emitted → recorded (event emission is explicit)
        TransitionRule(from_state="executed", to_state="emitted", action="emit_event",
                       emits="reaction_event_emitted"),
        TransitionRule(from_state="emitted", to_state="recorded", action="record"),
        # Direct record paths for non-emission outcomes
        TransitionRule(from_state="executed", to_state="recorded", action="record",
                       guard_label="no_event_emission"),
        TransitionRule(from_state="deferred", to_state="recorded", action="record"),
        TransitionRule(from_state="rejected", to_state="recorded", action="record"),
    ),
)


# ---------------------------------------------------------------------------
# Checkpoint / restore lifecycle state machine (new)
# ---------------------------------------------------------------------------

CHECKPOINT_LIFECYCLE_MACHINE = StateMachineSpec(
    machine_id="checkpoint-lifecycle",
    name="Checkpoint Lifecycle",
    version="1.0.0",
    states=(
        "idle",
        "capturing",
        "verifying_capture",
        "committed",
        "restoring",
        "verifying_restore",
        "verified",
        "rolling_back",
        "failed",
    ),
    initial_state="idle",
    terminal_states=("failed",),
    transitions=(
        # Capture flow: idle → capturing → verifying → committed → idle
        TransitionRule(from_state="idle", to_state="capturing", action="begin_capture",
                       emits="checkpoint_capture_started"),
        TransitionRule(from_state="capturing", to_state="verifying_capture", action="snapshots_complete",
                       emits="checkpoint_snapshots_captured"),
        TransitionRule(from_state="verifying_capture", to_state="committed", action="hash_verified",
                       emits="checkpoint_committed"),
        TransitionRule(from_state="verifying_capture", to_state="failed", action="hash_mismatch",
                       emits="checkpoint_capture_failed"),
        TransitionRule(from_state="committed", to_state="idle", action="capture_finalized",
                       emits="checkpoint_capture_complete"),
        # Restore flow: idle → restoring → verifying_restore → verified → idle
        TransitionRule(from_state="idle", to_state="restoring", action="begin_restore",
                       emits="checkpoint_restore_started"),
        TransitionRule(from_state="restoring", to_state="verifying_restore", action="subsystems_restored",
                       emits="checkpoint_subsystems_restored"),
        TransitionRule(from_state="verifying_restore", to_state="verified", action="restore_hash_verified",
                       emits="checkpoint_restore_verified"),
        TransitionRule(from_state="verified", to_state="idle", action="restore_finalized",
                       emits="checkpoint_restore_complete"),
        # Rollback paths
        TransitionRule(from_state="verifying_restore", to_state="rolling_back", action="restore_hash_mismatch",
                       emits="checkpoint_rollback_triggered"),
        TransitionRule(from_state="restoring", to_state="rolling_back", action="restore_error",
                       emits="checkpoint_rollback_triggered"),
        TransitionRule(from_state="rolling_back", to_state="idle", action="rollback_complete",
                       emits="checkpoint_rollback_complete"),
        TransitionRule(from_state="rolling_back", to_state="failed", action="rollback_failed",
                       emits="checkpoint_rollback_failed"),
    ),
)


# ---------------------------------------------------------------------------
# Machine registry — all canonical machines accessible by ID
# ---------------------------------------------------------------------------

MACHINE_REGISTRY: Mapping[str, StateMachineSpec] = MappingProxyType({
    OBLIGATION_MACHINE.machine_id: OBLIGATION_MACHINE,
    SUPERVISOR_MACHINE.machine_id: SUPERVISOR_MACHINE,
    REACTION_PIPELINE_MACHINE.machine_id: REACTION_PIPELINE_MACHINE,
    CHECKPOINT_LIFECYCLE_MACHINE.machine_id: CHECKPOINT_LIFECYCLE_MACHINE,
})


# ---------------------------------------------------------------------------
# Transition guard infrastructure
# ---------------------------------------------------------------------------

# Guard function signature: (context) -> bool
# Context is a dict with transition-specific data.
TransitionGuard = Callable[[Mapping[str, Any]], bool]


class TransitionGuardRegistry:
    """Registry for callable transition guards.

    Guards are registered by label string (matching TransitionRule.guard_label).
    When enforce_guarded_transition is called, the guard for the matching rule
    is looked up and executed. Missing guards for non-empty guard_labels
    fail closed (deny the transition).
    """

    def __init__(self) -> None:
        self._guards: dict[str, TransitionGuard] = {}

    def register(self, guard_label: str, guard: TransitionGuard) -> None:
        """Register a guard function for a label."""
        if not guard_label or not guard_label.strip():
            raise RuntimeCoreInvariantError("guard_label must be non-empty")
        self._guards[guard_label] = guard

    def has_guard(self, guard_label: str) -> bool:
        return guard_label in self._guards

    def evaluate(self, guard_label: str, context: Mapping[str, Any]) -> bool:
        """Evaluate a guard. Returns True if the guard passes.

        Missing guards for non-empty labels fail closed (return False).
        Empty guard labels always pass.
        """
        if not guard_label:
            return True
        guard = self._guards.get(guard_label)
        if guard is None:
            return False  # Fail closed
        return guard(context)

    @property
    def guard_count(self) -> int:
        return len(self._guards)

    def registered_labels(self) -> tuple[str, ...]:
        return tuple(sorted(self._guards.keys()))


# ---------------------------------------------------------------------------
# Transition auditor
# ---------------------------------------------------------------------------


class TransitionAuditor:
    """Records every transition attempt as an immutable audit record.

    Wraps enforcement with audit trail creation. Every call to
    audit_transition produces a TransitionAuditRecord regardless
    of whether the transition was allowed or denied.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._records: list[TransitionAuditRecord] = []
        self._seq = 0

    def audit_transition(
        self,
        machine: StateMachineSpec,
        entity_id: str,
        from_state: str,
        to_state: str,
        action: str,
        *,
        actor_id: str = "system",
        reason: str = "",
        guard_registry: TransitionGuardRegistry | None = None,
        guard_context: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TransitionAuditRecord:
        """Attempt a transition, record the outcome, and return the audit record.

        If the transition is illegal or the guard fails, the record captures
        the denial verdict. Does NOT raise — the caller decides how to handle
        denials.
        """
        self._seq += 1
        now = self._clock()
        audit_id = stable_identifier("tx-audit", {
            "machine": machine.machine_id,
            "entity": entity_id,
            "seq": self._seq,
        })

        # Check structural legality
        verdict = machine.is_legal(from_state, to_state, action)

        # If structurally legal, check guard
        if verdict == TransitionVerdict.ALLOWED and guard_registry is not None:
            # Find the matching rule to get its guard_label
            matching_rule = None
            for t in machine.transitions:
                if t.from_state == from_state and t.to_state == to_state and t.action == action:
                    matching_rule = t
                    break
            if matching_rule and matching_rule.guard_label:
                ctx = dict(guard_context) if guard_context else {}
                if not guard_registry.evaluate(matching_rule.guard_label, ctx):
                    verdict = TransitionVerdict.DENIED_GUARD_FAILED

        record = TransitionAuditRecord(
            audit_id=audit_id,
            machine_id=machine.machine_id,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            action=action,
            verdict=verdict,
            actor_id=actor_id,
            reason=reason,
            transitioned_at=now,
            metadata=metadata or {},
        )
        self._records.append(record)
        return record

    @property
    def record_count(self) -> int:
        return len(self._records)

    def records_for(self, entity_id: str) -> tuple[TransitionAuditRecord, ...]:
        """Return all audit records for a specific entity."""
        return tuple(r for r in self._records if r.entity_id == entity_id)

    def records_for_machine(self, machine_id: str) -> tuple[TransitionAuditRecord, ...]:
        """Return all audit records for a specific machine."""
        return tuple(r for r in self._records if r.machine_id == machine_id)

    def denied_records(self) -> tuple[TransitionAuditRecord, ...]:
        """Return all denied transition records."""
        return tuple(r for r in self._records if not r.succeeded)

    def all_records(self) -> tuple[TransitionAuditRecord, ...]:
        """Return all audit records in order."""
        return tuple(self._records)

    def snapshot(self) -> dict[str, Any]:
        """Capture audit trail as serializable dict."""
        return {
            "records": [r.to_dict() for r in self._records],
            "seq": self._seq,
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Restore audit trail from snapshot.

        Validates each record can be deserialized as a valid
        TransitionAuditRecord. Optionally cross-checks against
        MACHINE_REGISTRY if the machine_id is recognized.
        """
        restored: list[TransitionAuditRecord] = []
        for rdict in snapshot.get("records", []):
            rdict = dict(rdict)
            rdict["verdict"] = TransitionVerdict(rdict["verdict"])
            record = TransitionAuditRecord(**rdict)
            # Cross-validate against known machine if available
            machine = MACHINE_REGISTRY.get(record.machine_id)
            if machine is not None and record.verdict == TransitionVerdict.ALLOWED:
                live_verdict = machine.is_legal(
                    record.from_state, record.to_state, record.action,
                )
                if live_verdict != TransitionVerdict.ALLOWED:
                    raise RuntimeCoreInvariantError(
                        f"audit record {record.audit_id} claims ALLOWED for "
                        f"{record.from_state}→{record.to_state} via {record.action!r}, "
                        f"but machine {record.machine_id} says {live_verdict.value}"
                    )
            restored.append(record)
        # Commit atomically
        self._records.clear()
        self._records.extend(restored)
        self._seq = snapshot.get("seq", len(self._records))


# ---------------------------------------------------------------------------
# Transition replay from audit trail
# ---------------------------------------------------------------------------


class TransitionReplayVerdict(str):
    """Outcome of replaying a single transition."""


REPLAY_MATCH = "match"
REPLAY_DIVERGED = "diverged"
REPLAY_SKIPPED = "skipped"


class TransitionReplayEngine:
    """Replays transitions from an audit trail and verifies against a live machine.

    Takes a sequence of TransitionAuditRecords and re-evaluates each
    against the machine's transition table. Compares the original verdict
    with the re-evaluated verdict to detect divergence.
    """

    def __init__(self, *, guard_registry: TransitionGuardRegistry | None = None) -> None:
        self._guard_registry = guard_registry

    def replay(
        self,
        machine: StateMachineSpec,
        records: tuple[TransitionAuditRecord, ...],
        *,
        halt_on_divergence: bool = True,
    ) -> tuple[list[dict[str, Any]], str]:
        """Replay audit records against a machine.

        Tracks current_state progression so impossible sequences
        (e.g. jumping back to a prior state) are detected as divergence.

        Returns (step_results, overall_verdict) where:
        - step_results is a list of dicts with keys:
            audit_id, original_verdict, replayed_verdict, match
        - overall_verdict is "success" or "divergence_detected"
        """
        results: list[dict[str, Any]] = []
        diverged = False
        current_state: str | None = None  # tracks progression

        for record in records:
            if record.machine_id != machine.machine_id:
                results.append({
                    "audit_id": record.audit_id,
                    "original_verdict": record.verdict.value,
                    "replayed_verdict": "skipped",
                    "match": REPLAY_SKIPPED,
                })
                continue

            # State continuity check: if we are tracking state and the
            # record's from_state doesn't match where we think we are,
            # that's a sequence divergence.
            if current_state is not None and record.from_state != current_state:
                results.append({
                    "audit_id": record.audit_id,
                    "original_verdict": record.verdict.value,
                    "replayed_verdict": TransitionVerdict.DENIED_ILLEGAL_EDGE.value,
                    "match": REPLAY_DIVERGED,
                    "detail": f"expected from_state={current_state!r}, got {record.from_state!r}",
                })
                diverged = True
                if halt_on_divergence:
                    break
                continue

            replayed_verdict = machine.is_legal(
                record.from_state, record.to_state, record.action,
            )

            # Check guard if registry provided
            if replayed_verdict == TransitionVerdict.ALLOWED and self._guard_registry is not None:
                for t in machine.transitions:
                    if (t.from_state == record.from_state
                            and t.to_state == record.to_state
                            and t.action == record.action
                            and t.guard_label):
                        if not self._guard_registry.evaluate(t.guard_label, dict(record.metadata)):
                            replayed_verdict = TransitionVerdict.DENIED_GUARD_FAILED
                        break

            match = REPLAY_MATCH if replayed_verdict == record.verdict else REPLAY_DIVERGED
            if match == REPLAY_DIVERGED:
                diverged = True

            results.append({
                "audit_id": record.audit_id,
                "original_verdict": record.verdict.value,
                "replayed_verdict": replayed_verdict.value,
                "match": match,
            })

            # Advance tracked state only on allowed transitions
            if record.verdict == TransitionVerdict.ALLOWED:
                current_state = record.to_state

            if diverged and halt_on_divergence:
                break

        overall = "divergence_detected" if diverged else "success"
        return results, overall


# ---------------------------------------------------------------------------
# Enforcement helpers (backwards-compatible + guarded variant)
# ---------------------------------------------------------------------------


def enforce_transition(
    machine: StateMachineSpec,
    from_state: str,
    to_state: str,
    action: str,
) -> TransitionVerdict:
    """Check a transition and raise if illegal.

    Returns ALLOWED on success, raises RuntimeCoreInvariantError otherwise.
    """
    verdict = machine.is_legal(from_state, to_state, action)
    if verdict != TransitionVerdict.ALLOWED:
        raise RuntimeCoreInvariantError(
            f"[{machine.name}] illegal transition: {from_state} → {to_state} "
            f"via {action!r} ({verdict.value})"
        )
    return verdict


def enforce_guarded_transition(
    machine: StateMachineSpec,
    from_state: str,
    to_state: str,
    action: str,
    *,
    guard_registry: TransitionGuardRegistry,
    guard_context: Mapping[str, Any] | None = None,
) -> TransitionVerdict:
    """Check a transition with guard evaluation and raise if illegal or guard fails.

    Returns ALLOWED on success, raises RuntimeCoreInvariantError otherwise.
    """
    verdict = machine.is_legal(from_state, to_state, action)
    if verdict != TransitionVerdict.ALLOWED:
        raise RuntimeCoreInvariantError(
            f"[{machine.name}] illegal transition: {from_state} → {to_state} "
            f"via {action!r} ({verdict.value})"
        )

    # Find matching rule and evaluate guard
    for t in machine.transitions:
        if t.from_state == from_state and t.to_state == to_state and t.action == action:
            if t.guard_label:
                ctx = dict(guard_context) if guard_context else {}
                if not guard_registry.evaluate(t.guard_label, ctx):
                    raise RuntimeCoreInvariantError(
                        f"[{machine.name}] guard failed: {t.guard_label!r} "
                        f"for {from_state} → {to_state} via {action!r}"
                    )
            break

    return TransitionVerdict.ALLOWED
