"""Nested-mind receipt bridge contracts.

Purpose: bind Mullu transition receipts to future nested-mind proposal evidence
and commit witnesses without adding a proposal route.
Governance scope: evidence typing, commit witnessing, and live observation
bridge closure reports.
Invariants:
  - every bridge evidence object carries a Mullu TransitionReceipt hash
  - this phase allows only record_observation evidence
  - evidence requires an authority receipt hash
  - commit witnesses must bind back to the same Mullu receipt hash
  - live observation bridge success is reserved for VERIFIED witnesses only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text
from ._shared_enums import EffectClass
from .proof import TransitionReceipt


class NestedMindProposalKind(StrEnum):
    RECORD_OBSERVATION = "record_observation"


class NestedMindCommitWitnessStatus(StrEnum):
    OBSERVED = "observed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class NestedMindBridgeStatus(StrEnum):
    BRIDGED = "bridged"
    BLOCKED = "blocked"


class NestedMindReceiptBridgeStatus(StrEnum):
    BRIDGED = "bridged"
    BLOCKED = "blocked"


_MIND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_EFFECTS = frozenset({EffectClass.INTERNAL_PURE, EffectClass.EXTERNAL_READ})


def _mind_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not _MIND_ID_RE.fullmatch(normalized):
        raise ValueError("mind_id must be a path-segment-safe identifier")
    return normalized


def _enum(enum_type: type[StrEnum], value: Any, field_name: str) -> StrEnum:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not an allowed value") from exc


def _effect(value: Any) -> EffectClass:
    try:
        effect = EffectClass(str(value))
    except ValueError as exc:
        raise ValueError("effect_class is not an allowed value") from exc
    if effect not in _ALLOWED_EFFECTS:
        raise ValueError("nested-mind bridge allows only pure/read evidence")
    return effect


def _text_tuple(values: Sequence[str] | None, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    return tuple(require_non_empty_text(str(item), field_name) for item in values)


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_json_dict") and hasattr(value, "__dataclass_fields__"):
        return value.to_json_dict()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _hash(value: Any) -> str:
    payload = json.dumps(_json_safe(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _proposal_hash_content(
    *,
    evidence_id: str,
    mind_id: str,
    proposal_kind: NestedMindProposalKind,
    actor_id: str,
    reason: str,
    effect_class: EffectClass,
    mullu_receipt: "NestedMindReceiptRef",
    authority_receipt_hash: str,
    requested_at: str,
    effect_receipt_hashes: Sequence[str],
    metadata: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "evidence_id": evidence_id,
        "mind_id": mind_id,
        "proposal_kind": proposal_kind,
        "actor_id": actor_id,
        "reason": reason,
        "effect_class": effect_class,
        "mullu_receipt": mullu_receipt,
        "authority_receipt_hash": authority_receipt_hash,
        "requested_at": requested_at,
        "effect_receipt_hashes": tuple(effect_receipt_hashes),
        "metadata": dict(metadata),
    }


def _bridge_hash_content(
    *,
    report_id: str,
    proposal_evidence_id: str,
    commit_witness_id: str | None,
    status: NestedMindBridgeStatus | NestedMindReceiptBridgeStatus,
    bridged_at: str,
    blockers: Sequence[str],
    metadata: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "report_id": report_id,
        "proposal_evidence_id": proposal_evidence_id,
        "commit_witness_id": commit_witness_id,
        "status": status,
        "bridged_at": bridged_at,
        "blockers": tuple(blockers),
        "metadata": dict(metadata),
    }


@dataclass(frozen=True, slots=True)
class NestedMindReceiptRef(ContractRecord):
    receipt_id: str
    receipt_hash: str
    machine_id: str
    entity_id: str
    action: str
    verdict: str
    issued_at: str
    signed: bool = False
    signing_key_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "receipt_hash", "machine_id", "entity_id", "action", "verdict"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        if not isinstance(self.signed, bool):
            raise ValueError("signed must be a boolean")
        if not isinstance(self.signing_key_id, str):
            raise ValueError("signing_key_id must be a string")


@dataclass(frozen=True, slots=True)
class NestedMindProposalEvidence(ContractRecord):
    evidence_id: str
    mind_id: str
    proposal_kind: NestedMindProposalKind
    actor_id: str
    reason: str
    effect_class: EffectClass
    mullu_receipt: NestedMindReceiptRef
    authority_receipt_hash: str
    requested_at: str
    evidence_hash: str
    effect_receipt_hashes: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", require_non_empty_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "mind_id", _mind_id(self.mind_id))
        object.__setattr__(self, "proposal_kind", _enum(NestedMindProposalKind, self.proposal_kind, "proposal_kind"))
        object.__setattr__(self, "actor_id", require_non_empty_text(self.actor_id, "actor_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "effect_class", _effect(self.effect_class))
        if not isinstance(self.mullu_receipt, NestedMindReceiptRef):
            raise ValueError("mullu_receipt must be a NestedMindReceiptRef")
        object.__setattr__(self, "authority_receipt_hash", require_non_empty_text(self.authority_receipt_hash, "authority_receipt_hash"))
        object.__setattr__(self, "requested_at", require_datetime_text(self.requested_at, "requested_at"))
        object.__setattr__(self, "effect_receipt_hashes", freeze_value(_text_tuple(self.effect_receipt_hashes, "effect_receipt_hashes")))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        object.__setattr__(self, "evidence_hash", require_non_empty_text(self.evidence_hash, "evidence_hash"))
        if self.evidence_hash != proposal_evidence_hash(self):
            raise ValueError("evidence_hash does not match proposal evidence content")


@dataclass(frozen=True, slots=True)
class NestedMindCommitWitness(ContractRecord):
    witness_id: str
    proposal_evidence_id: str
    mind_id: str
    mullu_receipt_hash: str
    nested_mind_commit_hash: str
    nested_mind_history_hash: str
    witnessed_at: str
    status: NestedMindCommitWitnessStatus
    failures: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("witness_id", "proposal_evidence_id", "mullu_receipt_hash", "nested_mind_commit_hash", "nested_mind_history_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "mind_id", _mind_id(self.mind_id))
        object.__setattr__(self, "witnessed_at", require_datetime_text(self.witnessed_at, "witnessed_at"))
        object.__setattr__(self, "status", _enum(NestedMindCommitWitnessStatus, self.status, "status"))
        failures = _text_tuple(self.failures, "failures")
        if self.status is NestedMindCommitWitnessStatus.REJECTED and not failures:
            raise ValueError("rejected commit witness must include failures")
        if self.status is not NestedMindCommitWitnessStatus.REJECTED and failures:
            raise ValueError("non-rejected commit witness must not include failures")
        object.__setattr__(self, "failures", freeze_value(failures))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class NestedMindReceiptBridgeReport(ContractRecord):
    report_id: str
    proposal_evidence_id: str
    status: NestedMindBridgeStatus | NestedMindReceiptBridgeStatus
    bridged_at: str
    commit_witness_id: str | None = None
    bridge_hash: str = ""
    mind_id: str = ""
    blockers: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("report_id", "proposal_evidence_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.commit_witness_id is not None:
            object.__setattr__(self, "commit_witness_id", require_non_empty_text(self.commit_witness_id, "commit_witness_id"))
        if self.mind_id:
            object.__setattr__(self, "mind_id", _mind_id(self.mind_id))
        if not isinstance(self.status, (NestedMindBridgeStatus, NestedMindReceiptBridgeStatus)):
            raise ValueError("status must be a nested-mind bridge status value")
        object.__setattr__(self, "bridged_at", require_datetime_text(self.bridged_at, "bridged_at"))
        blockers = _text_tuple(self.blockers, "blockers")
        if str(self.status) == "bridged" and blockers:
            raise ValueError("bridged report must not contain blockers")
        if str(self.status) == "blocked" and not blockers:
            raise ValueError("blocked report must include blockers")
        object.__setattr__(self, "blockers", freeze_value(blockers))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        if self.bridge_hash:
            object.__setattr__(self, "bridge_hash", require_non_empty_text(self.bridge_hash, "bridge_hash"))
        if self.bridge_hash and self.bridge_hash != bridge_report_hash(self):
            raise ValueError("bridge_hash does not match bridge report content")


def receipt_ref_from_transition_receipt(receipt: TransitionReceipt) -> NestedMindReceiptRef:
    if not isinstance(receipt, TransitionReceipt):
        raise ValueError("receipt must be a TransitionReceipt")
    return NestedMindReceiptRef(
        receipt_id=receipt.receipt_id,
        receipt_hash=receipt.receipt_hash,
        machine_id=receipt.machine_id,
        entity_id=receipt.entity_id,
        action=receipt.action,
        verdict=str(receipt.verdict.value),
        issued_at=receipt.issued_at,
        signed=bool(receipt.signature),
        signing_key_id=receipt.signing_key_id,
    )


def proposal_evidence_hash(evidence: NestedMindProposalEvidence) -> str:
    return _hash(
        _proposal_hash_content(
            evidence_id=evidence.evidence_id,
            mind_id=evidence.mind_id,
            proposal_kind=evidence.proposal_kind,
            actor_id=evidence.actor_id,
            reason=evidence.reason,
            effect_class=evidence.effect_class,
            mullu_receipt=evidence.mullu_receipt,
            authority_receipt_hash=evidence.authority_receipt_hash,
            requested_at=evidence.requested_at,
            effect_receipt_hashes=evidence.effect_receipt_hashes,
            metadata=evidence.metadata,
        )
    )


def build_proposal_evidence(
    *,
    evidence_id: str,
    mind_id: str,
    transition_receipt: TransitionReceipt,
    actor_id: str,
    reason: str,
    authority_receipt_hash: str,
    requested_at: str,
    effect_class: EffectClass = EffectClass.INTERNAL_PURE,
    effect_receipt_hashes: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> NestedMindProposalEvidence:
    receipt_ref = receipt_ref_from_transition_receipt(transition_receipt)
    clean_mind_id = _mind_id(mind_id)
    clean_effect = _effect(effect_class)
    clean_effect_hashes = _text_tuple(effect_receipt_hashes, "effect_receipt_hashes")
    clean_metadata = dict(metadata or {})
    try:
        clean_authority_receipt_hash = require_non_empty_text(
            authority_receipt_hash,
            "authority_receipt_hash",
        )
    except ValueError as exc:
        raise ValueError("authority_receipt_hash must be a non-empty string") from exc
    payload = _proposal_hash_content(
        evidence_id=evidence_id,
        mind_id=clean_mind_id,
        proposal_kind=NestedMindProposalKind.RECORD_OBSERVATION,
        actor_id=actor_id,
        reason=reason,
        effect_class=clean_effect,
        mullu_receipt=receipt_ref,
        authority_receipt_hash=clean_authority_receipt_hash,
        requested_at=requested_at,
        effect_receipt_hashes=clean_effect_hashes,
        metadata=clean_metadata,
    )
    return NestedMindProposalEvidence(
        evidence_id=evidence_id,
        mind_id=clean_mind_id,
        proposal_kind=NestedMindProposalKind.RECORD_OBSERVATION,
        actor_id=actor_id,
        reason=reason,
        effect_class=clean_effect,
        mullu_receipt=receipt_ref,
        authority_receipt_hash=clean_authority_receipt_hash,
        requested_at=requested_at,
        effect_receipt_hashes=clean_effect_hashes,
        evidence_hash=_hash(payload),
        metadata=clean_metadata,
    )


def build_commit_witness(
    evidence: object,
    *,
    witness_id: str,
    nested_mind_commit_hash: str,
    nested_mind_history_hash: str,
    witnessed_at: str,
    status: NestedMindCommitWitnessStatus = NestedMindCommitWitnessStatus.OBSERVED,
    failures: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> NestedMindCommitWitness:
    proposal_evidence_id = getattr(evidence, "evidence_id", "") or getattr(evidence, "proposal_evidence_id", "")
    mind_id = getattr(evidence, "mind_id", "")
    receipt = getattr(evidence, "mullu_receipt", None)
    mullu_receipt_hash = getattr(receipt, "receipt_hash", "") or getattr(evidence, "mullu_receipt_hash", "")
    return NestedMindCommitWitness(
        witness_id=witness_id,
        proposal_evidence_id=proposal_evidence_id,
        mind_id=mind_id,
        mullu_receipt_hash=mullu_receipt_hash,
        nested_mind_commit_hash=nested_mind_commit_hash,
        nested_mind_history_hash=nested_mind_history_hash,
        witnessed_at=witnessed_at,
        status=status,
        failures=failures,
        metadata=metadata or {},
    )


def bridge_report_hash(report: NestedMindReceiptBridgeReport) -> str:
    return _hash(
        _bridge_hash_content(
            report_id=report.report_id,
            proposal_evidence_id=report.proposal_evidence_id,
            commit_witness_id=report.commit_witness_id,
            status=report.status,
            bridged_at=report.bridged_at,
            blockers=report.blockers,
            metadata=report.metadata,
        )
    )


def build_bridge_report(
    evidence: NestedMindProposalEvidence,
    witness: NestedMindCommitWitness,
    *,
    report_id: str,
    bridged_at: str,
    metadata: Mapping[str, Any] | None = None,
) -> NestedMindReceiptBridgeReport:
    blockers: list[str] = []
    if witness.proposal_evidence_id != evidence.evidence_id:
        blockers.append("proposal_evidence_id_mismatch")
    if witness.mind_id != evidence.mind_id:
        blockers.append("mind_id_mismatch")
    if witness.mullu_receipt_hash != evidence.mullu_receipt.receipt_hash:
        blockers.append("mullu_receipt_hash_mismatch")
    if witness.status is NestedMindCommitWitnessStatus.REJECTED:
        blockers.extend(f"nested_mind_rejected:{failure}" for failure in witness.failures)
    status = NestedMindBridgeStatus.BLOCKED if blockers else NestedMindBridgeStatus.BRIDGED
    clean_metadata = dict(metadata or {})
    payload = _bridge_hash_content(
        report_id=report_id,
        proposal_evidence_id=evidence.evidence_id,
        commit_witness_id=witness.witness_id,
        status=status,
        bridged_at=bridged_at,
        blockers=tuple(blockers),
        metadata=clean_metadata,
    )
    return NestedMindReceiptBridgeReport(
        report_id=report_id,
        proposal_evidence_id=evidence.evidence_id,
        commit_witness_id=witness.witness_id,
        status=status,
        bridged_at=bridged_at,
        blockers=tuple(blockers),
        bridge_hash=_hash(payload),
        metadata=clean_metadata,
    )


def build_verified_observation_bridge_report(
    evidence: object,
    submission: object,
    witness: NestedMindCommitWitness | None,
    *,
    report_id: str,
    bridged_at: str,
) -> NestedMindReceiptBridgeReport:
    """Build a live bridge report only for accepted submissions with VERIFIED witnesses."""

    blockers: list[str] = []
    evidence_id = require_non_empty_text(getattr(evidence, "evidence_id", ""), "proposal_evidence_id")
    mind_id = require_non_empty_text(getattr(evidence, "mind_id", ""), "mind_id")
    if getattr(submission, "status", None) != "accepted":
        blockers.append("submission_status_not_accepted")
    if witness is None:
        blockers.append("commit_witness_required")
    else:
        if witness.status is not NestedMindCommitWitnessStatus.VERIFIED:
            blockers.append("commit_witness_not_verified")
        if witness.proposal_evidence_id != evidence_id:
            blockers.append("proposal_evidence_id_mismatch")
        if witness.mind_id != mind_id:
            blockers.append("mind_id_mismatch")
        if witness.mullu_receipt_hash != getattr(evidence, "mullu_receipt_hash", ""):
            blockers.append("mullu_receipt_hash_mismatch")
        if getattr(submission, "commit_witness_id", None) != witness.witness_id:
            blockers.append("submission_commit_witness_id_mismatch")

    return NestedMindReceiptBridgeReport(
        report_id=report_id,
        proposal_evidence_id=evidence_id,
        mind_id=mind_id,
        commit_witness_id=witness.witness_id if witness is not None else None,
        status=(
            NestedMindReceiptBridgeStatus.BLOCKED
            if blockers
            else NestedMindReceiptBridgeStatus.BRIDGED
        ),
        bridged_at=bridged_at,
        blockers=tuple(blockers),
        metadata={
            "submission_report_id": getattr(submission, "report_id", ""),
        },
    )
