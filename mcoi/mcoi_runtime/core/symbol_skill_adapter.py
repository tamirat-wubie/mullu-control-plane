"""Purpose: project governed runtime artifacts into UniversalSymbol envelopes.
Governance scope: Foundation Mode symbolization only; no runtime authority.
Dependencies: Python standard library, contract serialization helpers, and
runtime invariant helpers.
Invariants:
  - Projection is deterministic and side-effect free.
  - Raw private payloads and raw secret values are rejected before projection.
  - Output authority flags are always denied.
  - Projection never dispatches work, calls connectors, writes files, or grants
    terminal closure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any

from mcoi_runtime.contracts._base import freeze_value
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_iso_timestamp,
    ensure_non_empty_text,
)


UNIVERSAL_SYMBOL_VERSION = "universal_symbol.v1"
UNIVERSAL_SYMBOL_KIND_COUNT = 16

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "raw_private_payload_stored",
    "raw_secret_value_stored",
    "connector_call_performed",
    "external_write_performed",
    "filesystem_write_performed",
    "runtime_dispatch_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)

_BLOCKED_ACTION_REFS: tuple[str, ...] = (
    "blocked://connector-call",
    "blocked://external-write",
    "blocked://filesystem-write",
    "blocked://runtime-dispatch",
    "blocked://state-mutation",
    "blocked://terminal-closure",
    "blocked://success-claim",
)

_SYMBOL_CORE_REFS: tuple[str, ...] = (
    "symbol://identity",
    "symbol://boundary",
    "symbol://metadata",
    "symbol://relations",
    "symbol://causality",
    "symbol://lineage",
    "symbol://governance",
    "symbol://proof",
    "symbol://skill-projection",
)

_FOUNDATION_OUTSIDE_REFS: tuple[str, ...] = (
    "runtime://live-dispatch",
    "connector://live-call",
    "filesystem://write",
    "external://write",
    "closure://terminal",
)

_FOUNDATION_PROTECTED_REFS: tuple[str, ...] = (
    "secret://raw-values",
    "payload://raw-private-data",
    "governance://authority-boundary",
)

_FOUNDATION_POLICY_REFS: tuple[str, ...] = (
    "policy://foundation-mode",
    "policy://no-runtime-authority",
    "policy://no-raw-private-payload-retention",
)

_PROHIBITED_TRUE_FIELDS: frozenset[str] = frozenset(
    {
        "raw_private_payload_stored",
        "raw_secret_value_stored",
        "raw_provider_payload_serialized",
        "raw_trace_stored",
        "raw_state_stored",
    }
)

_PROHIBITED_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "raw_payload",
        "raw_private_payload",
        "raw_provider_payload",
        "raw_trace",
        "raw_state",
        "raw_secret",
        "raw_secret_value",
        "secret_value",
        "private_key",
    }
)

_SAFE_SYMBOL_SEGMENT = re.compile(r"^[a-z0-9._:-]+$")


class SymbolAdapterSurface(StrEnum):
    """Supported source surfaces for first-pass symbol projection."""

    TEAMOPS_RECEIPT = "teamops_receipt"
    SOFTWARE_DEV_RECEIPT = "software_dev_receipt"
    SCCML_TRACE = "sccml_trace"
    WORKER_RECEIPT = "worker_receipt"
    COMPONENT_REGISTRY_ENTRY = "component_registry_entry"
    GENERIC_RECEIPT = "generic_receipt"


@dataclass(frozen=True, slots=True)
class _SurfaceDefaults:
    symbol_kind: str
    domain: str
    canonical_ref: str
    projected_skill_refs: tuple[str, ...]
    identifier_fields: tuple[str, ...]


_SURFACE_DEFAULTS: Mapping[SymbolAdapterSurface, _SurfaceDefaults] = {
    SymbolAdapterSurface.TEAMOPS_RECEIPT: _SurfaceDefaults(
        symbol_kind="receipt",
        domain="team_ops",
        canonical_ref="schemas/team_ops_shared_inbox_provider_observation_receipt.schema.json",
        projected_skill_refs=("skill://teamops-shared-inbox",),
        identifier_fields=("receipt_id",),
    ),
    SymbolAdapterSurface.SOFTWARE_DEV_RECEIPT: _SurfaceDefaults(
        symbol_kind="receipt",
        domain="software_dev",
        canonical_ref="mcoi_runtime.contracts.software_dev_loop.SoftwareChangeReceipt",
        projected_skill_refs=("skill://software-dev",),
        identifier_fields=("receipt_id", "request_id"),
    ),
    SymbolAdapterSurface.SCCML_TRACE: _SurfaceDefaults(
        symbol_kind="trace",
        domain="sccml",
        canonical_ref="schemas/sccml_trace_adapter_witness.schema.json",
        projected_skill_refs=("skill://sccml-trace-adapter",),
        identifier_fields=("witness_id", "trace_id"),
    ),
    SymbolAdapterSurface.WORKER_RECEIPT: _SurfaceDefaults(
        symbol_kind="receipt",
        domain="worker",
        canonical_ref="schemas/worker_failure_receipt.schema.json",
        projected_skill_refs=("skill://read-only-worker",),
        identifier_fields=("receipt_id", "worker_receipt_id", "run_id"),
    ),
    SymbolAdapterSurface.COMPONENT_REGISTRY_ENTRY: _SurfaceDefaults(
        symbol_kind="component",
        domain="component",
        canonical_ref="schemas/component_registry.schema.json",
        projected_skill_refs=("skill://component-registry",),
        identifier_fields=("component_id", "route_family", "name"),
    ),
    SymbolAdapterSurface.GENERIC_RECEIPT: _SurfaceDefaults(
        symbol_kind="receipt",
        domain="receipt",
        canonical_ref="schemas/universal_symbol.schema.json",
        projected_skill_refs=("skill://generic-receipt",),
        identifier_fields=("receipt_id", "id", "source_id"),
    ),
}


@dataclass(frozen=True, slots=True)
class SymbolAdapterSource:
    """Digest-only source facts needed to create one UniversalSymbol."""

    source_id: str
    source_surface: SymbolAdapterSurface
    label: str
    definition: str
    domain: str
    local_name: str
    canonical_ref: str
    symbol_kind: str
    evidence_refs: tuple[str, ...]
    target_refs: tuple[str, ...] = ()
    constraint_refs: tuple[str, ...] = ()
    metadata_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    upstream_refs: tuple[str, ...] = ()
    downstream_refs: tuple[str, ...] = ()
    peer_refs: tuple[str, ...] = ()
    cause_refs: tuple[str, ...] = ()
    effect_refs: tuple[str, ...] = ()
    pre_state_ref: str = ""
    post_state_ref: str = ""
    causal_trace_ref: str = ""
    unknown_refs: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()
    origin_ref: str = ""
    parent_symbol_refs: tuple[str, ...] = ()
    child_symbol_refs: tuple[str, ...] = ()
    promotion_refs: tuple[str, ...] = ()
    mutation_refs: tuple[str, ...] = ()
    projected_skill_refs: tuple[str, ...] = ()
    skill_transfer_refs: tuple[str, ...] = ()
    risk_tier: str = "medium"
    ontology_status: str = "candidate"

    def __post_init__(self) -> None:
        source_surface = _coerce_surface(self.source_surface)
        object.__setattr__(self, "source_surface", source_surface)
        object.__setattr__(self, "source_id", ensure_non_empty_text("source_id", self.source_id))
        object.__setattr__(self, "label", ensure_non_empty_text("label", self.label))
        object.__setattr__(self, "definition", ensure_non_empty_text("definition", self.definition))
        object.__setattr__(self, "domain", _require_symbol_segment("domain", self.domain))
        object.__setattr__(self, "local_name", _require_symbol_segment("local_name", self.local_name))
        object.__setattr__(self, "canonical_ref", ensure_non_empty_text("canonical_ref", self.canonical_ref))
        object.__setattr__(self, "symbol_kind", _require_symbol_kind(self.symbol_kind))
        object.__setattr__(self, "evidence_refs", _require_ref_tuple(self.evidence_refs, "evidence_refs", True))
        for field_name in (
            "target_refs",
            "constraint_refs",
            "metadata_refs",
            "relation_refs",
            "upstream_refs",
            "downstream_refs",
            "peer_refs",
            "cause_refs",
            "effect_refs",
            "unknown_refs",
            "contradiction_refs",
            "parent_symbol_refs",
            "child_symbol_refs",
            "promotion_refs",
            "mutation_refs",
            "projected_skill_refs",
            "skill_transfer_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_ref_tuple(getattr(self, field_name), field_name, False),
            )
        object.__setattr__(self, "pre_state_ref", ensure_non_empty_text("pre_state_ref", self.pre_state_ref))
        object.__setattr__(self, "post_state_ref", ensure_non_empty_text("post_state_ref", self.post_state_ref))
        object.__setattr__(self, "causal_trace_ref", ensure_non_empty_text("causal_trace_ref", self.causal_trace_ref))
        object.__setattr__(self, "origin_ref", ensure_non_empty_text("origin_ref", self.origin_ref))
        if self.risk_tier not in {"low", "medium", "high", "critical"}:
            raise RuntimeCoreInvariantError("risk_tier must be low, medium, high, or critical")
        if self.ontology_status not in {"known", "candidate", "hypothetical", "simulated", "unknown_status", "rejected"}:
            raise RuntimeCoreInvariantError("ontology_status must be a UniversalSymbol ontology status")


def source_from_record(
    record: Mapping[str, Any] | Any,
    source_surface: SymbolAdapterSurface | str,
    *,
    label: str | None = None,
    definition: str | None = None,
) -> SymbolAdapterSource:
    """Extract digest-only source facts from a known receipt, trace, or component."""

    surface = _coerce_surface(source_surface)
    defaults = _SURFACE_DEFAULTS[surface]
    record_map = _record_to_mapping(record)
    _reject_raw_payload_storage(record_map)

    source_id = _first_non_empty_text(record_map, defaults.identifier_fields)
    local_name = _bounded_symbol_segment(source_id)
    source_ref = f"{surface.value}://{source_id}"
    trace_scope = _mapping(record_map.get("trace_scope"))

    evidence_refs = _record_evidence_refs(record_map, surface, source_ref)
    target_refs = _record_refs(record_map, "target_refs")
    constraint_refs = _record_refs(record_map, "constraint_refs")
    metadata_refs = _metadata_refs(record_map, surface)
    pre_state_ref = _optional_text(trace_scope.get("pre_state_hash_ref")) or f"state://{surface.value}/{source_id}/pre"
    post_state_ref = _optional_text(trace_scope.get("post_state_hash_ref")) or f"state://{surface.value}/{source_id}/post"
    causal_trace_ref = _optional_text(trace_scope.get("instruction_trace_ref")) or f"trace://symbol-skill-adapter/{surface.value}/{source_id}"

    return SymbolAdapterSource(
        source_id=source_id,
        source_surface=surface,
        label=label or _default_label(surface, source_id, record_map),
        definition=definition or _default_definition(surface),
        domain=defaults.domain,
        local_name=local_name,
        canonical_ref=defaults.canonical_ref,
        symbol_kind=defaults.symbol_kind,
        evidence_refs=evidence_refs,
        target_refs=target_refs,
        constraint_refs=constraint_refs,
        metadata_refs=metadata_refs,
        relation_refs=(f"relation://{surface.value}-to-universal-symbol",),
        upstream_refs=(source_ref,),
        downstream_refs=("schema://universal-symbol-envelope",),
        peer_refs=_record_peer_refs(surface),
        cause_refs=(f"cause://{surface.value}/source-record-admitted",),
        effect_refs=(f"effect://{surface.value}/universal-symbol-envelope-created",),
        pre_state_ref=pre_state_ref,
        post_state_ref=post_state_ref,
        causal_trace_ref=causal_trace_ref,
        unknown_refs=("unknown://runtime-symbol-adapter-live-promotion",),
        contradiction_refs=(),
        origin_ref=source_ref,
        parent_symbol_refs=(f"symbol://{surface.value}",),
        child_symbol_refs=(),
        promotion_refs=(f"promotion://{surface.value}-to-universal-symbol-foundation",),
        mutation_refs=(),
        projected_skill_refs=defaults.projected_skill_refs,
        skill_transfer_refs=(f"transfer://{surface.value}-to-universal-symbol",),
        risk_tier="medium",
    )


def universal_symbol_from_record(
    record: Mapping[str, Any] | Any,
    source_surface: SymbolAdapterSurface | str,
    *,
    generated_at: str,
    label: str | None = None,
    definition: str | None = None,
) -> dict[str, Any]:
    """Create a Foundation Mode UniversalSymbol envelope from one source record."""

    source = source_from_record(record, source_surface, label=label, definition=definition)
    return universal_symbol_from_source(source, generated_at=generated_at)


def universal_symbol_from_source(source: SymbolAdapterSource, *, generated_at: str) -> dict[str, Any]:
    """Create a Foundation Mode UniversalSymbol envelope from digest-only source facts."""

    ensure_iso_timestamp("generated_at", generated_at)
    digest = _stable_hex16(
        {
            "source_id": source.source_id,
            "source_surface": source.source_surface.value,
            "canonical_ref": source.canonical_ref,
            "domain": source.domain,
            "local_name": source.local_name,
            "symbol_kind": source.symbol_kind,
        }
    )
    symbol_id = f"universal-symbol-{source.domain}.{source.local_name}-{digest}"
    return {
        "symbol_id": symbol_id,
        "symbol_version": UNIVERSAL_SYMBOL_VERSION,
        "generated_at": generated_at,
        "symbol_identity": {
            "label": source.label,
            "symbol_kind": source.symbol_kind,
            "domain": source.domain,
            "local_name": source.local_name,
            "canonical_ref": source.canonical_ref,
            "ontology_status": source.ontology_status,
            "definition": source.definition,
        },
        "symbol_boundary": {
            "boundary_scope": "foundation-mode-symbol-skill-adapter",
            "inside_refs": list(_SYMBOL_CORE_REFS),
            "outside_refs": list(_FOUNDATION_OUTSIDE_REFS),
            "protected_refs": list(_FOUNDATION_PROTECTED_REFS),
            "environment_refs": list(_merge_unique((source.canonical_ref,), source.evidence_refs)),
            "retention_policy_ref": "retention://symbol-skill-adapter/digest-and-refs-only",
        },
        "symbol_metadata": {
            "metadata_refs": list(_merge_unique(source.metadata_refs, ("metadata://digest-and-refs-only",))),
            "metadata_is_symbolizable": True,
            "question_refs": ["wh://what", "wh://why", "wh://how", "wh://depends-on"],
            "answer_refs": ["answer://foundation-symbol-skill-adapter-projection"],
            "unknown_refs": list(source.unknown_refs),
            "contradiction_refs": list(source.contradiction_refs),
        },
        "symbol_relations": {
            "relation_refs": list(source.relation_refs),
            "upstream_refs": list(source.upstream_refs),
            "downstream_refs": list(_merge_unique(source.downstream_refs, source.target_refs)),
            "peer_refs": list(source.peer_refs),
            "relation_is_symbolizable": True,
        },
        "symbol_causality": {
            "cause_refs": list(source.cause_refs),
            "effect_refs": list(source.effect_refs),
            "pre_state_ref": source.pre_state_ref,
            "post_state_ref": source.post_state_ref,
            "causal_trace_ref": source.causal_trace_ref,
            "unsupported_causal_gap_refs": ["gap://runtime-symbol-adapter-live-promotion"],
            "causality_is_symbolizable": True,
        },
        "symbol_lineage": {
            "origin_ref": source.origin_ref,
            "parent_symbol_refs": list(source.parent_symbol_refs),
            "child_symbol_refs": list(source.child_symbol_refs),
            "promotion_refs": list(source.promotion_refs),
            "mutation_refs": list(source.mutation_refs),
        },
        "symbol_governance": {
            "governance_mode": "foundation",
            "uao_ref": f"uao://symbol-skill-adapter/{source.source_surface.value}",
            "policy_refs": list(_merge_unique(_FOUNDATION_POLICY_REFS, source.constraint_refs)),
            "authority_refs": [],
            "approval_refs": [],
            "blocked_action_refs": list(_BLOCKED_ACTION_REFS),
            "risk_tier": source.risk_tier,
        },
        "symbol_proof": {
            "proof_state": "awaiting_evidence",
            "proof_refs": ["proof://symbol-skill-adapter/foundation-schema-valid"],
            "receipt_refs": list(_receipt_refs(source)),
            "witness_refs": ["witness://symbol-skill-adapter-no-authority"],
            "terminal_closure_ref": "",
            "proof_is_symbolizable": True,
        },
        "symbol_skill_projection": {
            "projected_skill_refs": list(source.projected_skill_refs),
            "adapter_refs": ["adapter://symbol-skill-adapter/foundation-read-only"],
            "skill_transfer_refs": list(source.skill_transfer_refs),
            "skill_projection_is_advisory_only": True,
        },
        "symbol_authority_boundary": {field_name: False for field_name in AUTHORITY_DENIAL_FIELDS},
        "contract_summary": {
            "symbol_native_boundary": True,
            "everything_symbolizable": True,
            "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
            "symbolizable_surface_count": UNIVERSAL_SYMBOL_KIND_COUNT,
            "evidence_ref_count": len(source.evidence_refs),
        },
        "evidence_refs": list(source.evidence_refs),
    }


def _coerce_surface(value: SymbolAdapterSurface | str) -> SymbolAdapterSurface:
    if isinstance(value, SymbolAdapterSurface):
        return value
    try:
        return SymbolAdapterSurface(str(value))
    except ValueError as exc:
        raise RuntimeCoreInvariantError("source_surface must be a supported SymbolAdapterSurface") from exc


def _record_to_mapping(record: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return freeze_value(dict(record))
    to_json_dict = getattr(record, "to_json_dict", None)
    if callable(to_json_dict):
        value = to_json_dict()
        if isinstance(value, Mapping):
            return freeze_value(dict(value))
    raise RuntimeCoreInvariantError("record must be a mapping or contract record")


def _reject_raw_payload_storage(value: Any, path: str = "record") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            item_path = f"{path}.{key_text}"
            if key_text in _PROHIBITED_TRUE_FIELDS and item is True:
                raise RuntimeCoreInvariantError(f"{item_path} violates digest-only symbol projection")
            if key_text in _PROHIBITED_VALUE_FIELDS and item not in (None, "", False):
                raise RuntimeCoreInvariantError(f"{item_path} violates digest-only symbol projection")
            _reject_raw_payload_storage(item, item_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_raw_payload_storage(item, f"{path}[{index}]")


def _first_non_empty_text(record: Mapping[str, Any], field_names: Sequence[str]) -> str:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    raise RuntimeCoreInvariantError("source record must contain a supported identifier field")


def _record_evidence_refs(
    record: Mapping[str, Any],
    surface: SymbolAdapterSurface,
    source_ref: str,
) -> tuple[str, ...]:
    refs: list[str] = [source_ref]
    refs.extend(_record_refs(record, "evidence_refs"))
    for field_name in (
        "provider_receipt_ref",
        "proof_ref",
        "receipt_ref",
        "receipt_id",
        "witness_id",
        "component_id",
    ):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            refs.append(value if "://" in value else f"{surface.value}://{field_name}/{value}")

    trace_scope = _mapping(record.get("trace_scope"))
    for field_name in ("instruction_trace_ref", "proof_ref", "unsupported_op_gap_ref"):
        value = trace_scope.get(field_name)
        if isinstance(value, str) and value.strip():
            refs.append(value)
    return _require_ref_tuple(tuple(refs), "evidence_refs", True)


def _metadata_refs(record: Mapping[str, Any], surface: SymbolAdapterSurface) -> tuple[str, ...]:
    refs = [f"metadata://{surface.value}/source-id"]
    for field_name in ("status", "solver_outcome", "proof_state", "stage", "outcome", "workflow_id"):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            refs.append(f"metadata://{surface.value}/{field_name}/{_bounded_symbol_segment(value)}")
    return _require_ref_tuple(tuple(refs), "metadata_refs", True)


def _record_refs(record: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = record.get(field_name)
    if value is None:
        return ()
    return _require_ref_tuple(value, field_name, False)


def _record_peer_refs(surface: SymbolAdapterSurface) -> tuple[str, ...]:
    if surface is SymbolAdapterSurface.SCCML_TRACE:
        return ("schemas/sccml_trace_adapter_witness.schema.json",)
    if surface is SymbolAdapterSurface.SOFTWARE_DEV_RECEIPT:
        return ("mcoi_runtime.contracts.software_dev_loop.SoftwareChangeReceipt",)
    if surface is SymbolAdapterSurface.TEAMOPS_RECEIPT:
        return ("schemas/team_ops_shared_inbox_provider_observation_receipt.schema.json",)
    if surface is SymbolAdapterSurface.COMPONENT_REGISTRY_ENTRY:
        return ("schemas/component_registry.schema.json",)
    if surface is SymbolAdapterSurface.WORKER_RECEIPT:
        return ("schemas/worker_failure_receipt.schema.json",)
    return ("schemas/universal_symbol.schema.json",)


def _receipt_refs(source: SymbolAdapterSource) -> tuple[str, ...]:
    if source.symbol_kind == "receipt":
        return (source.origin_ref,)
    return ()


def _default_label(surface: SymbolAdapterSurface, source_id: str, record: Mapping[str, Any]) -> str:
    stage = record.get("stage")
    if isinstance(stage, str) and stage.strip():
        return f"{surface.value} {stage} {source_id}"
    return f"{surface.value} {source_id}"


def _default_definition(surface: SymbolAdapterSurface) -> str:
    return (
        "Foundation Mode digest-only UniversalSymbol projection for an existing "
        f"{surface.value} source record."
    )


def _require_ref_tuple(values: Any, field_name: str, non_empty: bool) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RuntimeCoreInvariantError(f"{field_name} must be an array")
    refs: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise RuntimeCoreInvariantError(f"{field_name}[{index}] must be a non-empty string")
        normalized_value = value.strip()
        if normalized_value in seen:
            raise RuntimeCoreInvariantError(f"{field_name} must not contain duplicate refs")
        seen.add(normalized_value)
        refs.append(normalized_value)
    if non_empty and not refs:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return tuple(refs)


def _require_symbol_segment(field_name: str, value: str) -> str:
    segment = ensure_non_empty_text(field_name, value)
    if not _SAFE_SYMBOL_SEGMENT.fullmatch(segment):
        raise RuntimeCoreInvariantError(f"{field_name} must be a safe UniversalSymbol id segment")
    return segment


def _require_symbol_kind(value: str) -> str:
    kind = ensure_non_empty_text("symbol_kind", value)
    if kind not in {
        "concept",
        "skill",
        "component",
        "receipt",
        "action",
        "question",
        "answer",
        "metadata",
        "relation",
        "trace",
        "proof",
        "failure",
        "unknown",
        "policy",
        "boundary",
        "artifact",
    }:
        raise RuntimeCoreInvariantError("symbol_kind must be a UniversalSymbol kind")
    return kind


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_text(value: Any) -> str:
    return value if isinstance(value, str) and value.strip() else ""


def _bounded_symbol_segment(value: str) -> str:
    text = ensure_non_empty_text("symbol segment", value).strip().lower()
    segment = re.sub(r"[^a-z0-9._:-]+", "-", text).strip("-")
    if not segment:
        raise RuntimeCoreInvariantError("symbol segment must contain safe characters")
    return segment


def _merge_unique(*groups: Sequence[str]) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            if value not in seen:
                seen.add(value)
                refs.append(value)
    return tuple(refs)


def _stable_hex16(payload: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeCoreInvariantError("symbol id payload must be deterministic JSON") from exc
    return sha256(encoded.encode("utf-8")).hexdigest()[:16]
