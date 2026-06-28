"""Forge state-write admission tests.

Purpose: verify the Forge write-spine admission adapter can admit a local
prepared-transition model without granting runtime commit or production
authority.
Governance scope: Phi_gov certificate binding, H_lineage stage order,
Foundation Mode production denial, and non-mutating admission receipts.
Dependencies: gateway.forge_state_write_admission and admission packet schema.
Invariants:
  - Valid local evidence admits only a prepared transition model.
  - Live mutation and commit authority remain false.
  - Production, reordered stages, certificate drift, and premature mutation
    fail closed.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.forge_state_write_admission import (
    EXPECTED_CERTIFICATE_FIELDS,
    ForgeStateWriteCertificateEvidence,
    build_foundation_forge_state_write_request,
    evaluate_forge_state_write_admission,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "forge_state_write_admission_packet.schema.json"


def test_valid_foundation_request_admits_prepare_model_without_commit() -> None:
    request = build_foundation_forge_state_write_request()
    receipt = evaluate_forge_state_write_admission(request)

    assert receipt.status == "reference_prepare_admitted"
    assert receipt.admission_decision == "allow_prepare_model"
    assert receipt.prepared_transition_model_allowed is True
    assert receipt.commit_allowed is False
    assert receipt.live_mutation_allowed is False
    assert receipt.production_authorized is False
    assert receipt.state_write_runtime_registered is False
    assert receipt.external_effects_allowed is False
    assert receipt.blocked_reasons == []
    assert receipt.receipt_id.startswith("forge-state-write-admission-receipt-")
    assert len(receipt.receipt_hash) == 64


def test_packet_built_from_foundation_request_matches_schema() -> None:
    from gateway.forge_state_write_admission import build_forge_state_write_admission_packet

    packet = build_forge_state_write_admission_packet(build_foundation_forge_state_write_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), packet)

    assert errors == []
    assert packet["receipt"]["commit_allowed"] is False
    assert packet["receipt"]["prepared_transition_model_allowed"] is True
    assert packet["invariants"]["reference_only"] is True


def test_production_state_changing_request_is_blocked() -> None:
    request = replace(
        build_foundation_forge_state_write_request(),
        requested_environment="production_state_changing",
    )
    receipt = evaluate_forge_state_write_admission(request)

    assert receipt.status == "blocked"
    assert receipt.admission_decision == "block"
    assert receipt.prepared_transition_model_allowed is False
    assert receipt.commit_allowed is False
    assert "production_state_changing_no_go" in receipt.blocked_reasons
    assert "production_or_read_only_environment_not_admitted" in receipt.blocked_reasons


def test_reordered_stage_evidence_is_blocked() -> None:
    request = build_foundation_forge_state_write_request()
    reordered_stages = [request.stages[1], request.stages[0], *request.stages[2:]]
    receipt = evaluate_forge_state_write_admission(replace(request, stages=reordered_stages))

    assert receipt.status == "blocked"
    assert receipt.prepared_transition_model_allowed is False
    assert "write_spine_stage_order_invalid" in receipt.blocked_reasons
    assert receipt.commit_allowed is False


def test_certificate_field_drift_and_lifetime_excess_are_blocked() -> None:
    request = build_foundation_forge_state_write_request()
    certificate = ForgeStateWriteCertificateEvidence(
        **{
            **asdict(request.certificate),
            "required_fields": list(reversed(EXPECTED_CERTIFICATE_FIELDS)),
            "expires_at": "2026-06-27T13:00:01+00:00",
        }
    )
    receipt = evaluate_forge_state_write_admission(replace(request, certificate=certificate))

    assert receipt.status == "blocked"
    assert "certificate_required_fields_invalid" in receipt.blocked_reasons
    assert "certificate_lifetime_exceeds_policy" in receipt.blocked_reasons
    assert receipt.live_mutation_allowed is False


def test_premature_mutation_and_service_production_authority_are_blocked() -> None:
    request = build_foundation_forge_state_write_request()
    service_boundary = replace(request.service_boundary, production_authorized=True)
    receipt = evaluate_forge_state_write_admission(
        replace(request, mutation_performed=True, service_boundary=service_boundary)
    )

    assert receipt.status == "blocked"
    assert "mutation_performed_before_admission" in receipt.blocked_reasons
    assert "service_boundary_production_authorized_forbidden" in receipt.blocked_reasons
    assert receipt.production_authorized is False
    assert receipt.commit_allowed is False
