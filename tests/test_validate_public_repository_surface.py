"""Tests for public repository surface validation.

Purpose: prove deployment orchestration handoff evidence remains visible on
the public repository surface.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_public_repository_surface, DEPLOYMENT_STATUS.md,
and .github/workflows/gateway-publication.yml.
Invariants:
  - Deployment status documents the orchestration receipt validator.
  - Gateway publication workflow validates and uploads the receipt validation.
  - Missing public-surface anchors fail closed.
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.validate_public_repository_surface import (
    DEPLOYMENT_STATUS_REQUIRED_LITERALS,
    DEPLOYMENT_WITNESS_WORKFLOW_PATH,
    DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS,
    EXPECTED_PROTOCOL_MANIFEST_RESULT,
    CI_WORKFLOW_PATH,
    CI_WORKFLOW_REQUIRED_LITERALS,
    GATEWAY_PUBLICATION_WORKFLOW_PATH,
    GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS,
    GITHUB_SURFACE_REQUIRED_LITERALS,
    GOVERNANCE_PROTOCOL_DOC_PATH,
    GOVERNANCE_PROTOCOL_REQUIRED_LITERALS,
    LOGIC_GOVERNANCE_DOC_PATH,
    LOGIC_GOVERNANCE_REQUIRED_LITERALS,
    PRODUCT_BOUNDARY_REQUIRED_LITERALS,
    REPO_ROOT,
    STATUS_REQUIRED_LITERALS,
    _parse_json_object,
    read_json_url_with_gh,
    validate_required_document_text,
)
from scripts.validate_protocol_manifest import load_manifest


def test_deployment_status_requires_orchestration_receipt_validation() -> None:
    content = (REPO_ROOT / "DEPLOYMENT_STATUS.md").read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name="DEPLOYMENT_STATUS.md",
        content=content,
        required_literals=DEPLOYMENT_STATUS_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "validate_deployment_orchestration_receipt.py" in content
    assert "--require-mcp-operator-checklist" in content
    assert ".change_assurance/deployment_witness_orchestration.json" in content
    assert "## GitHub Runtime Input State" in content
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET" in content
    assert "MULLU_GATEWAY_URL" in content
    assert "responsibility_debt_clear=true" in content
    assert "runtime_responsibility_debt_clear=true" in content
    assert "authority_responsibility_debt_clear=true" in content
    assert "python scripts/collect_runtime_conformance.py --gateway-url \"$MULLU_GATEWAY_URL\" --conformance-secret \"$MULLU_RUNTIME_CONFORMANCE_SECRET\" --authority-operator-secret \"$MULLU_AUTHORITY_OPERATOR_SECRET\" --output .change_assurance/runtime_conformance_certificate.json" in content
    assert ".change_assurance/runtime_conformance_certificate.json" in content
    assert "schemas/runtime_conformance_collection.schema.json" in content
    assert "GitHub Actions secret name `MULLU_AUTHORITY_OPERATOR_SECRET` is present; secret value is not printed" in content
    assert "python scripts/plan_capability_adapter_closure.py --json" in content
    assert "python scripts/plan_deployment_publication_closure.py --json" in content
    assert "python scripts/validate_deployment_publication_closure_plan_schema.py --strict" in content
    assert "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json" in content
    assert ".change_assurance/deployment_publication_closure_validation.json" in content
    assert "python scripts/emit_deployment_upstream_blocker_receipt.py --target-gateway-url \"$MULLU_GATEWAY_URL\" --output .change_assurance/deployment_upstream_blocker_receipt.json --json" in content
    assert "python scripts/validate_deployment_upstream_blocker_receipt.py --receipt .change_assurance/deployment_upstream_blocker_receipt.json --output .change_assurance/deployment_upstream_blocker_receipt_validation.json --require-ready" in content
    assert "`api.mullusi.com` remains `AwaitingEvidence` until upstream recovery" in content
    assert "python scripts/emit_gateway_dns_target_binding_receipt.py --gateway-host \"$MULLU_GATEWAY_HOST\" --gateway-url \"$MULLU_GATEWAY_URL\" --expected-environment \"$MULLU_EXPECTED_RUNTIME_ENV\" --record-type \"$MULLU_GATEWAY_DNS_RECORD_TYPE\" --target \"$MULLU_GATEWAY_DNS_TARGET\" --provider \"$MULLU_DNS_PROVIDER\" --output .change_assurance/gateway_dns_target_binding_receipt.json --json" in content
    assert "python scripts/validate_gateway_dns_target_binding_receipt.py --receipt .change_assurance/gateway_dns_target_binding_receipt.json --output .change_assurance/gateway_dns_target_binding_receipt_validation.json --require-ready" in content
    assert "python scripts/apply_deployment_publication_status.py --operator-approval-ref \"$MULLU_DEPLOYMENT_PUBLICATION_APPROVAL_REF\" --receipt-output .change_assurance/public_production_health_declaration.json" in content
    assert ".change_assurance/public_production_health_declaration.json" in content
    assert "schemas/public_production_health_declaration.schema.json" in content
    assert "python scripts/plan_general_agent_promotion_closure.py --json" in content
    assert "python scripts/validate_general_agent_promotion_closure_plan_schema.py --strict" in content
    assert "python scripts/validate_general_agent_promotion_closure_plan.py --strict" in content
    assert "python scripts/validate_general_agent_promotion_handoff_packet.py --packet examples/general_agent_promotion_handoff_packet.json --json" in content
    assert "python scripts/validate_general_agent_promotion_operator_checklist.py --checklist examples/general_agent_promotion_operator_checklist.json --json" in content
    assert "python scripts/validate_general_agent_promotion_environment_bindings.py --contract examples/general_agent_promotion_environment_bindings.json --json" in content
    assert "python scripts/emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance/general_agent_promotion_environment_binding_receipt.json --json" in content
    assert "python scripts/validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance/general_agent_promotion_environment_binding_receipt.json --require-ready --json" in content
    assert "python scripts/produce_browser_sandbox_evidence.py --output \"$MULLU_BROWSER_SANDBOX_EVIDENCE\" --strict" in content
    assert "python scripts/validate_sandbox_execution_receipt.py --receipt \"$MULLU_BROWSER_SANDBOX_EVIDENCE\" --capability-prefix browser. --require-no-workspace-changes --json" in content
    assert "python scripts/validate_browser_sandbox_evidence.py --evidence \"$MULLU_BROWSER_SANDBOX_EVIDENCE\" --json" in content
    assert "python scripts/preflight_general_agent_promotion_handoff.py --output .change_assurance/general_agent_promotion_handoff_preflight.json --strict --json" in content
    assert "python scripts/validate_general_agent_promotion_handoff_preflight.py --report .change_assurance/general_agent_promotion_handoff_preflight.json --require-ready --json" in content
    assert "python scripts/validate_governed_runtime_promotion.py --strict" in content
    assert "docs/59_general_agent_promotion_handoff_packet.md" in content
    assert "examples/general_agent_promotion_handoff_packet.json" in content
    assert "examples/general_agent_promotion_environment_bindings.json" in content
    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in content
    assert "No `deployment-witness.yml` workflow runs are currently recorded" in content


def test_status_witness_requires_protocol_manifest_anchor() -> None:
    content = (REPO_ROOT / "STATUS.md").read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name="STATUS.md",
        content=content,
        required_literals=STATUS_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "Protocol witness" in content
    assert "docs/52_mullu_governance_protocol.md" in content
    assert "docs/60_logic_governance_application.md" in content
    assert "validate_logic_governance_application.py" in content
    assert "python scripts/validate_protocol_manifest.py" in content
    assert "scripts/validate_governed_runtime_promotion.py" in content


def test_github_surface_requires_protocol_document_anchor() -> None:
    content = (REPO_ROOT / "GITHUB_SURFACE.md").read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name="GITHUB_SURFACE.md",
        content=content,
        required_literals=GITHUB_SURFACE_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "docs/52_mullu_governance_protocol.md" in content
    assert "docs/PRODUCT_BOUNDARY.md" in content
    assert "python scripts/validate_protocol_manifest.py" in content
    assert "Public protocol schema index" in content


def test_product_boundary_names_product_and_launch_constraints() -> None:
    content = (REPO_ROOT / "docs" / "PRODUCT_BOUNDARY.md").read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name="docs/PRODUCT_BOUNDARY.md",
        content=content,
        required_literals=PRODUCT_BOUNDARY_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "Mullu Govern is the public product" in content
    assert "Mullu Control Plane" in content
    assert "Launch Constraint" in content


def test_gateway_publication_workflow_requires_receipt_validator() -> None:
    workflow_path = REPO_ROOT / GATEWAY_PUBLICATION_WORKFLOW_PATH
    content = workflow_path.read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name=GATEWAY_PUBLICATION_WORKFLOW_PATH,
        content=content,
        required_literals=GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "python scripts/validate_deployment_orchestration_receipt.py" in content
    assert ".change_assurance/deployment_witness_orchestration_validation.json" in content
    assert "actions/upload-artifact@v6" in content


def test_ci_workflow_requires_reflex_validator_receipt_artifact() -> None:
    workflow_path = REPO_ROOT / CI_WORKFLOW_PATH
    content = workflow_path.read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name=CI_WORKFLOW_PATH,
        content=content,
        required_literals=CI_WORKFLOW_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "Validate Reflex deployment witness replay" in content
    assert "schemas/reflex_deployment_witness_validator_receipt.schema.json" in content
    assert "reflex-deployment-witness-validator-receipt" in content
    assert ".change_assurance/reflex_deployment_witness_validator_receipt.json" in content


def test_deployment_witness_workflow_requires_conformance_secret_handoff() -> None:
    workflow_path = REPO_ROOT / DEPLOYMENT_WITNESS_WORKFLOW_PATH
    content = workflow_path.read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name=DEPLOYMENT_WITNESS_WORKFLOW_PATH,
        content=content,
        required_literals=DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "python scripts/preflight_deployment_witness.py" in content
    assert "--accept-repository-input-env" in content
    assert "--accept-workflow-file" in content
    assert ".change_assurance/deployment_witness_preflight.json" in content
    assert "deployment-witness-preflight" in content
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET" in content
    assert "MULLU_AUTHORITY_OPERATOR_SECRET" in content
    assert "python scripts/collect_runtime_conformance.py" in content
    assert '--authority-operator-secret "$MULLU_AUTHORITY_OPERATOR_SECRET"' in content
    assert ".change_assurance/runtime_conformance_certificate.json" in content
    assert "runtime-conformance-collection" in content
    assert '--conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET"' in content
    assert ".change_assurance/deployment_witness.json" in content
    assert "operator_approval_ref" in content
    assert "governed_swarm_pilot_readiness_path" in content
    assert "python scripts/apply_deployment_publication_status.py" in content
    assert "--operator-approval-ref \"${{ inputs.operator_approval_ref }}\"" in content
    assert ".change_assurance/public_production_health_declaration.json" in content
    assert "--declaration-receipt .change_assurance/public_production_health_declaration.json" in content
    assert "public-production-health-declaration" in content
    assert "python scripts/validate_governed_swarm_production_readiness.py" in content
    assert '--pilot-readiness "${{ inputs.governed_swarm_pilot_readiness_path }}"' in content
    assert "--deployment-witness .change_assurance/deployment_witness.json" in content
    assert "--public-health-declaration .change_assurance/public_production_health_declaration.json" in content
    assert "--output .change_assurance/governed_swarm_production_readiness.json" in content
    assert "governed-swarm-production-readiness" in content
    assert ".change_assurance/governed_swarm_production_readiness.json" in content


def test_governance_protocol_doc_is_public_surface_anchor() -> None:
    content = (REPO_ROOT / GOVERNANCE_PROTOCOL_DOC_PATH).read_text(encoding="utf-8")
    manifest = load_manifest()
    expected_manifest_result = f"protocol manifest ok: {len(manifest['schemas'])} schemas"

    errors = validate_required_document_text(
        document_name=GOVERNANCE_PROTOCOL_DOC_PATH,
        content=content,
        required_literals=GOVERNANCE_PROTOCOL_REQUIRED_LITERALS,
    )

    assert errors == []
    assert EXPECTED_PROTOCOL_MANIFEST_RESULT == expected_manifest_result
    assert expected_manifest_result in content
    assert expected_manifest_result in GOVERNANCE_PROTOCOL_REQUIRED_LITERALS
    assert "Capability candidate packages are public contracts" in content
    assert "Capability maturity assessments are public contracts" in content
    assert "Policy proof reports are public contracts" in content
    assert "Capability adapter closure plans are public contracts" in content
    assert "Agent identities are public contracts" in content
    assert "Memory lattice admission claims are public contracts" in content
    assert "Trust ledger bundles are public contracts" in content
    assert "Trust ledger anchor receipts are public contracts" in content
    assert "Domain operating packs are public contracts" in content
    assert "Multimodal operation receipts are public contracts" in content
    assert "Capability upgrade plans are public contracts" in content
    assert "Autonomous test-generation plans are public contracts" in content
    assert "Deployment handoff receipts are public contracts" in content
    assert "Deployment publication closure validation reports are public contracts" in content
    assert "Deployment publication closure plans are public contracts" in content
    assert "Public production health declaration receipts are public contracts" in content
    assert "Deployment orchestration receipt validation reports are public contracts" in content
    assert "Gateway publication readiness reports are public contracts" in content
    assert "Gateway publication receipt validation reports are public contracts" in content
    assert "World-state projections are public contracts" in content
    assert "Operator control tower snapshots are public contracts" in content
    assert "Low-code builder catalogs are public contracts" in content
    assert "Marketplace SDK catalogs are public contracts" in content
    assert "Goal compilation reports are public contracts" in content
    assert "Workflow mining reports are public contracts" in content
    assert "Simulation receipts are public contracts" in content
    assert "Governed runtime promotion validators are public contracts" in content
    assert "Terminal closure certificates are public contracts" in content
    assert "Finance approval live handoff artifacts are public contracts" in content
    assert "Finance payment provider binding receipts are public contracts" in content
    assert "finance approval live handoff artifact contract" in content
    assert "finance payment provider binding receipt contract" in content
    assert "Reflex deployment witness envelopes are public contracts" in content
    assert "Reflex deployment witness validator receipts are public contracts" in content
    assert "Temporal evidence freshness receipts are public contracts" in content
    assert "Temporal resolution receipts are public contracts" in content
    assert "Temporal reapproval receipts are public contracts" in content
    assert "Temporal dispatch window receipts are public contracts" in content
    assert "Temporal budget window receipts are public contracts" in content
    assert "Temporal causal order receipts are public contracts" in content
    assert "Temporal monotonic duration receipts are public contracts" in content
    assert "Temporal accepted-risk expiry receipts are public contracts" in content
    assert "Temporal credential expiry receipts are public contracts" in content
    assert "Temporal retention window receipts are public contracts" in content
    assert "Temporal rate-limit window receipts are public contracts" in content
    assert "Temporal retry window receipts are public contracts" in content
    assert "Temporal lease window receipts are public contracts" in content
    assert "Temporal idempotency window receipts are public contracts" in content
    assert "Temporal missed-run receipts are public contracts" in content
    assert "Temporal recurrence window receipts are public contracts" in content
    assert "Temporal memory refresh receipts are public contracts" in content
    assert "python scripts\\validate_protocol_manifest.py" in content


def test_logic_governance_doc_is_public_surface_anchor() -> None:
    content = (REPO_ROOT / LOGIC_GOVERNANCE_DOC_PATH).read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name=LOGIC_GOVERNANCE_DOC_PATH,
        content=content,
        required_literals=LOGIC_GOVERNANCE_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "Governance Law Mapping" in content
    assert "Mfidel substrate and overlay" in content
    assert "Proof-of-Resolution Stamp Template" in content


def test_required_document_text_reports_missing_orchestration_literal() -> None:
    content = "Gateway Publication Orchestration\n"

    errors = validate_required_document_text(
        document_name=GATEWAY_PUBLICATION_WORKFLOW_PATH,
        content=content,
        required_literals=(
            "Gateway Publication Orchestration",
            "python scripts/validate_deployment_orchestration_receipt.py",
            ".change_assurance/deployment_witness_orchestration_validation.json",
        ),
    )

    assert len(errors) == 1
    assert "validate_deployment_orchestration_receipt.py" in errors[0]
    assert "deployment_witness_orchestration_validation.json" in errors[0]
    assert "Gateway Publication Orchestration" not in errors[0]


def test_github_cli_fallback_error_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_url = "https://api.github.com/repos/tamirat-wubie/mullu-control-plane?token=secret-token"

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            ["gh", "api", "repos/tamirat-wubie/mullu-control-plane"],
            7,
            stdout="",
            stderr="provider returned secret-token in stderr",
        )

    monkeypatch.setattr(
        "scripts.validate_public_repository_surface.subprocess.run",
        _fake_run,
    )

    with pytest.raises(RuntimeError) as exc_info:
        read_json_url_with_gh(
            secret_url,
            prior_failure="network failure: secret-token",
        )

    message = str(exc_info.value)
    assert message == "github_api: network_failure; gh_cli_fallback_failed: github_cli_exit_7"
    assert "secret-token" not in message
    assert "mullu-control-plane" not in message


def test_github_cli_unsupported_url_error_is_bounded() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        read_json_url_with_gh(
            "https://example.invalid/private-path?token=secret-token",
            prior_failure="request timed out",
        )

    message = str(exc_info.value)
    assert message == "github_api: request_timed_out; no_github_cli_fallback_path"
    assert "secret-token" not in message
    assert "private-path" not in message


def test_json_parse_error_source_is_bounded() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _parse_json_object(
            source="https://api.github.com/repos/tamirat-wubie/mullu-control-plane?token=secret-token",
            payload="{not-json",
        )

    message = str(exc_info.value)
    assert message == "github_api: response was not valid JSON"
    assert "secret-token" not in message
    assert "mullu-control-plane" not in message
