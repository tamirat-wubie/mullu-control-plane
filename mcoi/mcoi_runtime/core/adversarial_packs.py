"""Purpose: pre-built adversarial test case packs — canonical stress-test cases
for every subsystem, organized by attack category.
Governance scope: benchmark plane adversarial case generation only.
Dependencies: benchmark contracts, invariant helpers.
Invariants:
  - Every adversarial case is explicit — no hidden malice.
  - Cases are reproducible — same factory, same inputs, same case.
  - Each pack targets a specific subsystem with a specific attack vector.
  - All cases are immutable frozen dataclasses.
"""

from __future__ import annotations

from mcoi_runtime.contracts.benchmark import (
    AdversarialCase,
    AdversarialCategory,
    AdversarialSeverity,
    BenchmarkCategory,
)
from .invariants import stable_identifier


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _case(
    name: str,
    description: str,
    category: AdversarialCategory,
    severity: AdversarialSeverity,
    target: BenchmarkCategory,
    attack_vector: str,
    inputs: dict,
    expected_behavior: str,
    tags: tuple[str, ...] = (),
) -> AdversarialCase:
    case_id = stable_identifier("adv-case", {"name": name, "category": category.value, "target": target.value})
    return AdversarialCase(
        case_id=case_id,
        name=name,
        description=description,
        category=category,
        severity=severity,
        target_subsystem=target,
        attack_vector=attack_vector,
        inputs=inputs,
        expected_behavior=expected_behavior,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Conflicting policies pack
# ---------------------------------------------------------------------------


def conflicting_policies_pack() -> tuple[AdversarialCase, ...]:
    """Cases where governance rules contradict each other."""
    return (
        _case(
            name="deny-vs-allow-same-scope",
            description="Two rules at same priority: one DENY, one ALLOW for same action in same scope",
            category=AdversarialCategory.CONFLICTING_POLICIES,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Submit two contradicting policy rules at identical priority",
            inputs={"rule_effects": ["deny", "allow"], "priority": 50, "scope": "global"},
            expected_behavior="Compiler detects conflict; DENY wins by effect precedence",
            tags=("governance", "conflict-detection"),
        ),
        _case(
            name="overlapping-scope-contradiction",
            description="Global rule allows, team-scoped rule denies same action",
            category=AdversarialCategory.CONFLICTING_POLICIES,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Create overlapping scope rules with contradictory effects",
            inputs={"global_effect": "allow", "team_effect": "deny", "team_id": "team-alpha"},
            expected_behavior="Evaluator applies most restrictive effect; team DENY overrides global ALLOW",
            tags=("governance", "scope-overlap"),
        ),
        _case(
            name="circular-escalation-chain",
            description="Rule A escalates to B, B escalates to A",
            category=AdversarialCategory.CONFLICTING_POLICIES,
            severity=AdversarialSeverity.CATASTROPHIC,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Create circular escalation references between policy rules",
            inputs={"rule_a_target": "rule-b", "rule_b_target": "rule-a"},
            expected_behavior="Compiler detects circular dependency and reports fatal conflict",
            tags=("governance", "circular-dependency"),
        ),
    )


# ---------------------------------------------------------------------------
# Malformed input pack
# ---------------------------------------------------------------------------


def malformed_input_pack() -> tuple[AdversarialCase, ...]:
    """Cases with structurally invalid or edge-case inputs."""
    return (
        _case(
            name="empty-string-fields",
            description="Contract creation with empty strings in required fields",
            category=AdversarialCategory.MALFORMED_INPUT,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Pass empty strings to all text fields",
            inputs={"rule_id": "", "name": "", "description": ""},
            expected_behavior="Contract validation rejects with ValueError for each field",
            tags=("validation", "empty-strings"),
        ),
        _case(
            name="negative-metric-values",
            description="Benchmark metric with negative value outside [0,1]",
            category=AdversarialCategory.MALFORMED_INPUT,
            severity=AdversarialSeverity.BENIGN,
            target=BenchmarkCategory.CROSS_PLANE,
            attack_vector="Submit metric with value=-0.5",
            inputs={"metric_value": -0.5, "threshold": 0.8},
            expected_behavior="require_unit_float rejects with ValueError",
            tags=("validation", "bounds"),
        ),
        _case(
            name="oversized-payload",
            description="Event with extremely large payload mapping",
            category=AdversarialCategory.MALFORMED_INPUT,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.EVENT_SPINE,
            attack_vector="Submit event with 10000-key payload",
            inputs={"payload_key_count": 10000},
            expected_behavior="System handles large payload without crash; freeze_value completes",
            tags=("event-spine", "payload-size"),
        ),
    )


# ---------------------------------------------------------------------------
# Deceptive payload pack
# ---------------------------------------------------------------------------


def deceptive_payload_pack() -> tuple[AdversarialCase, ...]:
    """Cases with payloads designed to mislead evaluation logic."""
    return (
        _case(
            name="type-coercion-in-conditions",
            description="Policy condition expects string but receives int that str-matches",
            category=AdversarialCategory.DECEPTIVE_PAYLOAD,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Submit context with numeric value where string expected",
            inputs={"field_path": "action.level", "expected": "5", "actual": 5},
            expected_behavior="Type-safe comparison returns False; no implicit coercion",
            tags=("governance", "type-safety"),
        ),
        _case(
            name="nested-path-traversal-escape",
            description="Dot-path with crafted segments to traverse unexpected structures",
            category=AdversarialCategory.DECEPTIVE_PAYLOAD,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Use field_path='__class__.__name__' to probe internals",
            inputs={"field_path": "__class__.__name__", "context": {}},
            expected_behavior="Dot-path traversal returns field-not-found; no internal access",
            tags=("governance", "path-traversal"),
        ),
    )


# ---------------------------------------------------------------------------
# Ambiguous approval pack
# ---------------------------------------------------------------------------


def ambiguous_approval_pack() -> tuple[AdversarialCase, ...]:
    """Cases where approval requirements are unclear or contradictory."""
    return (
        _case(
            name="approval-and-allow-same-priority",
            description="REQUIRE_APPROVAL and ALLOW at same priority for same context",
            category=AdversarialCategory.AMBIGUOUS_APPROVAL,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Two rules with identical priority: one REQUIRE_APPROVAL, one ALLOW",
            inputs={"effect_a": "require_approval", "effect_b": "allow", "priority": 50},
            expected_behavior="REQUIRE_APPROVAL wins by effect precedence (50 > 10)",
            tags=("governance", "approval"),
        ),
        _case(
            name="missing-approval-context",
            description="Governance gate invoked with no approval-related context",
            category=AdversarialCategory.AMBIGUOUS_APPROVAL,
            severity=AdversarialSeverity.BENIGN,
            target=BenchmarkCategory.GOVERNANCE,
            attack_vector="Evaluate rules when context has no approval fields",
            inputs={"context": {}, "rules_requiring_approval": 1},
            expected_behavior="Conditions referencing missing fields fail; rule does not fire",
            tags=("governance", "missing-context"),
        ),
    )


# ---------------------------------------------------------------------------
# Stale world-state pack
# ---------------------------------------------------------------------------


def stale_world_state_pack() -> tuple[AdversarialCase, ...]:
    """Cases where world-state data is outdated or inconsistent."""
    return (
        _case(
            name="snapshot-version-mismatch",
            description="World state snapshot version does not match expected version",
            category=AdversarialCategory.STALE_WORLD_STATE,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.WORLD_STATE,
            attack_vector="Present stale snapshot version to decision engine",
            inputs={"expected_version": 5, "actual_version": 3},
            expected_behavior="Version mismatch detected; decision deferred until refresh",
            tags=("world-state", "staleness"),
        ),
        _case(
            name="contradicting-entity-states",
            description="Two entities in snapshot contradict each other on shared fact",
            category=AdversarialCategory.STALE_WORLD_STATE,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.WORLD_STATE,
            attack_vector="Insert contradicting entity relations into snapshot",
            inputs={"entity_a_state": "active", "entity_b_ref_to_a": "terminated"},
            expected_behavior="Contradiction detection flags inconsistency; resolution strategy applied",
            tags=("world-state", "contradiction"),
        ),
    )


# ---------------------------------------------------------------------------
# High event churn pack
# ---------------------------------------------------------------------------


def high_event_churn_pack() -> tuple[AdversarialCase, ...]:
    """Cases with rapid-fire event bursts stressing the event spine."""
    return (
        _case(
            name="burst-identical-events",
            description="100 identical events published in rapid succession",
            category=AdversarialCategory.HIGH_EVENT_CHURN,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.EVENT_SPINE,
            attack_vector="Publish 100 events with same type and payload",
            inputs={"event_count": 100, "event_type": "task_completed", "unique_payloads": False},
            expected_behavior="Idempotency windows deduplicate; reaction engine fires at most once",
            tags=("event-spine", "idempotency"),
        ),
        _case(
            name="interleaved-event-types",
            description="Rapid alternation between event types to stress rule matching",
            category=AdversarialCategory.HIGH_EVENT_CHURN,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.REACTION,
            attack_vector="Alternate between 5 event types rapidly",
            inputs={"event_types": 5, "total_events": 50, "pattern": "round-robin"},
            expected_behavior="Each event matched to correct rules; no cross-contamination",
            tags=("reaction", "rule-matching"),
        ),
    )


# ---------------------------------------------------------------------------
# Overloaded workers pack
# ---------------------------------------------------------------------------


def overloaded_workers_pack() -> tuple[AdversarialCase, ...]:
    """Cases where worker/team capacity is exceeded."""
    return (
        _case(
            name="all-workers-at-capacity",
            description="Every worker in team at max load; new job arrives",
            category=AdversarialCategory.OVERLOADED_WORKERS,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.TEAM_FUNCTION,
            attack_vector="Fill all worker capacity then submit new job",
            inputs={"worker_count": 5, "capacity_each": 3, "current_load_each": 3, "new_jobs": 1},
            expected_behavior="Job queued or escalated; no worker overassignment",
            tags=("team", "capacity"),
        ),
        _case(
            name="zero-capacity-team",
            description="Team with zero workers receives job assignment",
            category=AdversarialCategory.OVERLOADED_WORKERS,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.TEAM_FUNCTION,
            attack_vector="Assign job to empty team",
            inputs={"worker_count": 0, "new_jobs": 1},
            expected_behavior="Assignment fails gracefully; escalation triggered",
            tags=("team", "empty-team"),
        ),
    )


# ---------------------------------------------------------------------------
# Provider volatility pack
# ---------------------------------------------------------------------------


def provider_volatility_pack() -> tuple[AdversarialCase, ...]:
    """Cases where provider availability changes rapidly."""
    return (
        _case(
            name="provider-disappears-mid-routing",
            description="Selected provider becomes unavailable after routing decision",
            category=AdversarialCategory.PROVIDER_VOLATILITY,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.PROVIDER_ROUTING,
            attack_vector="Remove provider from registry after routing selects it",
            inputs={"provider_id": "p-001", "removal_timing": "post-selection"},
            expected_behavior="Routing detects unavailability and falls back to next candidate",
            tags=("provider", "availability"),
        ),
        _case(
            name="all-providers-degraded",
            description="Every available provider reports degraded performance",
            category=AdversarialCategory.PROVIDER_VOLATILITY,
            severity=AdversarialSeverity.CATASTROPHIC,
            target=BenchmarkCategory.PROVIDER_ROUTING,
            attack_vector="Set all provider health to degraded simultaneously",
            inputs={"provider_count": 3, "health_status": "degraded"},
            expected_behavior="Routing selects least-degraded; escalation raised for operator",
            tags=("provider", "degradation"),
        ),
    )


# ---------------------------------------------------------------------------
# Simulation/utility disagreement pack
# ---------------------------------------------------------------------------


def simulation_utility_disagreement_pack() -> tuple[AdversarialCase, ...]:
    """Cases where simulation and utility engines produce conflicting recommendations."""
    return (
        _case(
            name="sim-recommends-utility-rejects",
            description="Simulation says proceed; utility says infeasible due to resource constraints",
            category=AdversarialCategory.SIMULATION_UTILITY_DISAGREEMENT,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.SIMULATION,
            attack_vector="Create scenario where risk is low but cost exceeds budget",
            inputs={"sim_verdict": "proceed", "utility_verdict": "reject", "reason": "budget_exceeded"},
            expected_behavior="Utility veto respected — more conservative engine wins",
            tags=("simulation", "utility", "disagreement"),
        ),
        _case(
            name="utility-favors-risky-option",
            description="Utility scores risky option highest due to cost savings; simulation flags risk",
            category=AdversarialCategory.SIMULATION_UTILITY_DISAGREEMENT,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.UTILITY,
            attack_vector="Create option with high utility score but critical risk level",
            inputs={"option_utility": 0.95, "risk_level": "critical", "sim_verdict": "reject"},
            expected_behavior="Risk-adjusted scoring penalizes high risk; simulation veto overrides utility preference",
            tags=("simulation", "utility", "risk-adjustment"),
        ),
    )


# ---------------------------------------------------------------------------
# Replay/idempotency pack
# ---------------------------------------------------------------------------


def replay_idempotency_pack() -> tuple[AdversarialCase, ...]:
    """Cases testing replay determinism and idempotency guarantees."""
    return (
        _case(
            name="duplicate-event-replay",
            description="Same event replayed after idempotency window expires",
            category=AdversarialCategory.REPLAY_IDEMPOTENCY,
            severity=AdversarialSeverity.MODERATE,
            target=BenchmarkCategory.EVENT_SPINE,
            attack_vector="Replay event after window expiry",
            inputs={"event_id": "evt-001", "window_ms": 5000, "replay_delay_ms": 6000},
            expected_behavior="Event processed again — idempotency window expired; result may differ",
            tags=("replay", "idempotency", "window-expiry"),
        ),
        _case(
            name="replay-within-window",
            description="Same event replayed within active idempotency window",
            category=AdversarialCategory.REPLAY_IDEMPOTENCY,
            severity=AdversarialSeverity.BENIGN,
            target=BenchmarkCategory.REACTION,
            attack_vector="Replay event within window",
            inputs={"event_id": "evt-001", "window_ms": 5000, "replay_delay_ms": 1000},
            expected_behavior="Duplicate detected; reaction suppressed",
            tags=("replay", "idempotency", "dedup"),
        ),
    )


# ---------------------------------------------------------------------------
# Resource exhaustion pack
# ---------------------------------------------------------------------------


def resource_exhaustion_pack() -> tuple[AdversarialCase, ...]:
    """Cases testing behavior under resource pressure."""
    return (
        _case(
            name="obligation-deadline-cascade",
            description="Multiple obligations expire simultaneously, all requiring escalation",
            category=AdversarialCategory.RESOURCE_EXHAUSTION,
            severity=AdversarialSeverity.CATASTROPHIC,
            target=BenchmarkCategory.OBLIGATION,
            attack_vector="Create 20 obligations with identical deadlines",
            inputs={"obligation_count": 20, "deadline": "2025-01-01T00:00:00Z"},
            expected_behavior="All obligations escalated in priority order; no silent drops",
            tags=("obligation", "deadline-cascade"),
        ),
        _case(
            name="backpressure-saturation",
            description="Reaction engine receives events faster than backpressure limit",
            category=AdversarialCategory.RESOURCE_EXHAUSTION,
            severity=AdversarialSeverity.AGGRESSIVE,
            target=BenchmarkCategory.REACTION,
            attack_vector="Flood reaction engine beyond max_pending threshold",
            inputs={"max_pending": 10, "incoming_rate": 50},
            expected_behavior="Backpressure policy rejects excess; no silent drops; metrics recorded",
            tags=("reaction", "backpressure"),
        ),
    )


# ---------------------------------------------------------------------------
# Aggregate: all packs
# ---------------------------------------------------------------------------


def all_adversarial_packs() -> dict[AdversarialCategory, tuple[AdversarialCase, ...]]:
    """Return all adversarial packs indexed by category."""
    return {
        AdversarialCategory.CONFLICTING_POLICIES: conflicting_policies_pack(),
        AdversarialCategory.MALFORMED_INPUT: malformed_input_pack(),
        AdversarialCategory.DECEPTIVE_PAYLOAD: deceptive_payload_pack(),
        AdversarialCategory.AMBIGUOUS_APPROVAL: ambiguous_approval_pack(),
        AdversarialCategory.STALE_WORLD_STATE: stale_world_state_pack(),
        AdversarialCategory.HIGH_EVENT_CHURN: high_event_churn_pack(),
        AdversarialCategory.OVERLOADED_WORKERS: overloaded_workers_pack(),
        AdversarialCategory.PROVIDER_VOLATILITY: provider_volatility_pack(),
        AdversarialCategory.SIMULATION_UTILITY_DISAGREEMENT: simulation_utility_disagreement_pack(),
        AdversarialCategory.REPLAY_IDEMPOTENCY: replay_idempotency_pack(),
        AdversarialCategory.RESOURCE_EXHAUSTION: resource_exhaustion_pack(),
    }


def all_adversarial_cases() -> tuple[AdversarialCase, ...]:
    """Return all adversarial cases across all packs as a flat tuple."""
    result: list[AdversarialCase] = []
    for pack in all_adversarial_packs().values():
        result.extend(pack)
    return tuple(result)


def adversarial_cases_for_subsystem(target: BenchmarkCategory) -> tuple[AdversarialCase, ...]:
    """Return all adversarial cases targeting a specific subsystem."""
    return tuple(c for c in all_adversarial_cases() if c.target_subsystem == target)
