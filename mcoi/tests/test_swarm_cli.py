"""Tests for the governed swarm CLI adapter.

Purpose: verify command-line invoice execution, lookup, listing, and governed
parse rejection over JSON envelopes.
Governance scope: CLI must not bypass runtime validation or append-only audit
persistence.
Dependencies: mcoi_runtime.swarm.cli.
Invariants: accepted runs persist, rejected commands return nonzero, and every
printed response remains a governed envelope.
"""

from __future__ import annotations

import json

from mcoi_runtime.swarm.cli import guarded_main


def _payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": "run_cli_invoice_001",
        "goal_id": "goal_cli_invoice_001",
        "tenant_id": "tenant_a",
        "invoice_ref": "invoice_cli_001",
        "invoice_amount_usd": "42.50",
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }
    value.update(overrides)
    return value


def _last_json(capsys) -> dict[str, object]:
    captured = capsys.readouterr()
    return json.loads(captured.out.strip().splitlines()[-1])


def test_cli_run_invoice_with_inline_json_persists_closed_record(tmp_path, capsys) -> None:
    audit_path = tmp_path / "swarm-runs.jsonl"
    exit_code = guarded_main(
        [
            "--audit-store",
            str(audit_path),
            "run-invoice",
            json.dumps(_payload()),
        ]
    )
    envelope = _last_json(capsys)

    assert exit_code == 0
    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "closed"
    assert envelope["payload"]["record"]["proof_stamp"]
    assert audit_path.exists()


def test_cli_get_and_list_runs_are_read_only(tmp_path, capsys) -> None:
    audit_path = tmp_path / "swarm-runs.jsonl"
    guarded_main(["--audit-store", str(audit_path), "run-invoice", json.dumps(_payload())])
    _last_json(capsys)

    get_code = guarded_main(["--audit-store", str(audit_path), "get-run", "run_cli_invoice_001"])
    get_envelope = _last_json(capsys)
    list_code = guarded_main(["--audit-store", str(audit_path), "list-runs"])
    list_envelope = _last_json(capsys)

    assert get_code == 0
    assert get_envelope["ok"] is True
    assert get_envelope["payload"]["record"]["run_id"] == "run_cli_invoice_001"
    assert list_code == 0
    assert list_envelope["payload"]["count"] == 1
    assert list_envelope["payload"]["records"][0]["closure_status"] == "closed"


def test_cli_rejected_runtime_request_returns_nonzero_without_persisting(tmp_path, capsys) -> None:
    audit_path = tmp_path / "swarm-runs.jsonl"
    exit_code = guarded_main(
        [
            "--audit-store",
            str(audit_path),
            "run-invoice",
            json.dumps(_payload(invoice_ref="")),
        ]
    )
    envelope = _last_json(capsys)

    assert exit_code == 1
    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "invoice_ref" in envelope["error"]
    assert not audit_path.exists()


def test_cli_invalid_json_returns_governed_rejection(tmp_path, capsys) -> None:
    exit_code = guarded_main(["--audit-store", str(tmp_path / "swarm-runs.jsonl"), "run-invoice", "{bad"])
    envelope = _last_json(capsys)

    assert exit_code == 1
    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert envelope["error"]
