"""Purpose: verify causal preview dry-run receipts before execution.
Governance scope: no-mutation preview, false-success prevention, stale-state
    handling, branch coverage, dependency unknowns, and recovery evidence.
Dependencies: pytest and mcoi_runtime.core.causal_preview.
Invariants:
  - Preview does not mutate caller-owned state.
  - Preview success is never reported as verified real success.
  - High-impact preview is blocked or deferred when evidence is missing.
  - Verified recovery evidence can lower risk only with fresh state.
"""

from __future__ import annotations

from mcoi_runtime.core.causal_preview import (
    ActionClass,
    CausalPreviewAction,
    CompensationVerificationStatus,
    PreviewVerdict,
    SideEffectClass,
    StateSnapshot,
    SymbolicPreviewState,
    TruthLevel,
    UniversalCausalPreviewDryRunEngine,
)


NOW = "2026-06-29T12:00:00+00:00"


def _clock() -> str:
    return NOW


def _state(mutable_state: dict | None = None) -> SymbolicPreviewState:
    return SymbolicPreviewState(
        identity={"system": "preview-fixture", "tenant": "tenant-1"},
        constraints={"no_real_write": True, "receipt_required": True},
        mutable_state=mutable_state or {"document": {"version": 1}},
        exposure={"allowed_actors": ("actor-1",), "visibility": "local"},
        history=({"event": "fixture_created"},),
    )


def _snapshot(
    *,
    state: SymbolicPreviewState,
    freshness_score: float = 1.0,
    completeness_score: float = 1.0,
    source_confidence: float = 1.0,
) -> StateSnapshot:
    return StateSnapshot(
        snapshot_id="snapshot-fixture",
        state_hash="state-fixture-hash",
        captured_at=NOW,
        freshness_score=freshness_score,
        completeness_score=completeness_score,
        source_confidence=source_confidence,
        state={
            "identity": dict(state.identity),
            "constraints": dict(state.constraints),
            "mutable_state": dict(state.mutable_state),
            "exposure": dict(state.exposure),
            "history": tuple(dict(item) for item in state.history),
        },
    )


def test_read_only_preview_clones_state_and_never_certifies_success() -> None:
    mutable_state = {"document": {"version": 1}}
    state = _state(mutable_state)
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="inspect-policy",
        action_class=ActionClass.READ,
        actor_id="actor-1",
        target_ref="doc://policy",
        goal="Inspect policy without changing it.",
        known_dependencies=("doc://policy",),
    )

    receipt = engine.run(
        real_state=state,
        action=action,
        effect_model=lambda cloned: {
            **cloned,
            "mutable_state": {"document": {"version": 99}},
        },
    )

    assert mutable_state == {"document": {"version": 1}}
    assert receipt.verdict is PreviewVerdict.APPROVE
    assert receipt.success_certified is False
    assert receipt.truth_level is TruthLevel.SIMULATED_CONSEQUENCE
    assert receipt.state_hash_after_preview == receipt.state_snapshot_hash
    assert len(receipt.branch_summary) == 8


def test_high_impact_stale_snapshot_requires_more_evidence() -> None:
    state = _state()
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="publish-dashboard",
        action_class=ActionClass.PUBLISH,
        actor_id="actor-1",
        target_ref="dashboard://public",
        goal="Publish a dashboard update.",
        side_effect_class=SideEffectClass.USER_FACING,
        approval_refs=("approval://publish-dashboard",),
        known_dependencies=("dashboard://public",),
    )

    receipt = engine.run(
        real_state=state,
        action=action,
        snapshot=_snapshot(state=state, freshness_score=0.6),
    )

    assert receipt.verdict is PreviewVerdict.REQUIRE_MORE_EVIDENCE
    assert receipt.branch_summary == ()
    assert receipt.risks[0].risk_type == "stale_state"
    assert receipt.confidence_score <= 0.35
    assert "Refresh state snapshot before execution." in receipt.required_guards


