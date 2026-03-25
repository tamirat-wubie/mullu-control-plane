"""Purpose: world-state integration bridge — connects the world-state engine
to snapshot assembly, expected-vs-actual comparison, conflict grouping,
delta computation, and dashboard surfacing.
Governance scope: world-state plane invocation for goal decomposition,
    workflow planning, recovery, and operator dashboard.
Dependencies: world-state engine, world-state contracts.
Invariants:
  - Bridge methods are stateless static helpers.
  - Each method composes existing engine calls.
  - No graph mutation beyond what engine methods document.
  - Assessment output is advisory only.
"""

from __future__ import annotations

from mcoi_runtime.contracts.world_state import (
    ConflictSet,
    DerivedFact,
    ExpectedState,
    StateConfidenceEnvelope,
    WorldStateDelta,
    WorldStateSnapshot,
)
from .world_state import WorldStateEngine


class WorldStateBridge:
    """Static methods bridging world-state engine operations to platform decision points.

    Provides convenience methods for:
    - Taking a full snapshot for cross-plane visibility
    - Comparing all expected states against actual to detect drift
    - Grouping contradictions to prioritize conflict resolution
    - Computing deltas between snapshots to understand state evolution
    - Generating per-entity confidence envelopes
    - Running a full health assessment for the dashboard
    """

    @staticmethod
    def take_snapshot(
        engine: WorldStateEngine,
        snapshot_id: str | None = None,
    ) -> WorldStateSnapshot:
        """Assemble a full world-state snapshot."""
        return engine.assemble_snapshot(snapshot_id)

    @staticmethod
    def check_all_expectations(
        engine: WorldStateEngine,
    ) -> tuple[tuple[ExpectedState, str, bool], ...]:
        """Compare every registered expected state against actual.

        Returns a tuple of (expected_state, actual_value_repr, matches)
        for each registered expectation.
        """
        results: list[tuple[ExpectedState, str, bool]] = []
        for exp in engine.list_expected_states():
            results.append(engine.compare_expected_vs_actual(exp.expectation_id))
        return tuple(results)

    @staticmethod
    def detect_violations(
        engine: WorldStateEngine,
    ) -> tuple[tuple[ExpectedState, str], ...]:
        """Return only the expectations that do NOT match actual state.

        Returns (expected_state, actual_value_repr) for each violation.
        """
        violations: list[tuple[ExpectedState, str]] = []
        for exp in engine.list_expected_states():
            expected, actual_repr, matches = engine.compare_expected_vs_actual(
                exp.expectation_id,
            )
            if not matches:
                violations.append((expected, actual_repr))
        return tuple(violations)

    @staticmethod
    def group_all_conflicts(
        engine: WorldStateEngine,
    ) -> tuple[ConflictSet, ...]:
        """Group all unresolved contradictions by entity."""
        return engine.group_conflicts()

    @staticmethod
    def compute_snapshot_deltas(
        engine: WorldStateEngine,
        previous: WorldStateSnapshot,
        current: WorldStateSnapshot,
    ) -> tuple[WorldStateDelta, ...]:
        """Compute deltas between two snapshots."""
        return engine.compute_deltas(previous, current)

    @staticmethod
    def entity_confidence_envelopes(
        engine: WorldStateEngine,
        entity_ids: tuple[str, ...],
        attribute: str,
    ) -> tuple[StateConfidenceEnvelope, ...]:
        """Compute confidence envelopes for a set of entities on a given attribute."""
        envelopes: list[StateConfidenceEnvelope] = []
        for eid in entity_ids:
            envelopes.append(engine.compute_confidence_envelope(eid, attribute))
        return tuple(envelopes)

    @staticmethod
    def full_health_assessment(
        engine: WorldStateEngine,
    ) -> dict[str, object]:
        """Run a full world-state health assessment for dashboard consumption.

        Returns a dict with:
        - snapshot: WorldStateSnapshot
        - violations: tuple of (expected_state, actual_repr)
        - conflict_sets: tuple of ConflictSet
        - violation_count: int
        - recommendation: str
        """
        snapshot = engine.assemble_snapshot()
        violations = WorldStateBridge.detect_violations(engine)
        conflict_sets = engine.group_conflicts()

        contradiction_count = len(snapshot.unresolved_contradictions)
        violation_count = len(violations)

        if contradiction_count == 0 and violation_count == 0:
            recommendation = "healthy"
        elif violation_count > 0 and contradiction_count > 0:
            recommendation = "investigate"
        elif violation_count > 0:
            recommendation = "drift_detected"
        else:
            recommendation = "conflicts_pending"

        return {
            "snapshot": snapshot,
            "violations": violations,
            "conflict_sets": conflict_sets,
            "violation_count": violation_count,
            "recommendation": recommendation,
        }
