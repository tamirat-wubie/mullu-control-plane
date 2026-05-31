"""Purpose: runtime-only nested-mind observation proposal and submission contracts.
Governance scope: record_observation planning/submission only; no public schema.
Dependencies: shared contract helpers and deterministic JSON hashing.
Invariants:
  - Only record_observation proposal payloads are represented.
  - Proposal payload hashes are deterministic and exclude raw credentials.
  - Submission reports persist only typed bounded fields and response digests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    thaw_value_json,
)


class NestedMindObservationProposalPlanStatus(StrEnum):
    DISABLED = "disabled"
    BLOCKED = "blocked"
    PLANNED = "planned"


class NestedMindObservationSubmissionStatus(StrEnum):
    DISABLED = "disabled"
    BLOCKED = "blocked"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    UNVERIFIED_RESPONSE = "unverified_response"


_OBSERVATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_observation_id(observation_id: str) -> str:
    """Return a path-segment-safe nested-mind observation identifier."""

    if not isinstance(observation_id, str):
        raise ValueError("observation_id must be a path-segment-safe identifier")
    value = observation_id.strip()
    if not _OBSERVATION_ID_RE.fullmatch(value):
        raise ValueError("observation_id must be a path-segment-safe identifier")
    return value


def stable_json_hash(payload: Mapping[str, Any]) -> str:
    """Hash a mapping using the canonical bounded JSON surface."""

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    try:
        encoded = json.dumps(
            thaw_value_json(payload),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be deterministic JSON") from exc
    return sha256(encoded.encode("utf-8")).hexdigest()


def nested_mind_observation_idempotency_key(
    evidence: NestedMindProposalEvidence,
    *,
    observation_hash: str,
) -> str:
    """Derive the deterministic idempotency key for one observation proposal."""

    return stable_json_hash(
        {
            "mind_id": evidence.mind_id,
            "proposal_evidence_hash": evidence.evidence_hash,
            "observation_hash": require_non_empty_text(observation_hash, "observation_hash"),
        }
    )


def build_observation_proposal_payload(
    evidence: NestedMindProposalEvidence,
    *,
    observation_id: str,
    observation_hash: str,
    observation_value: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Build the only proposal payload shape allowed for live observation writes."""

    safe_observation_id = validate_observation_id(observation_id)
    idempotency_key = nested_mind_observation_idempotency_key(
        evidence,
        observation_hash=observation_hash,
    )
    return {
        "kind": "record_observation",
        "ops": (
            {
                "op": "set",
                "key": f"observations/{safe_observation_id}",
                "value": dict(observation_value),
            },
        ),
        "metadata": {
            "proposal_evidence_hash": evidence.evidence_hash,
            "observation_id": safe_observation_id,
            "observation_hash": observation_hash,
            "idempotency_key": idempotency_key,
        },
    }


def _freeze_text_sequence(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be an array")
    frozen = tuple(values)
    for index, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{index}]")
    return frozen


