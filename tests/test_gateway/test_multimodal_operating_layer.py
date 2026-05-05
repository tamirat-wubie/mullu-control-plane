"""Gateway multimodal operating layer tests.

Purpose: verify modality-bound worker dispatch is governed before adapter execution.
Governance scope: source references, evidence refs, external effects, review gates, and receipt schema.
Dependencies: gateway.multimodal_operating_layer and schemas/multimodal_operation_receipt.schema.json.
Invariants:
  - Unknown modalities fail closed.
  - External effects require production certification and live-write evidence.
  - Receipts preserve source and evidence references.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.multimodal_operating_layer import (
    ModalityWorkerPolicy,
    MultimodalOperatingLayer,
    MultimodalOperationRequest,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "multimodal_operation_receipt.schema.json"


def test_multimodal_layer_allows_read_with_source_and_evidence() -> None:
    receipt = MultimodalOperatingLayer().evaluate(_request())

    assert receipt.status == "allowed"
    assert receipt.reason == "operation_allowed"
    assert receipt.source_reference_preserved is True
    assert receipt.worker_receipt_required is True
    assert receipt.terminal_closure_required is True
    assert receipt.receipt_id.startswith("multimodal-receipt-")


def test_multimodal_layer_blocks_unknown_modality() -> None:
    receipt = MultimodalOperatingLayer().evaluate(_request(modality="unknown", operation="inspect"))

    assert receipt.status == "blocked"
    assert receipt.reason == "modality_not_registered"
    assert "modality_not_registered" in receipt.blocked_reasons
    assert receipt.worker_plane == ""


def test_external_effect_requires_certified_worker_and_live_write_evidence() -> None:
    policy = ModalityWorkerPolicy(
        policy_id="multimodal-policy:email:test",
        modality="email",
        worker_plane="email/calendar",
        allowed_operations=("send_external",),
        side_effect_operations=("send_external",),
        external_effects_allowed=True,
        production_certified=True,
        maturity_level="C6",
    )
    receipt = MultimodalOperatingLayer({"email": policy}).evaluate(
        _request(
            modality="email",
            operation="send_external",
            declared_controls=("approval", "signed_worker_response"),
        )
    )

    assert receipt.status == "requires_review"
    assert receipt.reason == "live_write_receipt_evidence_required"
    assert "live_write_receipt_evidence_required" in receipt.review_reasons
    assert "live_write_receipt" in receipt.required_controls


def test_multimodal_layer_blocks_uncertified_external_effects() -> None:
    receipt = MultimodalOperatingLayer().evaluate(_request(modality="email", operation="send_external"))

    assert receipt.status == "blocked"
    assert "operation_forbidden" in receipt.blocked_reasons
    assert "external_effect_not_allowed" in receipt.blocked_reasons
    assert "production_certification_required" in receipt.blocked_reasons
    assert "capability_maturity_below_C6" in receipt.blocked_reasons


def test_multimodal_receipt_schema_exposes_source_preservation_contract() -> None:
    receipt = MultimodalOperatingLayer().evaluate(_request())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(receipt.to_json_dict())
    assert schema["$id"] == "urn:mullusi:schema:multimodal-operation-receipt:1"
    assert schema["properties"]["terminal_closure_required"]["const"] is True
    assert receipt.receipt_schema_ref == "urn:mullusi:schema:multimodal-operation-receipt:1"


def _request(**overrides: object) -> MultimodalOperationRequest:
    payload = {
        "request_id": "mm-req-1",
        "tenant_id": "tenant-a",
        "command_id": "command-1",
        "capability_id": "capability-document-read",
        "modality": "pdf",
        "operation": "parse",
        "source_ref": "source://document/1",
        "source_hash": "hash-doc-1",
        "sensitivity": "internal",
        "evidence_refs": ("proof://source-bound", "proof://worker-policy"),
        "declared_controls": ("tenant_binding", "source_reference", "worker_receipt", "terminal_closure"),
    }
    payload.update(overrides)
    return MultimodalOperationRequest(**payload)
