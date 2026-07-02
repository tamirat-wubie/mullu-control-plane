#!/usr/bin/env python3
"""Deterministic release-status validation for the MCOI internal-alpha surface.

Validates:
  1. Required release, operator, and pilot governance documents exist.
  2. Shared schemas, contract parity, and canonical fixtures remain valid.
  3. Shipped artifacts and governed operational docs remain aligned with live inventories.
  4. The CI workflow still carries the required test and validation command gates.
  5. A single release summary can be derived from live profiles, packs, schemas, and witnesses.

Usage:
  python scripts/validate_release_status.py
  python scripts/validate_release_status.py --strict
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.app.policy_packs import PolicyPackRegistry  # noqa: E402
from mcoi_runtime.app.profiles import list_profiles  # noqa: E402
from scripts import (  # noqa: E402
    validate_artifacts,
    validate_logic_governance_application,
    validate_protocol_manifest,
    validate_public_naming_readiness,
    validate_schemas,
)


REQUIRED_RELEASE_DOCUMENTS: tuple[str, ...] = (
    "README.md",
    "STATUS.md",
    "GITHUB_SURFACE.md",
    "DEPLOYMENT_STATUS.md",
    "docs/00_platform_overview.md",
    "docs/PRODUCT_BOUNDARY.md",
    "RELEASE_NOTES_v0.1.md",
    "RELEASE_CHECKLIST_v0.1.md",
    "KNOWN_LIMITATIONS_v0.1.md",
    "SECURITY_MODEL_v0.1.md",
    "OPERATOR_GUIDE_v0.1.md",
    "PILOT_WORKFLOWS_v0.1.md",
    "PILOT_CHECKLIST_v0.1.md",
    "PILOT_OPERATIONS_GUIDE_v0.1.md",
    "docs/59_general_agent_promotion_handoff_packet.md",
    "docs/60_logic_governance_application.md",
)

CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEPLOYMENT_WITNESS_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "deployment-witness.yml"
GATEWAY_PUBLICATION_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "gateway-publication.yml"
API_IMAGE_PUBLICATION_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "api-image-publication.yml"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

REQUIRED_CI_LITERALS: tuple[str, ...] = (
    'branches: [main, "codex/*", "phase-*", "maf/*", "mcoi/*", "infra/*"]',
    "mcoi-shard:",
    'python ../scripts/run_mcoi_shards.py --shard "${{ matrix.mcoi-shard }}"',
    "python ../scripts/run_mcoi_shards.py --soak-only",
    "Python Tests (ubuntu-latest, Python 3.13)",
    "needs: [python-tests, python-compatibility, python-soak-tests]",
    "npm run verify",
    "cargo test",
    "cargo build --release",
    "cargo fmt -- --check",
    "cargo clippy -- -D warnings",
    "python scripts/validate_schemas.py",
    "python scripts/validate_protocol_manifest.py",
    "python scripts/validate_logic_governance_application.py",
    "python -m scripts.proof_coverage_matrix --check",
    "python scripts/validate_terminal_closure_certificate.py --json",
    "python scripts/validate_artifacts.py",
    "python scripts/validate_schemas.py --strict",
    "python scripts/validate_artifacts.py --strict",
    "python scripts/validate_public_repository_surface.py",
    "python scripts/validate_public_repository_surface.py --local-only",
    "python scripts/validate_release_status.py",
    "python scripts/validate_release_status.py --strict",
    "python scripts/validate_reflective_contracts.py",
    "python scripts/run_red_team_harness.py --output .change_assurance/red_team_harness.json --min-pass-rate 1.0",
    "red-team-harness-witness",
    "python -m pytest tests/test_gateway tests/test_pilot_proof_slice.py -q",
    "python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json",
    "python scripts/validate_gateway_deployment_env.py --strict",
    "python scripts/validate_gateway_ingress_manifest.py --allow-placeholder",
    "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json",
    "schemas/deployment_publication_closure_validation.schema.json",
    "deployment-publication-closure-validation",
    "build-verification-deployment-publication-closure-validation",
    ".change_assurance/deployment_publication_closure_validation.json",
    "schemas/reflex_deployment_witness_validator_receipt.schema.json",
    "python -m pytest tests/test_validate_reflex_deployment_witness.py -q --junitxml=.change_assurance/reflex_deployment_witness_validator_junit.xml",
    "python scripts/emit_reflex_deployment_witness_validator_receipt.py --junit .change_assurance/reflex_deployment_witness_validator_junit.xml --output .change_assurance/reflex_deployment_witness_validator_receipt.json --json",
    "reflex-deployment-witness-validator-receipt",
    ".change_assurance/reflex_deployment_witness_validator_junit.xml",
    ".change_assurance/reflex_deployment_witness_validator_receipt.json",
    "python scripts/validate_general_agent_promotion_handoff_packet.py --packet examples/general_agent_promotion_handoff_packet.json --json",
    "python scripts/validate_general_agent_promotion_operator_checklist.py --checklist examples/general_agent_promotion_operator_checklist.json --json",
    "python scripts/validate_general_agent_promotion_environment_bindings.py --contract examples/general_agent_promotion_environment_bindings.json --json",
    "python scripts/emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance/general_agent_promotion_environment_binding_receipt.json --json",
    "python scripts/validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance/general_agent_promotion_environment_binding_receipt.json --require-ready --json",
    "python scripts/validate_general_agent_promotion.py --output .change_assurance/general_agent_promotion_readiness.json",
    "python scripts/validate_governed_runtime_promotion.py --output .change_assurance/governed_runtime_promotion_readiness.json",
    "python scripts/validate_governed_swarm_promotion_readiness.py --staging-evidence-bundle docs/governed-swarm-staging-evidence-bundle-example.json --target-environment pilot --output .change_assurance/governed_swarm_promotion_readiness.json --strict",
    "python scripts/validate_governed_swarm_production_readiness.py --pilot-readiness docs/governed-swarm-promotion-readiness-example.json --deployment-witness docs/governed-swarm-production-deployment-witness-example.json --public-health-declaration docs/governed-swarm-public-production-health-declaration-example.json --output .change_assurance/governed_swarm_production_readiness.json --strict",
    "python scripts/produce_capability_improvement_portfolio.py --output .change_assurance/capability_improvement_portfolio.json --json --strict",
    "python scripts/plan_capability_adapter_closure.py --output .change_assurance/capability_adapter_closure_plan.json",
    "python scripts/validate_capability_adapter_closure_plan_schema.py --output .change_assurance/capability_adapter_closure_plan_schema_validation.json --strict",
    "python scripts/plan_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_plan.json",
    "python scripts/validate_deployment_publication_closure_plan_schema.py --output .change_assurance/deployment_publication_closure_plan_schema_validation.json --strict",
    "python scripts/plan_general_agent_promotion_closure.py --portfolio-plan .change_assurance/capability_improvement_portfolio.json --output .change_assurance/general_agent_promotion_closure_plan.json",
    "python scripts/validate_general_agent_promotion_closure_plan_schema.py --output .change_assurance/general_agent_promotion_closure_plan_schema_validation.json --strict",
    "python scripts/validate_general_agent_promotion_closure_plan.py --portfolio-plan .change_assurance/capability_improvement_portfolio.json --output .change_assurance/general_agent_promotion_closure_plan_validation.json --strict",
    "python scripts/preflight_general_agent_promotion_handoff.py --output .change_assurance/general_agent_promotion_handoff_preflight.json --strict --json",
    "python scripts/validate_general_agent_promotion_handoff_preflight.py --report .change_assurance/general_agent_promotion_handoff_preflight.json --require-ready --json",
    "python scripts/validate_mil_audit_runbook_operator_checklist.py --checklist examples/mil_audit_runbook_operator_checklist.json --json",
    "python -m pytest tests/test_preflight_mil_audit_runbook_workflow.py tests/test_validate_mil_audit_runbook_operator_checklist.py -q",
    "python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md",
    "python scripts/validate_public_naming_readiness.py",
    "python -m pytest tests/test_public_naming_readiness.py -q",
    "python scripts/validate_api_image_publication_workflow.py",
)

METADATA_DOCUMENTS: tuple[str, ...] = (
    "RELEASE_NOTES_v0.1.md",
    "KNOWN_LIMITATIONS_v0.1.md",
    "SECURITY_MODEL_v0.1.md",
)

STATUS_DOCUMENT_REQUIRED_LITERALS: tuple[str, ...] = (
    "Repository Status Witness",
    "Branch witness",
    "Release witness",
    "CI witness",
    "Governance witness",
    "Known Reflection Gaps",
    "GITHUB_SURFACE.md",
    "DEPLOYMENT_STATUS.md",
    "docs/00_platform_overview.md",
    "docs/PRODUCT_BOUNDARY.md",
    "docs/52_mullu_governance_protocol.md",
    "Protocol witness",
    "Logic governance witness",
    "Repository topology witness",
    "32-schema public contract index",
    "python scripts/validate_protocol_manifest.py",
    "python scripts/validate_release_status.py --strict",
    "python scripts/validate_gateway_deployment_env.py --strict",
    "python scripts/gateway_runtime_smoke.py",
    "python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md",
    "Deployment runtime input witness",
    "Refresh deployment runtime input witness (#466)",
    "MULLU_GATEWAY_URL",
    "docs/59_general_agent_promotion_handoff_packet.md",
    "docs/60_logic_governance_application.md",
    "examples/general_agent_promotion_handoff_packet.json",
    "examples/general_agent_promotion_environment_bindings.json",
    ".change_assurance/general_agent_promotion_environment_binding_receipt.json",
    "validate_general_agent_promotion_handoff_packet.py",
    "validate_general_agent_promotion_operator_checklist.py",
    "validate_general_agent_promotion_environment_bindings.py",
    "emit_general_agent_promotion_environment_binding_receipt.py",
    "validate_general_agent_promotion_environment_binding_receipt.py",
    "preflight_general_agent_promotion_handoff.py",
    "validate_general_agent_promotion_handoff_preflight.py",
    "validate_governed_runtime_promotion.py",
)

RELEASE_NOTES_REQUIRED_LITERALS: tuple[str, ...] = (
    "scripts/run_red_team_harness.py --output .change_assurance/red_team_harness.json --min-pass-rate 1.0",
    "pass_rate: 1.0",
    ".change_assurance/red_team_harness.json",
    "sha256:86a63fb36fe94ff44d44a8124625367aa1ead6b99a698a4ebd1b61c6024e5710",
)

RELEASE_CHECKLIST_REQUIRED_LITERALS: tuple[str, ...] = (
    "Release Checklist",
    "Shared schemas validate with `scripts/validate_schemas.py --strict`",
    "Public protocol manifest validates with `scripts/validate_protocol_manifest.py`",
    "Logic governance application validates with `scripts/validate_logic_governance_application.py`",
    "Shipped artifacts and document references validate with `scripts/validate_artifacts.py --strict`",
    "Release status derives from `scripts/validate_release_status.py --strict`",
    "CI workflow retains the full gated release command set in `.github/workflows/ci.yml`",
)

DEPLOYMENT_MATRIX_REQUIRED_LITERALS: tuple[str, ...] = (
    "## Scaling Boundary",
    "The default `MULLU_STATE_DIR` snapshot path is a node-local repair and restart",
    "ReadWriteOnce state volume must run a single gateway replica",
    "Pilot and production multi-replica deployments must externalize governed state",
    "PostgreSQL via `MULLU_COMMAND_LEDGER_DB_URL`",
    "PostgreSQL audit store with atomic append",
    "RWX volume or object-store backed artifact path",
    "Ledger concurrency contract",
    "File snapshots are derived recovery artifacts, never the source of truth",
    "If `MULLU_STATE_DIR` is mounted as ReadWriteOnce, set gateway replicas to",
    "If gateway replicas are greater than `1`, use PostgreSQL for all governed",
)

PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS: dict[str, tuple[str, ...]] = {
    "GITHUB_SURFACE.md": (
        "GitHub Surface Witness",
        "Public surface mode",
        "quiet",
        "Expected description",
        "(none)",
        "v3.13.3",
        "No repository topics are required while quiet mode is active.",
        "docs/00_platform_overview.md",
        "docs/PRODUCT_BOUNDARY.md",
        "docs/52_mullu_governance_protocol.md",
        "python scripts/validate_protocol_manifest.py",
        "python scripts/validate_public_repository_surface.py",
    ),
    "docs/00_platform_overview.md": (
        "Platform Overview",
        "Repository Topology Decision",
        "repository: mullu-control-plane",
        "product: Mullu Govern",
        "company: Mullusi",
        "Do not split this repository while the active blocker is deployment evidence.",
        "Issue `#330` is closed by signed deployment witness evidence.",
        "target does not by itself prove the final product architecture",
    ),
    "docs/PRODUCT_BOUNDARY.md": (
        "Product Boundary",
        "Mullu Govern is the public product",
        "Mullu Control Plane",
        "Mullu Platform",
        "Mullusi",
        "Launch Constraint",
        "This rename target is not a repository-split trigger",
    ),
    "DEPLOYMENT_STATUS.md": (
        "Deployment Status Witness",
        "**Deployment witness state:**",
        "**Public production health endpoint:**",
        "https://api.mullusi.com/health",
        "python scripts/validate_gateway_deployment_env.py --strict",
        "python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json",
        "python scripts/collect_runtime_conformance.py --gateway-url \"$MULLU_GATEWAY_URL\" --conformance-secret \"$MULLU_RUNTIME_CONFORMANCE_SECRET\" --authority-operator-secret \"$MULLU_AUTHORITY_OPERATOR_SECRET\" --output .change_assurance/runtime_conformance_certificate.json",
        ".change_assurance/runtime_conformance_certificate.json",
        "schemas/runtime_conformance_collection.schema.json",
        "python scripts/collect_deployment_witness.py --gateway-url \"$MULLU_GATEWAY_URL\" --witness-secret \"$MULLU_RUNTIME_WITNESS_SECRET\" --conformance-secret \"$MULLU_RUNTIME_CONFORMANCE_SECRET\" --output .change_assurance/deployment_witness.json",
        "python scripts/collect_deployment_witness.py --gateway-url \"$MULLU_GATEWAY_URL\" --witness-secret \"$MULLU_RUNTIME_WITNESS_SECRET\" --conformance-secret \"$MULLU_RUNTIME_CONFORMANCE_SECRET\" --deployment-witness-secret \"$MULLU_DEPLOYMENT_WITNESS_SECRET\" --require-production-evidence --output .change_assurance/deployment_witness.json",
        "responsibility_debt_clear=true",
        "runtime_responsibility_debt_clear=true",
        "authority_responsibility_debt_clear=true",
        "/deployment/witness",
        "/capabilities/evidence",
        "/audit/verify",
        "/proof/verify",
        "schemas/production_evidence_witness.schema.json",
        "schemas/capability_evidence_endpoint.schema.json",
        "schemas/audit_verification_endpoint.schema.json",
        "schemas/proof_verification_endpoint.schema.json",
        ".github/workflows/deployment-witness.yml",
        ".github/workflows/gateway-publication.yml",
        ".github/workflows/api-image-publication.yml",
        "python scripts/validate_api_image_publication_workflow.py",
        ".change_assurance/api_image_publication_receipt.json",
        "api-image-publication-receipt",
        "python scripts/collect_deployment_publication_evidence_packet.py --output-dir .change_assurance\\deployment_publication_evidence_packet --gateway-url \"$env:MULLU_GATEWAY_URL\" --expected-environment \"$env:MULLU_EXPECTED_RUNTIME_ENV\" --upstream-readiness-report \"$env:UPSTREAM_API_READINESS_REPORT\" --dns-record-type \"$env:MULLU_GATEWAY_DNS_RECORD_TYPE\" --dns-target \"$env:MULLU_GATEWAY_DNS_TARGET\" --dns-provider \"$env:MULLU_DNS_PROVIDER\" --dispatch-witness --json",
        "python scripts/validate_deployment_publication_evidence_packet.py --packet .change_assurance\\deployment_publication_evidence_packet\\deployment_publication_evidence_packet.json --output .change_assurance\\deployment_publication_evidence_packet\\deployment_publication_evidence_packet_validation.json --require-ready --json",
        "python scripts/emit_deployment_publication_operator_input_request.py --packet .change_assurance\\deployment_publication_evidence_packet\\deployment_publication_evidence_packet.json --output .change_assurance\\deployment_publication_evidence_packet\\deployment_publication_operator_input_request.json --json",
        "python scripts\\validate_deployment_publication_operator_input_request.py --request .change_assurance\\deployment_publication_evidence_packet\\deployment_publication_operator_input_request.json --output .change_assurance\\deployment_publication_evidence_packet\\deployment_publication_operator_input_request_validation.json --json",
        "python scripts/emit_deployment_upstream_blocker_receipt.py --target-gateway-url \"$env:MULLU_GATEWAY_URL\" --upstream-readiness-report \"$env:UPSTREAM_API_READINESS_REPORT\" --output .change_assurance\\deployment_upstream_blocker_receipt.json --json",
        "python scripts/validate_deployment_upstream_blocker_receipt.py --receipt .change_assurance/deployment_upstream_blocker_receipt.json --output .change_assurance/deployment_upstream_blocker_receipt_validation.json --require-ready",
        "python scripts/emit_gateway_dns_target_binding_receipt.py --gateway-host \"$MULLU_GATEWAY_HOST\" --gateway-url \"$MULLU_GATEWAY_URL\" --expected-environment \"$MULLU_EXPECTED_RUNTIME_ENV\" --record-type \"$MULLU_GATEWAY_DNS_RECORD_TYPE\" --target \"$MULLU_GATEWAY_DNS_TARGET\" --provider \"$MULLU_DNS_PROVIDER\" --output .change_assurance/gateway_dns_target_binding_receipt.json --json",
        "python scripts/validate_gateway_dns_target_binding_receipt.py --receipt .change_assurance/gateway_dns_target_binding_receipt.json --output .change_assurance/gateway_dns_target_binding_receipt_validation.json --require-ready",
        "python scripts/collect_gateway_dns_resolution_receipt.py --gateway-url \"$MULLU_GATEWAY_URL\" --output .change_assurance/gateway_dns_resolution_receipt.json --json",
        "python scripts/validate_gateway_dns_resolution_receipt.py --receipt .change_assurance/gateway_dns_resolution_receipt.json --output .change_assurance/gateway_dns_resolution_receipt_validation.json --require-resolved",
        "python scripts/orchestrate_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --apply-ingress --require-preflight --require-mcp-operator-checklist --skip-target-provisioning --dispatch --orchestration-output \"$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT\"",
        ".change_assurance/deployment_witness_orchestration.json",
        "python scripts/validate_deployment_orchestration_receipt.py --receipt \"$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT\" --require-mcp-operator-checklist --require-preflight --expected-environment pilot",
        "python scripts/plan_capability_adapter_closure.py --json",
        "python scripts/validate_capability_adapter_closure_plan_schema.py --strict",
        "python scripts/plan_deployment_publication_closure.py --json",
        "python scripts/validate_deployment_publication_closure_plan_schema.py --strict",
        "python scripts/plan_general_agent_promotion_closure.py --json",
        "python scripts/validate_general_agent_promotion_closure_plan_schema.py --strict",
        "python scripts/validate_general_agent_promotion_closure_plan.py --strict",
        "python scripts/validate_general_agent_promotion_handoff_packet.py --packet examples/general_agent_promotion_handoff_packet.json --json",
        "python scripts/validate_general_agent_promotion_operator_checklist.py --checklist examples/general_agent_promotion_operator_checklist.json --json",
        "python scripts/validate_general_agent_promotion_environment_bindings.py --contract examples/general_agent_promotion_environment_bindings.json --json",
        "python scripts/emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance/general_agent_promotion_environment_binding_receipt.json --json",
        "python scripts/validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance/general_agent_promotion_environment_binding_receipt.json --require-ready --json",
        "python scripts/produce_browser_sandbox_evidence.py --output \"$MULLU_BROWSER_SANDBOX_EVIDENCE\" --strict",
        "python scripts/validate_sandbox_execution_receipt.py --receipt \"$MULLU_BROWSER_SANDBOX_EVIDENCE\" --capability-prefix browser. --require-no-workspace-changes --json",
        "python scripts/validate_browser_sandbox_evidence.py --evidence \"$MULLU_BROWSER_SANDBOX_EVIDENCE\" --json",
        "python scripts/preflight_general_agent_promotion_handoff.py --output .change_assurance/general_agent_promotion_handoff_preflight.json --strict --json",
        "python scripts/validate_general_agent_promotion_handoff_preflight.py --report .change_assurance/general_agent_promotion_handoff_preflight.json --require-ready --json",
        "python scripts/validate_governed_runtime_promotion.py --strict",
        "docs/59_general_agent_promotion_handoff_packet.md",
        "examples/general_agent_promotion_handoff_packet.json",
        "examples/general_agent_promotion_environment_bindings.json",
        ".change_assurance/general_agent_promotion_environment_binding_receipt.json",
        "python scripts/gateway_runtime_smoke.py",
        "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json",
        "python scripts/validate_gateway_ingress_manifest.py --allow-placeholder",
        ".change_assurance/deployment_publication_closure_validation.json",
        "python scripts/apply_deployment_publication_status.py --operator-approval-ref \"$MULLU_DEPLOYMENT_PUBLICATION_APPROVAL_REF\" --receipt-output .change_assurance/public_production_health_declaration.json",
        ".change_assurance/public_production_health_declaration.json",
        "schemas/public_production_health_declaration.schema.json",
        "python scripts/validate_public_repository_surface.py",
        "## GitHub Runtime Input State",
        "GitHub Actions secret name `MULLU_RUNTIME_WITNESS_SECRET` is present; secret value is not printed",
        "GitHub Actions secret name `MULLU_RUNTIME_CONFORMANCE_SECRET` is present; secret value is not printed",
        "GitHub Actions secret name `MULLU_DEPLOYMENT_WITNESS_SECRET` is present; secret value is not printed",
        "GitHub Actions secret name `MULLU_AUTHORITY_OPERATOR_SECRET` is present; secret value is not printed",
        "GitHub repository variables `MULLU_GATEWAY_URL=https://api.mullusi.com` and `MULLU_EXPECTED_RUNTIME_ENV=pilot` are set",
    ),
}
DEPLOYMENT_STATE_PATTERN = re.compile(
    r"^\*\*Deployment witness state:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
PUBLIC_HEALTH_PATTERN = re.compile(
    r"^\*\*Public production health endpoint:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)

DEPLOYMENT_STATUS_WITNESS_ALIGNMENT_REQUIRED_LITERALS: tuple[str, ...] = (
    "**Deployment witness state:**",
    "**Public production health endpoint:**",
    ".change_assurance/deployment_witness.json",
    ".change_assurance/public_production_health_declaration.json",
    "deployment_claim=published",
    "https://api.mullusi.com/health",
)

DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS: tuple[str, ...] = (
    "Deployment Witness Collection",
    "workflow_dispatch",
    "gateway_url",
    "operator_approval_ref",
    "governed_swarm_pilot_readiness_path",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
    "python scripts/preflight_deployment_witness.py",
    "--accept-repository-input-env",
    "--accept-workflow-file",
    ".change_assurance/deployment_witness_preflight.json",
    "deployment-witness-preflight",
    "python scripts/collect_runtime_conformance.py",
    '--authority-operator-secret "$MULLU_AUTHORITY_OPERATOR_SECRET"',
    ".change_assurance/runtime_conformance_certificate.json",
    "runtime-conformance-collection",
    "python scripts/collect_deployment_witness.py",
    '--conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET"',
    '--deployment-witness-secret "$MULLU_DEPLOYMENT_WITNESS_SECRET"',
    "--require-production-evidence",
    ".change_assurance/deployment_witness.json",
    "python scripts/apply_deployment_publication_status.py",
    "--operator-approval-ref \"${{ inputs.operator_approval_ref }}\"",
    ".change_assurance/public_production_health_declaration.json",
    "python scripts/validate_deployment_publication_closure.py",
    "--declaration-receipt .change_assurance/public_production_health_declaration.json",
    ".change_assurance/deployment_publication_closure_validation.json",
    "public-production-health-declaration",
    "python scripts/validate_governed_swarm_production_readiness.py",
    '--pilot-readiness "${{ inputs.governed_swarm_pilot_readiness_path }}"',
    "--deployment-witness .change_assurance/deployment_witness.json",
    "--public-health-declaration .change_assurance/public_production_health_declaration.json",
    "--output .change_assurance/governed_swarm_production_readiness.json",
    "governed-swarm-production-readiness",
    ".change_assurance/governed_swarm_production_readiness.json",
    "actions/upload-artifact@v6",
)

GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS: tuple[str, ...] = (
    "Gateway Publication Orchestration",
    "workflow_dispatch",
    "gateway_host",
    "apply_ingress",
    "dispatch_witness",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "MULLU_KUBECONFIG_B64",
    "python scripts/orchestrate_deployment_witness.py",
    "--require-preflight",
    "--require-mcp-operator-checklist",
    "--skip-target-provisioning",
    "--orchestration-output .change_assurance/deployment_witness_orchestration.json",
    "python scripts/validate_deployment_orchestration_receipt.py",
    ".change_assurance/deployment_witness_orchestration_validation.json",
    "--accept-runtime-secret-env",
    "--accept-conformance-secret-env",
    "--accept-deployment-witness-secret-env",
    "actions/upload-artifact@v6",
)
API_IMAGE_PUBLICATION_WORKFLOW_REQUIRED_LITERALS: tuple[str, ...] = (
    "API Image Publication",
    "workflow_dispatch",
    "operator_approval_ref",
    "confirm_publication",
    "packages: write",
    "docker/login-action@v3",
    "docker/build-push-action@v6",
    "ghcr.io/tamirat-wubie/mullu-control-plane",
    "push: ${{ inputs.confirm_publication }}",
    "api_image_publication_receipt.json",
    "api-image-publication-receipt",
    "secret_values_serialized",
    "dns_mutated",
    "runtime_mutated",
)

PLACEHOLDER_WORKFLOW_FILENAMES: tuple[str, ...] = (
    "scaffold.yml",
    "validation-placeholder.yml",
)
PLACEHOLDER_WORKFLOW_LITERALS: tuple[str, ...] = (
    "Validation placeholder for Milestone 0",
    "Mullu Platform scaffold workflow",
    "Placeholder step",
)

ACCEPTED_LIMITATION_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "registry_backend_limitation": (
        "make_dataclass",
    ),
    "coordination_persistence_limitation": (
        "Coordination state persistence is explicit and opt-in",
        "does not auto-save or auto-restore",
    ),
    "memory_persistence_limitation": (
        "Working and episodic memory persistence is explicit and opt-in",
        "does not auto-save or auto-restore",
    ),
    "http_connector_limitation": (
        "HTTP connector",
        "urllib",
    ),
    "auth_limitation": (
        "RBAC",
        "approval chains",
    ),
    "encryption_limitation": (
        "Field-Level Encryption",
        "AES-256-GCM",
    ),
}

PUBLIC_NAMING_RELEASE_SURFACE_LITERALS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "docs/PUBLIC_NAMING_REVIEW_PACKET.md",
        "docs/PUBLIC_NAMING_ARTIFACT_MANIFEST.md",
        "python scripts/report_public_naming_readiness.py",
        "python scripts/plan_public_naming_transition.py",
    ),
    "RELEASE_CHECKLIST_v0.1.md": (
        "docs/PUBLIC_NAMING_REVIEW_PACKET.md",
        "docs/PUBLIC_NAMING_ARTIFACT_MANIFEST.md",
        "python scripts/report_public_naming_readiness.py",
        "python scripts/plan_public_naming_transition.py",
        "No paid public product launch under `Mullu Govern` until clearance evidence is complete",
    ),
    "PILOT_CHECKLIST_v0.1.md": (
        "Public naming review packet has been checked",
        "Public naming artifact manifest is intact",
        "docs/PUBLIC_NAMING_REVIEW_PACKET.md",
        "paid public launch",
    ),
}

QUIET_PUBLIC_README_REQUIRED_LITERALS: tuple[str, ...] = (
    "# Repository Notice",
    "Public documentation is intentionally minimized at this time.",
    "This repository is not accepting public use, issues, or external contributions.",
    "See `LICENSE` for usage terms.",
)


def is_quiet_public_readme(content: str) -> bool:
    """Return true when README.md is intentionally minimized for public quiet mode."""
    return "Public documentation is intentionally minimized at this time." in content

SOURCE_HYGIENE_GLOBS: tuple[str, ...] = ("*.py", "*.rs", "*.toml", "*.yml", "*.yaml")
IGNORED_SOURCE_DIR_SEGMENTS: tuple[str, ...] = (
    ".claude",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
    "target",
)
PYTHON_BARE_EXCEPT_PATTERN = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
LINE_COMMENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"#\s*(TODO|FIXME|HACK)\b"),
    re.compile(r"//\s*(TODO|FIXME|HACK)\b"),
    re.compile(r"/\*\s*(TODO|FIXME|HACK)\b"),
)
MOJIBAKE_SOURCE_MARKERS: tuple[tuple[str, str], ...] = (
    ("\ufeff", "utf8_byte_order_mark"),
    ("\u00e2", "utf8_decoded_as_latin1_lead_byte"),
    ("\u00c3", "utf8_decoded_as_latin1_prefix"),
    ("\u00c2", "utf8_decoded_as_latin1_continuation"),
    ("\ufffd", "replacement_character"),
)


@dataclass(frozen=True, slots=True)
class ReleaseStatusSummary:
    """Live governed inventory behind the release-status claim."""

    release_documents: tuple[str, ...]
    schema_files: tuple[str, ...]
    builtin_profiles: tuple[str, ...]
    policy_packs: tuple[str, ...]
    config_artifacts: tuple[str, ...]
    request_artifacts: tuple[str, ...]
    auxiliary_artifacts: tuple[str, ...]
    maf_runtime_fixtures: tuple[str, ...]
    mcoi_runtime_fixtures: tuple[str, ...]
    ci_workflow_present: bool
    release_version: str | None
    release_date: str | None


def _sorted_names(paths: tuple[Path, ...] | list[Path]) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(REPO_ROOT).as_posix() for path in paths))


def discover_release_status_summary() -> ReleaseStatusSummary:
    """Collect the live governed inventory behind the release surface."""
    artifact_inventory = validate_artifacts.discover_example_inventory()
    schema_files = tuple(
        sorted(path.name for path in validate_schemas.SCHEMA_DIR.glob("*.schema.json"))
    )
    release_documents = tuple(
        document_name
        for document_name in REQUIRED_RELEASE_DOCUMENTS
        if (REPO_ROOT / document_name).exists()
    )
    builtin_profiles = tuple(sorted(list_profiles()))
    policy_packs = tuple(
        sorted(pack.pack_id for pack in PolicyPackRegistry().list_packs())
    )

    return ReleaseStatusSummary(
        release_documents=release_documents,
        schema_files=schema_files,
        builtin_profiles=builtin_profiles,
        policy_packs=policy_packs,
        config_artifacts=_sorted_names(list(artifact_inventory.config_paths)),
        request_artifacts=_sorted_names(list(artifact_inventory.request_paths)),
        auxiliary_artifacts=_sorted_names(list(artifact_inventory.auxiliary_paths)),
        maf_runtime_fixtures=_sorted_names(list(artifact_inventory.maf_runtime_fixture_paths)),
        mcoi_runtime_fixtures=_sorted_names(list(artifact_inventory.mcoi_runtime_fixture_paths)),
        ci_workflow_present=CI_WORKFLOW_PATH.exists(),
        release_version=None,
        release_date=None,
    )


def validate_ci_workflow_text(content: str) -> list[str]:
    """Validate that the CI workflow carries the required release gates."""
    errors: list[str] = []

    missing_literals = tuple(
        literal for literal in REQUIRED_CI_LITERALS if literal not in content
    )
    if missing_literals:
        errors.append(f"ci workflow missing required literals: {list(missing_literals)}")

    return errors


def validate_deployment_witness_workflow_text(content: str) -> list[str]:
    """Validate the manual deployment witness workflow is still evidence-bearing."""
    errors: list[str] = []
    missing_literals = tuple(
        literal for literal in DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS if literal not in content
    )
    if missing_literals:
        errors.append(
            f"deployment witness workflow missing required literals: {list(missing_literals)}"
        )
    return errors


def validate_gateway_publication_workflow_text(content: str) -> list[str]:
    """Validate the gateway publication workflow preserves handoff evidence."""
    errors: list[str] = []
    missing_literals = tuple(
        literal for literal in GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS if literal not in content
    )
    if missing_literals:
        errors.append(
            f"gateway publication workflow missing required literals: {list(missing_literals)}"
        )
    return errors


def validate_api_image_publication_workflow_text(content: str) -> list[str]:
    """Validate the API image publication workflow preserves approval and receipt evidence."""
    errors: list[str] = []
    missing_literals = tuple(
        literal for literal in API_IMAGE_PUBLICATION_WORKFLOW_REQUIRED_LITERALS if literal not in content
    )
    if missing_literals:
        errors.append(
            f"api image publication workflow missing required literals: {list(missing_literals)}"
        )
    if "on:\n  workflow_dispatch:" not in content:
        errors.append("api image publication workflow must be manual workflow_dispatch only")
    forbidden_triggers = {"  push:", "  pull_request:"}
    if any(line.rstrip() in forbidden_triggers for line in content.splitlines()):
        errors.append("api image publication workflow must not use push or pull_request triggers")
    return errors


def validate_workflow_hygiene(workflow_texts: dict[str, str]) -> list[str]:
    """Reject stale placeholder workflows from the public repository surface."""
    errors: list[str] = []
    for workflow_name, content in sorted(workflow_texts.items()):
        path_name = Path(workflow_name).name
        if path_name in PLACEHOLDER_WORKFLOW_FILENAMES:
            errors.append(f"{workflow_name}: placeholder workflow must be removed")
        if "jobs:\n  placeholder:" in content:
            errors.append(f"{workflow_name}: placeholder job must be removed")
        missing_hygiene = tuple(
            literal for literal in PLACEHOLDER_WORKFLOW_LITERALS if literal in content
        )
        if missing_hygiene:
            errors.append(
                f"{workflow_name}: placeholder workflow literals remain: {list(missing_hygiene)}"
            )
    return errors


def validate_protocol_manifest_surface() -> list[str]:
    """Validate the public protocol index as a release gate."""
    manifest = validate_protocol_manifest.load_manifest()
    return [
        f"protocol manifest: {error}"
        for error in validate_protocol_manifest.validate_protocol_manifest(manifest)
    ]


def validate_logic_governance_surface() -> list[str]:
    """Validate the formal logic governance doctrine as a release gate."""
    return [
        f"logic governance application: {error}"
        for error in validate_logic_governance_application.validate_logic_governance_document()
    ]


def _extract_metadata_field(content: str, label: str) -> str | None:
    match = re.search(rf"^\*\*{re.escape(label)}:\*\*\s*(.+)$", content, re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def validate_release_metadata_texts(metadata_texts: dict[str, str]) -> tuple[tuple[str | None, str | None], list[str]]:
    """Validate that release-surface docs carry aligned version and date metadata."""
    errors: list[str] = []
    extracted: dict[str, tuple[str | None, str | None]] = {}

    for document_name, content in metadata_texts.items():
        version = _extract_metadata_field(content, "Version")
        date = _extract_metadata_field(content, "Date")
        extracted[document_name] = (version, date)
        if version is None:
            errors.append(f"{document_name}: missing Version metadata")
        if date is None:
            errors.append(f"{document_name}: missing Date metadata")

    reference_version: str | None = None
    reference_date: str | None = None
    for document_name in METADATA_DOCUMENTS:
        version, date = extracted.get(document_name, (None, None))
        if version is not None and reference_version is None:
            reference_version = version
        if date is not None and reference_date is None:
            reference_date = date

    # Version must declare a recognized stage (internal alpha, or semver tag)
    if reference_version is not None:
        is_recognized = (
            "internal alpha" in reference_version
            or reference_version.startswith("0.")  # pre-1.0 semver
            or reference_version[0].isdigit()  # any semver like "0.2.0 (v3.9.2)"
        )
        if not is_recognized:
            errors.append(f"release metadata version not recognized: {reference_version}")

    for document_name, (version, date) in extracted.items():
        if reference_version is not None and version is not None and version != reference_version:
            errors.append(
                f"{document_name}: version metadata mismatch {version!r} != {reference_version!r}"
            )
        if reference_date is not None and date is not None and date != reference_date:
            errors.append(
                f"{document_name}: date metadata mismatch {date!r} != {reference_date!r}"
            )

    return (reference_version, reference_date), errors


def validate_release_limitation_coverage(
    *,
    known_limitations_text: str,
    security_model_text: str,
) -> list[str]:
    """Validate that accepted release limitations are anchored in supporting docs."""
    errors: list[str] = []
    limitation_sources = {
        "registry_backend_limitation": known_limitations_text,
        "coordination_persistence_limitation": known_limitations_text,
        "memory_persistence_limitation": known_limitations_text,
        "http_connector_limitation": known_limitations_text,
        "auth_limitation": security_model_text,
        "encryption_limitation": security_model_text,
    }

    for limitation_id, required_literals in ACCEPTED_LIMITATION_EXPECTATIONS.items():
        source = limitation_sources[limitation_id]
        missing_literals = tuple(literal for literal in required_literals if literal not in source)
        if missing_literals:
            errors.append(
                f"{limitation_id}: missing supporting literals {list(missing_literals)}"
            )

    return errors


def validate_status_document_text(content: str) -> list[str]:
    """Validate that the public repository-status witness has required anchors."""
    errors: list[str] = []
    missing_literals = tuple(
        literal
        for literal in STATUS_DOCUMENT_REQUIRED_LITERALS
        if literal not in content
    )
    if missing_literals:
        errors.append(
            f"STATUS.md missing required public-state anchors: {list(missing_literals)}"
        )
    return errors


def validate_deployment_status_phase_text(content: str) -> list[str]:
    """Validate deployment status phase anchors without pinning one phase."""
    errors: list[str] = []
    state_match = DEPLOYMENT_STATE_PATTERN.search(content)
    endpoint_match = PUBLIC_HEALTH_PATTERN.search(content)
    if state_match is None:
        errors.append("DEPLOYMENT_STATUS.md missing deployment witness state")
        return errors
    if endpoint_match is None:
        errors.append("DEPLOYMENT_STATUS.md missing public production health endpoint")
        return errors

    deployment_state = state_match.group(1).strip()
    public_health_endpoint = endpoint_match.group(1).strip()
    if deployment_state == "not-published":
        if public_health_endpoint != "not-declared":
            errors.append("not-published deployment must keep public health not-declared")
        if "deployment_claim=not-published" not in content:
            errors.append("not-published deployment status missing blocked witness anchor")
        return errors

    if deployment_state == "published":
        if not public_health_endpoint.startswith("https://"):
            errors.append("published deployment must declare an HTTPS public health endpoint")
        stale_fragments = (
            "deployment publication remains `not-published`",
            "deployment_claim=not-published",
            "live production runtime is not published",
            "public production health is not claimed",
            "`api.mullusi.com` remains `AwaitingEvidence`",
            "local deployment witness remains `not-published`",
            "public production health declaration while deployment publication remains",
            "Public production health | Not declared;",
        )
        stale = tuple(fragment for fragment in stale_fragments if fragment in content)
        if stale:
            errors.append(f"published deployment status contains stale blocked anchors: {list(stale)}")
        required_published_anchors = (
            "deployment_claim=published",
            ".change_assurance/public_production_health_declaration.json",
        )
        missing = tuple(anchor for anchor in required_published_anchors if anchor not in content)
        if missing:
            errors.append(f"published deployment status missing declaration anchors: {list(missing)}")
        return errors

    errors.append(f"unsupported deployment witness state: {deployment_state}")
    return errors


def validate_deployment_status_witness_alignment(content: str) -> list[str]:
    """Validate deployment status keeps witness and health declaration anchors aligned."""
    missing_literals = tuple(
        literal
        for literal in DEPLOYMENT_STATUS_WITNESS_ALIGNMENT_REQUIRED_LITERALS
        if literal not in content
    )
    if not missing_literals:
        return []
    return [
        "DEPLOYMENT_STATUS.md missing deployment witness alignment anchors: "
        f"{list(missing_literals)}"
    ]


def validate_public_surface_document_texts(
    document_texts: dict[str, str],
) -> list[str]:
    """Validate public-surface witness documents have required local anchors."""
    errors: list[str] = []
    for document_name, required_literals in PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS.items():
        content = document_texts.get(document_name)
        if content is None:
            errors.append(f"{document_name} missing from public-surface documents")
            continue
        missing_literals = tuple(
            literal for literal in required_literals if literal not in content
        )
        if missing_literals:
            errors.append(
                f"{document_name} missing required public-surface anchors: {list(missing_literals)}"
            )
        if document_name == "DEPLOYMENT_STATUS.md":
            errors.extend(validate_deployment_status_phase_text(content))
            errors.extend(validate_deployment_status_witness_alignment(content))
    return errors


def validate_public_naming_release_surface_links() -> list[str]:
    """Validate release-facing docs keep public naming review links visible."""
    errors: list[str] = []
    for relative_path, required_literals in PUBLIC_NAMING_RELEASE_SURFACE_LITERALS.items():
        path = REPO_ROOT / relative_path
        if not path.exists():
            errors.append(f"{relative_path}: missing public naming release surface")
            continue
        content = path.read_text(encoding="utf-8")
        if relative_path == "README.md" and is_quiet_public_readme(content):
            missing_quiet_literals = tuple(
                literal
                for literal in QUIET_PUBLIC_README_REQUIRED_LITERALS
                if literal not in content
            )
            if missing_quiet_literals:
                errors.append(
                    f"{relative_path}: missing quiet public README literals "
                    f"{list(missing_quiet_literals)}"
                )
            continue
        missing_literals = tuple(
            literal for literal in required_literals if literal not in content
        )
        if missing_literals:
            errors.append(
                f"{relative_path}: missing public naming literals {list(missing_literals)}"
            )
    return errors


def validate_release_notes_text(content: str) -> list[str]:
    """Validate release notes publish the red-team witness for this release."""
    missing_literals = tuple(
        literal for literal in RELEASE_NOTES_REQUIRED_LITERALS if literal not in content
    )
    if not missing_literals:
        return []
    return [
        "RELEASE_NOTES_v0.1.md missing required red-team release anchors: "
        f"{list(missing_literals)}"
    ]


def validate_release_checklist_text(content: str) -> list[str]:
    """Validate release checklist carries required governed release gates."""
    missing_literals = tuple(
        literal for literal in RELEASE_CHECKLIST_REQUIRED_LITERALS if literal not in content
    )
    if not missing_literals:
        return []
    return [
        "RELEASE_CHECKLIST_v0.1.md missing required release gates: "
        f"{list(missing_literals)}"
    ]


def validate_deployment_matrix_text(content: str) -> list[str]:
    """Validate deployment docs declare the scaling and ledger boundary."""
    missing_literals = tuple(
        literal for literal in DEPLOYMENT_MATRIX_REQUIRED_LITERALS if literal not in content
    )
    if not missing_literals:
        return []
    return [
        "DEPLOYMENT.md missing required scaling-boundary anchors: "
        f"{list(missing_literals)}"
    ]


def _iter_source_hygiene_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    pending = [REPO_ROOT]
    while pending:
        current = pending.pop()
        try:
            children = tuple(sorted(current.iterdir()))
        except OSError:
            continue
        for path in children:
            relative_path = path.relative_to(REPO_ROOT)
            if path.is_dir():
                if _skip_source_hygiene_directory(path, relative_path):
                    continue
                pending.append(path)
                continue
            if not path.is_file():
                continue
            if any(segment in IGNORED_SOURCE_DIR_SEGMENTS for segment in relative_path.parts):
                continue
            if not any(path.match(pattern) for pattern in SOURCE_HYGIENE_GLOBS):
                continue
            paths.append(path)
    return tuple(sorted(set(paths)))


def _skip_source_hygiene_directory(path: Path, relative_path: Path) -> bool:
    """Return whether a directory is outside release source-hygiene scope."""
    if any(segment in IGNORED_SOURCE_DIR_SEGMENTS for segment in relative_path.parts):
        return True
    if path != REPO_ROOT and (path / ".git").exists():
        return True
    return False


def scan_source_hygiene_text(path: Path, content: str) -> list[str]:
    """Scan one governed source file for release-checklist hygiene violations."""
    errors: list[str] = []
    relative_path = path.relative_to(REPO_ROOT).as_posix()

    if path.suffix == ".py" and PYTHON_BARE_EXCEPT_PATTERN.search(content):
        errors.append(f"{relative_path}: contains bare except clause")

    for pattern in LINE_COMMENT_PATTERNS:
        match = pattern.search(content)
        if match is not None:
            errors.append(
                f"{relative_path}: contains source hygiene marker {match.group(1)}"
            )
            break

    for marker, label in MOJIBAKE_SOURCE_MARKERS:
        if marker in content:
            errors.append(f"{relative_path}: contains mojibake marker {label}")
            break

    return errors


def validate_source_hygiene() -> list[str]:
    """Validate release-checklist hygiene claims across governed source files."""
    errors: list[str] = []
    for path in _iter_source_hygiene_paths():
        content = path.read_text(encoding="utf-8")
        errors.extend(scan_source_hygiene_text(path, content))
    return errors


def validate_release_status(*, strict: bool = False) -> tuple[ReleaseStatusSummary, list[str]]:
    """Validate the governed release surface and return live inventory plus errors."""
    errors: list[str] = []
    summary = discover_release_status_summary()

    missing_documents = tuple(
        document_name
        for document_name in REQUIRED_RELEASE_DOCUMENTS
        if document_name not in summary.release_documents
    )
    if missing_documents:
        errors.append(f"missing required release documents: {list(missing_documents)}")
    if not summary.ci_workflow_present:
        errors.append("missing required CI workflow: .github/workflows/ci.yml")
    else:
        ci_content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
        errors.extend(validate_ci_workflow_text(ci_content))
    if not DEPLOYMENT_WITNESS_WORKFLOW_PATH.exists():
        errors.append("missing required workflow: .github/workflows/deployment-witness.yml")
    else:
        workflow_content = DEPLOYMENT_WITNESS_WORKFLOW_PATH.read_text(encoding="utf-8")
        errors.extend(validate_deployment_witness_workflow_text(workflow_content))
    if not GATEWAY_PUBLICATION_WORKFLOW_PATH.exists():
        errors.append("missing required workflow: .github/workflows/gateway-publication.yml")
    else:
        workflow_content = GATEWAY_PUBLICATION_WORKFLOW_PATH.read_text(encoding="utf-8")
        errors.extend(validate_gateway_publication_workflow_text(workflow_content))
    if not API_IMAGE_PUBLICATION_WORKFLOW_PATH.exists():
        errors.append("missing required workflow: .github/workflows/api-image-publication.yml")
    else:
        workflow_content = API_IMAGE_PUBLICATION_WORKFLOW_PATH.read_text(encoding="utf-8")
        errors.extend(validate_api_image_publication_workflow_text(workflow_content))
    workflow_texts = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(WORKFLOW_DIR.glob("*.y*ml"))
    }
    errors.extend(validate_workflow_hygiene(workflow_texts))

    status_document_path = REPO_ROOT / "STATUS.md"
    if status_document_path.exists():
        status_content = status_document_path.read_text(encoding="utf-8")
        errors.extend(validate_status_document_text(status_content))

    public_surface_texts = {
        document_name: (REPO_ROOT / document_name).read_text(encoding="utf-8")
        for document_name in PUBLIC_SURFACE_DOCUMENT_REQUIRED_LITERALS
        if (REPO_ROOT / document_name).exists()
    }
    errors.extend(validate_public_surface_document_texts(public_surface_texts))

    metadata_texts = {
        document_name: (REPO_ROOT / document_name).read_text(encoding="utf-8")
        for document_name in METADATA_DOCUMENTS
        if (REPO_ROOT / document_name).exists()
    }
    (release_version, release_date), metadata_errors = validate_release_metadata_texts(
        metadata_texts
    )
    errors.extend(metadata_errors)
    if len(metadata_texts) == len(METADATA_DOCUMENTS):
        errors.extend(validate_release_notes_text(metadata_texts["RELEASE_NOTES_v0.1.md"]))
        errors.extend(
            validate_release_limitation_coverage(
                known_limitations_text=metadata_texts["KNOWN_LIMITATIONS_v0.1.md"],
                security_model_text=metadata_texts["SECURITY_MODEL_v0.1.md"],
            )
        )
    release_checklist_path = REPO_ROOT / "RELEASE_CHECKLIST_v0.1.md"
    if release_checklist_path.exists():
        errors.extend(
            validate_release_checklist_text(
                release_checklist_path.read_text(encoding="utf-8")
            )
        )
    deployment_matrix_path = REPO_ROOT / "DEPLOYMENT.md"
    if deployment_matrix_path.exists():
        errors.extend(
            validate_deployment_matrix_text(
                deployment_matrix_path.read_text(encoding="utf-8")
            )
        )
    else:
        errors.append("missing required deployment matrix: DEPLOYMENT.md")

    errors.extend(validate_source_hygiene())
    errors.extend(validate_public_naming_release_surface_links())

    summary = ReleaseStatusSummary(
        release_documents=summary.release_documents,
        schema_files=summary.schema_files,
        builtin_profiles=summary.builtin_profiles,
        policy_packs=summary.policy_packs,
        config_artifacts=summary.config_artifacts,
        request_artifacts=summary.request_artifacts,
        auxiliary_artifacts=summary.auxiliary_artifacts,
        maf_runtime_fixtures=summary.maf_runtime_fixtures,
        mcoi_runtime_fixtures=summary.mcoi_runtime_fixtures,
        ci_workflow_present=summary.ci_workflow_present,
        release_version=release_version,
        release_date=release_date,
    )

    errors.extend(validate_schemas.validate_json_schemas())
    errors.extend(validate_schemas.check_contract_parity(strict=strict))
    errors.extend(validate_schemas.check_rust_contract_parity(strict=strict))
    errors.extend(validate_schemas.validate_canonical_fixtures(strict=strict))
    errors.extend(validate_schemas.check_python_fixture_round_trip())
    errors.extend(validate_protocol_manifest_surface())
    errors.extend(validate_logic_governance_surface())
    errors.extend(validate_artifacts.validate_example_artifacts(strict=strict))
    try:
        validate_public_naming_readiness.validate_public_naming_readiness()
    except AssertionError as exc:
        errors.append(f"public naming readiness failed: {exc}")

    if strict:
        if not summary.schema_files:
            errors.append("release status requires at least one schema file")
        if not summary.builtin_profiles:
            errors.append("release status requires at least one built-in profile")
        if not summary.policy_packs:
            errors.append("release status requires at least one policy pack")
        if not summary.config_artifacts:
            errors.append("release status requires at least one config artifact")
        if not summary.request_artifacts:
            errors.append("release status requires at least one request artifact")
        if not summary.maf_runtime_fixtures:
            errors.append("release status requires at least one MAF runtime fixture")
        if not summary.mcoi_runtime_fixtures:
            errors.append("release status requires at least one MCOI runtime fixture")

    return summary, errors


def main() -> None:
    strict = "--strict" in sys.argv
    summary, errors = validate_release_status(strict=strict)

    print("=== Release Status Summary ===")
    print(f"  release docs:       {len(summary.release_documents)}")
    print(f"  schemas:            {len(summary.schema_files)}")
    print(f"  builtin profiles:   {len(summary.builtin_profiles)}")
    print(f"  policy packs:       {len(summary.policy_packs)}")
    print(f"  config artifacts:   {len(summary.config_artifacts)}")
    print(f"  request artifacts:  {len(summary.request_artifacts)}")
    print(f"  auxiliary artifacts:{len(summary.auxiliary_artifacts):>4}")
    print(f"  MAF runtime fixtures:{len(summary.maf_runtime_fixtures):>3}")
    print(f"  MCOI runtime fixtures:{len(summary.mcoi_runtime_fixtures):>2}")
    print(f"  ci workflow:        {'present' if summary.ci_workflow_present else 'missing'}")
    print(f"  release version:    {summary.release_version or 'missing'}")
    print(f"  release date:       {summary.release_date or 'missing'}")

    print("\n=== Live Inventory ===")
    print(f"  profiles: {', '.join(summary.builtin_profiles)}")
    print(f"  packs:    {', '.join(summary.policy_packs)}")

    print("\n=== Release Validation ===")
    if errors:
        print(f"\n{'=' * 40}")
        print(f"FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    print("ALL RELEASE GATES PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
