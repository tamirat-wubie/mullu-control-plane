#!/usr/bin/env python3
"""Validate the proprietary GitHub repository metadata surface for governed reflection.

Purpose: compare versioned repository-surface witnesses with GitHub metadata and
latest-release state while quiet public-surface mode is active.
Governance scope: repository description, topics, latest release, deployment
status witness, authenticated metadata access, and required repository
documents.
Dependencies: Python standard library, GITHUB_SURFACE.md, DEPLOYMENT_STATUS.md,
STATUS.md, docs/00_platform_overview.md, GitHub REST endpoints, and optional
authenticated GitHub CLI access.
Invariants:
  - Repository metadata must match the versioned quiet-surface witness.
  - Latest release must match the governed release tag.
  - Deployment health must match the governed endpoint evidence declared in
    DEPLOYMENT_STATUS.md.
  - No required repository witness document may be absent.
  - Private repository metadata must be verified through authenticated access,
    not treated as a public endpoint.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_API_URL = "https://api.github.com/repos/tamirat-wubie/mullu-control-plane"
LATEST_RELEASE_API_URL = f"{REPOSITORY_API_URL}/releases/latest"
GITHUB_CLI_TIMEOUT_SECONDS = 30


def expected_protocol_manifest_result() -> str:
    """Return the stable protocol manifest validator success prefix."""
    return "protocol manifest ok:"


EXPECTED_PROTOCOL_MANIFEST_RESULT = expected_protocol_manifest_result()

QUIET_PUBLIC_SURFACE_MODE = "quiet"
EXPECTED_DESCRIPTION: str | None = None
ALLOWED_REPOSITORY_DESCRIPTIONS = frozenset({None, ""})
EXPECTED_LATEST_RELEASE = "v3.13.3"
REQUIRED_TOPICS = frozenset()
FORBIDDEN_TOPIC = "a" + "i"
REQUIRED_PUBLIC_DOCUMENTS = (
    "STATUS.md",
    "GITHUB_SURFACE.md",
    "DEPLOYMENT_STATUS.md",
    "docs/00_platform_overview.md",
    "docs/PRODUCT_BOUNDARY.md",
    "docs/52_mullu_governance_protocol.md",
    "docs/60_logic_governance_application.md",
)
DEPLOYMENT_WITNESS_WORKFLOW_PATH = ".github/workflows/deployment-witness.yml"
GATEWAY_PUBLICATION_WORKFLOW_PATH = ".github/workflows/gateway-publication.yml"
API_IMAGE_PUBLICATION_WORKFLOW_PATH = ".github/workflows/api-image-publication.yml"
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
GOVERNANCE_PROTOCOL_DOC_PATH = "docs/52_mullu_governance_protocol.md"
GITHUB_SURFACE_REQUIRED_LITERALS = (
    "GitHub Surface Witness",
    "Public surface mode",
    QUIET_PUBLIC_SURFACE_MODE,
    "Expected description",
    "(none)",
    EXPECTED_LATEST_RELEASE,
    "No repository topics are required while quiet mode is active.",
    "docs/00_platform_overview.md",
    "docs/PRODUCT_BOUNDARY.md",
    "docs/52_mullu_governance_protocol.md",
    "python scripts/validate_protocol_manifest.py",
    "python scripts/validate_public_repository_surface.py",
    "scripts/validate_governed_runtime_promotion.py",
)
STATUS_REQUIRED_LITERALS = (
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
    "docs/60_logic_governance_application.md",
    "python scripts/validate_protocol_manifest.py",
    "python scripts/validate_public_repository_surface.py",
)
PRODUCT_BOUNDARY_REQUIRED_LITERALS = (
    "Product Boundary",
    "Mullu Govern is the public product",
    "Mullu Control Plane",
    "Mullu Platform",
    "Mullusi",
    "Launch Constraint",
    "This rename target is not a repository-split trigger",
    "developers should continue working in `mullu-control-plane`",
)
PLATFORM_OVERVIEW_REQUIRED_LITERALS = (
    "Platform Overview",
    "Repository Topology Decision",
    "repository: mullu-control-plane",
    "product: Mullu Govern",
    "company: Mullusi",
    "Do not split this repository while the active blocker is deployment evidence.",
    "Issue `#330` is closed by signed deployment witness evidence.",
    "50+ active users, multiple teams, or",
    "multiple independently deployable services.",
    "target does not by itself prove the final product architecture",
)
DEPLOYMENT_STATUS_REQUIRED_LITERALS = (
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
    "python scripts/provision_runtime_witness_secret.py --runtime-env-output .change_assurance/runtime_witness_secret.env",
    "python scripts/provision_deployment_target.py --gateway-url \"$MULLU_GATEWAY_URL\" --expected-environment pilot",
    "python scripts/validate_gateway_ingress_manifest.py --allow-placeholder",
    "python scripts/render_gateway_ingress.py --gateway-host \"$MULLU_GATEWAY_HOST\"",
    ".github/workflows/deployment-witness.yml",
    ".github/workflows/gateway-publication.yml",
    ".github/workflows/api-image-publication.yml",
    "python scripts/validate_api_image_publication_workflow.py",
    ".change_assurance/api_image_publication_receipt.json",
    "api-image-publication-receipt",
    "python scripts/report_gateway_publication_readiness.py --gateway-url \"$MULLU_GATEWAY_URL\" --dispatch-witness",
    "python scripts/dispatch_gateway_publication.py --readiness-report .change_assurance/gateway_publication_readiness.json",
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
    "python scripts/publish_gateway_publication.py --gateway-url \"$MULLU_GATEWAY_URL\" --dispatch-witness --dispatch --receipt-output .change_assurance/gateway_publication_receipt.json",
    ".change_assurance/gateway_publication_receipt.json",
    "python scripts/validate_gateway_publication_receipt.py --receipt .change_assurance/gateway_publication_receipt.json --require-ready --require-dispatched --require-success",
    "python scripts/dispatch_gateway_publication.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --dispatch-witness",
    "python scripts/dispatch_deployment_witness.py",
    "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json",
    ".change_assurance/deployment_publication_closure_validation.json",
    "python scripts/apply_deployment_publication_status.py --operator-approval-ref \"$MULLU_DEPLOYMENT_PUBLICATION_APPROVAL_REF\" --receipt-output .change_assurance/public_production_health_declaration.json",
    ".change_assurance/public_production_health_declaration.json",
    "schemas/public_production_health_declaration.schema.json",
    "python scripts/orchestrate_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --apply-ingress --require-preflight --require-mcp-operator-checklist --skip-target-provisioning --dispatch --orchestration-output \"$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT\"",
    ".change_assurance/deployment_witness_orchestration.json",
    "python scripts/validate_deployment_orchestration_receipt.py --receipt \"$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT\" --require-mcp-operator-checklist --require-preflight --expected-environment pilot",
    "python scripts/preflight_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot",
    "python scripts/gateway_runtime_smoke.py",
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
    "python scripts/validate_public_repository_surface.py",
    "## GitHub Runtime Input State",
    "GitHub Actions secret name `MULLU_RUNTIME_WITNESS_SECRET` is present; secret value is not printed",
    "GitHub Actions secret name `MULLU_RUNTIME_CONFORMANCE_SECRET` is present; secret value is not printed",
    "GitHub Actions secret name `MULLU_DEPLOYMENT_WITNESS_SECRET` is present; secret value is not printed",
    "GitHub Actions secret name `MULLU_AUTHORITY_OPERATOR_SECRET` is present; secret value is not printed",
    "GitHub repository variables `MULLU_GATEWAY_URL=https://api.mullusi.com` and `MULLU_EXPECTED_RUNTIME_ENV=pilot` are set",
)
DEPLOYMENT_STATE_PATTERN = re.compile(
    r"^\*\*Deployment witness state:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
PUBLIC_HEALTH_PATTERN = re.compile(
    r"^\*\*Public production health endpoint:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
GOVERNANCE_PROTOCOL_REQUIRED_LITERALS = (
    "Mullu Governance Protocol",
    "schemas/mullu_governance_protocol.manifest.json",
    "scripts/validate_protocol_manifest.py",
    "python scripts\\validate_protocol_manifest.py",
    EXPECTED_PROTOCOL_MANIFEST_RESULT,
    "Capability candidate packages are public contracts",
    "Capability maturity assessments are public contracts",
    "Policy proof reports are public contracts",
    "Capability adapter closure plans are public contracts",
    "Agent identities are public contracts",
    "Claim verification reports are public contracts",
    "Collaboration cases are public contracts",
    "Connector self-healing receipts are public contracts",
    "Memory lattice admission claims are public contracts",
    "Trust ledger bundles are public contracts",
    "Trust ledger anchor receipts are public contracts",
    "Domain operating packs are public contracts",
    "Multimodal operation receipts are public contracts",
    "Capability upgrade plans are public contracts",
    "Autonomous test-generation plans are public contracts",
    "Production evidence witnesses are public contracts",
    "Capability evidence endpoint responses are public contracts",
    "Audit verification endpoint responses are public contracts",
    "Proof verification endpoint responses are public contracts",
    "Operator control tower snapshots are public contracts",
    "Low-code builder catalogs are public contracts",
    "Marketplace SDK catalogs are public contracts",
    "Deployment handoff receipts are public contracts",
    "Deployment publication closure validation reports are public contracts",
    "Deployment publication closure plans are public contracts",
    "Public production health declaration receipts are public contracts",
    "Deployment orchestration receipt validation reports are public contracts",
    "Gateway publication readiness reports are public contracts",
    "Gateway publication receipt validation reports are public contracts",
    "World-state projections are public contracts",
    "Goal compilation reports are public contracts",
    "Workflow mining reports are public contracts",
    "Simulation receipts are public contracts",
    "General-agent promotion handoff packets are public contracts",
    "Governed runtime promotion",
    "Terminal closure certificates are public contracts",
    "Finance approval live handoff artifacts are public contracts",
    "Finance payment provider binding receipts are public contracts",
    "TeamOps shared inbox operator handoff packets are public contracts",
    "Reflex deployment witness envelopes are public contracts",
    "Reflex deployment witness validator receipts are public contracts",
    "Temporal operation receipts are public contracts",
    "Temporal resolution receipts are public contracts",
    "Temporal evidence freshness receipts are public contracts",
    "Temporal reapproval receipts are public contracts",
    "Temporal dispatch window receipts are public contracts",
    "Temporal budget window receipts are public contracts",
    "Temporal causal order receipts are public contracts",
    "Temporal monotonic duration receipts are public contracts",
    "Temporal accepted-risk expiry receipts are public contracts",
    "Temporal credential expiry receipts are public contracts",
    "Temporal retention window receipts are public contracts",
    "Temporal rate-limit window receipts are public contracts",
    "Temporal retry window receipts are public contracts",
    "Temporal lease window receipts are public contracts",
    "Temporal idempotency window receipts are public contracts",
    "Temporal missed-run receipts are public contracts",
    "Temporal recurrence window receipts are public contracts",
    "Temporal memory receipts are public contracts",
    "Temporal memory refresh receipts are public contracts",
    "Temporal scheduler receipts are public contracts",
)
LOGIC_GOVERNANCE_DOC_PATH = "docs/60_logic_governance_application.md"
LOGIC_GOVERNANCE_REQUIRED_LITERALS = (
    "Logic Governance Application",
    "Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS",
    "Full logic discipline is mandatory",
    "Governance Law Mapping",
    "Surface-Specific Logic Rules",
    "Mfidel substrate and overlay",
    "No Unicode normalization, decomposition, recomposition, root-letter logic",
    "Proof-of-Resolution Stamp Template",
    "STATUS:",
)
DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS = (
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
GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS = (
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
    "--require-mcp-operator-checklist",
    "--accept-runtime-secret-env",
    "--accept-conformance-secret-env",
    "--accept-deployment-witness-secret-env",
    "actions/upload-artifact@v6",
)
API_IMAGE_PUBLICATION_WORKFLOW_REQUIRED_LITERALS = (
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
CI_WORKFLOW_REQUIRED_LITERALS = (
    "Validate Reflex deployment witness replay",
    "schemas/reflex_deployment_witness_validator_receipt.schema.json",
    "python -m pytest tests/test_validate_reflex_deployment_witness.py -q --junitxml=.change_assurance/reflex_deployment_witness_validator_junit.xml",
    "python scripts/emit_reflex_deployment_witness_validator_receipt.py --junit .change_assurance/reflex_deployment_witness_validator_junit.xml --output .change_assurance/reflex_deployment_witness_validator_receipt.json --json",
    "reflex-deployment-witness-validator-receipt",
    ".change_assurance/reflex_deployment_witness_validator_junit.xml",
    ".change_assurance/reflex_deployment_witness_validator_receipt.json",
    "Validate API image publication workflow",
    "python scripts/validate_api_image_publication_workflow.py",
)


def _parse_json_object(*, source: str, payload: str) -> dict[str, Any]:
    """Parse one JSON object response with causal source context."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{_bounded_source_label(source)}: response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{_bounded_source_label(source)}: response root was not an object")
    return parsed


