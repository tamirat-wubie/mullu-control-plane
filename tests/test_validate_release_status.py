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

import json
from pathlib import Path

import scripts.validate_release_status as validate_release_status_module
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
    validate_deployment_status_witness_alignment,
    validate_gateway_publication_workflow_text,
    validate_deployment_status_phase_text,
    validate_logic_governance_surface,
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
    assert "python scripts/collect_deployment_witness.py" in content
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


def test_release_public_surface_requires_orchestration_receipt_anchors() -> None:
    document_texts = {
        document_name: (REPO_ROOT / document_name).read_text(encoding="utf-8")
        for document_name in PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS
    }

    errors = validate_public_surface_document_texts(document_texts)
    github_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS["GITHUB_SURFACE.md"]
    deployment_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS["DEPLOYMENT_STATUS.md"]
    product_boundary_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS[
        "docs/PRODUCT_BOUNDARY.md"
    ]
    platform_overview_literals = PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS[
        "docs/00_platform_overview.md"
    ]

    assert errors == []
    assert "docs/00_platform_overview.md" in github_literals
    assert "docs/PRODUCT_BOUNDARY.md" in github_literals
    assert "docs/52_mullu_governance_protocol.md" in github_literals
    assert "python scripts/validate_protocol_manifest.py" in github_literals
    assert "Repository Topology Decision" in platform_overview_literals
    assert "repository: mullu-control-plane" in platform_overview_literals
    assert "target does not by itself prove the final product architecture" in platform_overview_literals
    assert "Mullu Control Plane" in product_boundary_literals
    assert "Launch Constraint" in product_boundary_literals
    assert "This rename target is not a repository-split trigger" in product_boundary_literals
    assert ".github/workflows/gateway-publication.yml" in deployment_literals
    assert "## GitHub Runtime Input State" in deployment_literals
    assert any("orchestrate_deployment_witness.py" in literal for literal in deployment_literals)
    assert any("MULLU_GATEWAY_URL" in literal for literal in deployment_literals)
    assert any(
        "validate_deployment_orchestration_receipt.py" in literal
        for literal in deployment_literals
    )
    assert any(
        "validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json"
        in literal
        for literal in deployment_literals
    )
    assert any("collect_runtime_conformance.py" in literal for literal in deployment_literals)
    assert ".change_assurance/runtime_conformance_certificate.json" in deployment_literals
    assert "schemas/runtime_conformance_collection.schema.json" in deployment_literals
    assert ".change_assurance/deployment_publication_closure_validation.json" in deployment_literals
    assert any("emit_deployment_upstream_blocker_receipt.py" in literal for literal in deployment_literals)
    assert any("validate_deployment_upstream_blocker_receipt.py" in literal for literal in deployment_literals)
    assert any("deployment_upstream_blocker_receipt.json" in literal for literal in deployment_literals)
    assert any("api.mullusi.com" in literal for literal in deployment_literals)
    assert any("emit_gateway_dns_target_binding_receipt.py" in literal for literal in deployment_literals)
    assert any("validate_gateway_dns_target_binding_receipt.py" in literal for literal in deployment_literals)
    assert any("MULLU_GATEWAY_DNS_TARGET" in literal for literal in deployment_literals)
    assert any("gateway_dns_target_binding_receipt.json" in literal for literal in deployment_literals)
    assert any(
        "gateway_dns_target_binding_receipt_validation.json" in literal
        for literal in deployment_literals
    )
    assert any("apply_deployment_publication_status.py" in literal for literal in deployment_literals)
    assert ".change_assurance/public_production_health_declaration.json" in deployment_literals
    assert "schemas/public_production_health_declaration.schema.json" in deployment_literals
    assert any("plan_capability_adapter_closure.py" in literal for literal in deployment_literals)
    assert any("plan_deployment_publication_closure.py" in literal for literal in deployment_literals)
    assert any("validate_deployment_publication_closure_plan_schema.py" in literal for literal in deployment_literals)
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
    assert any("validate_gateway_ingress_manifest.py" in literal for literal in deployment_literals)
    assert any("preflight_general_agent_promotion_handoff.py" in literal for literal in deployment_literals)
    assert any("validate_general_agent_promotion_handoff_preflight.py" in literal for literal in deployment_literals)
    assert any("validate_governed_runtime_promotion.py" in literal for literal in deployment_literals)
    assert any("docs/59_general_agent_promotion_handoff_packet.md" in literal for literal in deployment_literals)
    assert any("examples/general_agent_promotion_handoff_packet.json" in literal for literal in deployment_literals)
    assert any("examples/general_agent_promotion_environment_bindings.json" in literal for literal in deployment_literals)
    assert any("general_agent_promotion_environment_binding_receipt.json" in literal for literal in deployment_literals)


