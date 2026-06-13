"""Purpose: read-only operator projection for bounded SNet mesh state.
Governance scope: local SNet counts, settlement summary, bounded symbol
    projection, receipt emission, and no-effect operator visibility.
Dependencies: SNet engine, SNet contracts, hashlib, and typing.
Invariants:
  - Raw answers and raw metadata values are not exposed.
  - The projection grants no execution, connector, filesystem, or route authority.
  - Symbol summaries are bounded by caller-provided limits.
  - Receipts are deterministic for a given mesh state.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from mcoi_runtime.contracts.snet import (
    SNET_READ_ONLY_SURFACE,
    SNET_SEMANTICS_HASH,
    SNET_VERSION,
    SNetMeshReceipt,
    SNetSettlementState,
    SNetSymbol,
)
from mcoi_runtime.snet.engine import SNetRecursiveMesh


SNET_OPERATOR_SURFACE = SNET_READ_ONLY_SURFACE


def build_snet_operator_read_model(
    mesh: SNetRecursiveMesh,
    *,
    max_symbol_count: int = 20,
) -> dict[str, Any]:
    """Build a bounded read-only SNet projection for operator review."""
    if not isinstance(max_symbol_count, int) or isinstance(max_symbol_count, bool) or max_symbol_count < 0:
        raise ValueError("max_symbol_count must be a non-negative integer")

    receipt = create_snet_mesh_receipt(mesh)
    symbols = sorted(
        mesh.symbols.values(),
        key=lambda symbol: (symbol.depth, symbol.label, symbol.symbol_id),
    )
    selected_symbols = tuple(symbols[:max_symbol_count])
    return {
        "enabled": True,
        "surface": SNET_OPERATOR_SURFACE,
        "raw_answers_exposed": False,
        "raw_metadata_values_exposed": False,
        "execution_authority_granted": False,
        "connector_authority_granted": False,
        "route_authority_granted": False,
        "filesystem_authority_granted": False,
        "symbol_count": receipt.symbol_count,
        "question_count": receipt.question_count,
        "answer_count": receipt.answer_count,
        "metadata_count": receipt.metadata_count,
        "relation_count": receipt.relation_count,
        "unknown_count": receipt.unknown_count,
        "contradiction_count": receipt.contradiction_count,
        "settlement_counts": receipt.to_json_dict()["settlement_counts"],
        "selected_symbols": [_symbol_summary(symbol) for symbol in selected_symbols],
        "truncated_symbol_count": max(0, receipt.symbol_count - len(selected_symbols)),
        "receipt": receipt.to_json_dict(),
    }


def create_snet_mesh_receipt(mesh: SNetRecursiveMesh) -> SNetMeshReceipt:
    """Create a deterministic read-only receipt for one SNet mesh state."""
    settlement_counts = _settlement_counts(mesh)
    mesh_digest = _mesh_digest(mesh, settlement_counts)
    receipt_material = "|".join(
        (
            SNET_VERSION,
            SNET_SEMANTICS_HASH,
            mesh_digest,
            str(len(mesh.symbols)),
            str(len(mesh.questions)),
            str(len(mesh.answers)),
            str(len(mesh.metadata)),
            str(len(mesh.relations)),
            str(len(mesh.unknowns)),
            str(len(mesh.contradictions)),
            str(mesh.budget.max_depth),
            f"{mesh.budget.promotion_threshold:.6f}",
            ",".join(f"{key}:{settlement_counts[key]}" for key in sorted(settlement_counts)),
        )
    )
    receipt_id = f"snet-mesh-{sha256(receipt_material.encode('utf-8')).hexdigest()[:16]}"
    return SNetMeshReceipt(
        receipt_id=receipt_id,
        snet_version=SNET_VERSION,
        semantics_hash=SNET_SEMANTICS_HASH,
        mesh_digest=mesh_digest,
        surface=SNET_OPERATOR_SURFACE,
        symbol_count=len(mesh.symbols),
        question_count=len(mesh.questions),
        answer_count=len(mesh.answers),
        metadata_count=len(mesh.metadata),
        relation_count=len(mesh.relations),
        unknown_count=len(mesh.unknowns),
        contradiction_count=len(mesh.contradictions),
        max_depth=mesh.budget.max_depth,
        promotion_threshold=mesh.budget.promotion_threshold,
        settlement_counts=settlement_counts,
        connector_authority_granted=False,
        route_authority_granted=False,
        filesystem_authority_granted=False,
        evidence_refs=(
            f"snet:mesh_digest:{mesh_digest}",
            f"snet:symbols:{len(mesh.symbols)}",
            f"snet:questions:{len(mesh.questions)}",
            f"snet:metadata:{len(mesh.metadata)}",
            f"snet:relations:{len(mesh.relations)}",
            f"snet:unknowns:{len(mesh.unknowns)}",
            f"snet:contradictions:{len(mesh.contradictions)}",
        ),
    )


def _mesh_digest(mesh: SNetRecursiveMesh, settlement_counts: dict[str, int]) -> str:
    digest_payload = {
        "budget": {
            "max_depth": mesh.budget.max_depth,
            "max_questions_per_symbol": mesh.budget.max_questions_per_symbol,
            "promotion_threshold": mesh.budget.promotion_threshold,
            "unknown_gravity_threshold": mesh.budget.unknown_gravity_threshold,
        },
        "settlement_counts": settlement_counts,
        "symbols": [
            [symbol.symbol_id, symbol.settlement_state.value, symbol.depth]
            for symbol in sorted(mesh.symbols.values(), key=lambda item: item.symbol_id)
        ],
        "questions": sorted(mesh.questions),
        "answers": sorted(mesh.answers),
        "metadata": [
            [
                record.metadata_id,
                record.parent_symbol_id,
                record.promoted_symbol_id,
                f"{record.promotion_score:.6f}",
                record.validation_state.value,
            ]
            for record in sorted(mesh.metadata.values(), key=lambda item: item.metadata_id)
        ],
        "relations": sorted(mesh.relations),
        "unknowns": sorted(mesh.unknowns),
        "contradictions": [
            [record.contradiction_id, record.resolution_state.value]
            for record in sorted(mesh.contradictions.values(), key=lambda item: item.contradiction_id)
        ],
    }
    encoded_payload = json.dumps(
        digest_payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"sha256:{sha256(encoded_payload.encode('utf-8')).hexdigest()}"


def _settlement_counts(mesh: SNetRecursiveMesh) -> dict[str, int]:
    counts: dict[str, int] = {state.value: 0 for state in SNetSettlementState}
    for symbol in mesh.symbols.values():
        counts[symbol.settlement_state.value] = counts.get(symbol.settlement_state.value, 0) + 1
    return counts


def _symbol_summary(symbol: SNetSymbol) -> dict[str, Any]:
    return {
        "symbol_id": symbol.symbol_id,
        "label": symbol.label,
        "symbol_type": symbol.symbol_type,
        "sense_id": symbol.sense_id,
        "ontology_status": symbol.ontology_status.value,
        "settlement_state": symbol.settlement_state.value,
        "depth": symbol.depth,
        "parent_context": symbol.parent_context,
        "metadata_count": len(symbol.metadata_refs),
        "relation_count": len(symbol.relation_refs),
        "inquiry_count": len(symbol.inquiry_history),
    }
