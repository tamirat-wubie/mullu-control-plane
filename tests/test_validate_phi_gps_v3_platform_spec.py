"""Purpose: verify the Phi2-GPS v3 platform overlay validator.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_phi_gps_v3_platform_spec and docs/PHI_CANONICAL_SPEC.md.
Invariants:
  - The current canonical spec carries the v3 overlay.
  - Missing overlay anchors are reported.
  - External effect-bearing runtime claims remain bounded.
  - Missing spec files raise explicit read errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_phi_gps_v3_platform_spec as validator


def test_current_phi_gps_v3_platform_spec_passes() -> None:
    spec_text = validator.load_spec(validator.DEFAULT_SPEC_PATH)
    findings = validator.validate_spec(spec_text)

    assert findings == []
    assert "Phi2-GPS v3 overlay     ACCEPTED SPEC" in spec_text
    assert "Repository-local v3 runtime contracts:    SolvedVerified" in spec_text
    assert "Effect-bearing external adapter execution: AwaitingEvidence" in spec_text
    assert "A v3 repository-local implementation is runtime-closed only when it passes these deterministic tests:" in spec_text


def test_missing_required_overlay_phrase_is_reported() -> None:
    spec_text = validator.load_spec(validator.DEFAULT_SPEC_PATH)
    damaged_text = spec_text.replace("Phi2_GPS_v3(Praw)", "Phi2_GPS_v3_missing(Praw)")
    findings = validator.validate_spec(damaged_text)
    rule_ids = {finding.rule_id for finding in findings}
    messages = "\n".join(finding.message for finding in findings)

    assert "platform-law" in rule_ids
    assert "Phi2_GPS_v3(Praw)" in messages
    assert len(findings) >= 1


def test_unbounded_external_adapter_claim_is_reported() -> None:
    spec_text = validator.load_spec(validator.DEFAULT_SPEC_PATH)
    unbounded_text = spec_text.replace(
        "Effect-bearing external adapter execution: AwaitingEvidence",
        "Effect-bearing external adapter execution: SolvedVerified",
    )
    findings = validator.validate_spec(unbounded_text)

    assert any(finding.rule_id == "unbounded-v3-claim" for finding in findings)
    assert any("Effect-bearing external adapter execution" in finding.message for finding in findings)
    assert len(findings) >= 1


def test_cli_reports_passed_for_current_spec(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main(["--spec", str(validator.DEFAULT_SPEC_PATH)])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "phi_gps_v3_overlay_present" in streams.out
    assert "STATUS: passed" in streams.out


def test_load_spec_rejects_missing_file(tmp_path: Path) -> None:
    missing_spec = tmp_path / "PHI_CANONICAL_SPEC.md"

    with pytest.raises(FileNotFoundError):
        validator.load_spec(missing_spec)

    assert not missing_spec.exists()
    assert missing_spec.name == "PHI_CANONICAL_SPEC.md"
