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

from scripts.validate_public_repository_surface import (
    DEPLOYMENT_STATUS_REQUIRED_LITERALS,
    DEPLOYMENT_WITNESS_WORKFLOW_PATH,
    DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS,
    CI_WORKFLOW_PATH,
    CI_WORKFLOW_REQUIRED_LITERALS,
    GATEWAY_PUBLICATION_WORKFLOW_PATH,
    GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS,
    GITHUB_SURFACE_REQUIRED_LITERALS,
    GOVERNANCE_PROTOCOL_DOC_PATH,
    GOVERNANCE_PROTOCOL_REQUIRED_LITERALS,
    LOGIC_GOVERNANCE_DOC_PATH,
    LOGIC_GOVERNANCE_REQUIRED_LITERALS,
    REPO_ROOT,
    STATUS_REQUIRED_LITERALS,
    validate_required_document_text,
)


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
    assert "python scripts/plan_capability_adapter_closure.py --json" in content
    assert "python scripts/plan_deployment_publication_closure.py --json" in content
    assert "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json" in content
    assert ".change_assurance/deployment_publication_closure_validation.json" in content
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
    assert "python scripts/validate_protocol_manifest.py" in content
    assert "Public protocol schema index" in content


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
    assert "actions/upload-artifact@v4" in content


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
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET" in content
    assert '--conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET"' in content
    assert ".change_assurance/deployment_witness.json" in content


def test_governance_protocol_doc_is_public_surface_anchor() -> None:
    content = (REPO_ROOT / GOVERNANCE_PROTOCOL_DOC_PATH).read_text(encoding="utf-8")

    errors = validate_required_document_text(
        document_name=GOVERNANCE_PROTOCOL_DOC_PATH,
        content=content,
        required_literals=GOVERNANCE_PROTOCOL_REQUIRED_LITERALS,
    )

    assert errors == []
    assert "protocol manifest ok: 60 schemas" in content
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
    assert "Deployment orchestration receipt validation reports are public contracts" in content
    assert "Gateway publication readiness reports are public contracts" in content
    assert "Gateway publication receipt validation reports are public contracts" in content
    assert "World-state projections are public contracts" in content
    assert "Goal compilation reports are public contracts" in content
    assert "Workflow mining reports are public contracts" in content
    assert "Simulation receipts are public contracts" in content
    assert "Governed runtime promotion validators are public contracts" in content
    assert "Terminal closure certificates are public contracts" in content
    assert "Reflex deployment witness envelopes are public contracts" in content
    assert "Reflex deployment witness validator receipts are public contracts" in content
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
