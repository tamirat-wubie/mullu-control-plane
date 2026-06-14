"""Purpose: governed personal-assistant memory observation candidates.
Governance scope: evidence-backed memory observation records, candidate ledger
read models, receipt emission, retention limits, and Nested Mind staging gates.
Dependencies: personal-assistant contracts, registry, and standard regex.
Invariants:
  - This module prepares candidate observations only; it does not write live memory.
  - Every observation requires source, confidence, scope, mutability, receipt,
    evidence, sensitivity, retention, and Nested Mind staging status.
  - Raw chat logs, raw connector payloads, and secret-like values are rejected.
  - Nested Mind live activation remains blocked and staging-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


MEMORY_OBSERVE_SKILL_ID = "memory.observe"

_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_FIELD_FRAGMENTS = (
    "raw",
    "body",
    "payload",
    "secret",
    "token",
    "credential",
    "private_key",
    "authorization",
    "cookie",
    "chat_log",
    "transcript",
)
_MEMORY_ACTIONS_NOT_TAKEN = (
    "live_memory_not_written",
    "nested_mind_not_activated",
    "raw_chat_log_not_stored",
    "raw_connector_payload_not_stored",
    "system_of_record_not_mutated",
)


class MemoryObservationType(StrEnum):
    """Schema-backed personal-assistant memory observation types."""

    PREFERENCE = "preference"
    IDENTITY_FACT = "identity_fact"
    PROJECT_STATE = "project_state"
    RELATIONSHIP_CONTEXT = "relationship_context"
    TASK_STATE = "task_state"
    DECISION_HISTORY = "decision_history"
    BLOCKED_BOUNDARY = "blocked_boundary"
    APPROVAL_RULE = "approval_rule"

    @staticmethod
    def coerce(value: str | "MemoryObservationType") -> "MemoryObservationType":
        """Coerce text into a memory observation type."""
        if isinstance(value, MemoryObservationType):
            return value
        try:
            return MemoryObservationType(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown memory_type: {value}") from exc


class MemorySourceType(StrEnum):
    """Schema-backed source classes for memory observations."""

    CONVERSATION = "conversation"
    CONNECTOR_RECEIPT = "connector_receipt"
    USER_CONFIRMATION = "user_confirmation"
    SYSTEM_RECEIPT = "system_receipt"
    PROJECT_ARTIFACT = "project_artifact"

    @staticmethod
    def coerce(value: str | "MemorySourceType") -> "MemorySourceType":
        """Coerce text into a memory source type."""
        if isinstance(value, MemorySourceType):
            return value
        try:
            return MemorySourceType(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown source_type: {value}") from exc


class MemoryConfidence(StrEnum):
    """Schema-backed confidence labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"

    @staticmethod
    def coerce(value: str | "MemoryConfidence") -> "MemoryConfidence":
        """Coerce text into a confidence label."""
        if isinstance(value, MemoryConfidence):
            return value
        try:
            return MemoryConfidence(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown confidence: {value}") from exc


class MemoryScope(StrEnum):
    """Schema-backed memory observation scopes."""

    ASSISTANT_WORKFLOW = "assistant_workflow"
    PROJECT = "project"
    RELATIONSHIP = "relationship"
    TASK = "task"
    SECURITY = "security"
    OPERATOR_PREFERENCE = "operator_preference"

    @staticmethod
    def coerce(value: str | "MemoryScope") -> "MemoryScope":
        """Coerce text into a memory scope."""
        if isinstance(value, MemoryScope):
            return value
        try:
            return MemoryScope(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown scope: {value}") from exc


class MemorySensitivity(StrEnum):
    """Schema-backed sensitivity labels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SECRET_FORBIDDEN = "secret_forbidden"

    @staticmethod
    def coerce(value: str | "MemorySensitivity") -> "MemorySensitivity":
        """Coerce text into a sensitivity label."""
        if isinstance(value, MemorySensitivity):
            return value
        try:
            return MemorySensitivity(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown sensitivity: {value}") from exc


class MemoryRetentionPolicy(StrEnum):
    """Schema-backed retention policies for observation candidates."""

    SESSION = "session"
    BOUNDED = "bounded"
    OPERATOR_REVIEW = "operator_review"
    DO_NOT_STORE = "do_not_store"

    @staticmethod
    def coerce(value: str | "MemoryRetentionPolicy") -> "MemoryRetentionPolicy":
        """Coerce text into a retention policy."""
        if isinstance(value, MemoryRetentionPolicy):
            return value
        try:
            return MemoryRetentionPolicy(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown retention_policy: {value}") from exc


class NestedMindStatus(StrEnum):
    """Schema-backed Nested Mind status values."""

    NOT_APPLICABLE = "not_applicable"
    STAGING_ONLY = "staging_only"
    AWAITING_EVIDENCE = "awaiting_evidence"

    @staticmethod
    def coerce(value: str | "NestedMindStatus") -> "NestedMindStatus":
        """Coerce text into a Nested Mind status."""
        if isinstance(value, NestedMindStatus):
            return value
        try:
            return NestedMindStatus(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown nested_mind_status: {value}") from exc


@dataclass(frozen=True, slots=True)
class MemoryObservationSource:
    """Evidence source binding for one memory observation candidate."""

    source_type: MemorySourceType | str
    source_ref: str
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", MemorySourceType.coerce(self.source_type))
        object.__setattr__(self, "source_ref", _require_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "observed_at", _require_text(self.observed_at, "observed_at"))

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "MemoryObservationSource":
        """Build a memory source from a schema-shaped mapping."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("source must be a mapping")
        _scan_private_or_secret_payload(payload, path="source")
        return MemoryObservationSource(
            source_type=_require_mapping_text(payload, "source_type"),
            source_ref=_require_mapping_text(payload, "source_ref"),
            observed_at=_require_mapping_text(payload, "observed_at"),
        )

    def as_dict(self) -> dict[str, str]:
        """Return a schema-ready source object."""
        return {
            "source_type": self.source_type.value,
            "source_ref": self.source_ref,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class MemoryObservationCandidate:
    """Governed memory observation candidate plus receipt."""

    observation: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.observation, Mapping):
            raise PersonalAssistantInvariantError("observation must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "observation", MappingProxyType(dict(self.observation)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    @property
    def memory_observation_id(self) -> str:
        """Return the observation id."""
        return str(self.observation["memory_observation_id"])

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready candidate envelope."""
        return {
            "memory_observation_id": self.memory_observation_id,
            "observation": dict(self.observation),
            "receipt": dict(self.receipt),
        }


@dataclass(slots=True)
class PersonalAssistantMemoryObservationLedger:
    """In-memory candidate ledger for operator-reviewable observations."""

    _candidates: dict[str, MemoryObservationCandidate] = field(default_factory=dict)

    def append(self, candidate: MemoryObservationCandidate) -> MemoryObservationCandidate:
        """Append one candidate to the local ledger without writing live memory."""
        if not isinstance(candidate, MemoryObservationCandidate):
            raise PersonalAssistantInvariantError("candidate must be a MemoryObservationCandidate")
        observation_id = candidate.memory_observation_id
        if observation_id in self._candidates:
            raise PersonalAssistantInvariantError(f"duplicate memory_observation_id: {observation_id}")
        if candidate.observation["sensitivity"] == MemorySensitivity.SECRET_FORBIDDEN.value:
            raise PersonalAssistantInvariantError("secret_forbidden observations cannot be appended")
        if candidate.observation["retention_policy"] == MemoryRetentionPolicy.DO_NOT_STORE.value:
            raise PersonalAssistantInvariantError("do_not_store observations cannot be appended")
        self._candidates[observation_id] = candidate
        return candidate

    def get(self, memory_observation_id: str) -> MemoryObservationCandidate:
        """Return one candidate by id."""
        observation_id = _require_prefix(memory_observation_id, "memory_observation_id", "pa_memory_")
        try:
            return self._candidates[observation_id]
        except KeyError as exc:
            raise PersonalAssistantInvariantError(f"unknown memory_observation_id: {observation_id}") from exc

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic operator-facing ledger read model."""
        candidates = tuple(self._candidates[observation_id] for observation_id in sorted(self._candidates))
        return {
            "candidate_count": len(candidates),
            "memory_observation_ids": [candidate.memory_observation_id for candidate in candidates],
            "memory_types": sorted({str(candidate.observation["memory_type"]) for candidate in candidates}),
            "live_memory_write_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "raw_private_payload_storage_allowed": False,
            "secret_value_storage_allowed": False,
            "candidate_only": True,
            "candidates": [candidate.as_dict() for candidate in candidates],
            "metadata": {
                "foundation_only": True,
                "ledger_projection": "read_model",
                "persistence_boundary": "stateless_unless_hosted_store_is_explicitly_bound",
                "live_memory_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
                "raw_private_payload_storage_allowed": False,
                "secret_value_storage_allowed": False,
            },
        }


def prepare_memory_observation(
    *,
    request_id: str,
    memory_observation_id: str,
    memory_type: MemoryObservationType | str,
    claim: str,
    source: MemoryObservationSource | Mapping[str, Any],
    confidence: MemoryConfidence | str,
    scope: MemoryScope | str,
    mutable: bool,
    receipt_id: str,
    evidence_refs: Sequence[str],
    observed_at: str,
    sensitivity: MemorySensitivity | str = MemorySensitivity.INTERNAL,
    retention_policy: MemoryRetentionPolicy | str = MemoryRetentionPolicy.OPERATOR_REVIEW,
    nested_mind_status: NestedMindStatus | str = NestedMindStatus.STAGING_ONLY,
    metadata: Mapping[str, Any] | None = None,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> MemoryObservationCandidate:
    """Prepare a schema-ready memory observation candidate and receipt."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(MEMORY_OBSERVE_SKILL_ID)
    if skill.memory_write_allowed:
        raise PersonalAssistantInvariantError("memory.observe must not allow live memory writes")
    request_id = _require_prefix(request_id, "request_id", "pa_request_")
    observation_id = _require_prefix(memory_observation_id, "memory_observation_id", "pa_memory_")
    claim = _require_text(claim, "claim")
    observation_source = source if isinstance(source, MemoryObservationSource) else MemoryObservationSource.from_mapping(source)
    confidence_value = MemoryConfidence.coerce(confidence)
    scope_value = MemoryScope.coerce(scope)
    sensitivity_value = MemorySensitivity.coerce(sensitivity)
    retention_value = MemoryRetentionPolicy.coerce(retention_policy)
    nested_status = NestedMindStatus.coerce(nested_mind_status)
    receipt_ref = _require_prefix(receipt_id, "receipt_id", "pa_receipt_")
    evidence = _text_tuple(evidence_refs, "evidence_refs")
    observed_at = _require_text(observed_at, "observed_at")
    if not isinstance(mutable, bool):
        raise PersonalAssistantInvariantError("mutable must be a boolean")
    if sensitivity_value is MemorySensitivity.SECRET_FORBIDDEN:
        raise PersonalAssistantInvariantError("secret_forbidden observations must not be prepared for storage")
    if retention_value is MemoryRetentionPolicy.DO_NOT_STORE:
        raise PersonalAssistantInvariantError("do_not_store observations must not be prepared for storage")
    if nested_status is not NestedMindStatus.STAGING_ONLY:
        raise PersonalAssistantInvariantError("personal-assistant memory observations require staging_only Nested Mind status")
    observation_metadata = _metadata(metadata)
    observation = {
        "memory_observation_id": observation_id,
        "memory_type": MemoryObservationType.coerce(memory_type).value,
        "claim": claim,
        "source": observation_source.as_dict(),
        "confidence": confidence_value.value,
        "scope": scope_value.value,
        "mutable": mutable,
        "receipt_id": receipt_ref,
        "evidence_refs": list(evidence),
        "sensitivity": sensitivity_value.value,
        "retention_policy": retention_value.value,
        "nested_mind_status": nested_status.value,
        "metadata": {
            **observation_metadata,
            "foundation_only": True,
            "source_projection": "claim_only",
            "live_memory_write_allowed": False,
            "nested_mind_live_activation_allowed": False,
        },
    }
    receipt = _memory_receipt(
        request_id=request_id,
        receipt_id=f"pa_receipt_{_memory_suffix(observation_id)}_{_safe_identifier(skill.skill_id)}",
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        timestamp=observed_at,
        memory_observation_id=observation_id,
        evidence_refs=evidence,
        metadata={
            "memory_type": observation["memory_type"],
            "confidence": confidence_value.value,
            "scope": scope_value.value,
            "retention_policy": retention_value.value,
            "live_memory_write_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "candidate_only": True,
        },
    )
    return MemoryObservationCandidate(observation=observation, receipt=receipt)


def _memory_receipt(
    *,
    request_id: str,
    receipt_id: str,
    skill_id: str,
    risk_level: str,
    timestamp: str,
    memory_observation_id: str,
    evidence_refs: Sequence[str],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "mode": "preview",
        "risk_level": risk_level,
        "inputs_used": ["memory_claim_projection", "source_ref", "receipt_ref"],
        "connectors_used": [],
        "decision": "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": ["memory_observation_candidate_prepared", "receipt_created"],
        "actions_not_taken": list(_MEMORY_ACTIONS_NOT_TAKEN),
        "redactions": ["claim_only_no_raw_chat_log", "secret_values_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "no_connector_payload",
            "body_projection": "digest_only",
        },
        "timestamp": timestamp,
        "evidence_refs": list(evidence_refs),
        "memory_observation_refs": [memory_observation_id],
        "replay_refs": [f"replay://personal-assistant/memory/{_memory_suffix(memory_observation_id)}"],
        "outcome": "SolvedVerified",
        "metadata": dict(metadata),
    }


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError("metadata must be a mapping")
    _scan_private_or_secret_payload(value, path="metadata")
    return dict(value)


def _text_tuple(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        item = _require_text(value, f"{field_name}[{index}]")
        if item not in normalized:
            normalized.append(item)
    if not normalized:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _require_mapping_text(payload: Mapping[str, Any], field_name: str) -> str:
    return _require_text(payload.get(field_name), field_name)


def _require_prefix(value: Any, field_name: str, prefix: str) -> str:
    text = _require_text(value, field_name)
    if not text.startswith(prefix):
        raise PersonalAssistantInvariantError(f"{field_name} must start with {prefix}")
    return text


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if any(fragment in normalized_key for fragment in _RAW_PRIVATE_FIELD_FRAGMENTS):
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str) and _contains_secret_like_value(payload):
        raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _memory_suffix(memory_observation_id: str) -> str:
    return _safe_identifier(memory_observation_id.removeprefix("pa_memory_"))


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "memory"
