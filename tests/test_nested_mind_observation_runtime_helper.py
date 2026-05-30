"""Tests for the env-driven nested-mind observation bridge planner.

Purpose: verify that the runtime integration can construct P2.1 observation
proposal plans from evidence while remaining default-off and planning-only.
Governance scope: observation proposal planning only; no connector execution,
child-mind creation, lawbook mutation, arbitrary patch operation, or memory
admission.
"""

from __future__ import annotations

from collections.abc import Iterator

from mcoi_runtime.app.nested_mind_integration import (
    NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV,
    NestedMindObservationBridgePlanner,
    mount_nested_mind_observation_bridge_from_env,
)
from mcoi_runtime.contracts.nested_mind_observation_bridge import (
    NestedMindObservationBridgeStatus,
    stable_json_hash,
)
from mcoi_runtime.contracts.nested_mind_receipts import build_proposal_evidence
from mcoi_runtime.contracts.proof import GuardVerdict, TransitionReceipt
from mcoi_runtime.contracts.state_machine import TransitionVerdict


def _clock() -> Iterator[str]:
    values = iter(
        (
            "2026-05-30T00:00:02+00:00",
            "2026-05-30T00:00:03+00:00",
            "2026-05-30T00:00:04+00:00",
            "2026-05-30T00:00:05+00:00",
        )
    )
    return values


def _clock_fn(values: Iterator[str]):
    return lambda: next(values)


def _transition_receipt() -> TransitionReceipt:
    return TransitionReceipt(
        receipt_id="rcpt-runtime-1",
        machine_id="maf-test-machine",
        entity_id="entity-1",
        from_state="draft",
        to_state="observed",
        action="record_observation",
        before_state_hash="before-hash",
        after_state_hash="after-hash",
        guard_verdicts=(GuardVerdict("authority", True, "ok"),),
        verdict=TransitionVerdict.ALLOWED,
        replay_token="replay-1",
        causal_parent="genesis",
        issued_at="2026-05-30T00:00:00+00:00",
        receipt_hash="mullu-receipt-hash-runtime-1",
        signature="sig-1",
        signing_key_id="key-1",
    )


def _evidence():
    return build_proposal_evidence(
        evidence_id="evidence-runtime-1",
        mind_id="root",
        transition_receipt=_transition_receipt(),
        actor_id="operator-a",
        reason="record bounded observation",
        authority_receipt_hash="authority-receipt-hash-runtime-1",
        requested_at="2026-05-30T00:00:01+00:00",
    )


def test_observation_bridge_mounts_default_off() -> None:
    bootstrap = mount_nested_mind_observation_bridge_from_env(
        runtime_env={},
        clock=_clock_fn(_clock()),
    )

    assert bootstrap.enabled is False
    assert isinstance(bootstrap.planner, NestedMindObservationBridgePlanner)
    assert bootstrap.planner.enabled is False


def test_observation_bridge_mounts_enabled_only_with_flag() -> None:
    bootstrap = mount_nested_mind_observation_bridge_from_env(
        runtime_env={NESTED_MIND_OBSERVATION_BRIDGE_ENABLED_ENV: "true"},
        clock=_clock_fn(_clock()),
    )

    assert bootstrap.enabled is True
    assert bootstrap.planner.enabled is True


def test_default_off_planner_constructs_disabled_plan_only() -> None:
    evidence = _evidence()
    planner = NestedMindObservationBridgePlanner(enabled=False, clock=_clock_fn(_clock()))

    plan = planner.plan_observation(
        evidence,
        observation_id="obs-runtime-1",
        observation={"kind": "note", "text": "bounded observation"},
    )

    assert plan.status is NestedMindObservationBridgeStatus.DISABLED
    assert plan.blockers == ("nested_mind_observation_bridge_disabled",)
    assert plan.target_route == "/minds/root/proposals"
    assert plan.method == "POST"
    assert plan.proposal_payload["ops"] == [
        {
            "op": "set",
            "key": "observations/obs-runtime-1",
            "value": {"kind": "note", "text": "bounded observation"},
        }
    ]
    assert plan.payload_hash == stable_json_hash(plan.proposal_payload)
    assert plan.created_at == "2026-05-30T00:00:03+00:00"


def test_enabled_planner_marks_plan_planned_without_connector_execution() -> None:
    evidence = _evidence()
    planner = NestedMindObservationBridgePlanner(enabled=True, clock=_clock_fn(_clock()))

    plan = planner.plan_observation(
        evidence,
        observation_id="obs-runtime-1",
        observation={"kind": "note", "text": "bounded observation"},
        observed_at="2026-05-30T00:00:02+00:00",
        metadata={"source": "unit-test"},
    )

    assert plan.status is NestedMindObservationBridgeStatus.PLANNED
    assert plan.blockers == ()
    assert plan.proposal_evidence_id == evidence.evidence_id
    assert plan.mullu_receipt_hash == evidence.mullu_receipt.receipt_hash
    assert plan.authority_receipt_hash == evidence.authority_receipt_hash
    assert plan.metadata["source"] == "unit-test"
    assert plan.created_at == "2026-05-30T00:00:02+00:00"


def test_plan_id_is_deterministic_for_same_inputs_and_clock() -> None:
    evidence = _evidence()
    first = NestedMindObservationBridgePlanner(enabled=True, clock=_clock_fn(_clock())).plan_observation(
        evidence,
        observation_id="obs-runtime-1",
        observation={"kind": "note", "text": "bounded observation"},
        observed_at="2026-05-30T00:00:02+00:00",
    )
    second = NestedMindObservationBridgePlanner(enabled=True, clock=_clock_fn(_clock())).plan_observation(
        evidence,
        observation_id="obs-runtime-1",
        observation={"kind": "note", "text": "bounded observation"},
        observed_at="2026-05-30T00:00:02+00:00",
    )

    assert first.plan_id == second.plan_id
    assert first.payload_hash == second.payload_hash
