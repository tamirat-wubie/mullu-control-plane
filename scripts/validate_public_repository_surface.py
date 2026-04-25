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
REPOSITORY_API_URL = "https://api.github.com/repos/tamirat-wubie/mullu-control-plane"
LATEST_RELEASE_API_URL = f"{REPOSITORY_API_URL}/releases/latest"

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
)
DEPLOYMENT_WITNESS_WORKFLOW_PATH = ".github/workflows/deployment-witness.yml"
GATEWAY_PUBLICATION_WORKFLOW_PATH = ".github/workflows/gateway-publication.yml"
GITHUB_SURFACE_REQUIRED_LITERALS = (
    "GitHub Surface Witness",
    EXPECTED_DESCRIPTION,
    EXPECTED_LATEST_RELEASE,
    "symbolic-intelligence",
    "python scripts/validate_public_repository_surface.py",
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
    "python scripts/validate_public_repository_surface.py",
)
DEPLOYMENT_STATUS_REQUIRED_LITERALS = (
    "Deployment Status Witness",
    "**Deployment witness state:** `not-published`",
    "**Public production health endpoint:** `not-declared`",
    "No governed production endpoint is declared in this repository",
    "python scripts/validate_gateway_deployment_env.py --strict",
    "python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json",
    "python scripts/collect_deployment_witness.py --gateway-url \"$MULLU_GATEWAY_URL\" --witness-secret \"$MULLU_RUNTIME_WITNESS_SECRET\" --output .change_assurance/deployment_witness.json",
    "python scripts/provision_runtime_witness_secret.py --runtime-env-output .change_assurance/runtime_witness_secret.env",
    "python scripts/provision_deployment_target.py --gateway-url \"$MULLU_GATEWAY_URL\" --expected-environment pilot",
    "python scripts/validate_gateway_ingress_manifest.py --allow-placeholder",
    "python scripts/render_gateway_ingress.py --gateway-host \"$MULLU_GATEWAY_HOST\"",
    ".github/workflows/deployment-witness.yml",
    ".github/workflows/gateway-publication.yml",
    "python scripts/report_gateway_publication_readiness.py --gateway-url \"$MULLU_GATEWAY_URL\" --dispatch-witness",
    "python scripts/dispatch_gateway_publication.py --readiness-report .change_assurance/gateway_publication_readiness.json",
    "python scripts/publish_gateway_publication.py --gateway-url \"$MULLU_GATEWAY_URL\" --dispatch-witness --dispatch",
    "python scripts/dispatch_gateway_publication.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --dispatch-witness",
    "python scripts/dispatch_deployment_witness.py",
    "python scripts/orchestrate_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot --apply-ingress --require-preflight --dispatch",
    "python scripts/preflight_deployment_witness.py --gateway-host \"$MULLU_GATEWAY_HOST\" --expected-environment pilot",
    "python scripts/gateway_runtime_smoke.py",
    "python scripts/validate_public_repository_surface.py",
)
DEPLOYMENT_WITNESS_WORKFLOW_REQUIRED_LITERALS = (
    "Deployment Witness Collection",
    "workflow_dispatch",
    "gateway_url",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "python scripts/collect_deployment_witness.py",
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
    "MULLU_KUBECONFIG_B64",
    "python scripts/orchestrate_deployment_witness.py",
    "--require-preflight",
    "--accept-runtime-secret-env",
    "actions/upload-artifact@v4",
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
