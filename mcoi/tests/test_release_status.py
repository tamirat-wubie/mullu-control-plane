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
    assert summary.release_version == "0.1.0 (internal alpha)"
    assert summary.release_date == "2026-03-19"


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


def test_validate_release_metadata_texts_rejects_mismatch() -> None:
    (_, _), errors = validate_release_status.validate_release_metadata_texts(
        {
            "RELEASE_NOTES_v0.1.md": "**Version:** 0.1.0 (internal alpha)\n**Date:** 2026-03-19\n",
            "KNOWN_LIMITATIONS_v0.1.md": "**Version:** 0.1.0 (internal alpha)\n**Date:** 2026-03-20\n",
            "SECURITY_MODEL_v0.1.md": "**Version:** 0.2.0 (internal alpha)\n**Date:** 2026-03-19\n",
        }
    )

    assert len(errors) == 2
    assert any("KNOWN_LIMITATIONS_v0.1.md: date metadata mismatch" in error for error in errors)
    assert any("SECURITY_MODEL_v0.1.md: version metadata mismatch" in error for error in errors)


def test_validate_release_limitation_coverage_rejects_missing_anchor() -> None:
    errors = validate_release_status.validate_release_limitation_coverage(
        known_limitations_text="make_dataclass\nHTTP connector\nurllib\n",
        security_model_text="No Authentication or Authorization\n",
    )

    assert len(errors) >= 3
    assert any("coordination_persistence_limitation" in error for error in errors)
    assert any("memory_persistence_limitation" in error for error in errors)
    assert any("encryption_limitation" in error for error in errors)


def test_scan_source_hygiene_text_rejects_bare_except_and_marker() -> None:
    path = REPO_ROOT / "sample.py"
    marker = "TO" + "DO"
    errors = validate_release_status.scan_source_hygiene_text(
        path,
        f"try:\n    pass\nexcept:\n    pass\n# {marker} fix later\n",
    )

    assert len(errors) == 2
    assert any("contains bare except clause" in error for error in errors)
    assert any("contains source hygiene marker TODO" in error for error in errors)


def test_validate_source_hygiene_passes_for_current_repo() -> None:
    errors = validate_release_status.validate_source_hygiene()

    assert errors == []
    assert len(errors) == 0


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
