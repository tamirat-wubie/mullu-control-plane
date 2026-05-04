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
    DEPLOYMENT_WITNESS_WORKFLOW_PATH,
    GATEWAY_PUBLICATION_WORKFLOW_PATH,
    PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS,
    RELEASE_CHECKLIST_REQUIRED_LITERALS,
    REQUIRED_CI_LITERALS,
    REPO_ROOT,
    STATUS_DOCUMENT_REQUIRED_LITERALS,
    WORKFLOW_DIR,
    validate_ci_workflow_text,
    validate_deployment_witness_workflow_text,
    validate_gateway_publication_workflow_text,
    validate_protocol_manifest_surface,
    validate_public_surface_document_texts,
    validate_release_checklist_text,
    validate_status_document_text,
    validate_workflow_hygiene,
)


def test_gateway_publication_workflow_carries_receipt_validation_gate() -> None:
    content = GATEWAY_PUBLICATION_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_gateway_publication_workflow_text(content)

    assert errors == []
    assert "python scripts/validate_deployment_orchestration_receipt.py" in content
    assert "--require-mcp-operator-checklist" in content
    assert ".change_assurance/deployment_witness_orchestration_validation.json" in content


def test_deployment_witness_workflow_carries_conformance_secret_handoff() -> None:
    content = DEPLOYMENT_WITNESS_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_deployment_witness_workflow_text(content)

    assert errors == []
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET" in content
    assert '--conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET"' in content
    assert "python scripts/collect_deployment_witness.py" in content


def test_release_public_surface_requires_orchestration_receipt_anchors() -> None:
    document_texts = {
        document_name: (REPO_ROOT / document_name).read_text(encoding="utf-8")
        for document_name in PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS
    }

    errors = validate_public_surface_document_texts(document_texts)
    github_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS["GITHUB_SURFACE.md"]
    deployment_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS["DEPLOYMENT_STATUS.md"]

    assert errors == []
    assert "docs/52_mullu_governance_protocol.md" in github_literals
    assert "python scripts/validate_protocol_manifest.py" in github_literals
    assert ".github/workflows/gateway-publication.yml" in deployment_literals
    assert "## GitHub Runtime Input State" in deployment_literals
    assert any("orchestrate_deployment_witness.py" in literal for literal in deployment_literals)
    assert any("MULLU_GATEWAY_URL" in literal for literal in deployment_literals)
    assert any(
        "validate_deployment_orchestration_receipt.py" in literal
        for literal in deployment_literals
    )
    assert any("plan_capability_adapter_closure.py" in literal for literal in deployment_literals)
    assert any("plan_deployment_publication_closure.py" in literal for literal in deployment_literals)
    assert any("plan_general_agent_promotion_closure.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_closure_plan_schema.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_closure_plan.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_handoff_packet.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_operator_checklist.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_environment_bindings.py" in literal for literal in deployment_literals)
    assert any("emit_general_agent_promotion_environment_binding_receipt.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_environment_binding_receipt.py" in literal for literal in deployment_literals)
    assert any("produce_browser_sandbox_evidence.py" in literal for literal in deployment_literals)
    assert any("validate_sandbox_execution_receipt.py" in literal for literal in deployment_literals)
    assert any("validate_browser_sandbox_evidence.py" in literal for literal in deployment_literals)
    assert any("preflight_general_agent_promotion_handoff.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_handoff_preflight.py" in literal for literal in deployment_literals)
    assert any("validate_governed_runtime_promotion.py" in literal for literal in deployment_literals)
    assert any("docs/59_general_agent_promotion_handoff_packet.md" in literal for literal in deployment_literals)
    assert any("examples/general_agent_promotion_handoff_packet.json" in literal for literal in deployment_literals)
    assert any("examples/general_agent_promotion_environment_bindings.json" in literal for literal in deployment_literals)
    assert any("general_agent_promotion_environment_binding_receipt.json" in literal for literal in deployment_literals)