def test_dry_run_execution_flags_block_before_simulation() -> None:
    mutable_state = {"counter": 0}
    state = _state(mutable_state)
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="bad-dry-run",
        action_class=ActionClass.WRITE,
        actor_id="actor-1",
        target_ref="file://config",
        goal="Preview a config write.",
        side_effect_class=SideEffectClass.LOCAL_ONLY,
        parameters={"execute_now": True},
    )

    receipt = engine.run(real_state=state, action=action)

    assert receipt.verdict is PreviewVerdict.BLOCK
    assert receipt.branch_summary == ()
    assert any("execute_now" in unknown for unknown in receipt.unknowns)
    assert mutable_state == {"counter": 0}
    assert receipt.success_certified is False


def test_missing_high_impact_approval_blocks_admission() -> None:
    state = _state()
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="charge-card",
        action_class=ActionClass.TRANSFER,
        actor_id="actor-1",
        target_ref="payment://charge-1",
        goal="Charge a card.",
        side_effect_class=SideEffectClass.FINANCIAL,
        known_dependencies=("payment://provider",),
    )

    receipt = engine.run(real_state=state, action=action)

    assert receipt.verdict is PreviewVerdict.BLOCK
    assert receipt.branch_coverage_score == 0.0
    assert any("approval evidence" in unknown for unknown in receipt.unknowns)
    assert receipt.confidence_score <= 0.2
    assert receipt.success_certified is False


def test_unknown_dependencies_reduce_confidence_and_defer_external_action() -> None:
    state = _state()
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="send-notification",
        action_class=ActionClass.SEND,
        actor_id="actor-1",
        target_ref="mail://thread-1",
        goal="Send a user-visible notification.",
        side_effect_class=SideEffectClass.EXTERNAL_SYSTEM,
        approval_refs=("approval://send-notification",),
        suspected_dependencies=("mail-provider://primary",),
    )

    receipt = engine.run(real_state=state, action=action)

    assert receipt.verdict is PreviewVerdict.REQUIRE_MORE_EVIDENCE
    assert receipt.compensation_plans[0].verification_status is CompensationVerificationStatus.UNTESTED
    assert "Resolve preview unknowns before execution." in receipt.required_guards
    assert any(risk.risk_type == "unresolved_unknowns" for risk in receipt.risks)
    assert receipt.confidence_score <= 0.35


def test_verified_rollback_allows_guarded_user_facing_preview() -> None:
    state = _state()
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="deploy-feature-flag",
        action_class=ActionClass.DEPLOY,
        actor_id="actor-1",
        target_ref="feature://new-path",
        goal="Deploy a guarded feature path.",
        side_effect_class=SideEffectClass.USER_FACING,
        approval_refs=("approval://deploy-feature",),
        known_dependencies=("frontend://route", "api://feature"),
        rollback_evidence_refs=("rollback://feature-flag-disable",),
        parameters={"external_confirmation_ref": "provider://deployment-window"},
    )

    receipt = engine.run(real_state=state, action=action)

    assert receipt.verdict is PreviewVerdict.APPROVE_WITH_GUARDS
    assert receipt.compensation_plans[0].verification_status is CompensationVerificationStatus.VERIFIED
    assert receipt.confidence_score >= 0.8
    assert receipt.unknowns == ()
    assert "Emit post-execution verification receipt before success claim." in (
        receipt.post_execution_verification_plan
    )


def test_required_branch_gap_makes_simulation_inconclusive() -> None:
    state = _state()
    engine = UniversalCausalPreviewDryRunEngine(clock=_clock)
    action = CausalPreviewAction(
        action_id="inspect-with-extra-branch",
        action_class=ActionClass.READ,
        actor_id="actor-1",
        target_ref="doc://extra",
        goal="Inspect with an intentionally uncovered branch.",
        known_dependencies=("doc://extra",),
        required_branch_ids=("expected", "unmodeled_extreme_failure"),
    )

    receipt = engine.run(real_state=state, action=action)

    assert receipt.verdict is PreviewVerdict.SIMULATION_INCONCLUSIVE
    assert receipt.branch_coverage_score == 0.5
    assert receipt.confidence_score <= 0.35
    assert receipt.violations == ()
    assert receipt.success_certified is False
