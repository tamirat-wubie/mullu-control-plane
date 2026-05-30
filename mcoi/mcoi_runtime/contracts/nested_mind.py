"""Typed nested-mind projection import contracts.

Purpose: validate bounded nested-mind Γ projection/history envelopes before the
control plane consumes them as read models.
Governance scope: read-only import contracts only; no nested-mind proposal,
child-mind creation, lawbook mutation, or commit-writing surface is introduced.
Dependencies: canonical contract base helpers and connector result contracts.
Invariants:
  - Projection imports bind to an existing governed connector result.
  - Public and summary projections cannot carry sensitive state keys.
  - Import receipts never admit projection content into memory directly.
  - Mutation-shaped payloads are rejected at the typed boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)
from .integration import ConnectorResult, ConnectorStatus

__all__ = (
    "NestedMindHistoryEnvelope",
    "NestedMindHistorySurface",
    "NestedMindImportStatus",
    "NestedMindProjectionEnvelope",
    "NestedMindProjectionImportReceipt",
    "NestedMindProjectionScope",
    "build_nested_mind_projection_import_receipt",
    "nested_mind_projection_hash",
    "parse_nested_mind_history_payload",
    "parse_nested_mind_projection_payload",
)


class NestedMindProjectionScope(StrEnum):
    """Projection scope exposed by the nested-mind Γ boundary."""

    PUBLIC = "public"
    SUMMARY = "summary"
    INTERNAL = "internal"


class NestedMindHistorySurface(StrEnum):
    """History verification surface exposed by the nested-mind Γ boundary."""

    AUDIT = "audit"
    REPLAY = "replay"


class NestedMindImportStatus(StrEnum):
    """Typed import result at the Mullu control-plane boundary."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


_MIND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MUTATION_PAYLOAD_KEYS = frozenset(
    {
        "proposal",
        "proposals",
        "patch",
        "patches",
        "ops",
        "operation",
        "lawbook_migration",
        "lawbook_migrations",
        "child_mind_create",
        "commit_write",
    }
)
_SENSITIVE_STATE_KEY_PARTS = (
    "secret",
    "password",
    "token",
    "credential",
    "private_key",
)


def _validate_mind_id(mind_id: str) -> str:
    value = str(mind_id or "").strip()
    if not _MIND_ID_RE.fullmatch(value):
        raise ValueError("mind_id must be a path-segment-safe identifier")
    return value


