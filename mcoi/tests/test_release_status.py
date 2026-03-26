"""Purpose: verify the governed release-status summary remains live and fail-closed.
Governance scope: release inventory and release validation script only.
Dependencies: release status script and governed repo inventories.
Invariants:
  - Release status derives from live inventories, not hardcoded counts.
  - Missing required release docs fail closed.
  - Strict release validation stays aligned with schema and artifact validators.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_release_status


def test_discover_release_status_summary_exposes_live_inventory() -> None:
    summary = validate_release_status.discover_release_status_summary()

    assert "RELEASE_CHECKLIST_v0.1.md" in summary.release_documents
    assert "workflow.schema.json" in summary.schema_files
    assert "pilot-prod" in summary.builtin_profiles
    assert "default-safe" in summary.policy_packs
    assert "mcoi/examples/request-echo.json" in summary.request_artifacts


def test_validate_release_status_strictly() -> None:
    summary, errors = validate_release_status.validate_release_status(strict=True)

    assert errors == []
    assert len(summary.release_documents) >= 8
    assert len(summary.schema_files) >= 10
    assert len(summary.config_artifacts) >= 5
    assert summary.ci_workflow_present is True


def test_validate_ci_workflow_text_rejects_missing_release_gate() -> None:
    errors = validate_release_status.validate_ci_workflow_text(
        """
name: CI - Build Verification
python -m pytest --tb=short -q -m "not soak"
python scripts/validate_schemas.py --strict
python scripts/validate_artifacts.py --strict
"""
    )

    assert len(errors) == 1
    assert "python scripts/validate_release_status.py --strict" in errors[0]
    assert "cargo test" in errors[0]


def test_validate_release_status_rejects_missing_required_docs(monkeypatch) -> None:
    monkeypatch.setattr(
        validate_release_status,
        "REQUIRED_RELEASE_DOCUMENTS",
        ("README.md", "MISSING_RELEASE_SURFACE.md"),
    )

    summary, errors = validate_release_status.validate_release_status(strict=True)

    assert "README.md" in summary.release_documents
    assert len(errors) >= 1
    assert any("MISSING_RELEASE_SURFACE.md" in error for error in errors)
