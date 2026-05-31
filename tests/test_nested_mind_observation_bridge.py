"""Tests for the default-off nested-mind observation proposal bridge.

Purpose: verify that P2.1 can construct only a fixed-shape record_observation
proposal plan from Mullu receipt evidence.
Governance scope: planning only; no route, connector execution, child-mind
creation, lawbook mutation, arbitrary patch operation, or memory admission.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.nested_mind_observation_bridge import (
    NestedMindObservationBridgeStatus,
    NestedMindObservationProposalPlan,
    build_observation_proposal_plan,
    build_observation_proposal_payload,
    stable_json_hash,
)
from mcoi_runtime.contracts.nested_mind_receipts import build_proposal_evidence
from mcoi_runtime.contracts.proof import GuardVerdict, TransitionReceipt
from mcoi_runtime.contracts.state_machine import TransitionVerdict


def _transition_receipt() -> TransitionReceipt:
    return TransitionReceipt(
        receipt_id="rcpt-obs-1",
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
        receipt_hash="mullu-receipt-hash-obs-1",
        signature="sig-1",
        signing_key_id="key-1",
    )


def _evidence():
    return build_proposal_evidence(
        evidence_id="evidence-obs-1",
        mind_id="root",
        transition_receipt=_transition_receipt(),
        actor_id="operator-a",
        reason="record bounded observation",
        authority_receipt_hash="authority-receipt-hash-1",
        requested_at="2026-05-30T00:00:01+00:00",
    )


def test_build_observation_payload_is_fixed_shape() -> None:
    evidence = _evidence()
    payload = build_observation_proposal_payload(
        evidence,
        observation_id="obs-1",
        observation={"kind": "note", "text": "bounded observation"},
        observed_at="2026-05-30T00:00:02+00:00",
    )

    assert set(payload) == {"actor", "reason", "kind", "metadata", "ops"}
    assert payload["kind"] == "record_observation"
    assert payload["metadata"]["mullu_receipt_hash"] == evidence.mullu_receipt.receipt_hash
    assert payload["metadata"]["authority_receipt_hash"] == evidence.authority_receipt_hash
    assert payload["metadata"]["proposal_evidence_hash"] == evidence.evidence_hash
    assert payload["ops"] == [
        {
            "op": "set",
            "key": "observations/obs-1",
            "value": {"kind": "note", "text": "bounded observation"},
        }
    ]


def test_bridge_plan_is_disabled_by_default() -> None:
    evidence = _evidence()
    plan = build_observation_proposal_plan(
        evidence,
        plan_id="plan-1",
        observation_id="obs-1",
        observation={"kind": "note", "text": "bounded observation"},
        observed_at="2026-05-30T00:00:02+00:00",
        created_at="2026-05-30T00:00:03+00:00",
    )

    assert plan.status is NestedMindObservationBridgeStatus.DISABLED
    assert plan.blockers == ("nested_mind_observation_bridge_disabled",)
    assert plan.method == "POST"
    assert plan.target_route == "/minds/root/proposals"
    assert plan.payload_hash == stable_json_hash(plan.proposal_payload)


def test_enabled_plan_has_no_blockers_but_same_fixed_route() -> None:
    evidence = _evidence()
    plan = build_observation_proposal_plan(
        evidence,
        plan_id="plan-1",
        observation_id="obs-1",
        observation={"kind": "note", "text": "bounded observation"},
        observed_at="2026-05-30T00:00:02+00:00",
        created_at="2026-05-30T00:00:03+00:00",
        bridge_enabled=True,
    )

    assert plan.status is NestedMindObservationBridgeStatus.PLANNED
    assert plan.blockers == ()
    assert plan.target_route == "/minds/root/proposals"
    assert len(plan.proposal_payload["ops"]) == 1


def test_plan_rejects_arbitrary_route_or_method() -> None:
    evidence = _evidence()
    plan = build_observation_proposal_plan(
        evidence,
        plan_id="plan-1",
        observation_id="obs-1",
        observation={"kind": "note"},
        observed_at="2026-05-30T00:00:02+00:00",
        created_at="2026-05-30T00:00:03+00:00",
        bridge_enabled=True,
    )

    with pytest.raises(ValueError, match="fixed nested-mind proposals route"):
        NestedMindObservationProposalPlan(
            **{**plan.to_dict(), "target_route": "/minds/root/lawbook/migrations"}
        )
    with pytest.raises(ValueError, match="method must be POST"):
        NestedMindObservationProposalPlan(**{**plan.to_dict(), "method": "GET"})


def test_plan_rejects_arbitrary_ops() -> None:
    evidence = _evidence()
    plan = build_observation_proposal_plan(
        evidence,
        plan_id="plan-1",
        observation_id="obs-1",
        observation={"kind": "note"},
        observed_at="2026-05-30T00:00:02+00:00",
        created_at="2026-05-30T00:00:03+00:00",
        bridge_enabled=True,
    )
    payload = plan.to_dict()["proposal_payload"]
    payload["ops"] = [
        {"op": "set", "key": "observations/obs-1", "value": {"kind": "note"}},
        {"op": "set", "key": "lawbook/rule", "value": "forbidden"},
    ]

    with pytest.raises(ValueError, match="exactly one op"):
        NestedMindObservationProposalPlan(
            **{**plan.to_dict(), "proposal_payload": payload, "payload_hash": stable_json_hash(payload)}
        )


def test_plan_rejects_payload_hash_mismatch() -> None:
    evidence = _evidence()
    plan = build_observation_proposal_plan(
        evidence,
        plan_id="plan-1",
        observation_id="obs-1",
        observation={"kind": "note"},
        observed_at="2026-05-30T00:00:02+00:00",
        created_at="2026-05-30T00:00:03+00:00",
        bridge_enabled=True,
    )

    with pytest.raises(ValueError, match="payload_hash"):
        NestedMindObservationProposalPlan(**{**plan.to_dict(), "payload_hash": "wrong-hash"})


def test_observation_id_cannot_change_route_shape() -> None:
    evidence = _evidence()

    with pytest.raises(ValueError, match="observation_id"):
        build_observation_proposal_plan(
            evidence,
            plan_id="plan-1",
            observation_id="../lawbook",
            observation={"kind": "note"},
            observed_at="2026-05-30T00:00:02+00:00",
            created_at="2026-05-30T00:00:03+00:00",
            bridge_enabled=True,
        )
