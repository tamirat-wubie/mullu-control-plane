"""Tests for overdue authority obligation closure helper.

Purpose: prove the operator closure helper derives required evidence refs and
fails closed when runtime authority debt remains.
Governance scope: authority obligation closure receipts and redacted operator
workflow support.
Dependencies: scripts.satisfy_overdue_authority_obligations.
Invariants:
  - Evidence refs match each obligation's declared required evidence labels.
  - Empty authority secrets are rejected before any operator request.
  - Debt-clear proof is explicit in the closure receipt.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import satisfy_overdue_authority_obligations as closure  # noqa: E402


def test_evidence_refs_for_obligation_matches_required_labels() -> None:
    obligation = {
        "obligation_id": "obligation-1",
        "evidence_required": ["case_disposition", "owner_attestation"],
    }

    refs = closure.evidence_refs_for_obligation(obligation, "operator-review-20260608")

    assert refs == (
        "case_disposition:operator-review-20260608:obligation-1",
        "owner_attestation:operator-review-20260608:obligation-1",
    )
    assert all("operator-review-20260608" in item for item in refs)
    assert all(item.endswith(":obligation-1") for item in refs)


def test_evidence_refs_for_obligation_uses_generic_ref_when_no_required_labels() -> None:
    obligation = {"obligation_id": "obligation-2", "evidence_required": []}

    refs = closure.evidence_refs_for_obligation(obligation, "manual-closure")

    assert refs == ("operator_closure:manual-closure:obligation-2",)
    assert refs[0].startswith("operator_closure:")
    assert refs[0].endswith(":obligation-2")


def test_satisfy_overdue_obligations_reports_clear_public_status(monkeypatch) -> None:
    obligation = {
        "obligation_id": "obligation-3",
        "command_id": "cmd-1",
        "obligation_type": "case_review",
        "evidence_required": ["case_disposition"],
    }

    monkeypatch.setattr(
        closure,
        "list_overdue_obligations",
        lambda gateway_url, *, operator_secret, limit: (obligation,),
    )
    monkeypatch.setattr(
        closure,
        "satisfy_obligation",
        lambda gateway_url, obligation, *, operator_secret, closure_ref: {
            "obligation_id": obligation["obligation_id"],
            "status": "satisfied",
            "evidence_refs": ["case_disposition:closure-ref:obligation-3"],
        },
    )
    monkeypatch.setattr(
        closure,
        "collect_public_status",
        lambda gateway_url: {
            "deployment": {"checks_missing": []},
            "runtime_conformance": {
                "authority_responsibility_debt_clear": True,
                "authority_overdue_obligation_count": 0,
            },
        },
    )

    receipt = closure.satisfy_overdue_authority_obligations(
        "https://gateway.example.test",
        operator_secret="secret-value",
        closure_ref="closure-ref",
        limit=10,
        require_clear=True,
    )

    assert receipt["satisfied_count"] == 1
    assert receipt["authority_debt_clear"] is True
    assert receipt["errors"] == []


def test_satisfy_overdue_obligations_fails_when_debt_remains(monkeypatch) -> None:
    monkeypatch.setattr(
        closure,
        "list_overdue_obligations",
        lambda gateway_url, *, operator_secret, limit: (),
    )
    monkeypatch.setattr(
        closure,
        "collect_public_status",
        lambda gateway_url: {
            "deployment": {"checks_missing": ["runtime_conformance"]},
            "runtime_conformance": {
                "authority_responsibility_debt_clear": False,
                "authority_overdue_obligation_count": 2,
            },
        },
    )

    receipt = closure.satisfy_overdue_authority_obligations(
        "https://gateway.example.test",
        operator_secret="secret-value",
        closure_ref="closure-ref",
        limit=10,
        require_clear=True,
    )

    assert receipt["satisfied_count"] == 0
    assert receipt["authority_debt_clear"] is False
    assert receipt["errors"] == ["authority responsibility debt was not clear after closure"]
