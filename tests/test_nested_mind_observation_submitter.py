"""Tests for the guarded nested-mind record_observation submitter.

Purpose: verify default-off submission, proposal validation, response binding,
and commit witness construction for the live nested-mind write boundary.
Governance scope: record_observation only; no child mind, lawbook, or arbitrary
patch routes.
Dependencies: nested_mind_observation_submitter and runtime-only contracts.
Invariants: no network call occurs unless enabled and valid; bearer tokens and
raw response bodies are never persisted.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.adapters import (
    JsonConnectorOutcome,
    NESTED_MIND_OBSERVATION_SUBMIT_CONNECTOR_ID,
    NestedMindObservationSubmitter,
)
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts import (
    NestedMindCommitWitnessStatus,
    NestedMindProposalEvidence,
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationSubmissionStatus,
    build_observation_proposal_payload,
    nested_mind_observation_idempotency_key,
    stable_json_hash,
)


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _payload(*, kind: str = "record_observation", key: str = "observations/obs-1") -> dict:
    return {
        "kind": kind,
        "ops": (
            {
                "op": "set",
                "key": key,
                "value": {"observation_id": "obs-1", "source": "unit-test"},
            },
        ),
        "metadata": {"proposal_evidence_hash": "proposal-evidence-hash-1"},
    }


def _plan(**overrides: object) -> NestedMindObservationProposalPlan:
    payload = overrides.pop("proposal_payload", _payload())
    return NestedMindObservationProposalPlan(
        plan_id=str(overrides.pop("plan_id", "plan-1")),
        proposal_evidence_id=str(overrides.pop("proposal_evidence_id", "evidence-1")),
        mind_id=str(overrides.pop("mind_id", "root")),
        method=str(overrides.pop("method", "POST")),
        target_route=str(overrides.pop("target_route", "/minds/root/proposals")),
        proposal_payload=payload,
        payload_hash=str(overrides.pop("payload_hash", stable_json_hash(payload))),
        mullu_receipt_hash=str(overrides.pop("mullu_receipt_hash", "mullu-receipt-hash-1")),
        authority_receipt_hash=str(overrides.pop("authority_receipt_hash", "authority-receipt-hash-1")),
        status=overrides.pop("status", NestedMindObservationProposalPlanStatus.PLANNED),
        planned_at=str(overrides.pop("planned_at", _clock())),
        blockers=overrides.pop("blockers", ()),
    )


def _connector_result(
    *,
    status: ConnectorStatus = ConnectorStatus.SUCCEEDED,
    error_code: str | None = None,
) -> ConnectorResult:
    return ConnectorResult(
        result_id="connector-result-1",
        connector_id=NESTED_MIND_OBSERVATION_SUBMIT_CONNECTOR_ID,
        status=status,
        response_digest="d" * 64 if status is ConnectorStatus.SUCCEEDED else "none",
        started_at=_clock(),
        finished_at=_clock(),
        error_code=error_code,
    )


def _accepted_response(**overrides: object) -> dict:
    response = {
        "mind_id": "root",
        "status": "accepted",
        "commit_hash": "commit-hash-1",
        "history_hash": "history-hash-1",
        "state_hash": "state-hash-1",
        "sequence": 7,
        "committed_at": _clock(),
        "proposal_evidence_hash": "proposal-evidence-hash-1",
        "payload_hash": _plan().payload_hash,
        "mullu_receipt_hash": "mullu-receipt-hash-1",
        "authority_receipt_hash": "authority-receipt-hash-1",
        "failures": (),
    }
    response.update(overrides)
    return response


def _proposal_evidence() -> NestedMindProposalEvidence:
    return NestedMindProposalEvidence(
        evidence_id="evidence-1",
        mind_id="root",
        evidence_hash="proposal-evidence-hash-1",
        mullu_receipt_hash="mullu-receipt-hash-1",
        authority_receipt_hash="authority-receipt-hash-1",
    )


class FakeJsonConnector:
    def __init__(
        self,
        *,
        connector_result: ConnectorResult | None = None,
        payload: dict | None = None,
    ) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []
        self.connector_result = connector_result or _connector_result()
        self.payload = payload or _accepted_response()

    def invoke_json(self, connector: object, request: dict[str, object]) -> JsonConnectorOutcome:
        self.calls.append((connector, request))
        return JsonConnectorOutcome(
            connector_result=self.connector_result,
            json_payload=self.payload,
        )


def _submitter(fake: FakeJsonConnector) -> NestedMindObservationSubmitter:
    return NestedMindObservationSubmitter(
        clock=_clock,
        base_url="https://nested.example",
        bearer_token="secret-token",
        http_json_connector=fake,
    )


def test_submitter_constructor_rejects_unsafe_base_urls() -> None:
    for base_url in (
        "http://nested.example",
        "https://nested.example?debug=true",
        "https://nested.example#fragment",
        "https://user:pass@nested.example",
    ):
        with pytest.raises(ValueError, match="base_url"):
            NestedMindObservationSubmitter(
                clock=_clock,
                base_url=base_url,
                http_json_connector=FakeJsonConnector(),
            )


def test_submitter_constructor_accepts_https_path_base_url() -> None:
    submitter = NestedMindObservationSubmitter(
        clock=_clock,
        base_url="https://nested.example/api/",
        http_json_connector=FakeJsonConnector(),
    )

    assert submitter.base_url == "https://nested.example/api"


def test_disabled_submit_flag_returns_disabled_without_transport_call() -> None:
    fake = FakeJsonConnector()
    report = _submitter(fake).submit_observation_plan(_plan(), submit_enabled=False)

    assert report.status is NestedMindObservationSubmissionStatus.DISABLED
    assert report.connector_result_id is None
    assert report.commit_witness_id is None
    assert report.blockers == ("nested_mind_observation_submit_disabled",)
    assert fake.calls == []


def test_plan_status_disabled_blocks_submission() -> None:
    fake = FakeJsonConnector()
    report = _submitter(fake).submit_observation_plan(
        _plan(status=NestedMindObservationProposalPlanStatus.DISABLED),
        submit_enabled=True,
    )

    assert report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert "plan_status_not_planned" in report.blockers
    assert fake.calls == []


def test_invalid_target_route_and_method_block_submission() -> None:
    fake = FakeJsonConnector()
    report = _submitter(fake).submit_observation_plan(
        _plan(method="GET", target_route="/minds/root/children"),
        submit_enabled=True,
    )

    assert report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert "method_not_post" in report.blockers
    assert "target_route_mismatch" in report.blockers
    assert fake.calls == []


def test_payload_hash_mismatch_blocks_submission() -> None:
    fake = FakeJsonConnector()
    report = _submitter(fake).submit_observation_plan(
        _plan(payload_hash="wrong-hash"),
        submit_enabled=True,
    )

    assert report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert "payload_hash_mismatch" in report.blockers
    assert fake.calls == []


def test_observation_key_must_be_strict_path_segment() -> None:
    for key in (
        "observations/../x",
        "observations/x/y",
        "observations/x\\y",
        "observations/x?y",
        "observations/x#y",
        "observations/%2e%2e",
    ):
        payload = _payload(key=key)
        fake = FakeJsonConnector()
        report = _submitter(fake).submit_observation_plan(
            _plan(proposal_payload=payload, payload_hash=stable_json_hash(payload)),
            submit_enabled=True,
        )

        assert report.status is NestedMindObservationSubmissionStatus.BLOCKED
        assert "op_key_must_not_shape_route" in report.blockers
        assert fake.calls == []


def test_arbitrary_op_list_blocks_submission() -> None:
    payload = _payload()
    payload["ops"] = (
        payload["ops"][0],
        {"op": "set", "key": "observations/obs-2", "value": {"observation_id": "obs-2"}},
    )
    fake = FakeJsonConnector()
    report = _submitter(fake).submit_observation_plan(
        _plan(proposal_payload=payload, payload_hash=stable_json_hash(payload)),
        submit_enabled=True,
    )

    assert report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert "ops_must_contain_exactly_one_operation" in report.blockers
    assert fake.calls == []


def test_lawbook_and_child_mind_attempts_block_submission() -> None:
    fake = FakeJsonConnector()
    lawbook_report = _submitter(fake).submit_observation_plan(
        _plan(
            target_route="/minds/root/lawbook",
            proposal_payload=_payload(key="lawbook/rules"),
            payload_hash=stable_json_hash(_payload(key="lawbook/rules")),
        ),
        submit_enabled=True,
    )
    child_report = _submitter(fake).submit_observation_plan(
        _plan(target_route="/minds/root/children"),
        submit_enabled=True,
    )

    assert lawbook_report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert "target_route_mismatch" in lawbook_report.blockers
    assert "op_key_must_target_observations" in lawbook_report.blockers
    assert child_report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert fake.calls == []


def test_nested_observation_path_blocks_submission() -> None:
    payload = _payload(key="observations/obs-1/child")
    fake = FakeJsonConnector()
    report = _submitter(fake).submit_observation_plan(
        _plan(proposal_payload=payload, payload_hash=stable_json_hash(payload)),
        submit_enabled=True,
    )

    assert report.status is NestedMindObservationSubmissionStatus.BLOCKED
    assert "op_key_must_not_shape_route" in report.blockers
    assert fake.calls == []


def test_successful_accepted_response_builds_verified_commit_witness() -> None:
    plan = _plan()
    fake = FakeJsonConnector(payload=_accepted_response(payload_hash=plan.payload_hash))
    outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

    descriptor, request = fake.calls[0]
    report = outcome.report
    witness = outcome.commit_witness
    report_text = str(report.to_json_dict())

    assert descriptor.connector_id == NESTED_MIND_OBSERVATION_SUBMIT_CONNECTOR_ID
    assert request["url"] == "https://nested.example/minds/root/proposals"
    assert request["method"] == "POST"
    assert request["json_body"] == plan.proposal_payload
    assert report.status is NestedMindObservationSubmissionStatus.ACCEPTED
    assert report.connector_result_id == "connector-result-1"
    assert witness is not None
    assert witness.status is NestedMindCommitWitnessStatus.VERIFIED
    assert witness.nested_mind_commit_hash == "commit-hash-1"
    assert "secret-token" not in report_text


def test_response_payload_hash_mismatch_becomes_unverified_response() -> None:
    fake = FakeJsonConnector(payload=_accepted_response(payload_hash="wrong"))
    outcome = _submitter(fake).submit_observation_plan_with_witness(_plan(), submit_enabled=True)

    assert outcome.report.status is NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE
    assert "payload_hash_mismatch" in outcome.report.failures
    assert outcome.commit_witness is None


def test_response_mullu_receipt_hash_mismatch_becomes_unverified_response() -> None:
    plan = _plan()
    fake = FakeJsonConnector(
        payload=_accepted_response(
            payload_hash=plan.payload_hash,
            mullu_receipt_hash="wrong-mullu-receipt",
        )
    )
    outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

    assert outcome.report.status is NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE
    assert "mullu_receipt_hash_mismatch" in outcome.report.failures
    assert outcome.commit_witness is None


def test_rejected_nested_mind_response_records_failures_without_witness() -> None:
    plan = _plan()
    fake = FakeJsonConnector(
        payload={
            **_accepted_response(payload_hash=plan.payload_hash),
            "status": "rejected",
            "commit_hash": None,
            "history_hash": None,
            "state_hash": None,
            "sequence": None,
            "committed_at": None,
            "failures": ("policy_rejected",),
        }
    )
    outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

    assert outcome.report.status is NestedMindObservationSubmissionStatus.REJECTED
    assert outcome.report.failures == ("policy_rejected",)
    assert outcome.commit_witness is None


def test_non_2xx_connector_result_records_failed_without_witness() -> None:
    fake = FakeJsonConnector(
        connector_result=_connector_result(status=ConnectorStatus.FAILED, error_code="http_500"),
        payload={},
    )
    outcome = _submitter(fake).submit_observation_plan_with_witness(_plan(), submit_enabled=True)

    assert outcome.report.status is NestedMindObservationSubmissionStatus.FAILED
    assert outcome.report.failures == ("http_500",)
    assert outcome.commit_witness is None


def test_bearer_token_appears_only_in_authorization_header_not_report() -> None:
    plan = _plan()
    fake = FakeJsonConnector(payload=_accepted_response(payload_hash=plan.payload_hash))
    outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

    assert fake.calls[0][1]["headers"] == {"Authorization": "Bearer secret-token"}
    assert "secret-token" not in str(outcome.report.to_json_dict())
    assert "secret-token" not in str(outcome.commit_witness.to_json_dict())


def test_response_boolean_sequence_is_unverified() -> None:
    plan = _plan()
    for sequence in (True, False):
        fake = FakeJsonConnector(payload=_accepted_response(payload_hash=plan.payload_hash, sequence=sequence))
        outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

        assert outcome.report.status is NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE
        assert outcome.commit_witness is None
        assert any("sequence must be a non-negative integer" in failure for failure in outcome.report.failures)


def test_response_numeric_sequence_is_accepted() -> None:
    plan = _plan()
    for sequence in (0, 1):
        fake = FakeJsonConnector(payload=_accepted_response(payload_hash=plan.payload_hash, sequence=sequence))
        outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

        assert outcome.report.status is NestedMindObservationSubmissionStatus.ACCEPTED
        assert outcome.commit_witness is not None
        assert outcome.commit_witness.metadata["sequence"] == sequence


def test_same_observation_creates_same_idempotency_key() -> None:
    evidence = _proposal_evidence()
    payload_a = build_observation_proposal_payload(
        evidence,
        observation_id="obs-1",
        observation_hash="observation-hash-1",
        observation_value={"observation_id": "obs-1"},
    )
    payload_b = build_observation_proposal_payload(
        evidence,
        observation_id="obs-1",
        observation_hash="observation-hash-1",
        observation_value={"observation_id": "obs-1"},
    )

    expected = nested_mind_observation_idempotency_key(
        evidence,
        observation_hash="observation-hash-1",
    )
    assert payload_a["metadata"]["idempotency_key"] == expected
    assert payload_b["metadata"]["idempotency_key"] == expected
    assert stable_json_hash(payload_a) == stable_json_hash(payload_b)


def test_observation_payload_builder_rejects_unsafe_observation_ids() -> None:
    evidence = _proposal_evidence()

    payload = build_observation_proposal_payload(
        evidence,
        observation_id="obs-1",
        observation_hash="observation-hash-1",
        observation_value={"observation_id": "obs-1"},
    )
    assert payload["ops"][0]["key"] == "observations/obs-1"

    for observation_id in ("../x", "x/y", "x\\y", "x?y", "x#y", "%2e%2e", "obs-1/child"):
        with pytest.raises(ValueError, match="observation_id"):
            build_observation_proposal_payload(
                evidence,
                observation_id=observation_id,
                observation_hash="observation-hash-1",
                observation_value={"observation_id": observation_id},
            )


def test_duplicate_response_verifies_when_hashes_and_idempotency_match() -> None:
    evidence = _proposal_evidence()
    payload = build_observation_proposal_payload(
        evidence,
        observation_id="obs-1",
        observation_hash="observation-hash-1",
        observation_value={"observation_id": "obs-1"},
    )
    plan = _plan(proposal_payload=payload, payload_hash=stable_json_hash(payload))
    idempotency_key = payload["metadata"]["idempotency_key"]
    fake = FakeJsonConnector(
        payload={
            **_accepted_response(payload_hash=plan.payload_hash),
            "status": "duplicate",
            "metadata": {
                "idempotency_decision": "already_applied",
                "idempotency_key": idempotency_key,
            },
        }
    )

    outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

    assert outcome.report.status is NestedMindObservationSubmissionStatus.ACCEPTED
    assert outcome.commit_witness is not None
    assert outcome.commit_witness.metadata["idempotency_decision"] == "already_applied"


def test_duplicate_with_mismatched_payload_hash_blocks() -> None:
    evidence = _proposal_evidence()
    payload = build_observation_proposal_payload(
        evidence,
        observation_id="obs-1",
        observation_hash="observation-hash-1",
        observation_value={"observation_id": "obs-1"},
    )
    plan = _plan(proposal_payload=payload, payload_hash=stable_json_hash(payload))
    fake = FakeJsonConnector(
        payload={
            **_accepted_response(payload_hash="wrong-payload-hash"),
            "status": "duplicate",
            "metadata": {
                "idempotency_decision": "already_applied",
                "idempotency_key": payload["metadata"]["idempotency_key"],
            },
        }
    )

    outcome = _submitter(fake).submit_observation_plan_with_witness(plan, submit_enabled=True)

    assert outcome.report.status is NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE
    assert "payload_hash_mismatch" in outcome.report.failures
    assert outcome.commit_witness is None
