"""Tests for terminal closure certificate artifact validation.

Purpose: prove the public terminal closure certificate example and CLI validator
produce deterministic, disposition-aware proof results.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_terminal_closure_certificate and
examples/terminal_closure_certificate.json.
Invariants:
  - The canonical example validates against the terminal closure schema.
  - Committed closure cannot carry compensation or accepted-risk identifiers.
  - Accepted-risk closure requires both risk and case anchors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.validate_terminal_closure_certificate import (
    DEFAULT_CERTIFICATE,
    DEFAULT_SCHEMA,
    main,
    validate_terminal_closure_certificate,
)


def test_terminal_closure_certificate_example_validates() -> None:
    result = validate_terminal_closure_certificate()

    assert result.valid is True
    assert result.disposition == "committed"
    assert result.evidence_ref_count == 2
    assert result.errors == ()


def test_terminal_closure_certificate_rejects_committed_compensation(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        compensation_outcome_id="compensation-outcome-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "committed"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("committed closure must not include compensation_outcome_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_accepted_risk_without_case(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="accepted_risk",
        accepted_risk_id="accepted-risk-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "accepted_risk"
    assert any("case_id" in error for error in result.errors)
    assert any("accepted_risk closure requires case_id" in error for error in result.errors)


def test_terminal_closure_certificate_cli_returns_success(capsys: Any) -> None:
    exit_code = main(["--certificate", str(DEFAULT_CERTIFICATE), "--schema", str(DEFAULT_SCHEMA)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "terminal closure certificate ok" in output
    assert "disposition=committed" in output
    assert "error:" not in output


def _write_certificate(
    tmp_path: Path,
    *,
    disposition: str = "committed",
    compensation_outcome_id: str | None = None,
    accepted_risk_id: str | None = None,
) -> Path:
    certificate = json.loads(DEFAULT_CERTIFICATE.read_text(encoding="utf-8"))
    certificate["disposition"] = disposition
    if compensation_outcome_id is not None:
        certificate["compensation_outcome_id"] = compensation_outcome_id
    if accepted_risk_id is not None:
        certificate["accepted_risk_id"] = accepted_risk_id
    certificate_path = tmp_path / "terminal_closure_certificate.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    return certificate_path
