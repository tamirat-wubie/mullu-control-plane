"""
Substrate persistence — JSON snapshots per tenant.

Each tenant's full registry (constructs + dependent edges) serializes to a
single JSON file. Snapshots are atomic (temp file + rename) so a crash
mid-write does not leave a half-readable file.

What is NOT persisted:
  - Φ_agent filters (they are Python callables; cannot serialize)
  - The MUSIA_MODE flag (still doesn't exist in code; see PHASE_2_NOTES)

Production deployments restore filters at startup via
`install_phi_agent_filter(filter, tenant_id)` after `load_tenant()`.

Schema version is recorded so future changes can migrate cleanly. v1
covers all 25 construct types as of v4.4.0.
"""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from mcoi_runtime.substrate.cascade import DependencyGraph
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    Composition,
    Conservation,
    ConstructBase,
    ConstructType,
    Constraint,
    Coupling,
    Decision,
    Emergence,
    Equilibrium,
    Evolution,
    Execution,
    Inference,
    Integrity,
    Interaction,
    Learning,
    MfidelSignature,
    Observation,
    Pattern,
    Resonance,
    Source,
    State,
    Synchronization,
    Tier,
    Transformation,
    Validation,
    Binding,
)


SCHEMA_VERSION = "1"


# Map ConstructType → dataclass class. Required for deserialization.
_TYPE_TO_CLASS: dict[ConstructType, type[ConstructBase]] = {
    # Tier 1
    ConstructType.STATE: State,
    ConstructType.CHANGE: Change,
    ConstructType.CAUSATION: Causation,
    ConstructType.CONSTRAINT: Constraint,
    ConstructType.BOUNDARY: Boundary,
    # Tier 2
    ConstructType.PATTERN: Pattern,
    ConstructType.TRANSFORMATION: Transformation,
    ConstructType.COMPOSITION: Composition,
    ConstructType.INTERACTION: Interaction,
    ConstructType.CONSERVATION: Conservation,
    # Tier 3
    ConstructType.COUPLING: Coupling,
    ConstructType.SYNCHRONIZATION: Synchronization,
    ConstructType.RESONANCE: Resonance,
    ConstructType.EQUILIBRIUM: Equilibrium,
    ConstructType.EMERGENCE: Emergence,
    # Tier 4
    ConstructType.SOURCE: Source,
    ConstructType.BINDING: Binding,
    ConstructType.VALIDATION: Validation,
    ConstructType.EVOLUTION: Evolution,
    ConstructType.INTEGRITY: Integrity,
    # Tier 5
    ConstructType.OBSERVATION: Observation,
    ConstructType.INFERENCE: Inference,
    ConstructType.DECISION: Decision,
    ConstructType.EXECUTION: Execution,
    ConstructType.LEARNING: Learning,
}


def _verify_type_registry_complete() -> None:
    """Every ConstructType value must map to a class. Module load fails otherwise."""
    missing = set(ConstructType) - set(_TYPE_TO_CLASS.keys())
    if missing:
        raise RuntimeError(
            f"persistence type registry is incomplete: missing {sorted(t.value for t in missing)}"
        )


_verify_type_registry_complete()


# ---- Serialization ----


