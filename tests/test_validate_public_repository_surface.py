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
    GATEWAY_PUBLICATION_WORKFLOW_PATH,
    GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS,
    REPO_ROOT,
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
    assert "python scripts/plan_capability_adapter_closure.py --json" in content
    assert "python scripts/plan_deployment_publication_closure.py --json" in content
    assert "python scripts/plan_general_agent_promotion_closure.py --json" in content
    assert "python scripts/validate_general_agent_promotion_closure_plan_schema.py --strict" in content
    assert "python scripts/validate_general_agent_promotion_closure_plan.py --strict" in content
    assert "python scripts/validate_general_agent_promotion_handoff_packet.py --packet examples/general_agent_promotion_handoff_packet.json --json" in content
    assert "python scripts/validate_general_agent_promotion_operator_checklist.py --checklist examples/general_agent_promotion_operator_checklist.json --json" in content
    assert "python scripts/validate_general_agent_promotion_environment_bindings.py --contract examples/general_agent_promotion_environment_bindings.json --json" in content
    assert "python scripts/emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance/general_agent_promotion_environment_binding_receipt.json --json" in content
    assert "python scripts/preflight_general_agent_promotion_handoff.py --output .change_assurance/general_agent_promotion_handoff_preflight.json --strict --json" in content
    assert "docs/59_general_agent_promotion_handoff_packet.md" in content
    assert "examples/general_agent_promotion_handoff_packet.json" in content
    assert "examples/general_agent_promotion_environment_bindings.json" in content
    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in content
    assert "No `deployment-witness.yml` workflow runs are currently recorded" in content


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
