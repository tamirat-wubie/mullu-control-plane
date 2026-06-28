"""AxiomWorld generic event adapter tests.

Purpose: verify plain payload ingestion into the AxiomWorld kernel overlay.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.axiomworld_generic_event_adapter.
Invariants:
  - Generic payloads are normalized before kernel admission.
  - Evidence is required for observed symbols.
  - Conflicts remain explicit across adapter ingests.
  - Public projections redact private state.
  - High-risk action payloads stop at approval readiness.
"""

from __future__ import annotations

import pytest

from gateway.axiomworld_generic_event_adapter import AxiomWorldGenericEventAdapter
from gateway.axiomworld_kernel import AxiomActionStatus, AxiomDecision


NOW = "2026-06-28T13:00:00+00:00"
TENANT = "tenant-adapter"


def test_generic_event_adapter_ingests_observation_claim_action_and_projection() -> None:
    adapter = AxiomWorldGenericEventAdapter()

    result = adapter.ingest(_payload())
    payload = result.to_json_dict()
    action = adapter.kernel.action_record("action:local-label")

    assert result.decision == AxiomDecision.ACCEPT
    assert result.materialized_state.entity_count == 1
    assert result.materialized_state.claim_count == 1
    assert [symbol["entity_id"] for symbol in result.projection.symbols] == ["repo:mullu-control-plane"]
    assert [claim["claim_id"] for claim in result.projection.claims] == ["claim:foundation-ready"]
    assert action is not None
    assert action.status == AxiomActionStatus.CHECKED
    assert len(result.receipts) == 4
    assert payload["decision"] == "ACCEPT"
    assert payload["materialized_state"]["state_hash"]


def test_generic_event_adapter_rejects_missing_evidence_before_symbol_admission() -> None:
    adapter = AxiomWorldGenericEventAdapter()
    payload = _payload()
    payload["evidence"] = []

    with pytest.raises(ValueError, match="evidence_required"):
        adapter.ingest(payload)

    state = adapter.kernel.materialize(tenant_id=TENANT)
    receipts = adapter.kernel.receipts()

    assert state.entity_count == 0
    assert state.claim_count == 0
    assert state.open_contradiction_count == 0
    assert receipts == ()


def test_generic_event_adapter_preserves_claim_conflict_across_ingests() -> None:
    adapter = AxiomWorldGenericEventAdapter()
    first = adapter.ingest(
        _payload(
            claims=[
                {
                    "claim_id": "claim:ci-green",
                    "subject_ref": "repo:mullu-control-plane",
                    "predicate": "ci_status",
                    "object_value": "green",
                }
            ]
        )
    )

    second = adapter.ingest(
        {
            "event_id": "event:claim-red",
            "tenant_id": TENANT,
            "source": "github_snapshot",
            "observed_at": NOW,
            "evidence": [_evidence("evidence-red")],
            "claims": [
                {
                    "claim_id": "claim:ci-red",
                    "subject_ref": "repo:mullu-control-plane",
                    "predicate": "ci_status",
                    "object_value": "red",
                }
            ],
            "projection": {"observer": "operator", "scope": "internal"},
        }
    )
    state = adapter.kernel.materialize(tenant_id=TENANT)

    assert first.decision == AxiomDecision.ACCEPT
    assert second.decision == AxiomDecision.QUARANTINE
    assert state.claim_count == 2
    assert state.open_contradiction_count == 1
    assert any(receipt.reason == "claim_conflict_preserved" for receipt in second.receipts)
    assert second.projection.claims[0]["truth_state"] == "CONFLICTED"


def test_generic_event_adapter_public_projection_redacts_private_payload() -> None:
    adapter = AxiomWorldGenericEventAdapter()

    result = adapter.ingest(
        _payload(
            symbol={
                "entity_id": "repo:private",
                "entity_type": "repository",
                "display_name": "Private Repository",
                "stable_fingerprint": {"provider": "github", "repo": "private"},
                "scope": "private",
                "permissions": {"public": False},
            },
            claims=[
                {
                    "claim_id": "claim:private-status",
                    "subject_ref": "repo:private",
                    "predicate": "status",
                    "object_value": "operator-only",
                    "scope": "private",
                }
            ],
            actions=[],
            projection={"observer": "public-web", "scope": "public"},
        )
    )

    assert result.decision == AxiomDecision.ACCEPT
    assert result.projection.symbols == ()
    assert result.projection.claims == ()
    assert "symbol_scope_redacted" in result.projection.redactions
    assert "claim_subject_scope_redacted" in result.projection.redactions
    assert result.materialized_state.entity_count == 1
    assert result.materialized_state.claim_count == 1


def test_generic_event_adapter_gates_high_risk_action_payload() -> None:
    adapter = AxiomWorldGenericEventAdapter()

    result = adapter.ingest(
        _payload(
            actions=[
                {
                    "action_id": "action:publish",
                    "actor": "operator",
                    "intent": "publish external projection",
                    "target_ref": "repo:mullu-control-plane",
                    "risk_level": "high",
                    "reversibility": "irreversible",
                    "permissions_required": ["world_state:write"],
                    "preconditions": ["operator_approval"],
                }
            ]
        )
    )
    action = adapter.kernel.action_record("action:publish")

    assert result.decision == AxiomDecision.REQUIRE_APPROVAL
    assert action is not None
    assert action.status == AxiomActionStatus.PROPOSED
    assert any(receipt.reason == "action_requires_approval" for receipt in result.receipts)
    assert result.materialized_state.entity_count == 1
    assert result.materialized_state.claim_count == 1


def _payload(
    *,
    symbol: dict[str, object] | None = None,
    claims: list[dict[str, object]] | None = None,
    actions: list[dict[str, object]] | None = None,
    projection: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "event_id": "event:repo-observed",
        "tenant_id": TENANT,
        "source": "github_snapshot",
        "observed_at": NOW,
        "evidence": [_evidence("evidence-1")],
        "symbol": symbol
        or {
            "entity_id": "repo:mullu-control-plane",
            "entity_type": "repository",
            "display_name": "Mullu Control Plane",
            "stable_fingerprint": {
                "provider": "github",
                "owner": "tamirat-wubie",
                "repo": "mullu-control-plane",
            },
            "scope": "public",
            "permissions": {"public": True},
            "attributes": {"default_branch": "main"},
            "aliases": ["Mullu Control Plane"],
        },
        "claims": claims
        if claims is not None
        else [
            {
                "claim_id": "claim:foundation-ready",
                "subject_ref": "repo:mullu-control-plane",
                "predicate": "readiness",
                "object_value": "foundation",
                "scope": "public",
            }
        ],
        "actions": actions
        if actions is not None
        else [
            {
                "action_id": "action:local-label",
                "actor": "operator",
                "intent": "attach local metadata label",
                "target_ref": "repo:mullu-control-plane",
                "risk_level": "low",
                "reversibility": "full",
                "expected_delta": {"kind": "metadata_only"},
            }
        ],
        "projection": projection or {"observer": "public-web", "scope": "public"},
    }


def _evidence(evidence_id: str) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "evidence_type": "snapshot",
        "source": "fixture",
        "observed_at": NOW,
        "content_hash": f"sha256:{evidence_id}",
    }