@dataclass(frozen=True, slots=True)
class NestedMindProposalEvidence(ContractRecord):
    evidence_id: str
    mind_id: str
    evidence_hash: str
    mullu_receipt_hash: str
    authority_receipt_hash: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_id",
            "mind_id",
            "evidence_hash",
            "mullu_receipt_hash",
            "authority_receipt_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class NestedMindObservationProposalPlan(ContractRecord):
    plan_id: str
    proposal_evidence_id: str
    mind_id: str
    method: str
    target_route: str
    proposal_payload: Mapping[str, Any]
    payload_hash: str
    mullu_receipt_hash: str
    authority_receipt_hash: str
    status: NestedMindObservationProposalPlanStatus
    planned_at: str
    blockers: Sequence[str] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "plan_id",
            "proposal_evidence_id",
            "mind_id",
            "method",
            "target_route",
            "payload_hash",
            "mullu_receipt_hash",
            "authority_receipt_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.status, NestedMindObservationProposalPlanStatus):
            raise ValueError("status must be a NestedMindObservationProposalPlanStatus value")
        object.__setattr__(self, "planned_at", require_datetime_text(self.planned_at, "planned_at"))
        object.__setattr__(self, "proposal_payload", freeze_value(self.proposal_payload))
        object.__setattr__(self, "blockers", _freeze_text_sequence(self.blockers, "blockers"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class NestedMindCommitResponseEnvelope(ContractRecord):
    mind_id: str
    status: str
    commit_hash: str | None
    history_hash: str | None
    state_hash: str | None
    sequence: int | None
    committed_at: str | None
    proposal_evidence_hash: str
    payload_hash: str
    mullu_receipt_hash: str
    authority_receipt_hash: str
    failures: Sequence[str] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "mind_id",
            "status",
            "proposal_evidence_hash",
            "payload_hash",
            "mullu_receipt_hash",
            "authority_receipt_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if self.status not in {"accepted", "duplicate", "rejected"}:
            raise ValueError("status must be accepted, duplicate, or rejected")
        if self.status in {"accepted", "duplicate"}:
            for field_name in ("commit_hash", "history_hash", "state_hash", "committed_at"):
                require_non_empty_text(getattr(self, field_name), field_name)
            if self.sequence is None or self.sequence < 0:
                raise ValueError("sequence must be a non-negative integer for accepted responses")
            if self.failures:
                raise ValueError("accepted or duplicate responses must not include failures")
        if self.status == "rejected" and not self.failures:
            raise ValueError("rejected responses require failures")
        if self.committed_at is not None:
            object.__setattr__(self, "committed_at", require_datetime_text(self.committed_at, "committed_at"))
        object.__setattr__(self, "failures", _freeze_text_sequence(self.failures, "failures"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class NestedMindObservationSubmissionReport(ContractRecord):
    report_id: str
    plan_id: str
    mind_id: str
    proposal_evidence_id: str
    payload_hash: str
    connector_result_id: str | None
    connector_response_digest: str | None
    response_envelope_hash: str | None
    commit_witness_id: str | None
    status: NestedMindObservationSubmissionStatus
    submitted_at: str
    blockers: Sequence[str] = ()
    failures: Sequence[str] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("report_id", "plan_id", "mind_id", "proposal_evidence_id", "payload_hash"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.status, NestedMindObservationSubmissionStatus):
            raise ValueError("status must be a NestedMindObservationSubmissionStatus value")
        if self.status in {
            NestedMindObservationSubmissionStatus.DISABLED,
            NestedMindObservationSubmissionStatus.BLOCKED,
        }:
            if self.connector_result_id is not None or self.commit_witness_id is not None:
                raise ValueError("disabled or blocked reports cannot include connector or witness ids")
            if not self.blockers:
                raise ValueError("disabled or blocked reports require blockers")
        if self.status in {
            NestedMindObservationSubmissionStatus.SUBMITTED,
            NestedMindObservationSubmissionStatus.ACCEPTED,
        }:
            require_non_empty_text(self.connector_result_id or "", "connector_result_id")
            require_non_empty_text(self.connector_response_digest or "", "connector_response_digest")
        if self.status is NestedMindObservationSubmissionStatus.ACCEPTED:
            require_non_empty_text(self.commit_witness_id or "", "commit_witness_id")
        if self.status in {
            NestedMindObservationSubmissionStatus.REJECTED,
            NestedMindObservationSubmissionStatus.FAILED,
            NestedMindObservationSubmissionStatus.UNVERIFIED_RESPONSE,
        } and not self.failures:
            raise ValueError("rejected, failed, and unverified reports require failures")
        object.__setattr__(self, "submitted_at", require_datetime_text(self.submitted_at, "submitted_at"))
        object.__setattr__(self, "blockers", _freeze_text_sequence(self.blockers, "blockers"))
        object.__setattr__(self, "failures", _freeze_text_sequence(self.failures, "failures"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


def nested_mind_commit_response_hash(envelope: NestedMindCommitResponseEnvelope) -> str:
    return stable_json_hash(envelope.to_json_dict())


def nested_mind_observation_submission_report_hash(
    report: NestedMindObservationSubmissionReport,
) -> str:
    return stable_json_hash(report.to_json_dict())
