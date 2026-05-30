"""Default-off nested-mind observation proposal bridge contracts.

Purpose: produce a fixed, hash-bound `record_observation` proposal plan from
Mullu receipt evidence without exposing broad nested-mind mutation authority.
Governance scope: proposal planning only; no route, connector execution, child
mind creation, lawbook mutation, arbitrary patch operation, or memory admission.
Dependencies: nested_mind_receipts contract layer.
Invariants:
  - only record_observation evidence can produce a plan.
  - bridge is disabled by default and records an explicit blocker.
  - proposal payload has exactly one fixed `set` op under observations/<id>.
  - caller-provided arbitrary ops are never accepted.
  - payload and observation are content-addressed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text
from .nested_mind_receipts import NestedMindProposalEvidence, NestedMindProposalKind


class NestedMindObservationBridgeStatus(StrEnum):
    """Plan status for the default-off observation bridge."""

    DISABLED = "disabled"
    PLANNED = "planned"


_MIND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_OBSERVATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DISABLED_BLOCKER = "nested_mind_observation_bridge_disabled"


def _mind_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not _MIND_ID_RE.fullmatch(normalized):
        raise ValueError("mind_id must be a path-segment-safe identifier")
    return normalized


def _observation_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not _OBSERVATION_ID_RE.fullmatch(normalized):
        raise ValueError("observation_id must be a path-segment-safe identifier")
    return normalized


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
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def stable_json_hash(value: Any) -> str:
    """Return a deterministic SHA-256 hash for JSON-compatible values."""

    payload = json.dumps(
        _json_safe(value),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _validate_payload(payload: Mapping[str, Any], *, mind_id: str) -> None:
    if set(payload.keys()) != {"actor", "reason", "kind", "metadata", "ops"}:
        raise ValueError("observation proposal payload has unexpected keys")
    if payload.get("kind") != NestedMindProposalKind.RECORD_OBSERVATION.value:
        raise ValueError("observation proposal payload kind must be record_observation")
    metadata = _require_mapping(payload.get("metadata"), "metadata")
    for key in ("mullu_receipt_hash", "authority_receipt_hash", "proposal_evidence_hash", "observation_hash", "observed_at"):
        require_non_empty_text(str(metadata.get(key, "")), key)
    ops = payload.get("ops")
    if not isinstance(ops, list) or len(ops) != 1:
        raise ValueError("observation proposal payload must contain exactly one op")
    op = _require_mapping(ops[0], "ops[0]")
    if set(op.keys()) != {"op", "key", "value"}:
        raise ValueError("observation proposal op has unexpected keys")
    if op.get("op") != "set":
        raise ValueError("observation proposal op must be set")
    key = str(op.get("key", ""))
    if not key.startswith("observations/"):
        raise ValueError("observation proposal key must live under observations/")
    _observation_id(key.removeprefix("observations/"))
    _require_mapping(op.get("value"), "observation value")
    if mind_id != _mind_id(mind_id):
        raise ValueError("invalid mind_id")


@dataclass(frozen=True, slots=True)
class NestedMindObservationProposalPlan(ContractRecord):
    """Hash-bound plan for a narrow nested-mind observation proposal."""

    plan_id: str
    mind_id: str
    proposal_evidence_id: str
    mullu_receipt_hash: str
    authority_receipt_hash: str
    target_route: str
    method: str
    payload_hash: str
    observation_hash: str
    created_at: str
    status: NestedMindObservationBridgeStatus
    proposal_payload: Mapping[str, Any]
    blockers: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("plan_id", "proposal_evidence_id", "mullu_receipt_hash", "authority_receipt_hash", "payload_hash", "observation_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "mind_id", _mind_id(self.mind_id))
        expected_route = f"/minds/{self.mind_id}/proposals"
        if self.target_route != expected_route:
            raise ValueError("target_route must be the fixed nested-mind proposals route")
        if self.method != "POST":
            raise ValueError("observation proposal plan method must be POST")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "status", NestedMindObservationBridgeStatus(str(self.status)))
        payload = _require_mapping(self.proposal_payload, "proposal_payload")
        _validate_payload(payload, mind_id=self.mind_id)
        if self.payload_hash != stable_json_hash(payload):
            raise ValueError("payload_hash does not match proposal payload")
        payload_observation_hash = str(payload["metadata"]["observation_hash"])
        if self.observation_hash != payload_observation_hash:
            raise ValueError("observation_hash must match payload metadata")
        if self.mullu_receipt_hash != str(payload["metadata"]["mullu_receipt_hash"]):
            raise ValueError("mullu_receipt_hash must match payload metadata")
        if self.authority_receipt_hash != str(payload["metadata"]["authority_receipt_hash"]):
            raise ValueError("authority_receipt_hash must match payload metadata")
        blockers = _text_tuple(self.blockers, "blockers")
        if self.status is NestedMindObservationBridgeStatus.DISABLED and _DISABLED_BLOCKER not in blockers:
            raise ValueError("disabled observation bridge plan must include disabled blocker")
        if self.status is NestedMindObservationBridgeStatus.PLANNED and blockers:
            raise ValueError("planned observation bridge plan must not contain blockers")
        object.__setattr__(self, "proposal_payload", freeze_value(payload))
        object.__setattr__(self, "blockers", freeze_value(blockers))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


def build_observation_proposal_payload(
    evidence: NestedMindProposalEvidence,
    *,
    observation_id: str,
    observation: Mapping[str, Any],
    observed_at: str,
) -> Mapping[str, Any]:
    """Build the only payload shape allowed by the P2.1 bridge."""

    if not isinstance(evidence, NestedMindProposalEvidence):
        raise ValueError("evidence must be NestedMindProposalEvidence")
    if evidence.proposal_kind is not NestedMindProposalKind.RECORD_OBSERVATION:
        raise ValueError("only record_observation evidence is allowed")
    safe_observation_id = _observation_id(observation_id)
    clean_observation = dict(_require_mapping(observation, "observation"))
    observation_hash = stable_json_hash(clean_observation)
    require_datetime_text(observed_at, "observed_at")
    return {
        "actor": evidence.actor_id,
        "reason": evidence.reason,
        "kind": NestedMindProposalKind.RECORD_OBSERVATION.value,
        "metadata": {
            "mullu_receipt_hash": evidence.mullu_receipt.receipt_hash,
            "authority_receipt_hash": evidence.authority_receipt_hash,
            "proposal_evidence_hash": evidence.evidence_hash,
            "observation_hash": observation_hash,
            "observed_at": observed_at,
        },
        "ops": [
            {
                "op": "set",
                "key": f"observations/{safe_observation_id}",
                "value": clean_observation,
            }
        ],
    }


def build_observation_proposal_plan(
    evidence: NestedMindProposalEvidence,
    *,
    plan_id: str,
    observation_id: str,
    observation: Mapping[str, Any],
    observed_at: str,
    created_at: str,
    bridge_enabled: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> NestedMindObservationProposalPlan:
    """Build a default-off, fixed-shape observation proposal plan."""

    payload = build_observation_proposal_payload(
        evidence,
        observation_id=observation_id,
        observation=observation,
        observed_at=observed_at,
    )
    status = NestedMindObservationBridgeStatus.PLANNED if bridge_enabled else NestedMindObservationBridgeStatus.DISABLED
    blockers = () if bridge_enabled else (_DISABLED_BLOCKER,)
    return NestedMindObservationProposalPlan(
        plan_id=plan_id,
        mind_id=evidence.mind_id,
        proposal_evidence_id=evidence.evidence_id,
        mullu_receipt_hash=evidence.mullu_receipt.receipt_hash,
        authority_receipt_hash=evidence.authority_receipt_hash,
        target_route=f"/minds/{evidence.mind_id}/proposals",
        method="POST",
        payload_hash=stable_json_hash(payload),
        observation_hash=str(payload["metadata"]["observation_hash"]),
        created_at=created_at,
        status=status,
        proposal_payload=payload,
        blockers=blockers,
        metadata=metadata or {},
    )
