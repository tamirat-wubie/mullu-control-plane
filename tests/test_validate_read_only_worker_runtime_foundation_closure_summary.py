"""Tests for read-only worker runtime Foundation closure summaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_foundation_closure_summary import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_foundation_closure_summary,
    main,
    validate_runtime_foundation_closure_summary,
    write_runtime_foundation_closure_summary_validation,
)


def test_runtime_foundation_closure_summary_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_foundation_closure_summary()

    assert fixture == generated
    assert fixture["solver_outcome"] == "SolvedVerified"
    assert fixture["proof_state"] == "Pass"
    assert fixture["foundation_closure_complete"] is True
    assert fixture["live_runtime_blocked"] is True
    assert fixture["terminal_closure_claimed"] is False
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["summary"]["chain_ref_count"] == 11
    assert fixture["summary"]["accepted_evidence_ref_count"] == 12


def test_runtime_foundation_closure_summary_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_foundation_closure_summary_validation.json"
    validation = validate_runtime_foundation_closure_summary()

    written = write_runtime_foundation_closure_summary_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.chain_ref_count == 11
    assert validation.accepted_evidence_ref_count == 12
    assert validation.live_runtime_blocked is True
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_foundation_closure_summary_rejects_runtime_overclaim(tmp_path: Path) -> None:
    summary_path = _write_mutated_summary(tmp_path)
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["live_runtime_blocked"] = False
    payload["runtime_enablement_allowed"] = True
    payload["runtime_dispatch_allowed"] = True
    summary_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_foundation_closure_summary(summary_path=summary_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "live_runtime_blocked must be true" in serialized_errors
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "runtime_dispatch_allowed must be false" in serialized_errors


def test_runtime_foundation_closure_summary_rejects_chain_drift(tmp_path: Path) -> None:
    summary_path = _write_mutated_summary(tmp_path)
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["chain_refs"] = payload["chain_refs"][:-1]
    payload["summary"]["chain_ref_count"] = 10
    summary_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_foundation_closure_summary(summary_path=summary_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "chain_refs must match the complete Foundation runtime chain" in serialized_errors
    assert "runtime Foundation closure summary does not match generated" in serialized_errors
    assert validation.runtime_enablement_allowed is False


def test_runtime_foundation_closure_summary_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_foundation_closure_summary_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["chain_ref_count"] == 11
    assert captured.err == ""


def _write_mutated_summary(tmp_path: Path) -> Path:
    summary_path = tmp_path / "runtime_foundation_closure_summary.json"
    summary_path.write_text(json.dumps(build_runtime_foundation_closure_summary()), encoding="utf-8")
    return summary_path