def test_release_deployment_status_phase_accepts_published_declaration() -> None:
    content = "\n".join(
        (
            "**Deployment witness state:** `published`",
            "**Public production health endpoint:** `https://api.mullusi.com/health`",
            "| Public production health | Declared from a verified published deployment witness; `.change_assurance/deployment_witness.json` records `deployment_claim=published`, and `.change_assurance/public_production_health_declaration.json` records the operator-approved declaration receipt | Reflected |",
        )
    )

    assert validate_deployment_status_phase_text(content) == []


def test_release_deployment_status_phase_rejects_stale_published_declaration() -> None:
    content = "\n".join(
        (
            "**Deployment witness state:** `published`",
            "**Public production health endpoint:** `https://api.mullusi.com/health`",
            "| Public production health | Not declared; `.change_assurance/deployment_witness.json` records `deployment_claim=not-published` | Reflected |",
        )
    )

    errors = validate_deployment_status_phase_text(content)

    assert len(errors) == 2
    assert "stale blocked anchors" in errors[0]


def test_status_document_reflects_deployment_runtime_input_gap() -> None:
    content = (REPO_ROOT / "STATUS.md").read_text(encoding="utf-8")

    errors = validate_status_document_text(content)

    assert errors == []
    assert "Deployment runtime input witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "Protocol witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "Logic governance witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "Repository topology witness" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "docs/00_platform_overview.md" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "docs/PRODUCT_BOUNDARY.md" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "docs/52_mullu_governance_protocol.md" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "docs/60_logic_governance_application.md" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "python scripts/validate_protocol_manifest.py" in STATUS_DOCUMENT_REQUIRED_LITERALS
    assert "python scripts/validate_logic_governance_application.py" in REQUIRED_CI_LITERALS
    assert "Refresh deployment runtime input witness (#466)" in content
    assert "MULLU_GATEWAY_URL" in content
    assert "MULLU_AUTHORITY_OPERATOR_SECRET" in content
    assert "deployment_claim=published" in content
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
    assert "Repository topology witness" in content
    assert "docs/00_platform_overview.md" in content
    assert "32-schema public contract index" in content
    assert "python scripts/validate_protocol_manifest.py" in content
    assert "python scripts/validate_logic_governance_application.py" in content
    assert "docs/60_logic_governance_application.md" in content


def test_deployment_guide_requires_read_only_email_calendar_scope() -> None:
    content = (REPO_ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    template = (REPO_ROOT / "examples" / "finance_email_calendar_recovery.env.example").read_text(encoding="utf-8")

    assert "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID=gmail.readonly" in content
    assert "required read-only scope witness when a connector token is set" in content
    assert "Any configured connector token must be paired" in content
    assert "calendar.events.readonly" in content
    assert "python scripts/preflight_finance_email_calendar_recovery.py --receipt .change_assurance/email_calendar_live_receipt.json --strict --json" in content
    assert "python scripts/validate_finance_approval_email_calendar_live_receipt.py --require-ready --json" in content
    assert "examples/finance_email_calendar_recovery.env.example" in content
    assert "MULLU_EMAIL_CALENDAR_WORKER_URL=http://email-calendar-worker:8050/email-calendar/execute" in template
    assert "MULLU_EMAIL_CALENDAR_WORKER_SECRET=<secret-from-secret-manager>" in template
    assert "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID=gmail.readonly" in template
    assert "GOOGLE_CALENDAR_SCOPE_ID=calendar.events.readonly" in template
    assert "MICROSOFT_GRAPH_SCOPE_ID=mail.read" in template
    assert (
        "python scripts/validate_finance_email_calendar_recovery_env_example.py "
        "--template examples/finance_email_calendar_recovery.env.example --strict --json"
    ) in content


def test_release_source_hygiene_scan_skips_nested_git_worktree(tmp_path: Path) -> None:
    nested_repo = tmp_path / "mullu-control-plane-shadow"
    nested_repo.mkdir()
    (nested_repo / ".git").write_text(
        "gitdir: ../.git/worktrees/mullu-control-plane-shadow\n",
        encoding="utf-8",
    )
    (nested_repo / "bad.py").write_text(
        "try:\n    pass\nexcept:\n    pass\n",
        encoding="utf-8",
    )
    active_file = tmp_path / "good.py"
    active_file.write_text("def ok() -> None:\n    return None\n", encoding="utf-8")

    original_root = validate_release_status_module.REPO_ROOT
    try:
        validate_release_status_module.REPO_ROOT = tmp_path
        paths = validate_release_status_module._iter_source_hygiene_paths()
    finally:
        validate_release_status_module.REPO_ROOT = original_root

    assert paths == (active_file,)
    assert nested_repo / "bad.py" not in paths
    assert active_file in paths


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
        "MULLU_DEPLOYMENT_WITNESS_SECRET\n"
        "python scripts/collect_deployment_witness.py\n"
        ".change_assurance/deployment_witness.json\n"
        "actions/upload-artifact@v6\n"
    )

    errors = validate_deployment_witness_workflow_text(content)

    assert len(errors) == 1
    assert "preflight_deployment_witness.py" in errors[0]
    assert "deployment_witness_preflight.json" in errors[0]
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
    assert "Logic governance application validates with `scripts/validate_logic_governance_application.py`" in content
    assert "Public protocol manifest validates with `scripts/validate_protocol_manifest.py`" in RELEASE_CHECKLIST_REQUIRED_LITERALS
    assert "Logic governance application validates with `scripts/validate_logic_governance_application.py`" in RELEASE_CHECKLIST_REQUIRED_LITERALS
    assert "Release status derives from `scripts/validate_release_status.py --strict`" in RELEASE_CHECKLIST_REQUIRED_LITERALS


