"""Purpose: verify repository AGENTS.md governance policy validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agents_governance and AGENTS.md.
Invariants:
  - The validator accepts the current policy surface.
  - Missing required sections are reported.
  - Blocked vocabulary is reported.
  - Missing policy files raise explicit read errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_agents_governance as validator


def test_current_agents_policy_passes() -> None:
    policy_text = validator.load_policy(validator.DEFAULT_POLICY_PATH)
    findings = validator.validate_policy(policy_text)

    assert findings == []
    assert "## Mfidel Enforcement" in policy_text
    assert "## Universal Action Orchestration" in policy_text
    assert "## Trusted Local Control Studio Authorization" in policy_text
    assert "## Phi GPS v3 Platform Overlay" in policy_text
    assert "effect-bearing adapter authority as `AwaitingEvidence`" in policy_text
    assert "must not exfiltrate them" in policy_text
    assert "symbolic intelligence" in policy_text


def test_missing_required_sections_are_reported() -> None:
    findings = validator.validate_policy("# Empty policy\n")
    rule_ids = {finding.rule_id for finding in findings}
    messages = "\n".join(finding.message for finding in findings)

    assert "missing-section" in rule_ids
    assert "missing-section-proof" in rule_ids
    assert "Identity" in messages
    assert "Mfidel Enforcement" in messages


def test_forbidden_vocabulary_is_reported() -> None:
    policy_text = validator.DEFAULT_POLICY_PATH.read_text(encoding="utf-8")
    forbidden_policy = policy_text + "\n" + "artificial " + "intelligence"
    findings = validator.validate_policy(forbidden_policy)

    assert any(finding.rule_id == "forbidden-vocabulary" for finding in findings)
    assert len(findings) >= 1
    assert any("blocked vocabulary" in finding.message for finding in findings)


def test_cli_reports_passed_for_current_policy(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main(["--policy", str(validator.DEFAULT_POLICY_PATH)])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "agents_policy_governance_surface" in streams.out
    assert "STATUS: passed" in streams.out


def test_load_policy_rejects_missing_file(tmp_path: Path) -> None:
    missing_policy = tmp_path / "AGENTS.md"

    with pytest.raises(FileNotFoundError):
        validator.load_policy(missing_policy)

    assert not missing_policy.exists()
    assert missing_policy.name == "AGENTS.md"
