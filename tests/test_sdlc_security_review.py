"""Purpose: verify governed SDLC security review validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_security_review.
Invariants:
  - Critical/high open findings block release.
  - Failed required checks are rejected.
  - Impact categories require mapped checks.
"""

from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout
from pathlib import Path

from scripts import validate_sdlc_artifact
from scripts import validate_sdlc_security_review as validator


def test_current_sdlc_security_review_passes_strict() -> None:
    errors = validator.validate_contract(strict=True)

    assert errors == []
    assert validate_sdlc_artifact.ARTIFACT_SPEC_BY_KIND["security_review"].example_path.exists()
    assert "policy" in validate_sdlc_artifact.load_example_records()["security_review"]["impact_categories"]


def test_open_high_finding_blocks_release() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])
    review["findings"] = [
        {
            "finding_id": "finding-high",
            "severity": "high",
            "status": "open",
            "mitigation": "add tenant enforcement",
            "evidence_refs": ["test://tenant-scope"],
            "residual_risk": "high",
        }
    ]
    review["release_blocked"] = false_value = False

    errors = validate_sdlc_artifact.validate_security_review_record(review, strict=True)

    assert "security_review: unresolved critical/high findings must block release" in errors
    assert false_value is False
    assert len(errors) >= 1


def test_failed_required_check_is_rejected() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])
    review["required_checks"][0]["status"] = "failed"

    errors = validate_sdlc_artifact.validate_security_review_record(review, strict=True)

    assert "security_review: failed required checks must be resolved before release" in errors
    assert review["required_checks"][0]["status"] == "failed"
    assert len(errors) >= 1


def test_impact_category_requires_mapped_check() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])
    review["impact_categories"].append("tenant_scope")

    errors = validator.validate_required_security_checks(review, strict=True)

    assert "security_review: impact tenant_scope requires IDOR check" in errors
    assert "tenant_scope" in review["impact_categories"]
    assert len(errors) >= 1


def test_duplicate_category_checks_preserve_required_control() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])

    errors = validator.validate_required_security_checks(review, strict=True)
    audit_checks = [check for check in review["required_checks"] if check["category"] == "audit"]

    assert errors == []
    assert len(audit_checks) >= 2
    assert any("audit visibility" in check["check"] for check in audit_checks)
    assert any("PR enforcement drift" in check["check"] for check in audit_checks)


def test_trusted_identity_header_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_trusted_identity_header_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "trusted identity header boundary security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_oidc_jwks_refresh_evidence_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_oidc_jwks_refresh_evidence_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "OIDC JWKS refresh evidence security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "network" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_adapter_external_effect_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_adapter_external_effect_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "adapter external effect security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "external_api" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_adapter_messaging_phone_dispatch_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_adapter_messaging_phone_dispatch_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "adapter messaging phone security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "external_api" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_github_check_run_write_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_github_check_run_write_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "GitHub check-run write security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_github_app_token_exchange_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_github_app_token_exchange_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "GitHub App token exchange security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_github_action_execution_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_github_action_execution_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "GitHub action execution security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_github_branch_protection_reconcile_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_github_branch_protection_reconcile_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "GitHub branch-protection reconcile security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_distributed_lease_claim_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_distributed_lease_claim_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "distributed lease claim security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_distributed_lease_adapter_registry_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_distributed_lease_adapter_registry_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "distributed lease adapter registry security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_distributed_lease_execution_receipt_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_distributed_lease_execution_receipt_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "distributed lease execution security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_scheduler_worker_runtime_receipt_handoff_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_scheduler_worker_runtime_receipt_handoff_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "scheduler worker handoff security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_scheduler_worker_runtime_receipt_emitter_dry_run_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_scheduler_worker_runtime_receipt_emitter_dry_run_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "scheduler worker emitter dry-run security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_connector_action_promotion_gate_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_connector_action_promotion_gate_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "connector action promotion gate security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_readiness_waiver_review_packet_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_readiness_waiver_review_packet_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "readiness waiver review packet security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_browser_observation_receipt_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_browser_observation_receipt_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "browser observation receipt security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_research_source_conflict_map_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_research_source_conflict_map_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "research source conflict map security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_trusted_capture_evidence_packet_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_trusted_capture_evidence_packet_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "trusted capture evidence packet security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_sccml_trace_adapter_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_sccml_trace_adapter_witness_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "sccml trace adapter witness security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_chaos_rehearsal_execution_report_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_chaos_rehearsal_execution_report_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "chaos rehearsal security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_invariant_fuzz_execution_report_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_invariant_fuzz_execution_report_20260617.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "invariant fuzz security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_world_substrate_replay_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_world_substrate_replay_witness_20260617.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "world substrate replay witness security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_worker_receipt_ledger_read_model_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_worker_receipt_ledger_read_model_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "worker receipt ledger security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_mfidel_substrate_conformance_receipt_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_mfidel_substrate_conformance_receipt_20260616.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "mfidel substrate security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_maf_receipt_parity_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_maf_receipt_parity_witness_20260618.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "maf receipt parity security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_maf_abi_cli_contract_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_maf_abi_cli_contract_witness_20260618.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "maf ABI CLI security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_maf_subprocess_effect_boundary_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_maf_subprocess_effect_boundary_witness_20260618.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "maf subprocess security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "network" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_maf_deterministic_fixture_parity_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_maf_deterministic_fixture_parity_witness_20260618.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "maf deterministic fixture security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "network" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_maf_failure_receipt_path_witness_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_maf_failure_receipt_path_witness_20260618.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "maf failure receipt path security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "external_api" in review["impact_categories"]
    assert "network" in review["impact_categories"]
    assert "secrets" in review["impact_categories"]
    assert "policy" in review["impact_categories"]
    assert "receipts" in review["impact_categories"]
    assert "audit" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_security_review_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--strict"])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "sdlc_security_review_schema" in output
    assert "STATUS: passed" in output
