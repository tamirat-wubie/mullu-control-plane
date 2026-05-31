"""Tests for the nested-mind record_observation staging harness.

Purpose: prove the operator staging path can close with fake connectors only.
Governance scope: P2 nested-mind observation bridge readiness; no live writes.
Dependencies: submitter, reconciler, evidence store, and P3 readiness validator.
Invariants: submit remains explicit, reconciliation is read-only, and memory
admission requires a bound verified evidence chain.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.adapters import JsonConnectorOutcome, NestedMindObservationReconciler, NestedMindObservationSubmitter
from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationReconciliationStatus,
    NestedMindObservationSubmissionStatus,
    NestedMindProposalEvidence,
    build_observation_proposal_payload,
    build_verified_observation_bridge_report,
    stable_json_hash,
)
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.persistence import NestedMindEvidenceStore
from mcoi_runtime.core.invariants import stable_identifier
from scripts.report_nested_mind_evidence import build_nested_mind_evidence_report
from scripts.validate_nested_mind_p3_readiness import validate_p3_readiness


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _connector_result(result_id: str, *, status: ConnectorStatus = ConnectorStatus.SUCCEEDED) -> ConnectorResult:
    return ConnectorResult(
        result_id=result_id,
        connector_id="fake-nested-mind",
        status=status,
        response_digest="d" * 64 if status is ConnectorStatus.SUCCEEDED else "none",
        started_at=_clock(),
        finished_at=_clock(),
        error_code=None if status is ConnectorStatus.SUCCEEDED else "fake_connector_failed",
    )


def _evidence() -> NestedMindProposalEvidence:
    return NestedMindProposalEvidence(
        evidence_id="evidence-1",
        mind_id="root",
        evidence_hash="proposal-evidence-hash-1",
        mullu_receipt_hash="mullu-receipt-hash-1",
        authority_receipt_hash="authority-receipt-hash-1",
    )


def _plan(evidence: NestedMindProposalEvidence | None = None) -> NestedMindObservationProposalPlan:
    proposal_evidence = evidence or _evidence()
    observation = {
        "observation_id": "obs-1",
        "source": "fake-staging-harness",
        "effect": "record_observation_probe",
    }
    proposal_payload = build_observation_proposal_payload(
        proposal_evidence,
        observation_id="obs-1",
        observation_hash=stable_json_hash(observation),
        observation_value=observation,
    )
    payload_hash = stable_json_hash(proposal_payload)
    return NestedMindObservationProposalPlan(
        plan_id=stable_identifier(
            "nested-mind-observation-plan",
            {
                "evidence_id": proposal_evidence.evidence_id,
                "payload_hash": payload_hash,
                "planned_at": _clock(),
            },
        ),
        proposal_evidence_id=proposal_evidence.evidence_id,
        mind_id=proposal_evidence.mind_id,
        method="POST",
        target_route=f"/minds/{proposal_evidence.mind_id}/proposals",
        proposal_payload=proposal_payload,
        payload_hash=payload_hash,
        mullu_receipt_hash=proposal_evidence.mullu_receipt_hash,
        authority_receipt_hash=proposal_evidence.authority_receipt_hash,
        status=NestedMindObservationProposalPlanStatus.PLANNED,
        planned_at=_clock(),
    )


class FakeSubmitConnector:
    def __init__(self, *, overrides: Mapping[str, Any] | None = None) -> None:
        self.calls: list[tuple[object, Mapping[str, Any]]] = []
        self._overrides = dict(overrides or {})

    def invoke_json(self, connector: object, request: Mapping[str, Any]) -> JsonConnectorOutcome:
        self.calls.append((connector, request))
        payload_hash = stable_json_hash(request["json_body"])  # type: ignore[arg-type]
        payload = {
            "mind_id": "root",
            "status": "accepted",
            "commit_hash": "commit-hash-1",
            "history_hash": "history-hash-1",
            "state_hash": "state-hash-1",
            "sequence": 1,
            "committed_at": _clock(),
            "proposal_evidence_hash": "proposal-evidence-hash-1",
            "payload_hash": payload_hash,
            "mullu_receipt_hash": "mullu-receipt-hash-1",
            "authority_receipt_hash": "authority-receipt-hash-1",
            "failures": (),
        }
        payload.update(self._overrides)
        return JsonConnectorOutcome(
            connector_result=_connector_result("submit-result-1"),
            json_payload=payload,
        )


class FakeReadConnector:
    def __init__(self, witness: NestedMindCommitWitness, *, audit_history_hash: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._witness = witness
        self._audit_history_hash = audit_history_hash or witness.nested_mind_history_hash

    def read_projection_json(self, mind_id: str) -> JsonConnectorOutcome:
        self.calls.append(("projection", mind_id))
        return JsonConnectorOutcome(
            connector_result=_connector_result("projection-result-1"),
            json_payload={
                "commit_hash": self._witness.nested_mind_commit_hash,
                "history_hash": self._witness.nested_mind_history_hash,
            },
        )

    def verify_history_json(self, mind_id: str) -> JsonConnectorOutcome:
        self.calls.append(("audit", mind_id))
        return JsonConnectorOutcome(
            connector_result=_connector_result("audit-result-1"),
            json_payload={"verified_history_hash": self._audit_history_hash},
        )

    def replay_history_json(self, mind_id: str) -> JsonConnectorOutcome:
        self.calls.append(("replay", mind_id))
        return JsonConnectorOutcome(
            connector_result=_connector_result("replay-result-1"),
            json_payload={"causal_chain_verified": True},
        )


def _submitter(fake_connector: FakeSubmitConnector) -> NestedMindObservationSubmitter:
    return NestedMindObservationSubmitter(
        clock=_clock,
        base_url="https://nested.example/staging",
        bearer_token="staging-secret-token",
        http_json_connector=fake_connector,
    )


def test_fake_staging_harness_closes_full_record_observation_chain(tmp_path) -> None:
    evidence = _evidence()
    plan = _plan(evidence)
    fake_submit = FakeSubmitConnector()
    submitter = _submitter(fake_submit)
    dry_run = submitter.submit_observation_plan_with_witness(plan, submit_enabled=False)

    assert dry_run.report.status is NestedMindObservationSubmissionStatus.DISABLED
    assert dry_run.commit_witness is None
    assert fake_submit.calls == []

    submission = submitter.submit_observation_plan_with_witness(plan, submit_enabled=True)
    assert submission.report.status is NestedMindObservationSubmissionStatus.ACCEPTED
    assert submission.commit_witness is not None
    assert fake_submit.calls[0][1]["url"] == "https://nested.example/staging/minds/root/proposals"

    store_path = tmp_path / "nested-mind-evidence.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_plan(plan)
    store.record_submission_report(submission.report)
    store.record_commit_witness(submission.commit_witness)
    bridge = build_verified_observation_bridge_report(
        evidence,
        submission.report,
        submission.commit_witness,
        report_id="bridge-1",
        bridged_at=_clock(),
    )
    store.record_bridge_report(bridge)

    reconciliation = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(submission.commit_witness),
    ).reconcile(plan_id=plan.plan_id, witness=submission.commit_witness)
    store.record_reconciliation_report(reconciliation)

    reloaded = NestedMindEvidenceStore(store_path)
    chain = reloaded.list_by_mullu_receipt_hash("mullu-receipt-hash-1")
    readiness = validate_p3_readiness(store_path, mind_id="root")
    report = build_nested_mind_evidence_report(store_path, mind_id="root")
    persisted_text = store_path.read_text(encoding="utf-8")

    assert [entry.record_type for entry in chain] == [
        "plan",
        "submission_report",
        "commit_witness",
        "bridge_report",
        "reconciliation_report",
    ]
    assert readiness["status"] == "ready"
    assert readiness["commit_witness_id"] == submission.commit_witness.witness_id
    assert report["status"] == "ready"
    assert report["record_counts"]["reconciliation_report"] == 1
    assert "staging-secret-token" not in persisted_text
    assert "raw_response_body" not in persisted_text


def test_fake_staging_harness_rejects_unbound_submit_responses() -> None:
    plan = _plan()
    cases = (
        ({"payload_hash": "wrong-payload-hash"}, "payload_hash_mismatch"),
        ({"mullu_receipt_hash": "wrong-receipt-hash"}, "mullu_receipt_hash_mismatch"),
        (
            {
                "status": "duplicate",
                "metadata": {
                    "idempotency_decision": "already_applied",
                    "idempotency_key": "wrong-idempotency-key",
                },
            },
            "idempotency_key_mismatch",
        ),
    )

    for overrides, expected_failure in cases:
        outcome = _submitter(FakeSubmitConnector(overrides=overrides)).submit_observation_plan_with_witness(
            plan,
            submit_enabled=True,
        )

        assert outcome.report.status is NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE
        assert expected_failure in outcome.report.failures
        assert outcome.commit_witness is None


def test_fake_staging_harness_blocks_without_verified_reconciliation(tmp_path) -> None:
    evidence = _evidence()
    plan = _plan(evidence)
    submission = _submitter(FakeSubmitConnector()).submit_observation_plan_with_witness(
        plan,
        submit_enabled=True,
    )
    assert submission.commit_witness is not None

    store_path = tmp_path / "nested-mind-evidence.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_plan(plan)
    store.record_submission_report(submission.report)
    store.record_commit_witness(submission.commit_witness)

    missing_reconciliation = validate_p3_readiness(store_path, mind_id="root")
    mismatch = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(submission.commit_witness, audit_history_hash="wrong-history"),
    ).reconcile(plan_id=plan.plan_id, witness=submission.commit_witness)

    assert missing_reconciliation["status"] == "blocked"
    assert "verified_reconciliation_missing" in missing_reconciliation["blockers"]
    assert mismatch.status is NestedMindObservationReconciliationStatus.HISTORY_MISMATCH
    assert "audit_history_hash_mismatch" in mismatch.blockers