def test_release_checklist_reports_missing_protocol_manifest_gate() -> None:
    content = "Release Checklist\nShared schemas validate with `scripts/validate_schemas.py --strict`\n"

    errors = validate_release_checklist_text(content)

    assert len(errors) == 1
    assert "Public protocol manifest validates" in errors[0]
    assert "scripts/validate_protocol_manifest.py" in errors[0]
    assert "Release Checklist" not in errors[0]


def test_release_gate_validates_logic_governance_application() -> None:
    errors = validate_logic_governance_surface()

    assert errors == []
    assert "python scripts/validate_logic_governance_application.py" in REQUIRED_CI_LITERALS
    assert (REPO_ROOT / "scripts" / "validate_logic_governance_application.py").exists()


def test_ci_workflow_runs_protocol_manifest_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert "python scripts/validate_protocol_manifest.py" in REQUIRED_CI_LITERALS
    assert "python -m scripts.proof_coverage_matrix --check" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_terminal_closure_certificate.py --json" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_gateway_ingress_manifest.py --allow-placeholder" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_reflective_contracts.py" in REQUIRED_CI_LITERALS
    assert "Python Tests (ubuntu-latest, Python 3.13)" in REQUIRED_CI_LITERALS
    assert "needs: [python-tests, python-compatibility, python-soak-tests]" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json" in REQUIRED_CI_LITERALS
    assert "schemas/deployment_publication_closure_validation.schema.json" in REQUIRED_CI_LITERALS
    assert "deployment-publication-closure-validation" in REQUIRED_CI_LITERALS
    assert "build-verification-deployment-publication-closure-validation" in REQUIRED_CI_LITERALS
    assert ".change_assurance/deployment_publication_closure_validation.json" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_logic_governance_application.py" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_governed_runtime_promotion.py --output .change_assurance/governed_runtime_promotion_readiness.json" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_governed_swarm_promotion_readiness.py --staging-evidence-bundle docs/governed-swarm-staging-evidence-bundle-example.json --target-environment pilot --output .change_assurance/governed_swarm_promotion_readiness.json --strict" in REQUIRED_CI_LITERALS
    assert "python scripts/validate_governed_swarm_production_readiness.py --pilot-readiness docs/governed-swarm-promotion-readiness-example.json --deployment-witness docs/governed-swarm-production-deployment-witness-example.json --public-health-declaration docs/governed-swarm-public-production-health-declaration-example.json --output .change_assurance/governed_swarm_production_readiness.json --strict" in REQUIRED_CI_LITERALS
    assert "cargo build --release" in REQUIRED_CI_LITERALS
    assert any(
        "validate_general_agent_promotion_closure_plan.py" in literal
        for literal in REQUIRED_CI_LITERALS
    )
    assert any(
        "validate_deployment_publication_closure_plan_schema.py" in literal
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
    assert content.count("python -m scripts.proof_coverage_matrix --check") == 2
    assert content.count("python scripts/validate_terminal_closure_certificate.py --json") == 1
    assert content.count("python scripts/validate_gateway_ingress_manifest.py --allow-placeholder") == 2
    assert content.count("python scripts/validate_reflective_contracts.py") == 1
    assert content.count("python scripts/validate_logic_governance_application.py") == 1
    assert content.count("Python Tests (ubuntu-latest, Python 3.13)") == 1
    assert content.count("needs: [python-tests, python-compatibility, python-soak-tests]") == 1
    assert content.count("cargo build --release") == 1
    assert "Validate protocol manifest" in content
    assert "Validate proof coverage matrix" in content
    assert "Proof coverage matrix check" in content
    assert "Validate terminal closure certificate" in content
    assert "Validate logic governance application" in content
    assert "Gateway ingress manifest check" in content
    assert "Reflective Contract Guard" in content
    assert "Rust build check" in content
    assert "test -f schemas/deployment_publication_closure_validation.schema.json" in content
    assert "Upload build verification deployment publication closure validation" in content


def test_ci_workflow_runs_promotion_closure_schema_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert any("validate_general_agent_promotion_closure_plan_schema.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert any("validate_deployment_publication_closure_plan_schema.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert content.count("validate_general_agent_promotion_closure_plan_schema.py") == 2
    assert content.count("validate_deployment_publication_closure_plan_schema.py") == 2
    assert "deployment_publication_closure_plan_schema_validation.json" in content
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
    assert content.count("produce_capability_improvement_portfolio.py") == 2
    assert content.count("--portfolio-plan .change_assurance/capability_improvement_portfolio.json") == 4
    assert content.count("preflight_general_agent_promotion_handoff.py") == 2
    assert content.count("preflight_general_agent_promotion_handoff.py --output") == 2
    assert content.count("validate_general_agent_promotion_handoff_preflight.py") == 2
    assert content.count("validate_general_agent_promotion_handoff_preflight.py --report") == 2
    workflow_lines = content.splitlines()
    assert sum(
        1
        for line in workflow_lines
        if "preflight_general_agent_promotion_handoff.py" in line
        and "--strict --json" in line
    ) == 2
    packet_gate_lines = [
        index
        for index, line in enumerate(workflow_lines)
        if "validate_general_agent_promotion_handoff_packet.py --packet" in line
    ]
    closure_validation_lines = [
        index
        for index, line in enumerate(workflow_lines)
        if "validate_general_agent_promotion_closure_plan.py" in line
        and "--output .change_assurance/general_agent_promotion_closure_plan_validation.json" in line
    ]
    assert len(packet_gate_lines) == 2
    assert len(closure_validation_lines) == 2
    assert all(closure_line < packet_line for closure_line, packet_line in zip(closure_validation_lines, packet_gate_lines))
    assert "examples/general_agent_promotion_handoff_packet.json" in content
    assert "examples/general_agent_promotion_environment_bindings.json" in content
    assert "capability_improvement_portfolio.json" in content
    assert "general_agent_promotion_environment_binding_receipt.json" in content
    assert "general_agent_promotion_handoff_preflight.json" in content
    assert "Validate general-agent promotion closure plan" in content


def test_ci_workflow_runs_governed_swarm_promotion_readiness_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert any("validate_governed_swarm_promotion_readiness.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert content.count("validate_governed_swarm_promotion_readiness.py") == 2
    assert "governed-swarm-staging-evidence-bundle-example.json" in content
    assert ".change_assurance/governed_swarm_promotion_readiness.json" in content


def test_ci_workflow_runs_governed_swarm_production_readiness_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert any("validate_governed_swarm_production_readiness.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert content.count("validate_governed_swarm_production_readiness.py") == 2
    assert "governed-swarm-production-deployment-witness-example.json" in content
    assert "governed-swarm-public-production-health-declaration-example.json" in content
    assert ".change_assurance/governed_swarm_production_readiness.json" in content


def test_ci_workflow_runs_mil_audit_runbook_workflow_gate() -> None:
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    errors = validate_ci_workflow_text(content)

    assert errors == []
    assert any("validate_mil_audit_runbook_operator_checklist.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert any("test_preflight_mil_audit_runbook_workflow.py" in literal for literal in REQUIRED_CI_LITERALS)
    assert content.count(
        "python scripts/validate_mil_audit_runbook_operator_checklist.py "
        "--checklist examples/mil_audit_runbook_operator_checklist.json --json"
    ) == 1
    assert content.count("test_preflight_mil_audit_runbook_workflow.py") == 1
    assert content.count("test_validate_mil_audit_runbook_operator_checklist.py") == 1
    assert "Validate MIL audit runbook workflow" in content


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
