"""Purpose: reactive orchestration engine — listens to the event spine, matches
reaction rules, gates every candidate through simulation/utility/meta-reasoning,
and produces auditable execution records.
Governance scope: reaction plane core logic only.
Dependencies: reaction contracts, event contracts, invariant helpers.
Invariants:
  - No direct event-to-action shortcuts — every reaction passes through gating.
  - Idempotency windows prevent duplicate work on event replay.
  - Backpressure policies bound reaction throughput.
  - All decisions are recorded — proceed, defer, reject.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.event import EventRecord, EventType
from mcoi_runtime.contracts.reaction import (
    BackpressurePolicy,
    BackpressureStrategy,
    IdempotencyWindow,
    ReactionCondition,
    ReactionDecision,
    ReactionExecutionRecord,
    ReactionGateResult,
    ReactionRule,
    ReactionTarget,
    ReactionTargetKind,
    ReactionVerdict,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


def _bounded_gate_callback_error(exc: Exception) -> str:
    """Return a stable gate callback failure without raw backend detail."""
    return f"gate callback error ({type(exc).__name__})"


# ---------------------------------------------------------------------------
# Gate callback protocol
# ---------------------------------------------------------------------------

# A gate function receives the event + matched rule and returns a
# ReactionGateResult.  The reactive engine does not own simulation,
# utility, or meta-reasoning — the bridge injects them via this callback.
GateCallback = Callable[[EventRecord, ReactionRule], ReactionGateResult]


class ReactionEngine:
    """Reactive orchestration engine with rule matching, decision gating,
    idempotency enforcement, and backpressure awareness.

    This engine:
    - Registers and manages reaction rules
    - Matches incoming events against enabled rules
    - Evaluates conditions against event payloads
    - Delegates gating decisions to an injected callback
    - Enforces idempotency windows to prevent duplicate reactions
    - Tracks backpressure policy and rejects when overloaded
    - Records every reaction decision for audit
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        gate: GateCallback | None = None,
        idempotency_expiry: str = "9999-12-31T23:59:59+00:00",
    ) -> None:
        self._rules: dict[str, ReactionRule] = {}
        self._executions: dict[str, ReactionExecutionRecord] = {}
        self._decisions: dict[str, ReactionDecision] = {}
        self._idempotency: dict[str, IdempotencyWindow] = {}
        self._backpressure: BackpressurePolicy | None = None
        self._active_count: int = 0
        self._window_count: int = 0
        self._window_start: str = ""
        self._exec_seq: int = 0
        self._idempotency_expiry = idempotency_expiry
        self._gate = gate or self._default_gate
        self._clock = clock or self._default_clock

    @staticmethod
    def _default_clock() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _now(self) -> str:
        return self._clock()

    @staticmethod
    def _default_gate(event: EventRecord, rule: ReactionRule) -> ReactionGateResult:
        """Default gate: always proceed with full confidence."""
        return ReactionGateResult(
            gate_id=stable_identifier("gate", {
                "event_id": event.event_id,
                "rule_id": rule.rule_id,
            }),
            rule_id=rule.rule_id,
            event_id=event.event_id,
            verdict=ReactionVerdict.PROCEED,
            simulation_safe=True,
            utility_acceptable=True,
            meta_reasoning_clear=True,
            confidence=1.0,
            reason="default gate — no gating logic configured",
            gated_at=event.emitted_at,
        )

    # --- Rule management ---

    def register_rule(self, rule: ReactionRule) -> ReactionRule:
        """Register a reaction rule. Duplicate rule_ids are rejected."""
        if rule.rule_id in self._rules:
            raise RuntimeCoreInvariantError("rule already exists")
        self._rules[rule.rule_id] = rule
        return rule

    def unregister_rule(self, rule_id: str) -> None:
        ensure_non_empty_text("rule_id", rule_id)
        if rule_id not in self._rules:
            raise RuntimeCoreInvariantError("rule not found")
        del self._rules[rule_id]

    def get_rule(self, rule_id: str) -> ReactionRule | None:
        ensure_non_empty_text("rule_id", rule_id)
        return self._rules.get(rule_id)

    def list_rules(self, *, enabled_only: bool = True) -> tuple[ReactionRule, ...]:
        rules = sorted(self._rules.values(), key=lambda r: (r.priority, r.rule_id))
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return tuple(rules)

    # --- Backpressure ---

    def set_backpressure(self, policy: BackpressurePolicy) -> None:
        self._backpressure = policy

    @property
    def backpressure(self) -> BackpressurePolicy | None:
        return self._backpressure

    def _check_backpressure(self) -> bool:
        """Return True if reaction can proceed under current backpressure."""
        if self._backpressure is None:
            return True
        # Auto-reset window if window_seconds has elapsed
        if self._window_start and self._backpressure.window_seconds > 0:
            now = self._now()
            if now > self._window_start:
                # Simple ISO string comparison works for monotonic clocks
                from datetime import datetime as _dt
                try:
                    start = _dt.fromisoformat(self._window_start)
                    current = _dt.fromisoformat(now)
                    elapsed = (current - start).total_seconds()
                    if elapsed >= self._backpressure.window_seconds:
                        self._window_count = 0
                        self._window_start = now
                except (ValueError, TypeError):
                    pass  # clock format issue — keep existing window
        if self._active_count >= self._backpressure.max_concurrent:
            return False
        if self._window_count >= self._backpressure.max_per_window:
            return False
        return True

    def _record_throughput(self) -> None:
        """Track a reaction execution for backpressure accounting."""
        self._active_count += 1
        self._window_count += 1

    def release_active(self) -> None:
        """Signal that an active reaction has completed."""
        if self._active_count > 0:
            self._active_count -= 1

    def reset_window(self) -> None:
        """Reset the rate-limiting window counter."""
        self._window_count = 0
        self._window_start = self._now()

    # --- Idempotency ---

    def is_duplicate(self, event_id: str, rule_id: str) -> bool:
        """Check if this event+rule combination was already processed."""
        key = f"{event_id}:{rule_id}"
        window = self._idempotency.get(key)
        if window is None:
            return False
        now = self._now()
        if window.expires_at <= now:
            del self._idempotency[key]
            return False
        return True

    def _record_idempotency(
        self, event_id: str, rule_id: str, execution_id: str,
    ) -> IdempotencyWindow:
        now = self._now()
        win_id = stable_identifier("idem", {
            "event_id": event_id,
            "rule_id": rule_id,
        })
        window = IdempotencyWindow(
            window_id=win_id,
            event_id=event_id,
            rule_id=rule_id,
            execution_id=execution_id,
            processed_at=now,
            expires_at=self._idempotency_expiry,
        )
        key = f"{event_id}:{rule_id}"
        self._idempotency[key] = window
        return window

    # --- Condition evaluation ---

    @staticmethod
    def evaluate_condition(condition: ReactionCondition, payload: Mapping[str, Any]) -> bool:
        """Evaluate a single condition against an event payload."""
        parts = condition.field_path.split(".")
        current: Any = payload
        for part in parts:
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                return False  # field not found — all operators fail including exists
        op = condition.operator
        expected = condition.expected_value
        if op == "eq":
            return current == expected
        if op == "neq":
            return current != expected
        try:
            if op == "gt":
                return current > expected
            if op == "gte":
                return current >= expected
            if op == "lt":
                return current < expected
            if op == "lte":
                return current <= expected
        except TypeError:
            return False  # incompatible types for comparison
        if op == "contains":
            return expected in current if hasattr(current, "__contains__") else False
        if op == "in":
            return current in expected if hasattr(expected, "__contains__") else False
        if op == "exists":
            return True  # we got here, so field exists
        raise RuntimeCoreInvariantError(
            f"unknown condition operator {op!r} — "
            f"valid operators: eq, neq, gt, gte, lt, lte, contains, in, exists"
        )

    def match_rules(self, event: EventRecord) -> tuple[ReactionRule, ...]:
        """Find all enabled rules whose event_type and conditions match."""
        matched: list[ReactionRule] = []
        for rule in self.list_rules(enabled_only=True):
            if rule.event_type != event.event_type.value:
                continue
            all_match = all(
                self.evaluate_condition(c, event.payload)
                for c in rule.conditions
            )
            if all_match:
                matched.append(rule)
        return tuple(matched)

    # --- Core reaction cycle ---

    def react(self, event: EventRecord) -> ReactionDecision:
        """Process a single event through the full reaction cycle.

        1. Match rules against event
        2. For each matched rule:
           a. Check idempotency
           b. Check backpressure
           c. Gate through simulation/utility/meta-reasoning
           d. Record execution
        3. Return a ReactionDecision summarizing all evaluations
        """
        now = self._now()
        all_rules = self.list_rules(enabled_only=True)
        matched = self.match_rules(event)

        executions: list[ReactionExecutionRecord] = []
        executed_count = 0
        deferred_count = 0
        rejected_count = 0

        for rule in matched:
            self._exec_seq += 1
            exec_id = stable_identifier("rxn", {
                "event_id": event.event_id,
                "rule_id": rule.rule_id,
                "seq": self._exec_seq,
            })

            # Idempotency check
            if self.is_duplicate(event.event_id, rule.rule_id):
                gate_result = ReactionGateResult(
                    gate_id=stable_identifier("gate", {
                        "event_id": event.event_id,
                        "rule_id": rule.rule_id,
                        "seq": self._exec_seq,
                    }),
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    verdict=ReactionVerdict.REJECT,
                    simulation_safe=True,
                    utility_acceptable=True,
                    meta_reasoning_clear=True,
                    confidence=1.0,
                    reason="duplicate event — idempotency window active",
                    gated_at=now,
                )
                rec = ReactionExecutionRecord(
                    execution_id=exec_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    target=rule.target,
                    gate_result=gate_result,
                    executed=False,
                    result_ref_id="none",
                    execution_notes="rejected: duplicate event",
                    executed_at=now,
                )
                self._executions[exec_id] = rec
                executions.append(rec)
                rejected_count += 1
                continue

            # Backpressure check
            if not self._check_backpressure():
                gate_result = ReactionGateResult(
                    gate_id=stable_identifier("gate", {
                        "event_id": event.event_id,
                        "rule_id": rule.rule_id,
                        "seq": self._exec_seq,
                    }),
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    verdict=ReactionVerdict.DEFER,
                    simulation_safe=True,
                    utility_acceptable=True,
                    meta_reasoning_clear=True,
                    confidence=1.0,
                    reason="backpressure limit reached — deferring",
                    gated_at=now,
                )
                rec = ReactionExecutionRecord(
                    execution_id=exec_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    target=rule.target,
                    gate_result=gate_result,
                    executed=False,
                    result_ref_id="none",
                    execution_notes="deferred: backpressure",
                    executed_at=now,
                )
                self._executions[exec_id] = rec
                executions.append(rec)
                deferred_count += 1
                continue

            # Decision gating — wrap in try/except for safety
            try:
                gate_result = self._gate(event, rule)
            except Exception as exc:
                gate_result = ReactionGateResult(
                    gate_id=stable_identifier("gate", {
                        "event_id": event.event_id,
                        "rule_id": rule.rule_id,
                        "seq": self._exec_seq,
                        "error": True,
                    }),
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    verdict=ReactionVerdict.REJECT,
                    simulation_safe=False,
                    utility_acceptable=False,
                    meta_reasoning_clear=False,
                    confidence=0.0,
                    reason=_bounded_gate_callback_error(exc),
                    gated_at=now,
                )

            if gate_result.verdict == ReactionVerdict.PROCEED:
                self._record_throughput()
                self._record_idempotency(event.event_id, rule.rule_id, exec_id)
                rec = ReactionExecutionRecord(
                    execution_id=exec_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    target=rule.target,
                    gate_result=gate_result,
                    executed=True,
                    result_ref_id=exec_id,
                    execution_notes="executed successfully",
                    executed_at=now,
                )
                executed_count += 1
            elif gate_result.verdict == ReactionVerdict.DEFER:
                rec = ReactionExecutionRecord(
                    execution_id=exec_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    target=rule.target,
                    gate_result=gate_result,
                    executed=False,
                    result_ref_id="none",
                    execution_notes=f"deferred: {gate_result.reason}",
                    executed_at=now,
                )
                deferred_count += 1
            else:
                rec = ReactionExecutionRecord(
                    execution_id=exec_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    target=rule.target,
                    gate_result=gate_result,
                    executed=False,
                    result_ref_id="none",
                    execution_notes=f"{gate_result.verdict.value}: {gate_result.reason}",
                    executed_at=now,
                )
                rejected_count += 1

            self._executions[exec_id] = rec
            executions.append(rec)

        decision_id = stable_identifier("rdec", {
            "event_id": event.event_id,
            "seq": self._exec_seq,
        })
        decision = ReactionDecision(
            decision_id=decision_id,
            event_id=event.event_id,
            correlation_id=event.correlation_id,
            rules_evaluated=len(all_rules),
            rules_matched=len(matched),
            rules_executed=executed_count,
            rules_deferred=deferred_count,
            rules_rejected=rejected_count,
            executions=tuple(executions),
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        return decision

    # --- History ---

    def get_execution(self, execution_id: str) -> ReactionExecutionRecord | None:
        ensure_non_empty_text("execution_id", execution_id)
        return self._executions.get(execution_id)

    def list_executions(
        self,
        *,
        event_id: str | None = None,
        rule_id: str | None = None,
        executed_only: bool = False,
    ) -> tuple[ReactionExecutionRecord, ...]:
        execs = sorted(self._executions.values(), key=lambda e: e.executed_at)
        if event_id is not None:
            execs = [e for e in execs if e.event_id == event_id]
        if rule_id is not None:
            execs = [e for e in execs if e.rule_id == rule_id]
        if executed_only:
            execs = [e for e in execs if e.executed]
        return tuple(execs)

    def get_decision(self, decision_id: str) -> ReactionDecision | None:
        ensure_non_empty_text("decision_id", decision_id)
        return self._decisions.get(decision_id)

    def list_decisions(self) -> tuple[ReactionDecision, ...]:
        return tuple(sorted(self._decisions.values(), key=lambda d: d.decided_at))

    # --- Properties ---

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def execution_count(self) -> int:
        return len(self._executions)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def idempotency_count(self) -> int:
        return len(self._idempotency)
