"""Purpose: default-off nested-mind record_observation proposal submitter.
Governance scope: explicit operator-flagged record_observation writes only.
Dependencies: governed HTTP JSON connector, nested-mind contracts, receipts.
Invariants:
  - No network call occurs unless the caller passes submit_enabled=True.
  - Only /minds/{mind_id}/proposals POST is reachable.
  - Only record_observation payloads with exactly one set op are accepted.
  - Bearer tokens and raw response bodies are never persisted in reports.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from mcoi_runtime.adapters.http_connector import HttpConnector, HttpConnectorConfig
from mcoi_runtime.adapters.nested_mind import validate_mind_id
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorStatus
from mcoi_runtime.contracts.nested_mind_observation_submission import (
    NestedMindCommitResponseEnvelope,
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
    nested_mind_commit_response_hash,
    stable_json_hash,
)
from mcoi_runtime.contracts.nested_mind_receipts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    build_commit_witness,
)
from mcoi_runtime.contracts.provider_policy import HttpProviderPolicy
from mcoi_runtime.core.invariants import stable_identifier

NESTED_MIND_OBSERVATION_SUBMIT_CONNECTOR_ID = "nested-mind-observation-submit"
NESTED_MIND_OBSERVATION_SUBMIT_CREDENTIAL_SCOPE_ID = "nested-mind:write:record-observation"
NESTED_MIND_PROVIDER = "nested-mind"
_AUTHORIZATION_HEADER = "Authorization"


@dataclass(frozen=True, slots=True)
class NestedMindObservationSubmissionOutcome:
    """Return surface for submitter callers that need the typed witness."""

    report: NestedMindObservationSubmissionReport
    commit_witness: NestedMindCommitWitness | None
    response_envelope: NestedMindCommitResponseEnvelope | None


class NestedMindObservationSubmitter:
    """Governed live submitter for record_observation proposal plans."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        base_url: str,
        bearer_token: str | None = None,
        http_json_connector: object | None = None,
    ) -> None:
        normalized_base_url = str(base_url or "").strip().rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url must be a non-empty string")
        token = str(bearer_token or "").strip()
        self._clock = clock
        self._base_url = normalized_base_url
        self._bearer_token = token or None
        self._descriptor = ConnectorDescriptor(
            connector_id=NESTED_MIND_OBSERVATION_SUBMIT_CONNECTOR_ID,
            name="Nested Mind record_observation submitter",
            provider=NESTED_MIND_PROVIDER,
            effect_class=EffectClass.EXTERNAL_WRITE,
            trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id=NESTED_MIND_OBSERVATION_SUBMIT_CREDENTIAL_SCOPE_ID,
            enabled=True,
            metadata={
                "route_surface": ("record_observation_proposal",),
                "mutation_routes_enabled": True,
                "allowed_proposal_kind": "record_observation",
                "child_mind_creation_enabled": False,
                "lawbook_migration_enabled": False,
                "arbitrary_patch_ops_enabled": False,
            },
        )
        self._http_json_connector = http_json_connector or HttpConnector(
            clock=clock,
            config=HttpConnectorConfig(
                allowed_methods=("POST",),
                allowed_content_types=("application/json",),
                allowed_headers=(_AUTHORIZATION_HEADER,),
                max_response_bytes=65_536,
                max_request_body_bytes=65_536,
            ),
            policy=HttpProviderPolicy(
                policy_id="nested-mind-observation-submit-http-policy",
                allowed_methods=("POST",),
                allowed_content_types=("application/json",),
                max_response_bytes=65_536,
                header_allowlist=(_AUTHORIZATION_HEADER,),
                require_https=True,
            ),
        )

    @property
    def descriptor(self) -> ConnectorDescriptor:
        return self._descriptor

    @property
    def base_url(self) -> str:
        return self._base_url

    def submit_observation_plan(
        self,
        plan: NestedMindObservationProposalPlan,
        *,
        submit_enabled: bool,
    ) -> NestedMindObservationSubmissionReport:
        """Submit a validated record_observation plan or return fail-closed report."""

        return self.submit_observation_plan_with_witness(
            plan,
            submit_enabled=submit_enabled,
        ).report

    def submit_observation_plan_with_witness(
        self,
        plan: NestedMindObservationProposalPlan,
        *,
        submit_enabled: bool,
    ) -> NestedMindObservationSubmissionOutcome:
        now = self._clock()
        if not submit_enabled:
            return self._outcome(
                self._report(
                    plan=plan,
                    status=NestedMindObservationSubmissionStatus.DISABLED,
                    submitted_at=now,
                    blockers=("nested_mind_observation_submit_disabled",),
                )
            )

        blockers = self._validate_plan(plan)
        if blockers:
            return self._outcome(
                self._report(
                    plan=plan,
                    status=NestedMindObservationSubmissionStatus.BLOCKED,
                    submitted_at=now,
                    blockers=tuple(blockers),
                )
            )

        connector_outcome = self._http_json_connector.invoke_json(
            self._descriptor,
            {
                "url": self._url(plan),
                "method": "POST",
                "headers": self._headers(),
                "json_body": plan.proposal_payload,
            },
        )
        connector_result = connector_outcome.connector_result
        if connector_result.status is not ConnectorStatus.SUCCEEDED:
            return self._outcome(
                self._report(
                    plan=plan,
                    status=NestedMindObservationSubmissionStatus.FAILED,
                    submitted_at=now,
                    connector_result_id=connector_result.result_id,
                    connector_response_digest=connector_result.response_digest,
                    failures=(connector_result.error_code or "connector_failed",),
                )
            )

        try:
            envelope = self._response_envelope(connector_outcome.json_payload)
        except ValueError as exc:
            return self._outcome(
                self._report(
                    plan=plan,
                    status=NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE,
                    submitted_at=now,
                    connector_result_id=connector_result.result_id,
                    connector_response_digest=connector_result.response_digest,
                    failures=(str(exc),),
                )
            )

        envelope_hash = nested_mind_commit_response_hash(envelope)
        verification_failures = self._verify_response(plan, envelope)
        if verification_failures:
            return self._outcome(
                self._report(
                    plan=plan,
                    status=NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE,
                    submitted_at=now,
                    connector_result_id=connector_result.result_id,
                    connector_response_digest=connector_result.response_digest,
                    response_envelope_hash=envelope_hash,
                    failures=tuple(verification_failures),
                ),
                response_envelope=envelope,
            )

        if envelope.status == "rejected":
            return self._outcome(
                self._report(
                    plan=plan,
                    status=NestedMindObservationSubmissionStatus.REJECTED,
                    submitted_at=now,
                    connector_result_id=connector_result.result_id,
                    connector_response_digest=connector_result.response_digest,
                    response_envelope_hash=envelope_hash,
                    failures=tuple(envelope.failures),
                ),
                response_envelope=envelope,
            )

        idempotency_metadata: dict[str, Any] = {}
        if envelope.status == "duplicate":
            idempotency_failures = self._verify_duplicate_response(plan, envelope)
            if idempotency_failures:
                return self._outcome(
                    self._report(
                        plan=plan,
                        status=NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE,
                        submitted_at=now,
                        connector_result_id=connector_result.result_id,
                        connector_response_digest=connector_result.response_digest,
                        response_envelope_hash=envelope_hash,
                        failures=tuple(idempotency_failures),
                    ),
                    response_envelope=envelope,
                )
            idempotency_metadata["idempotency_decision"] = "already_applied"

        witness = build_commit_witness(
            plan,
            witness_id=stable_identifier(
                "nested-mind-commit-witness",
                {
                    "plan_id": plan.plan_id,
                    "commit_hash": envelope.commit_hash,
                    "history_hash": envelope.history_hash,
                },
            ),
            nested_mind_commit_hash=envelope.commit_hash or "",
            nested_mind_history_hash=envelope.history_hash or "",
            witnessed_at=envelope.committed_at or now,
            status=NestedMindCommitWitnessStatus.VERIFIED,
            metadata={
                "state_hash": envelope.state_hash,
                "sequence": envelope.sequence,
                "connector_result_id": connector_result.result_id,
                "connector_response_digest": connector_result.response_digest,
                "payload_hash": plan.payload_hash,
                **idempotency_metadata,
            },
        )
        return self._outcome(
            self._report(
                plan=plan,
                status=NestedMindObservationSubmissionStatus.ACCEPTED,
                submitted_at=now,
                connector_result_id=connector_result.result_id,
                connector_response_digest=connector_result.response_digest,
                response_envelope_hash=envelope_hash,
                commit_witness_id=witness.witness_id,
            ),
            commit_witness=witness,
            response_envelope=envelope,
        )

    def _validate_plan(self, plan: NestedMindObservationProposalPlan) -> list[str]:
        blockers: list[str] = []
        if not isinstance(plan, NestedMindObservationProposalPlan):
            return ["plan_must_be_nested_mind_observation_proposal_plan"]
        try:
            safe_mind_id = validate_mind_id(plan.mind_id)
        except ValueError:
            blockers.append("mind_id_not_path_segment_safe")
            safe_mind_id = plan.mind_id
        if plan.status is not NestedMindObservationProposalPlanStatus.PLANNED:
            blockers.append("plan_status_not_planned")
        if plan.blockers:
            blockers.append("plan_has_blockers")
        if plan.method.upper() != "POST":
            blockers.append("method_not_post")
        if plan.target_route != f"/minds/{safe_mind_id}/proposals":
            blockers.append("target_route_mismatch")
        if stable_json_hash(plan.proposal_payload) != plan.payload_hash:
            blockers.append("payload_hash_mismatch")
        payload = plan.proposal_payload
        if payload.get("kind") != "record_observation":
            blockers.append("proposal_kind_not_record_observation")
        ops = payload.get("ops")
        if not isinstance(ops, tuple | list) or len(ops) != 1:
            blockers.append("ops_must_contain_exactly_one_operation")
            return blockers
        op = ops[0]
        if not isinstance(op, Mapping):
            blockers.append("op_must_be_object")
            return blockers
        if op.get("op") != "set":
            blockers.append("op_must_be_set")
        key = op.get("key")
        if not isinstance(key, str) or not key.startswith("observations/"):
            blockers.append("op_key_must_target_observations")
        elif "../" in key or key.startswith("/") or "?" in key or "#" in key:
            blockers.append("op_key_must_not_shape_route")
        if not isinstance(op.get("value"), Mapping):
            blockers.append("op_value_must_be_object")
        return blockers

    def _verify_response(
        self,
        plan: NestedMindObservationProposalPlan,
        envelope: NestedMindCommitResponseEnvelope,
    ) -> list[str]:
        failures: list[str] = []
        metadata = plan.proposal_payload.get("metadata")
        proposal_evidence_hash = (
            metadata.get("proposal_evidence_hash") if isinstance(metadata, Mapping) else None
        )
        expected = {
            "mind_id": plan.mind_id,
            "proposal_evidence_hash": proposal_evidence_hash,
            "payload_hash": plan.payload_hash,
            "mullu_receipt_hash": plan.mullu_receipt_hash,
            "authority_receipt_hash": plan.authority_receipt_hash,
        }
        actual = {
            "mind_id": envelope.mind_id,
            "proposal_evidence_hash": envelope.proposal_evidence_hash,
            "payload_hash": envelope.payload_hash,
            "mullu_receipt_hash": envelope.mullu_receipt_hash,
            "authority_receipt_hash": envelope.authority_receipt_hash,
        }
        for field_name, expected_value in expected.items():
            if expected_value != actual[field_name]:
                failures.append(f"{field_name}_mismatch")
        return failures

    def _verify_duplicate_response(
        self,
        plan: NestedMindObservationProposalPlan,
        envelope: NestedMindCommitResponseEnvelope,
    ) -> list[str]:
        failures: list[str] = []
        metadata = plan.proposal_payload.get("metadata")
        expected_key = metadata.get("idempotency_key") if isinstance(metadata, Mapping) else None
        response_decision = envelope.metadata.get("idempotency_decision")
        response_key = envelope.metadata.get("idempotency_key")
        if response_decision != "already_applied":
            failures.append("idempotency_decision_mismatch")
        if not expected_key or response_key != expected_key:
            failures.append("idempotency_key_mismatch")
        return failures

    def _response_envelope(self, payload: Mapping[str, Any]) -> NestedMindCommitResponseEnvelope:
        return NestedMindCommitResponseEnvelope(
            mind_id=str(payload.get("mind_id", "")),
            status=str(payload.get("status", "")),
            commit_hash=_optional_text(payload.get("commit_hash")),
            history_hash=_optional_text(payload.get("history_hash")),
            state_hash=_optional_text(payload.get("state_hash")),
            sequence=payload.get("sequence") if isinstance(payload.get("sequence"), int) else None,
            committed_at=_optional_text(payload.get("committed_at")),
            proposal_evidence_hash=str(payload.get("proposal_evidence_hash", "")),
            payload_hash=str(payload.get("payload_hash", "")),
            mullu_receipt_hash=str(payload.get("mullu_receipt_hash", "")),
            authority_receipt_hash=str(payload.get("authority_receipt_hash", "")),
            failures=tuple(str(item) for item in payload.get("failures", ()) or ()),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {},
        )

    def _report(
        self,
        *,
        plan: NestedMindObservationProposalPlan,
        status: NestedMindObservationSubmissionStatus,
        submitted_at: str,
        connector_result_id: str | None = None,
        connector_response_digest: str | None = None,
        response_envelope_hash: str | None = None,
        commit_witness_id: str | None = None,
        blockers: tuple[str, ...] = (),
        failures: tuple[str, ...] = (),
    ) -> NestedMindObservationSubmissionReport:
        return NestedMindObservationSubmissionReport(
            report_id=stable_identifier(
                "nested-mind-observation-submission",
                {
                    "plan_id": plan.plan_id,
                    "status": status.value,
                    "submitted_at": submitted_at,
                    "connector_result_id": connector_result_id,
                    "commit_witness_id": commit_witness_id,
                },
            ),
            plan_id=plan.plan_id,
            mind_id=plan.mind_id,
            proposal_evidence_id=plan.proposal_evidence_id,
            payload_hash=plan.payload_hash,
            connector_result_id=connector_result_id,
            connector_response_digest=connector_response_digest,
            response_envelope_hash=response_envelope_hash,
            commit_witness_id=commit_witness_id,
            status=status,
            submitted_at=submitted_at,
            blockers=blockers,
            failures=failures,
        )

    def _outcome(
        self,
        report: NestedMindObservationSubmissionReport,
        *,
        commit_witness: NestedMindCommitWitness | None = None,
        response_envelope: NestedMindCommitResponseEnvelope | None = None,
    ) -> NestedMindObservationSubmissionOutcome:
        return NestedMindObservationSubmissionOutcome(
            report=report,
            commit_witness=commit_witness,
            response_envelope=response_envelope,
        )

    def _url(self, plan: NestedMindObservationProposalPlan) -> str:
        return f"{self._base_url}/{plan.target_route.lstrip('/')}"

    def _headers(self) -> Mapping[str, str]:
        if self._bearer_token is None:
            return {}
        return {_AUTHORIZATION_HEADER: f"Bearer {self._bearer_token}"}


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
