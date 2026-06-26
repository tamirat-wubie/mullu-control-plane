"""Tests for the governance normalization map validator.

Purpose: prove governance doctrine repetition is routed to canonical local
source, validator, test, and preflight artifacts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_governance_normalization_map.
Invariants:
  - The current map passes.
  - Missing artifacts and source anchors are explicit findings.
  - Readiness promotion phrases remain rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_governance_normalization_map as validator


def test_current_governance_normalization_map_passes() -> None:
    findings = validator.validate_governance_normalization_map()
    map_text = validator.load_text(validator.DEFAULT_MAP_PATH, "normalization map")

    assert findings == []
    assert "Status: Foundation Mode" in map_text
    assert len(validator.CANONICAL_SURFACES) == 7
    assert any(surface.surface_id == "mfidel_substrate" for surface in validator.CANONICAL_SURFACES)


def test_map_text_rejects_missing_surface_value() -> None:
    map_text = validator.load_text(validator.DEFAULT_MAP_PATH, "normalization map")
    damaged_text = map_text.replace("scripts/validate_agents_governance.py", "scripts/missing_agents.py")

    findings = validator.validate_map_text(damaged_text)
    messages = "\n".join(finding.message for finding in findings)

    assert findings
    assert any(finding.rule_id == "normalization_map_surface_missing" for finding in findings)
    assert "scripts/validate_agents_governance.py" in messages


def test_map_text_rejects_readiness_promotion_phrase() -> None:
    map_text = validator.load_text(validator.DEFAULT_MAP_PATH, "normalization map")
    promoted_text = map_text + "\npublic launch ready\n"

    findings = validator.validate_map_text(promoted_text)
    rule_ids = {finding.rule_id for finding in findings}

    assert findings
    assert "normalization_map_forbidden_promotion" in rule_ids
    assert any("public_launch_ready" in finding.message for finding in findings)


def test_surface_artifacts_report_missing_source() -> None:
    surfaces = (
        validator.CanonicalSurface(
            "missing_surface",
            "docs/missing-governance-source.md",
            "scripts/validate_agents_governance.py",
            "tests/test_validate_agents_governance.py",
            "missing anchor",
        ),
    )

    findings = validator.validate_canonical_surface_artifacts(surfaces)
    messages = "\n".join(finding.message for finding in findings)

    assert findings
    assert any(finding.rule_id == "normalization_surface_artifact_missing" for finding in findings)
    assert "docs/missing-governance-source.md" in messages


def test_surface_artifacts_report_missing_anchor() -> None:
    surfaces = (
        validator.CanonicalSurface(
            "agents_policy",
            "AGENTS.md",
            "scripts/validate_agents_governance.py",
            "tests/test_validate_agents_governance.py",
            "anchor that is intentionally absent",
        ),
    )

    findings = validator.validate_canonical_surface_artifacts(surfaces)

    assert findings
    assert any(finding.rule_id == "normalization_surface_anchor_missing" for finding in findings)
    assert any("anchor that is intentionally absent" in finding.message for finding in findings)


def test_cli_reports_passed_for_current_map(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main(["--map", str(validator.DEFAULT_MAP_PATH)])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "governance_normalization_map" in streams.out
    assert "STATUS: passed" in streams.out
    assert streams.err == ""


def test_load_text_rejects_missing_file(tmp_path: Path) -> None:
    missing_map = tmp_path / "GOVERNANCE_NORMALIZATION_MAP.md"

    with pytest.raises(FileNotFoundError):
        validator.load_text(missing_map, "missing map")

    assert not missing_map.exists()
    assert missing_map.name == "GOVERNANCE_NORMALIZATION_MAP.md"
