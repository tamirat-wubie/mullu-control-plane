#!/usr/bin/env python3
"""Validate the public GitHub repository surface for governed reflection.

Purpose: compare versioned public-surface witnesses with GitHub metadata and
latest-release state.
Governance scope: repository description, topics, latest release, deployment
status witness, and required public documents.
Dependencies: Python standard library, GITHUB_SURFACE.md, DEPLOYMENT_STATUS.md,
STATUS.md, and GitHub public REST endpoints.
Invariants:
  - Public metadata must match the versioned witness.
  - Latest release must match the governed release tag.
  - Deployment health must remain explicitly not-published until endpoint
    evidence is declared.
  - No required public witness document may be absent.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_MANIFEST_PATH = REPO_ROOT / "schemas" / "mullu_governance_protocol.manifest.json"
REPOSITORY_API_URL = "https://api.github.com/repos/tamirat-wubie/mullu-control-plane"
LATEST_RELEASE_API_URL = f"{REPOSITORY_API_URL}/releases/latest"


def expected_protocol_manifest_result() -> str:
    """Return the expected protocol manifest validator success line."""
    try:
        manifest = json.loads(PROTOCOL_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "protocol manifest ok: unavailable schemas"
    schemas = manifest.get("schemas", ())
    schema_count = len(schemas) if isinstance(schemas, list) else 0
    return f"protocol manifest ok: {schema_count} schemas"


EXPECTED_PROTOCOL_MANIFEST_RESULT = expected_protocol_manifest_result()

EXPECTED_DESCRIPTION = (
    "Governed symbolic intelligence control plane - multi-tenant LLM orchestration "
    "with budget enforcement, audit trails, and policy-driven governance"
)
EXPECTED_LATEST_RELEASE = "v3.13.0"
REQUIRED_TOPICS = frozenset(
    {
        "audit-trail",
        "budget-enforcement",
        "fastapi",
        "governance",
        "llm",
        "multi-tenant",
        "orchestration",
        "python",
        "rust",
        "symbolic-intelligence",
    }
)
FORBIDDEN_TOPIC = "a" + "i"
REQUIRED_PUBLIC_DOCUMENTS = (
    "STATUS.md",
    "GITHUB_SURFACE.md",
    "DEPLOYMENT_STATUS.md",
    "docs/52_mullu_governance_protocol.md",
    "docs/60_logic_governance_application.md",
)
DEPLOYMENT_WITNESS_WORKFLOW_PATH = ".github/workflows/deployment-witness.yml"
GATEWAY_PUBLICATION_WORKFLOW_PATH = ".github/workflows/gateway-publication.yml"
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
GOVERNANCE_PROTOCOL_DOC_PATH = "docs/52_mullu_governance_protocol.md"
GITHUB_SURFACE_REQUIRED_LITERALS = (
    "GitHub Surface Witness",
    EXPECTED_DESCRIPTION,
    EXPECTED_LATEST_RELEASE,
    "symbolic-intelligence",
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
    "docs/52_mullu_governance_protocol.md",
    "docs/60_logic_governance_application.md",
    "python scripts/validate_protocol_manifest.py",
    "python scripts/validate_public_repository_surface.py",
)
DEPLOYMENT_STATUS_REQUIRED_LITERALS = (
    "Deployment Status Witness",
    "**Deployment witness state:** `not-published`",
    "**Public production health endpoint:** `not-declared`",
    "No governed production endpoint is declared in this repository",
    "python scripts/validate_gateway_deployment_env.py --strict",
    "python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json",
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
    "python scripts/report_gateway_publication_readiness.py --gateway-url \"$MULLU_GATEWAY_URL\" --dispatch-witness",
    "python scripts/dispatch_gateway_publication.py --readiness-report .change_assurance/gateway_publication_readiness.json",
    "python scripts/publish_gateway_publication.py --gateway-url \"$MULLU_GATEWAY_URL\" --dispatch-witness --dispatch --receipt-output .change_assurance/gateway_publication_receipt.json",
    ".change_assurance/gateway_publication_receipt.json",
    "python scripts/validate_gateway_publication_receipt.py --receipt .change_assurance/gateway_publication_receipt.json --require-ready --require-dispatched --require-success",
    "python scripts/dispatch_gateway_publication.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --dispatch-witness",
    "python scripts/dispatch_deployment_witness.py",
    "python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json",
    ".change_assurance/deployment_publication_closure_validation.json",
    "python scripts/orchestrate_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --apply-ingress --require-preflight --require-mcp-operator-checklist --dispatch --orchestration-output \"$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT\"",
    ".change_assurance/deployment_witness_orchestration.json",
    "python scripts/validate_deployment_orchestration_receipt.py --receipt \"$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT\" --require-mcp-operator-checklist --require-preflight --expected-environment pilot",
    "python scripts/preflight_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot",
    "python scripts/gateway_runtime_smoke.py",
    "python scripts/plan_capability_adapter_closure.py --json",
    "python scripts/validate_capability_adapter_closure_plan_schema.py --strict",
    "python scripts/plan_deployment_publication_closure.py --json",
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
    "GitHub repository variables `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` are not currently set",
    "No `deployment-witness.yml` workflow runs are currently recorded",
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
    "Deployment handoff receipts are public contracts",
    "Deployment publication closure validation reports are public contracts",
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
    "Reflex deployment witness envelopes are public contracts",
    "Reflex deployment witness validator receipts are public contracts",
    "Temporal operation receipts are public contracts",
    "Temporal evidence freshness receipts are public contracts",
    "Temporal reapproval receipts are public contracts",
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
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "python scripts/collect_deployment_witness.py",
    '--conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET"',
    '--deployment-witness-secret "$MULLU_DEPLOYMENT_WITNESS_SECRET"',
    "--require-production-evidence",
    ".change_assurance/deployment_witness.json",
    "actions/upload-artifact@v4",
)
GATEWAY_PUBLICATION_WORKFLOW_REQUIRED_LITERALS = (
    "Gateway Publication Orchestration",
    "workflow_dispatch",
    "gateway_host",
    "apply_ingress",
    "dispatch_witness",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_KUBECONFIG_B64",
    "python scripts/orchestrate_deployment_witness.py",
    "--require-preflight",
    "--require-mcp-operator-checklist",
    "--orchestration-output .change_assurance/deployment_witness_orchestration.json",
    "python scripts/validate_deployment_orchestration_receipt.py",
    ".change_assurance/deployment_witness_orchestration_validation.json",
    "--require-mcp-operator-checklist",
    "--accept-runtime-secret-env",
    "--accept-conformance-secret-env",
    "actions/upload-artifact@v4",
)
CI_WORKFLOW_REQUIRED_LITERALS = (
    "Validate Reflex deployment witness replay",
    "schemas/reflex_deployment_witness_validator_receipt.schema.json",
    "python -m pytest tests/test_validate_reflex_deployment_witness.py -q --junitxml=.change_assurance/reflex_deployment_witness_validator_junit.xml",
    "python scripts/emit_reflex_deployment_witness_validator_receipt.py --junit .change_assurance/reflex_deployment_witness_validator_junit.xml --output .change_assurance/reflex_deployment_witness_validator_receipt.json --json",
    "reflex-deployment-witness-validator-receipt",
    ".change_assurance/reflex_deployment_witness_validator_junit.xml",
    ".change_assurance/reflex_deployment_witness_validator_receipt.json",
)


def read_json_url(url: str) -> dict[str, Any]:
    """Read one GitHub JSON endpoint with explicit timeout and error context."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mullu-public-surface-validator",
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
        raise RuntimeError(f"{url}: GitHub returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url}: network failure: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"{url}: request timed out") from exc

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url}: response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{url}: response root was not an object")
    return parsed


