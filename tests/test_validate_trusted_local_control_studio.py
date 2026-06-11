"""Purpose: verify trusted local control studio policy validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_trusted_local_control_studio, AGENTS.md, and docs/TRUSTED_LOCAL_CONTROL_STUDIO.md.
Invariants:
  - The validator accepts the current trusted control studio policy.
  - Missing authorization phrases fail closed.
  - Secret-disclosure and external-effect boundary weakening fails closed.
  - Missing files raise explicit read errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_trusted_local_control_studio as validator


def test_current_trusted_local_control_studio_policy_passes() -> None:
    policy_text = validator.load_text(validator.DEFAULT_POLICY_PATH, "policy")
    doc_text = validator.load_text(validator.DEFAULT_DOC_PATH, "doc")
    findings = validator.validate_studio_policy(policy_text, doc_text)

    assert findings == []
    assert "## Trusted Local Control Studio Authorization" in policy_text
    assert "# Trusted Local Control Studio" in doc_text
    assert "secret presence, names, scopes, and bounded shape" in policy_text
    assert "Raw secret values require explicit task-scoped operator" in policy_text
    assert "Do not read or print full secret values" in policy_text
    assert "STATUS:" in doc_text


def test_missing_policy_authorization_is_reported() -> None:
    policy_text = "# Empty policy\n"
    doc_text = validator.DEFAULT_DOC_PATH.read_text(encoding="utf-8")
    findings = validator.validate_studio_policy(policy_text, doc_text)
    messages = "\n".join(finding.message for finding in findings)

    assert any(finding.rule_id == "missing-policy-phrase" for finding in findings)
    assert "Trusted Local Control Studio Authorization" in messages
    assert "AwaitingEvidence" in messages
    assert len(findings) >= 3


def test_forbidden_policy_weakening_is_reported() -> None:
    policy_text = validator.DEFAULT_POLICY_PATH.read_text(encoding="utf-8")
    doc_text = validator.DEFAULT_DOC_PATH.read_text(encoding="utf-8")
    weakened_policy = policy_text + "\nUnlimited authority with no restriction.\n"
    findings = validator.validate_studio_policy(weakened_policy, doc_text)

    assert any(finding.rule_id == "forbidden-policy-phrase" for finding in findings)
    assert any("unlimited authority" in finding.message for finding in findings)
    assert any("no restriction" in finding.message for finding in findings)


def test_cli_reports_passed_for_current_policy(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main(["--policy", str(validator.DEFAULT_POLICY_PATH), "--doc", str(validator.DEFAULT_DOC_PATH)])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "trusted_local_control_studio_policy" in streams.out
    assert "trusted_local_control_studio_secret_boundary" in streams.out
    assert "STATUS: passed" in streams.out


def test_load_text_rejects_missing_file(tmp_path: Path) -> None:
    missing_doc = tmp_path / "TRUSTED_LOCAL_CONTROL_STUDIO.md"

    with pytest.raises(FileNotFoundError):
        validator.load_text(missing_doc, "doc")

    assert not missing_doc.exists()
    assert missing_doc.name == "TRUSTED_LOCAL_CONTROL_STUDIO.md"
