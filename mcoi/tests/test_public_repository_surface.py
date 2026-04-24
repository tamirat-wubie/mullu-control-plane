"""Purpose: verify public repository-surface validation remains fail-closed.
Governance scope: GitHub metadata witness, latest release witness, deployment
status witness, and required public documents.
Dependencies: scripts.validate_public_repository_surface only.
Invariants:
  - Metadata mismatches are explicit.
  - Latest-release mismatches are explicit.
  - Required local witness anchors cannot be silently removed.
  - Local-only validation does not require network access.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_public_repository_surface  # noqa: E402


def test_validate_repository_payload_accepts_expected_metadata() -> None:
    errors = validate_public_repository_surface.validate_repository_payload(
        {
            "description": validate_public_repository_surface.EXPECTED_DESCRIPTION,
            "topics": sorted(validate_public_repository_surface.REQUIRED_TOPICS),
        }
    )

    assert errors == []
    assert len(errors) == 0
    assert validate_public_repository_surface.EXPECTED_DESCRIPTION.startswith(
        "Governed symbolic intelligence control plane"
    )


def test_validate_repository_payload_rejects_mismatch_and_legacy_topic() -> None:
    errors = validate_public_repository_surface.validate_repository_payload(
        {
            "description": "stale description",
            "topics": ["python", "rust", "a" + "i"],
        }
    )

    assert len(errors) == 3
    assert any("repository description mismatch" in error for error in errors)
    assert any("repository missing required topics" in error for error in errors)
    assert any("forbidden legacy topic" in error for error in errors)


def test_validate_latest_release_payload_rejects_mismatch() -> None:
    errors = validate_public_repository_surface.validate_latest_release_payload(
        {"tag_name": "v0.0.0"}
    )

    assert len(errors) == 1
    assert "latest release mismatch" in errors[0]
    assert validate_public_repository_surface.EXPECTED_LATEST_RELEASE in errors[0]


def test_validate_required_document_text_rejects_missing_literals() -> None:
    errors = validate_public_repository_surface.validate_required_document_text(
        document_name="DEPLOYMENT_STATUS.md",
        content="# Deployment Status Witness\n",
        required_literals=(
            "Deployment Status Witness",
            "not-published",
            "not-declared",
        ),
    )

    assert len(errors) == 1
    assert "not-published" in errors[0]
    assert "not-declared" in errors[0]


def test_validate_local_public_documents_passes_current_repo() -> None:
    errors = validate_public_repository_surface.validate_local_public_documents()

    assert errors == []
    assert len(errors) == 0
    assert (REPO_ROOT / "GITHUB_SURFACE.md").exists()


def test_validate_public_repository_surface_local_only_passes_current_repo() -> None:
    errors = validate_public_repository_surface.validate_public_repository_surface(
        live=False
    )

    assert errors == []
    assert len(errors) == 0
    assert (REPO_ROOT / "DEPLOYMENT_STATUS.md").exists()

