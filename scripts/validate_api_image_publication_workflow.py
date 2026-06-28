#!/usr/bin/env python3
"""Validate the governed API image publication workflow.

Purpose: keep API container image publication evidence explicit and approval-gated.
Governance scope: production image publication workflow, GHCR package authority,
operator approval references, and public-safe image publication receipts.
Dependencies: .github/workflows/api-image-publication.yml.
Invariants:
  - The workflow is manual only.
  - Publication requires an operator approval reference and explicit boolean confirmation.
  - The image target is constrained to GHCR.
  - A public-safe receipt is uploaded without secret values, DNS mutation, or runtime mutation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "api-image-publication.yml"

REQUIRED_LITERALS: tuple[str, ...] = (
    "API Image Publication",
    "workflow_dispatch",
    "operator_approval_ref",
    "confirm_publication",
    "permissions:",
    "packages: write",
    "docker/login-action@v3",
    "docker/build-push-action@v6",
    "ghcr.io/tamirat-wubie/mullu-control-plane",
    "image_digest",
    "image_ref",
    "api_image_publication_receipt.json",
    "api-image-publication-receipt",
    "secret_values_serialized",
    "dns_mutated",
    "runtime_mutated",
)

FORBIDDEN_LITERALS: tuple[str, ...] = (
    "CLOUDFLARE_API_TOKEN",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "kubectl apply",
    "cloudflare",
)


def validate_api_image_publication_workflow_text(content: str) -> list[str]:
    """Return workflow validation errors without mutating repository state."""
    errors: list[str] = []
    missing_literals = tuple(literal for literal in REQUIRED_LITERALS if literal not in content)
    if missing_literals:
        errors.append(f"api image publication workflow missing required literals: {list(missing_literals)}")

    forbidden_literals = tuple(literal for literal in FORBIDDEN_LITERALS if literal in content)
    if forbidden_literals:
        errors.append(f"api image publication workflow contains forbidden literals: {list(forbidden_literals)}")

    if "on:\n  workflow_dispatch:" not in content:
        errors.append("api image publication workflow must be manual workflow_dispatch only")
    forbidden_triggers = {"  push:", "  pull_request:"}
    if any(line.rstrip() in forbidden_triggers for line in content.splitlines()):
        errors.append("api image publication workflow must not publish from push or pull_request triggers")
    if "push: ${{ inputs.confirm_publication }}" not in content:
        errors.append("api image publication workflow must bind push to confirm_publication")
    return errors


def validate_api_image_publication_workflow() -> list[str]:
    """Validate the checked-in workflow file."""
    if not WORKFLOW_PATH.exists():
        return [f"missing API image publication workflow: {WORKFLOW_PATH.relative_to(REPO_ROOT).as_posix()}"]
    return validate_api_image_publication_workflow_text(WORKFLOW_PATH.read_text(encoding="utf-8"))


def main() -> None:
    """CLI entry point."""
    errors = validate_api_image_publication_workflow()
    if errors:
        print("API IMAGE PUBLICATION WORKFLOW INVALID")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("API IMAGE PUBLICATION WORKFLOW OK")


if __name__ == "__main__":
    main()