def validate_repository_payload(payload: dict[str, Any]) -> list[str]:
    """Validate public repository metadata against the governed witness."""
    errors: list[str] = []

    description = payload.get("description")
    if description != EXPECTED_DESCRIPTION:
        errors.append(
            f"repository description mismatch: {description!r} != {EXPECTED_DESCRIPTION!r}"
        )

    raw_topics = payload.get("topics")
    if not isinstance(raw_topics, list) or not all(
        isinstance(topic, str) for topic in raw_topics
    ):
        errors.append("repository topics missing or malformed")
        return errors

    topics = frozenset(raw_topics)
    missing_topics = REQUIRED_TOPICS - topics
    if missing_topics:
        errors.append(f"repository missing required topics: {sorted(missing_topics)}")
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
    """Validate one public witness document has required local anchors."""
    missing_literals = tuple(
        literal for literal in required_literals if literal not in content
    )
    if not missing_literals:
        return []
    return [f"{document_name} missing required literals: {list(missing_literals)}"]


def validate_local_public_documents() -> list[str]:
    """Validate required public witness documents and deployment-health anchors."""
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
        errors.extend(
            validate_required_document_text(
                document_name="DEPLOYMENT_STATUS.md",
                content=deployment_status_path.read_text(encoding="utf-8"),
                required_literals=DEPLOYMENT_STATUS_REQUIRED_LITERALS,
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
    """Validate local witnesses and, when enabled, live GitHub public state."""
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

    print("=== Public Repository Surface Validation ===")
    print("  repository:     tamirat-wubie/mullu-control-plane")
    print(f"  latest release: {EXPECTED_LATEST_RELEASE}")
    print(f"  live checks:    {'disabled' if local_only else 'enabled'}")

    if errors:
        print(f"\nFAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print("\nALL PUBLIC SURFACE GATES PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