def _enum_value(enum_type: type[StrEnum], value: Any, field_name: str) -> StrEnum:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not an allowed value") from exc


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            _json_safe(value),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("nested-mind import payload must be deterministic JSON") from exc


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_json_dict") and hasattr(value, "__dataclass_fields__"):
        return value.to_json_dict()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, frozenset):
        return sorted([_json_safe(item) for item in value], key=str)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _as_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _as_tuple(values: Sequence[str] | None, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    return tuple(str(value) for value in values)


def _sensitive_paths(value: Any, prefix: str = "state") -> tuple[str, ...]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            key_lower = key.lower()
            path = f"{prefix}.{key}"
            if any(part in key_lower for part in _SENSITIVE_STATE_KEY_PARTS):
                paths.append(path)
            paths.extend(_sensitive_paths(item, path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            paths.extend(_sensitive_paths(item, f"{prefix}[{index}]"))
    return tuple(paths)


def _reject_mutation_shape(payload: Mapping[str, Any]) -> None:
    present = sorted(str(key) for key in payload if str(key) in _MUTATION_PAYLOAD_KEYS)
    if present:
        raise ValueError("nested-mind projection payload must not include mutation keys")
    if payload.get("mutation_routes_enabled") is True:
        raise ValueError("nested-mind projection payload must not enable mutation routes")


@dataclass(frozen=True, slots=True)
class NestedMindProjectionEnvelope(ContractRecord):
    """Schema-validated nested-mind Γ projection content.

    The envelope is a read model. It is not memory admission, not a proposal, and
    not authority to mutate nested-mind state.
    """

    mind_id: str
    scope: NestedMindProjectionScope
    sequence: int
    commit_hash: str
    state_hash: str
    lawbook_hash: str
    history_hash: str
    projected_at: str
    state: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mind_id", _validate_mind_id(self.mind_id))
        object.__setattr__(self, "scope", _enum_value(NestedMindProjectionScope, self.scope, "scope"))
        object.__setattr__(self, "sequence", require_non_negative_int(self.sequence, "sequence"))
        for field_name in ("commit_hash", "state_hash", "lawbook_hash", "history_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "projected_at", require_datetime_text(self.projected_at, "projected_at"))
        state = _as_mapping(self.state, "state")
        metadata = _as_mapping(self.metadata, "metadata")
        if self.scope in (NestedMindProjectionScope.PUBLIC, NestedMindProjectionScope.SUMMARY):
            leaked_paths = _sensitive_paths(state)
            if leaked_paths:
                raise ValueError("public or summary nested-mind projection contains sensitive state keys")
        object.__setattr__(self, "state", freeze_value(state))
        object.__setattr__(self, "metadata", freeze_value(metadata))


@dataclass(frozen=True, slots=True)
class NestedMindHistoryEnvelope(ContractRecord):
    """Schema-validated audit/replay history verification envelope."""

    mind_id: str
    surface: NestedMindHistorySurface
    verified: bool
    history_hash: str
    checked_at: str
    sequence: int = 0
    failures: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mind_id", _validate_mind_id(self.mind_id))
        object.__setattr__(self, "surface", _enum_value(NestedMindHistorySurface, self.surface, "surface"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")
        object.__setattr__(self, "history_hash", require_non_empty_text(self.history_hash, "history_hash"))
        object.__setattr__(self, "checked_at", require_datetime_text(self.checked_at, "checked_at"))
        object.__setattr__(self, "sequence", require_non_negative_int(self.sequence, "sequence"))
        object.__setattr__(self, "failures", freeze_value(_as_tuple(self.failures, "failures")))
        object.__setattr__(self, "metadata", freeze_value(_as_mapping(self.metadata, "metadata")))


@dataclass(frozen=True, slots=True)
class NestedMindProjectionImportReceipt(ContractRecord):
    """Receipt proving a nested-mind projection was imported as a bounded read model."""

    receipt_id: str
    mind_id: str
    scope: NestedMindProjectionScope
    connector_result_id: str
    connector_response_digest: str
    projection_hash: str
    state_hash: str
    commit_hash: str
    imported_at: str
    status: NestedMindImportStatus
    validation_errors: Sequence[str] = field(default_factory=tuple)
    admitted_to_memory: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "connector_result_id",
            "connector_response_digest",
            "projection_hash",
            "state_hash",
            "commit_hash",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "mind_id", _validate_mind_id(self.mind_id))
        object.__setattr__(self, "scope", _enum_value(NestedMindProjectionScope, self.scope, "scope"))
        object.__setattr__(self, "imported_at", require_datetime_text(self.imported_at, "imported_at"))
        object.__setattr__(self, "status", _enum_value(NestedMindImportStatus, self.status, "status"))
        errors = _as_tuple(self.validation_errors, "validation_errors")
        if self.status is NestedMindImportStatus.ACCEPTED and errors:
            raise ValueError("accepted nested-mind import receipt must not contain validation errors")
        if self.status is NestedMindImportStatus.REJECTED and not errors:
            raise ValueError("rejected nested-mind import receipt must contain validation errors")
        if self.admitted_to_memory is not False:
            raise ValueError("nested-mind projection import does not admit content into memory")
        object.__setattr__(self, "validation_errors", freeze_value(errors))
        object.__setattr__(self, "metadata", freeze_value(_as_mapping(self.metadata, "metadata")))


def parse_nested_mind_projection_payload(payload: Mapping[str, Any]) -> NestedMindProjectionEnvelope:
    """Parse and validate a nested-mind projection payload as a bounded envelope."""

    payload = _as_mapping(payload, "payload")
    _reject_mutation_shape(payload)
    mind_id = payload.get("mind_id", payload.get("id"))
    if mind_id is None:
        raise ValueError("payload must include mind_id")
    state = _as_mapping(payload.get("state", {}), "state")
    return NestedMindProjectionEnvelope(
        mind_id=str(mind_id),
        scope=NestedMindProjectionScope(str(payload.get("scope", NestedMindProjectionScope.PUBLIC.value))),
        sequence=int(payload.get("sequence", 0)),
        commit_hash=str(payload.get("commit_hash", "")),
        state_hash=str(payload.get("state_hash", "")),
        lawbook_hash=str(payload.get("lawbook_hash", "")),
        history_hash=str(payload.get("history_hash", payload.get("event_chain_hash", ""))),
        projected_at=str(payload.get("projected_at", "")),
        state=state,
        metadata=_as_mapping(payload.get("metadata", {}), "metadata"),
    )


def parse_nested_mind_history_payload(
    payload: Mapping[str, Any], *, surface: NestedMindHistorySurface | str
) -> NestedMindHistoryEnvelope:
    """Parse audit/replay verification payload without importing symbolic state."""

    payload = _as_mapping(payload, "payload")
    _reject_mutation_shape(payload)
    mind_id = payload.get("mind_id", payload.get("id"))
    if mind_id is None:
        raise ValueError("payload must include mind_id")
    return NestedMindHistoryEnvelope(
        mind_id=str(mind_id),
        surface=NestedMindHistorySurface(str(surface)),
        verified=bool(payload.get("verified", False)),
        history_hash=str(payload.get("history_hash", payload.get("event_chain_hash", ""))),
        checked_at=str(payload.get("checked_at", payload.get("projected_at", ""))),
        sequence=int(payload.get("sequence", 0)),
        failures=_as_tuple(payload.get("failures", ()), "failures"),
        metadata=_as_mapping(payload.get("metadata", {}), "metadata"),
    )


def nested_mind_projection_hash(envelope: NestedMindProjectionEnvelope) -> str:
    """Return a deterministic hash for a typed projection envelope."""

    if not isinstance(envelope, NestedMindProjectionEnvelope):
        raise ValueError("envelope must be a NestedMindProjectionEnvelope")
    return _sha256_json(envelope)


def build_nested_mind_projection_import_receipt(
    envelope: NestedMindProjectionEnvelope,
    *,
    connector_result: ConnectorResult,
    receipt_id: str,
    imported_at: str,
    metadata: Mapping[str, Any] | None = None,
) -> NestedMindProjectionImportReceipt:
    """Bind a typed projection envelope to the governed HTTP connector receipt."""

    if not isinstance(envelope, NestedMindProjectionEnvelope):
        raise ValueError("envelope must be a NestedMindProjectionEnvelope")
    if not isinstance(connector_result, ConnectorResult):
        raise ValueError("connector_result must be a ConnectorResult")
    if connector_result.status is not ConnectorStatus.SUCCEEDED:
        raise ValueError("connector_result must have succeeded before projection import")
    return NestedMindProjectionImportReceipt(
        receipt_id=receipt_id,
        mind_id=envelope.mind_id,
        scope=envelope.scope,
        connector_result_id=connector_result.result_id,
        connector_response_digest=connector_result.response_digest,
        projection_hash=nested_mind_projection_hash(envelope),
        state_hash=envelope.state_hash,
        commit_hash=envelope.commit_hash,
        imported_at=imported_at,
        status=NestedMindImportStatus.ACCEPTED,
        validation_errors=(),
        admitted_to_memory=False,
        metadata=metadata or MappingProxyType({}),
    )
