"""Tests for release-status handoff evidence validation.

Purpose: prove release readiness includes gateway publication orchestration
and post-run receipt validation anchors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_release_status and gateway publication workflow.
Invariants:
  - Gateway publication workflow must validate orchestration receipts.
  - Deployment status must name orchestration receipt handoff evidence.
  - Missing handoff anchors fail closed during release validation.
"""

from __future__ import annotations

from scripts.validate_release_status import (
    CI_WORKFLOW_PATH,
    GATEWAY_PUBLICATION_WORKFLOW_PATH,
    PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS,
    REQUIRED_CI_LITERALS,
    REPO_ROOT,
    WORKFLOW_DIR,
    validate_ci_workflow_text,
    validate_gateway_publication_workflow_text,
    validate_protocol_manifest_surface,
    validate_public_surface_document_texts,
    validate_workflow_hygiene,
)


def test_gateway_publication_workflow_carries_receipt_validation_gate() -> None:
    content = GATEWAY_PUBLICATION_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_gateway_publication_workflow_text(content)

    assert errors == []
    assert "python scripts/validate_deployment_orchestration_receipt.py" in content
    assert "--require-mcp-operator-checklist" in content
    assert ".change_assurance/deployment_witness_orchestration_validation.json" in content


def test_release_public_surface_requires_orchestration_receipt_anchors() -> None:
    document_texts = {
        document_name: (REPO_ROOT / document_name).read_text(encoding="utf-8")
        for document_name in PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS
    }

    errors = validate_public_surface_document_texts(document_texts)
    deployment_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS["DEPLOYMENT_STATUS.md"]

    assert errors == []
    assert ".github/workflows/gateway-publication.yml" in deployment_literals
    assert any("orchestrate_deployment_witness.py" in literal for literal in deployment_literals)
    assert any(
        "validate_deployment_orchestration_receipt.py" in literal
        for literal in deployment_literals
    )


def test_gateway_publication_workflow_reports_missing_receipt_validator() -> None:
    content = "Gateway Publication Orchestration\nworkflow_dispatch\n"

    errors = validate_gateway_publication_workflow_text(content)

    assert len(errors) == 1
    assert "validate_deployment_orchestration_receipt.py" in errors[0]
    assert "deployment_witness_orchestration_validation.json" in errors[0]
    assert "--require-mcp-operator-checklist" in errors[0]


def test_release_gate_validates_public_protocol_manifest() -> None:
    errors = validate_protocol_manifest_surface()

    assert errors == []
    assert (REPO_ROOT / "schemas" / "mullu_governance_protocol.manifest.json").exists()
    assert (REPO_ROOT / "schemas" / "deployment_orchestration_receipt.schema.json").exists()
    assert (REPO_ROOT / "scripts" / "validate_protocol_manifest.py").exists()


def test_ci_workflow_runs_protocol_manifest_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert "python scripts/validate_protocol_manifest.py" in REQUIRED_CI_LITERALS
    assert content.count("python scripts/validate_protocol_manifest.py") == 2
    assert "Validate protocol manifest" in content


def test_release_gate_rejects_placeholder_workflows() -> None:
    workflow_texts = {
        ".github/workflows/validation-placeholder.yml": (
            "name: validation-placeholder\n"
            "jobs:\n"
            "  placeholder:\n"
            "    steps:\n"
            "      - name: Placeholder step\n"
            "        run: echo \"Validation placeholder for Milestone 0\"\n"
        )
    }

    errors = validate_workflow_hygiene(workflow_texts)

    assert len(errors) == 3
    assert any("validation-placeholder.yml" in error for error in errors)
    assert any("placeholder job" in error for error in errors)
    assert any("Validation placeholder for Milestone 0" in error for error in errors)


def test_release_gate_has_no_placeholder_workflows() -> None:
    workflow_texts = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(WORKFLOW_DIR.glob("*.y*ml"))
    }

    errors = validate_workflow_hygiene(workflow_texts)

    assert errors == []
    assert ".github/workflows/scaffold.yml" not in workflow_texts
    assert ".github/workflows/validation-placeholder.yml" not in workflow_texts
    assert all("Placeholder step" not in content for content in workflow_texts.values())
