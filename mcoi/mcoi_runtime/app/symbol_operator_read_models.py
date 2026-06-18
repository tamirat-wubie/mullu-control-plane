"""Purpose: build read-only UniversalSymbol operator projections.
Governance scope: Foundation Mode symbol inspection only; no runtime authority.
Dependencies: component read model, worker receipt ledger fixture, and
UniversalSymbol skill adapter.
Invariants:
  - Projection is deterministic and side-effect free.
  - Source records are digest/ref only.
  - All UniversalSymbol authority fields remain denied.
  - Worker fixture projection never reads a live receipt store or dispatches work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from mcoi_runtime.app.component_read_model import build_component_read_model
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_iso_timestamp
from mcoi_runtime.core.symbol_skill_adapter import (
    AUTHORITY_DENIAL_FIELDS,
    SymbolAdapterSurface,
    universal_symbol_from_record,
)


SYMBOL_OPERATOR_READ_MODEL_VERSION = "universal_symbol_operator_read_model.v1"
SYMBOL_OPERATOR_GENERATED_AT = "2026-06-18T00:00:00+00:00"
DEFAULT_SYMBOL_OPERATOR_LIMIT = 25
MAX_SYMBOL_OPERATOR_LIMIT = 100
COMPONENT_SYMBOL_READ_MODEL_ID = "universal-symbol-component-read-model-foundation"
WORKER_RECEIPT_SYMBOL_READ_MODEL_ID = "universal-symbol-worker-receipt-read-model-foundation"


class SymbolOperatorReadModelError(ValueError):
    """Raised when a symbol operator read model cannot be built safely."""


def build_component_symbol_read_model(
    *,
    component_read_model: Mapping[str, Any] | None = None,
    limit: int = DEFAULT_SYMBOL_OPERATOR_LIMIT,
) -> dict[str, Any]:
    """Project Component Harness entries into read-only UniversalSymbol records."""

    _validate_limit(limit)
    read_model = dict(component_read_model) if component_read_model is not None else build_component_read_model()
    components = _object_list(read_model.get("components"), "component read model components")
    selected_components = components[:limit]
    source_refs = _mapping(read_model.get("source_refs"))
    symbols = [
        universal_symbol_from_record(
            _component_symbol_source_record(component, source_refs),
            SymbolAdapterSurface.COMPONENT_REGISTRY_ENTRY,
            generated_at=SYMBOL_OPERATOR_GENERATED_AT,
        )
        for component in selected_components
    ]
    summary = _mapping(read_model.get("summary"))
    return _symbol_operator_payload(
        read_model_id=COMPONENT_SYMBOL_READ_MODEL_ID,
        operation="component_symbol_read_model",
        source_surface=SymbolAdapterSurface.COMPONENT_REGISTRY_ENTRY.value,
        source_model_ref="component_read_model.foundation.v1",
        source_count=len(components),
        selected_count=len(selected_components),
        limit=limit,
        symbols=symbols,
        source_summary={
            "component_count": int(summary.get("component_count", len(components))),
            "proof_bound_count": int(summary.get("proof_bound_count", 0)),
            "awaiting_binding_count": int(summary.get("awaiting_binding_count", 0)),
            "blocked_component_count": int(summary.get("blocked_component_count", 0)),
        },
        evidence_refs=_merge_refs(
            (
                "mcoi/mcoi_runtime/app/component_read_model.py",
                "mcoi/mcoi_runtime/app/routers/components.py",
                "mcoi/mcoi_runtime/app/symbol_operator_read_models.py",
                "mcoi/tests/test_symbol_operator_read_models.py",
            ),
            tuple(str(value) for value in source_refs.values() if isinstance(value, str) and value),
        ),
    )


def build_worker_receipt_symbol_read_model(
    *,
    worker_read_model: Mapping[str, Any] | None = None,
    worker_read_model_path: Path | None = None,
    limit: int = DEFAULT_SYMBOL_OPERATOR_LIMIT,
) -> dict[str, Any]:
    """Project WorkerReceiptLedgerReadModel chains into UniversalSymbol records."""

    _validate_limit(limit)
    read_model = (
        dict(worker_read_model)
        if worker_read_model is not None
        else _load_json_object(worker_read_model_path or _repo_root() / "examples" / "worker_receipt_ledger_read_model.foundation.json")
    )
    source_scope = _mapping(read_model.get("source_scope"))
    if source_scope.get("source_receipt_store_live_read_performed") is not False:
        raise SymbolOperatorReadModelError("worker symbol projection requires source_receipt_store_live_read_performed=false")
    if source_scope.get("fixture_projection") is not True:
        raise SymbolOperatorReadModelError("worker symbol projection requires fixture_projection=true")

    chains = _object_list(read_model.get("receipt_chains"), "worker receipt chains")
    selected_chains = chains[:limit]
    generated_at = ensure_iso_timestamp(
        "generated_at",
        str(read_model.get("generated_at") or SYMBOL_OPERATOR_GENERATED_AT),
    )
    symbols = [
        universal_symbol_from_record(
            _worker_chain_symbol_source_record(chain, read_model),
            SymbolAdapterSurface.WORKER_RECEIPT,
            generated_at=generated_at,
        )
        for chain in selected_chains
    ]
    status_summary = _mapping(read_model.get("status_summary"))
    return _symbol_operator_payload(
        read_model_id=WORKER_RECEIPT_SYMBOL_READ_MODEL_ID,
        operation="worker_receipt_symbol_read_model",
        source_surface=SymbolAdapterSurface.WORKER_RECEIPT.value,
        source_model_ref="worker_receipt_ledger_read_model.v1",
        source_count=len(chains),
        selected_count=len(selected_chains),
        limit=limit,
        symbols=symbols,
        source_summary={
            "chain_count": int(status_summary.get("chain_count", len(chains))),
            "blocked_chain_count": int(status_summary.get("blocked_chain_count", 0)),
            "recovery_required_count": int(status_summary.get("recovery_required_count", 0)),
            "terminal_closure_allowed_count": int(status_summary.get("terminal_closure_allowed_count", 0)),
            "success_claim_allowed_count": int(status_summary.get("success_claim_allowed_count", 0)),
        },
        evidence_refs=_merge_refs(
            (
                "examples/worker_receipt_ledger_read_model.foundation.json",
                "schemas/worker_receipt_ledger_read_model.schema.json",
                "scripts/validate_worker_receipt_ledger_read_model.py",
                "tests/test_validate_worker_receipt_ledger_read_model.py",
                "mcoi/mcoi_runtime/app/symbol_operator_read_models.py",
                "mcoi/tests/test_symbol_operator_read_models.py",
            ),
            _string_sequence(read_model.get("evidence_refs")),
        ),
    )


def _symbol_operator_payload(
    *,
    read_model_id: str,
    operation: str,
    source_surface: str,
    source_model_ref: str,
    source_count: int,
    selected_count: int,
    limit: int,
    symbols: list[dict[str, Any]],
    source_summary: dict[str, int],
    evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "read_model_id": read_model_id,
        "read_model_version": SYMBOL_OPERATOR_READ_MODEL_VERSION,
        "operation": operation,
        "source_surface": source_surface,
        "source_model_ref": source_model_ref,
        "generated_at": SYMBOL_OPERATOR_GENERATED_AT,
        "governed": True,
        "foundation_mode": True,
        "read_model_is_not_execution_authority": True,
        "symbol_projection_is_read_only": True,
        "source_count": source_count,
        "selected_count": selected_count,
        "symbol_count": len(symbols),
        "limit": limit,
        "source_summary": source_summary,
        "authority_denial_fields": list(AUTHORITY_DENIAL_FIELDS),
        "symbols": symbols,
        "evidence_refs": list(evidence_refs),
    }
    payload.update({field_name: False for field_name in AUTHORITY_DENIAL_FIELDS})
    return payload


def _component_symbol_source_record(
    component: Mapping[str, Any],
    source_refs: Mapping[str, Any],
) -> dict[str, Any]:
    component_id = _required_text(component, "component_id", "component")
    lifecycle_receipt = _mapping(component.get("lifecycle_receipt"))
    authority_witness = _mapping(component.get("authority_witness"))
    route_binding = _mapping(component.get("route_binding"))
    proof_binding = _mapping(component.get("proof_binding"))
    return {
        "component_id": component_id,
        "name": _required_text(component, "name", f"component {component_id}"),
        "route_family": _required_text(component, "type", f"component {component_id}"),
        "status": _required_text(component, "state", f"component {component_id}"),
        "proof_state": str(authority_witness.get("proof_state", "awaiting_evidence")),
        "evidence_refs": _merge_refs(
            (f"component_read_model://component/{component_id}",),
            tuple(str(value) for value in source_refs.values() if isinstance(value, str) and value),
            _string_sequence(lifecycle_receipt.get("evidence_refs")),
            _string_sequence(authority_witness.get("evidence_refs")),
        ),
        "target_refs": _merge_refs(
            _string_sequence(route_binding.get("proof_surface_ids")),
            _string_sequence(proof_binding.get("required_surface_ids")),
            _string_sequence(proof_binding.get("inventory_surface_ids")),
        ),
        "constraint_refs": _merge_refs(
            tuple(f"blocked://component/{ref}" for ref in _string_sequence(component.get("blocked_actions"))),
            _string_sequence(lifecycle_receipt.get("validator_refs")),
            _string_sequence(authority_witness.get("validator_refs")),
        ),
    }


def _worker_chain_symbol_source_record(
    chain: Mapping[str, Any],
    read_model: Mapping[str, Any],
) -> dict[str, Any]:
    chain_id = _required_text(chain, "chain_id", "worker receipt chain")
    receipt_refs = _mapping(read_model.get("receipt_refs"))
    return {
        "receipt_id": chain_id,
        "worker_receipt_id": chain_id,
        "worker_id": _required_text(chain, "worker_id", f"worker receipt chain {chain_id}"),
        "status": _required_text(chain, "chain_status", f"worker receipt chain {chain_id}"),
        "solver_outcome": _required_text(chain, "latest_solver_outcome", f"worker receipt chain {chain_id}"),
        "evidence_refs": _merge_refs(
            (f"worker_receipt_ledger://chain/{chain_id}",),
            _string_sequence(chain.get("source_receipt_refs")),
            tuple(str(value) for value in receipt_refs.values() if isinstance(value, str) and value),
            _string_sequence(read_model.get("evidence_refs")),
        ),
        "target_refs": tuple(f"worker_receipt_kind://{ref}" for ref in _string_sequence(chain.get("receipt_kinds"))),
        "constraint_refs": _merge_refs(
            _string_sequence(chain.get("blocked_reason_refs")),
            _string_sequence(chain.get("recovery_obligation_refs")),
        ),
    }


def _validate_limit(limit: int) -> None:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise RuntimeCoreInvariantError("limit must be an integer")
    if limit < 1 or limit > MAX_SYMBOL_OPERATOR_LIMIT:
        raise RuntimeCoreInvariantError("limit must be between 1 and 100")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SymbolOperatorReadModelError(f"worker read model file missing: {_path_label(path)}") from exc
    except json.JSONDecodeError as exc:
        raise SymbolOperatorReadModelError(f"worker read model JSON parse failed: {_path_label(path)}") from exc
    if not isinstance(payload, dict):
        raise SymbolOperatorReadModelError("worker read model root must be an object")
    return payload


def _object_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise SymbolOperatorReadModelError(f"{label} must be a list")
    records: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise SymbolOperatorReadModelError(f"{label}[{index}] must be an object")
        records.append(item)
    return records


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _required_text(payload: Mapping[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SymbolOperatorReadModelError(f"{label} must carry non-empty {field_name}")
    return value


def _string_sequence(value: Any) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str) and item)


def _merge_refs(*groups: Sequence[str]) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            if value in seen:
                continue
            seen.add(value)
            refs.append(value)
    return tuple(refs)


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "examples" / "worker_receipt_ledger_read_model.foundation.json").exists():
            return candidate
    raise SymbolOperatorReadModelError("repository root with worker receipt ledger read model could not be found")


def _path_label(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.name