def _value_to_jsonable(v: Any) -> Any:
    """Recursively convert a value to a JSON-friendly form.

    Handles: UUID, datetime, Enum, MfidelSignature, tuple, set, dict, list,
    primitives. Falls back to str() for unknown types (lossy but safe).
    """
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, MfidelSignature):
        return {"coords": [list(c) for c in v.coords]}
    if isinstance(v, (tuple, list)):
        return [_value_to_jsonable(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted([_value_to_jsonable(x) for x in v], key=str)
    if isinstance(v, dict):
        return {str(k): _value_to_jsonable(val) for k, val in v.items()}
    return str(v)  # last resort


def construct_to_dict(c: ConstructBase) -> dict[str, Any]:
    """Serialize a construct to a JSON-friendly dict."""
    d: dict[str, Any] = {}
    for f in dataclasses.fields(c):
        d[f.name] = _value_to_jsonable(getattr(c, f.name))
    return d


# Field name → reconstruction strategy. UUID-typed fields need explicit
# conversion since they round-trip through strings; tuples need rebuilding
# from JSON lists; sets likewise.
_UUID_FIELDS = {
    # Most cross-construct references in Tier 2-5 use these names.
    "id",
    "state_before_id", "state_after_id",
    "cause_id", "effect_id",
    "initial_state_id", "target_state_id",
    "change_id", "causation_id", "boundary_id",
    "container_pattern_id",
    "invariant_pattern_id", "enforcing_constraint_id", "scope_boundary_id",
    "source_id", "target_id",
    "pattern_id", "basin_boundary_id", "novel_pattern_id",
    "current_constraint_id", "proposed_constraint_id",
    "consequence_change_id",
    "target_pattern_id",
    "interpreted_state_id", "conclusion_id", "chosen_option_id",
    "decision_id", "produced_change_id",
    "extracted_pattern_id", "integration_target_id", "validation_id",
}

_UUID_TUPLE_FIELDS = {
    # Tuples of UUIDs.
    "instance_state_ids",
    "contained_pattern_ids",
    "participant_state_ids",
    "causation_ids",
    "pattern_ids",
    "attractor_state_ids",
    "component_ids",
    "interaction_ids",
    "core_invariant_pattern_ids",
    "premise_ids",
    "option_ids",
    "experience_execution_ids",
}

_STRING_TUPLE_FIELDS = {
    "interface_points",
    "variation_tolerance",
    "criteria",
    "evidence_refs",
    "resource_allocations",
    "monitoring_endpoints",
    "invariants",
}


def dict_to_construct(d: dict[str, Any]) -> ConstructBase:
    """Reconstruct a construct from a serialized dict."""
    payload = dict(d)  # don't mutate caller

    type_value = payload.get("type")
    if not type_value:
        raise ValueError("serialized construct missing 'type'")
    try:
        ct = ConstructType(type_value)
    except ValueError:
        raise ValueError(f"unknown construct type: {type_value!r}")

    cls = _TYPE_TO_CLASS[ct]

    # Type and tier as enums
    payload["type"] = ct
    if "tier" in payload and not isinstance(payload["tier"], Tier):
        payload["tier"] = Tier(payload["tier"])

    # id
    if "id" in payload and isinstance(payload["id"], str):
        payload["id"] = UUID(payload["id"])

    # created_at
    if "created_at" in payload and isinstance(payload["created_at"], str):
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])

    # invariants — tuple of strings
    if "invariants" in payload and isinstance(payload["invariants"], list):
        payload["invariants"] = tuple(payload["invariants"])

    # mfidel_signature
    if payload.get("mfidel_signature") is not None and isinstance(
        payload["mfidel_signature"], dict
    ):
        sig = payload["mfidel_signature"]
        coords = tuple((int(c[0]), int(c[1])) for c in sig.get("coords", []))
        payload["mfidel_signature"] = MfidelSignature(coords=coords) if coords else None

    # Convert known UUID fields
    for f in dataclasses.fields(cls):
        if f.name not in payload:
            continue
        val = payload[f.name]
        if val is None:
            continue
        if f.name in _UUID_FIELDS and isinstance(val, str):
            payload[f.name] = UUID(val)
        elif f.name in _UUID_TUPLE_FIELDS and isinstance(val, list):
            payload[f.name] = tuple(UUID(x) for x in val)
        elif f.name in _STRING_TUPLE_FIELDS and isinstance(val, list):
            payload[f.name] = tuple(val)

    # Trim payload to only fields the dataclass accepts
    field_names = {f.name for f in dataclasses.fields(cls)}
    cleaned = {k: v for k, v in payload.items() if k in field_names}

    return cls(**cleaned)


# ---- Snapshot format ----


def snapshot_graph(
    tenant_id: str,
    graph: DependencyGraph,
    *,
    quota: Any = None,
) -> dict[str, Any]:
    """Serialize a tenant's dependency graph to a JSON-friendly dict.

    The optional ``quota`` argument (v4.10.0+) lets callers persist the
    tenant's quota alongside the graph. When None, no quota field is
    written; readers default to TenantQuota() on load.
    """
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "constructs": [construct_to_dict(c) for c in graph.constructs.values()],
        "dependents": {
            str(k): sorted(str(d) for d in v)
            for k, v in graph.dependents.items()
            if v
        },
    }
    if quota is not None:
        payload["quota"] = {
            "max_constructs": quota.max_constructs,
            "max_writes_per_window": quota.max_writes_per_window,
            "window_seconds": quota.window_seconds,
        }
    return payload