def test_status_document_reflects_deployment_runtime_input_gap() -> None:
    content = (REPO_ROOT / "STATUS.md").read_text(encoding="utf-8")

    errors = validate_status_document_text(content)

    assert errors == []
    assert "Deployment runtime input witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "Protocol witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "Logic governance witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "docs/52_mullu_governance_protocol.md" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "docs/60_logic_governance_application.md" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "python scripts/validate_protocol_manifest.py" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "Refresh deployment runtime input witness (#466)" in content
    assert "MULLU_GATEWAY_URL" in content
    assert "deployment_claim: published" in content
    assert "docs/59_general_agent_promotion_handoff_packet.md" in content
    assert "examples/general_agent_promotion_handoff_packet.json" in content
    assert "examples/general_agent_promotion_environment_bindings.json" in content
    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in content
    assert "validate_general_agent_promotion_handoff_packet.py" in content
    assert "validate_general_agent_promotion_operator_checklist.py" in content
    assert "validate_general_agent_promotion_environment_bindings.py" in content
    assert "emit_general_agent_promotion_environment_binding_receipt.py" in content
    assert "validate_general_agent_promotion_environment_binding_receipt.py" in content
    assert "produce_browser_sandbox_evidence.py" in content
    assert "validate_sandbox_execution_receipt.py" in content
    assert "validate_browser_sandbox_evidence.py" in content
    assert "preflight_general_agent_promotion_handoff.py" in content
    assert "validate_general_agent_promotion_handoff_preflight.py" in content
    assert "validate_governed_runtime_promotion.py" in content
    assert "Protocol witness" in content
    assert "Logic governance witness" in content
    assert "32-schema public contract index" in content
    assert "python scripts/validate_protocol_manifest.py" in content
    assert "docs/60_logic_governance_application.md" in content


def test_gateway_publication_workflow_reports_missing_receipt_validator() -> None:
    content = "Gateway Publication Orchestration\nworkflow_dispatch\n"

    errors = validate_gateway_publication_workflow_text(content)

    assert len(errors) == 1
    assert "validate_deployment_orchestration_receipt.py" in errors[0]
    assert "deployment_witness_orchestration_validation.json" in errors[0]
    assert "--require-mcp-operator-checklist" in errors[0]


def test_deployment_witness_workflow_reports_missing_conformance_secret_handoff() -> None:
    content = (
        "Deployment Witness Collection\n"
        "workflow_dispatch\n"
        "gateway_url\n"
        "MULLU_RUNTIME_WITNESS_SECRET\n"
        "MULLU_RUNTIME_CONFORMANCE_SECRET\n"
        "python scripts/collect_deployment_witness.py\n"
        ".change_assurance/deployment_witness.json\n"
        "actions/upload-artifact@v4\n"
    )

    errors = validate_deployment_witness_workflow_text(content)

    assert len(errors) == 1
    assert "--conformance-secret" in errors[0]
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET" in errors[0]
    assert "Deployment Witness Collection" not in errors[0]


def test_release_gate_validates_public_protocol_manifest() -> None:
    errors = validate_protocol_manifest_surface()

    assert errors == []
    assert (REPO_ROOT / "schemas" / "mullu_governance_protocol.manifest.json").exists()
    assert (REPO_ROOT / "schemas" / "deployment_orchestration_receipt.schema.json").exists()
    assert (REPO_ROOT / "scripts" / "validate_protocol_manifest.py").exists()


def test_release_checklist_requires_protocol_manifest_gate() -> None:
    content = (REPO_ROOT / "RELEASE_CHECKLIST_v0.1.md").read_text(encoding="utf-8")

    errors = validate_release_checklist_text(content)

    assert errors == []
    assert "Public protocol manifest validates with `scripts/validate_protocol_manifest.py`" in content
    assert "Public protocol manifest validates with `scripts/validate_protocol_manifest.py`" in RELEASE_CHECKLIST_REQUIRED_LITERALS
    assert "Release status derives from `scripts/validate_release_status.py --strict`" in RELEASE_CHECKLIST_REQUIRED_LITERALS


def test_release_checklist_reports_missing_protocol_manifest_gate() -> None:
    content = "Release Checklist\nShared schemas validate with `scripts/validate_schemas.py --strict`\n"

    errors = validate_release_checklist_text(content)

    assert len(errors) == 1
    assert "Public protocol manifest validates" in errors[0]
    assert "scripts/validate_protocol_manifest.py" in errors[0]
    assert "Release Checklist" not in errors[0]


def test_ci_workflow_runs_protocol_manifest_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert "python scripts/validate_protocol_manifest.py" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_governed_runtime_promotion.py --output .change_assurance/governed_runtime_promotion_readiness.json" in REQUIRED_CI_LITERALS
    assert any(
        "validate_general_agent_promotion_closure_plan.py" in literal
        for literal in REQUIRED_CI_LITERALS
    )
    assert any(
        "validate_general_agent_promotion_operator_checklist.py" in literal
        for literal in REQUIRED_CI_LITERALS
    )
    assert any(
        "validate_general_agent_promotion_environment_bindings.py" in literal
        for literal in REQUIRED_CI_LITERALS
    )
    assert any(
        "emit_general_agent_promotion_environment_binding_receipt.py" in literal
        for literal in REQUIRED_CI_LITERALS
    )
    assert any(
        "validate_general_agent_promotion_environment_binding_receipt.py" in literal
        for literal in REQUIRED_CI_LITERALS
    )
    assert content.count("python scripts/validate_protocol_manifest.py") == 2
    assert "Validate protocol manifest" in content


def test_ci_workflow_runs_promotion_closure_schema_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert any("validate_general_agent_promotion_closure_plan_schema.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert content.count("validate_general_agent_promotion_closure_plan_schema.py") == 2
    assert "general_agent_promotion_closure_plan_schema_validation.json" in content


def test_ci_workflow_runs_promotion_handoff_packet_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert any("validate_general_agent_promotion_handoff_packet.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert any("preflight_general_agent_promotion_handoff.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert any("validate_general_agent_promotion_handoff_preflight.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert content.count("validate_general_agent_promotion_handoff_packet.py") == 2
    assert content.count("validate_general_agent_promotion_environment_bindings.py") == 2
    assert content.count("emit_general_agent_promotion_environment_binding_receipt.py") == 2
    assert content.count("validate_general_agent_promotion_environment_binding_receipt.py") == 2
    assert content.count("preflight_general_agent_promotion_handoff.py") == 2
    assert content.count("preflight_general_agent_promotion_handoff.py --output") == 2
    assert content.count("validate_general_agent_promotion_handoff_preflight.py") == 2
    assert content.count("validate_general_agent_promotion_handoff_preflight.py --report") == 2
    assert content.count("--strict --json") == 2
    assert "examples/general_agent_promotion_handoff_packet.json" in content
    assert "examples/general_agent_promotion_environment_bindings.json" in content
    assert "general_agent_promotion_environment_binding_receipt.json" in content
    assert "general_agent_promotion_handoff_preflight.json" in content
    assert "Validate general-agent promotion closure plan" in content


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