def _github_api_path(url: str) -> str | None:
    """Return the GitHub API path accepted by gh api for a known GitHub URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "api.github.com":
        return None
    api_path = parsed.path.strip("/")
    return api_path or None


def _bounded_source_label(source: str) -> str:
    """Return a public-safe source label for operator-visible errors."""
    if source.startswith("gh api "):
        return "github_cli_api"
    if source == REPOSITORY_API_URL:
        return "github_repository_api"
    if source == LATEST_RELEASE_API_URL:
        return "github_latest_release_api"
    if _github_api_path(source) is not None:
        return "github_api"
    return "provided_source"


def _bounded_prior_failure(prior_failure: str) -> str:
    """Return a bounded network failure reason without provider detail."""
    if prior_failure.startswith("GitHub returned HTTP "):
        status_code = prior_failure.removeprefix("GitHub returned HTTP ").strip()
        return (
            f"github_http_{status_code}"
            if status_code.isdigit()
            else "github_http_error"
        )
    if prior_failure == "request timed out":
        return "request_timed_out"
    if prior_failure.startswith("network failure"):
        return "network_failure"
    return "request_failed"


def _bounded_gh_failure(result: subprocess.CompletedProcess[str]) -> str:
    """Return a bounded GitHub CLI failure reason."""
    return f"github_cli_exit_{result.returncode}"


def read_json_url_with_gh(url: str, *, prior_failure: str) -> dict[str, Any]:
    """Read one GitHub JSON endpoint through authenticated GitHub CLI access."""
    api_path = _github_api_path(url)
    failure_reason = _bounded_prior_failure(prior_failure)
    if api_path is None:
        raise RuntimeError(f"github_api: {failure_reason}; no_github_cli_fallback_path")
    try:
        result = subprocess.run(
            ["gh", "api", api_path],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=GITHUB_CLI_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"github_api: {failure_reason}; github_cli_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"github_api: {failure_reason}; github_cli_timed_out") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"github_api: {failure_reason}; gh_cli_fallback_failed: "
            f"{_bounded_gh_failure(result)}"
        )
    return _parse_json_object(source=f"gh api {api_path}", payload=result.stdout)


def read_json_url(url: str) -> dict[str, Any]:
    """Read one GitHub JSON endpoint with authenticated fallback and context."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mullu-repository-surface-validator",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = Request(
        url,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        return read_json_url_with_gh(
            url,
            prior_failure=f"GitHub returned HTTP {exc.code}",
        )
    except URLError:
        return read_json_url_with_gh(
            url,
            prior_failure="network failure",
        )
    except TimeoutError:
        return read_json_url_with_gh(url, prior_failure="request timed out")

    return _parse_json_object(source=url, payload=payload)


def validate_repository_payload(payload: dict[str, Any]) -> list[str]:
    """Validate repository metadata against the governed quiet-surface witness."""
    errors: list[str] = []

    description = payload.get("description")
    if description not in ALLOWED_REPOSITORY_DESCRIPTIONS:
        errors.append(
            "repository description mismatch: "
            f"{description!r} is not empty for quiet public surface mode"
        )

    raw_topics = payload.get("topics")
    if not isinstance(raw_topics, list) or not all(
        isinstance(topic, str) for topic in raw_topics
    ):
        errors.append("repository topics missing or malformed")
        return errors

    topics = frozenset(raw_topics)
    if REQUIRED_TOPICS:
        missing_topics = REQUIRED_TOPICS - topics
        if missing_topics:
            errors.append(f"repository missing required topics: {sorted(missing_topics)}")
    elif topics:
        errors.append(
            f"repository topics must be empty in quiet public surface mode: {sorted(topics)}"
        )
    if FORBIDDEN_TOPIC in topics:
        errors.append("repository contains forbidden legacy topic")

    return errors


def validate_latest_release_payload(payload: dict[str, Any]) -> list[str]:
    """Validate that the latest GitHub release matches the governed release tag."""
    tag_name = payload.get("tag_name")
    if tag_name != EXPECTED_LATEST_RELEASE:
        return [f"latest release mismatch: {tag_name!r} != {EXPECTED_LATEST_RELEASE!r}"]
    return []


def validate_required_document_text(
    *,
    document_name: str,
    content: str,
    required_literals: tuple[str, ...],
) -> list[str]:
    """Validate one repository witness document has required local anchors."""
    missing_literals = tuple(
        literal for literal in required_literals if literal not in content
    )
    if not missing_literals:
        return []
    return [f"{document_name} missing required literals: {list(missing_literals)}"]


def validate_deployment_status_phase_text(content: str) -> list[str]:
    """Validate deployment status phase anchors without hard-coding one phase."""
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


def validate_local_public_documents() -> list[str]:
    """Validate required repository witness documents and deployment-health anchors."""
    errors: list[str] = []

    for document_name in REQUIRED_PUBLIC_DOCUMENTS:
        if not (REPO_ROOT / document_name).exists():
            errors.append(f"missing required public witness document: {document_name}")

    github_surface_path = REPO_ROOT / "GITHUB_SURFACE.md"
    if github_surface_path.exists():
        errors.extend(
            validate_required_document_text(
                document_name="GITHUB_SURFACE.md",
                content=github_surface_path.read_text(encoding="utf-8"),
                required_literals=GITHUB_SURFACE_REQUIRED_LITERALS,
            )
        )

    status_path = REPO_ROOT / "STATUS.md"
    if status_path.exists():
        errors.extend(
            validate_required_document_text(
                document_name="STATUS.md",
                content=status_path.read_text(encoding="utf-8"),
                required_literals=STATUS_REQUIRED_LITERALS,
            )
        )

    deployment_status_path = REPO_ROOT / "DEPLOYMENT_STATUS.md"
    if deployment_status_path.exists():
        deployment_status_text = deployment_status_path.read_text(encoding="utf-8")
        errors.extend(
            validate_required_document_text(
                document_name="DEPLOYMENT_STATUS.md",
                content=deployment_status_text,
                required_literals=DEPLOYMENT_STATUS_REQUIRED_LITERALS,
            )
        )
        errors.extend(validate_deployment_status_phase_text(deployment_status_text))

    product_boundary_path = REPO_ROOT / "docs" / "PRODUCT_BOUNDARY.md"
    if product_boundary_path.exists():
        errors.extend(
            validate_required_document_text(
                document_name="docs/PRODUCT_BOUNDARY.md",
                content=product_boundary_path.read_text(encoding="utf-8"),
                required_literals=PRODUCT_BOUNDARY_REQUIRED_LITERALS,
            )
        )

    platform_overview_path = REPO_ROOT / "docs" / "00_platform_overview.md"
    if platform_overview_path.exists():
        errors.extend(
            validate_required_document_text(
                document_name="docs/00_platform_overview.md",
                content=platform_overview_path.read_text(encoding="utf-8"),
                required_literals=PLATFORM_OVERVIEW_REQUIRED_LITERALS,
            )
        )

    governance_protocol_path = REPO_ROOT / GOVERNANCE_PROTOCOL_DOC_PATH
    if governance_protocol_path.exists():
        errors.extend(
            validate_required_document_text(
                document_name=GOVERNANCE_PROTOCOL_DOC_PATH,
                content=governance_protocol_path.read_text(encoding="utf-8"),
                required_literals=GOVERNANCE_PROTOCOL_REQUIRED_LITERALS,
            )
        )

    logic_governance_path = REPO_ROOT / LOGIC_GOVERNANCE_DOC_PATH
    if logic_governance_path.exists():
        errors.extend(
            validate_required_document_text(
                document_name=LOGIC_GOVERNANCE_DOC_PATH,
                content=logic_governance_path.read_text(encoding="utf-8"),
                required_literals=LOGIC_GOVERNANCE_REQUIRED_LITERALS,
            )
        )

    workflow_path = REPO_ROOT / DEPLOYMENT_WITNESS_WORKFLOW_PATH
    if not workflow_path.exists():
        errors.append(f"missing required deployment witness workflow: {DEPLOYMENT_WITNESS_WORKFLOW_PATH}")
    else:
        errors.extend(
            validate_required_document_text(
                document_name=DEPLOYMENT_WITNESS_WORKFLOW_PATH,
                content=workflow_path.read_text(encoding="utf-8"),
                required_literals=DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS,
            )
        )

    publication_workflow_path = REPO_ROOT / GATEWAY_PUBLICATION_WORKFLOW_PATH
    if not publication_workflow_path.exists():
        errors.append(f"missing required gateway publication workflow: {GATEWAY_PUBLICATION_WORKFLOW_PATH}")
    else:
        errors.extend(
            validate_required_document_text(
                document_name=GATEWAY_PUBLICATION_WORKFLOW_PATH,
                content=publication_workflow_path.read_text(encoding="utf-8"),
                required_literals=GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS,
            )
        )

    api_image_workflow_path = REPO_ROOT / API_IMAGE_PUBLICATION_WORKFLOW_PATH
    if not api_image_workflow_path.exists():
        errors.append(f"missing required API image publication workflow: {API_IMAGE_PUBLICATION_WORKFLOW_PATH}")
    else:
        errors.extend(
            validate_required_document_text(
                document_name=API_IMAGE_PUBLICATION_WORKFLOW_PATH,
                content=api_image_workflow_path.read_text(encoding="utf-8"),
                required_literals=API_IMAGE_PUBLICATION_WORKFLOW_REQUIRED_LITERALS,
            )
        )

    ci_workflow_path = REPO_ROOT / CI_WORKFLOW_PATH
    if not ci_workflow_path.exists():
        errors.append(f"missing required CI workflow: {CI_WORKFLOW_PATH}")
    else:
        errors.extend(
            validate_required_document_text(
                document_name=CI_WORKFLOW_PATH,
                content=ci_workflow_path.read_text(encoding="utf-8"),
                required_literals=CI_WORKFLOW_REQUIRED_LITERALS,
            )
        )

    return errors


def validate_public_repository_surface(*, live: bool = True) -> list[str]:
    """Validate local witnesses and, when enabled, live GitHub metadata state."""
    errors = validate_local_public_documents()
    if not live:
        return errors

    try:
        repository_payload = read_json_url(REPOSITORY_API_URL)
        latest_release_payload = read_json_url(LATEST_RELEASE_API_URL)
    except RuntimeError as exc:
        return [str(exc)]

    errors.extend(validate_repository_payload(repository_payload))
    errors.extend(validate_latest_release_payload(latest_release_payload))
    return errors


def main() -> None:
    local_only = "--local-only" in sys.argv
    errors = validate_public_repository_surface(live=not local_only)

    print("=== Repository Metadata Surface Validation ===")
    print("  repository:     tamirat-wubie/mullu-control-plane")
    print(f"  latest release: {EXPECTED_LATEST_RELEASE}")
    print(f"  live checks:    {'disabled' if local_only else 'enabled'}")

    if errors:
        print(f"\nFAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print("\nALL REPOSITORY METADATA GATES PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