def restore_quota_from_payload(payload: dict[str, Any]) -> Any:
    """Restore a TenantQuota from a snapshot payload. Returns None if absent.

    v4.14.1+: TenantQuota lives in substrate/_quota.py to keep this module
    free of a registry_store dependency (which would create a cycle since
    registry_store also needs FileBackedPersistence).
    """
    raw = payload.get("quota")
    if raw is None:
        return None
    from mcoi_runtime.substrate._quota import TenantQuota
    return TenantQuota(
        max_constructs=raw.get("max_constructs"),
        max_writes_per_window=raw.get("max_writes_per_window"),
        window_seconds=raw.get("window_seconds", 3600),
    )


def restore_graph(payload: dict[str, Any]) -> DependencyGraph:
    """Rebuild a DependencyGraph from a snapshot dict."""
    schema = payload.get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version: {schema!r} "
            f"(this build understands {SCHEMA_VERSION!r})"
        )

    graph = DependencyGraph()

    # Reconstruct constructs and re-register without dependencies first
    # (dependents are restored separately because they are derived edges, not
    # construct-internal references).
    constructs: list[ConstructBase] = []
    for c_dict in payload.get("constructs", []):
        constructs.append(dict_to_construct(c_dict))

    for c in constructs:
        graph.constructs[c.id] = c

    # Restore dependent edges
    raw_dependents = payload.get("dependents", {})
    for src, deps in raw_dependents.items():
        src_id = UUID(src)
        graph.dependents.setdefault(src_id, set()).update(UUID(d) for d in deps)

    return graph


# ---- File-backed persistence ----


class FileBackedPersistence:
    """JSON-file-per-tenant persistence.

    Files: ``<directory>/registry-<tenant_id>.json``.
    Atomic writes: write to ``<file>.tmp`` then ``os.replace`` so partial
    writes are never observed by a reader.

    The directory is created on first use.
    """

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, tenant_id: str) -> Path:
        if not tenant_id:
            raise ValueError("tenant_id must be non-empty")
        # Conservative filename: replace separators with _
        safe = tenant_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"registry-{safe}.json"

    def save(
        self,
        tenant_id: str,
        graph: DependencyGraph,
        *,
        quota: Any = None,
    ) -> Path:
        """Atomically write a snapshot for one tenant. Returns the file path.

        v4.10.0+: optional ``quota`` is included in the snapshot if provided.
        """
        target = self.path_for(tenant_id)
        snapshot = snapshot_graph(tenant_id, graph, quota=quota)

        # Atomic write via temp file
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"registry-{tenant_id.replace('/', '_')}-",
            suffix=".tmp",
            dir=str(self._dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        return target

    def load(self, tenant_id: str) -> DependencyGraph | None:
        """Load the saved snapshot for one tenant, or None if no file exists.

        Returns only the graph; for the quota too, use ``load_with_quota``.
        Kept as the public method for back-compat with v4.4–v4.9 callers.
        """
        target = self.path_for(tenant_id)
        if not target.exists():
            return None
        with open(target, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return restore_graph(payload)

    def load_with_quota(
        self, tenant_id: str
    ) -> tuple[DependencyGraph, Any] | None:
        """Load graph + quota. Returns (graph, quota_or_None). v4.10.0+."""
        target = self.path_for(tenant_id)
        if not target.exists():
            return None
        with open(target, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return restore_graph(payload), restore_quota_from_payload(payload)

    def list_tenants(self) -> list[str]:
        """Tenants with persisted snapshots in this directory."""
        out: list[str] = []
        for p in self._dir.glob("registry-*.json"):
            name = p.name
            if name.startswith("registry-") and name.endswith(".json"):
                out.append(name[len("registry-"):-len(".json")])
        return sorted(out)

    def delete(self, tenant_id: str) -> bool:
        """Remove a tenant's snapshot. Returns True if a file was removed."""
        target = self.path_for(tenant_id)
        if target.exists():
            target.unlink()
            return True
        return False
