"""Gateway multimodal operating layer tests.

Purpose: verify modality-bound operations remain source-referenced, worker
policy gated, schema-backed, and explicitly non-terminal.
Governance scope: multimodal operation admission, source preservation,
sensitive-data controls, external-effect controls, and receipt compatibility.
Dependencies: gateway.multimodal_operating_layer and public receipt schema.
Invariants:
  - Allowed operations emit schema-valid receipts.
  - Unknown modalities fail closed with a receipt.
  - Sensitive inputs require redaction evidence before dispatch.
  - External effects require certification, approval, signed worker evidence,
    and live-write receipts.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.multimodal_operating_layer import (
    ModalityWorkerPolicy,
    MultimodalOperatingLayer,
    MultimodalOperationRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "multimodal_operation_receipt.schema.json"
FIXED_TIME = "2026-05-05T13:00:00+00:00"


def test_pdf_extract_fields_emits_schema_valid_source_bound_receipt() -> None:
    layer = MultimodalOperatingLayer(clock=lambda: FIXED_TIME)
    receipt = layer.evaluate(_request(), _policy())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "allowed"
    assert receipt.receipt_id.startswith("multimodal-receipt-")
    assert receipt.source_ref == "doc://invoice-001"
    assert receipt.source_hash == "sha256:" + "2" * 64
    assert receipt.source_reference_preserved is True
    assert receipt.worker_receipt_required is True
    assert receipt.terminal_closure_required is True
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True
    assert receipt.metadata["dispatch_allowed"] is True


def test_email_external_send_is_blocked_by_default() -> None:
    layer = MultimodalOperatingLayer(clock=lambda: FIXED_TIME)
    receipt = layer.evaluate(
        replace(
            _request(),
            modality="email",
            operation="send_email",
            external_effect=True,
        ),
        replace(
            _policy(),
            modalities=["email"],
            allowed_operations=["send_email"],
            maturity_level="C4",
        ),
    )

    assert receipt.status == "blocked"
    assert "external_effect_not_allowed" in receipt.blocked_reasons
    assert "production_certification_required" in receipt.blocked_reasons
    assert "capability_maturity_below_C6" in receipt.blocked_reasons
    assert "approval" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.terminal_closure_required is True


def test_sensitive_voice_transcription_requires_redaction_evidence() -> None:
    layer = MultimodalOperatingLayer(clock=lambda: FIXED_TIME)
    receipt = layer.evaluate(
        replace(
            _request(),
            modality="voice",
            operation="transcribe",
            sensitivity_level="restricted",
        ),
        replace(
            _policy(),
            modalities=["voice"],
            allowed_operations=["transcribe"],
            allowed_sensitive_levels=["public", "internal", "restricted"],
        ),
    )

    assert receipt.status == "requires_review"
    assert receipt.blocked_reasons == []
    assert "pii_redaction" in receipt.required_controls
    assert "pii_redaction_evidence_required" in receipt.review_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["sensitivity_level"] == "restricted"


def test_unknown_modality_fails_closed_with_schema_valid_receipt() -> None:
    layer = MultimodalOperatingLayer(clock=lambda: FIXED_TIME)
    receipt = layer.evaluate(replace(_request(), modality="hologram"), _policy())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.modality == "unknown"
    assert receipt.metadata["original_modality"] == "hologram"
    assert "unknown_modality" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.receipt_hash


def test_certified_external_send_can_be_allowed_with_required_evidence() -> None:
    layer = MultimodalOperatingLayer(clock=lambda: FIXED_TIME)
    receipt = layer.evaluate(
        replace(
            _request(),
            modality="email",
            operation="send_email",
            external_effect=True,
            evidence_refs=[
                "source:evidence:invoice-001",
                "approval:manager-1",
                "worker:signed:mail-1",
                "live_write_receipt:mail-1",
            ],
        ),
        replace(
            _policy(),
            modalities=["email"],
            allowed_operations=["send_email"],
            maturity_level="C6",
            production_certified=True,
            external_effects_allowed=True,
        ),
    )

    assert receipt.status == "allowed"
    assert receipt.blocked_reasons == []
    assert receipt.review_reasons == []
    assert "signed_worker_response" in receipt.required_controls
    assert "live_write_receipt" in receipt.required_controls
    assert receipt.metadata["production_certified"] is True
    assert receipt.metadata["dispatch_allowed"] is True


def _policy() -> ModalityWorkerPolicy:
    return ModalityWorkerPolicy(
        worker_id="worker-multimodal-1",
        capability="document.extract",
        modalities=["pdf"],
        allowed_operations=["extract_fields"],
        policy_refs=["policy:multimodal:1"],
    )


def _request() -> MultimodalOperationRequest:
    return MultimodalOperationRequest(
        request_id="multimodal-request-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        worker_id="worker-multimodal-1",
        capability="document.extract",
        modality="pdf",
        operation="extract_fields",
        command_id="command-1",
        input_hash="sha256:" + "1" * 64,
        source_ref="doc://invoice-001",
        source_hash="sha256:" + "2" * 64,
        evidence_refs=["source:evidence:invoice-001"],
        requested_at="2026-05-05T12:59:00+00:00",
    )
