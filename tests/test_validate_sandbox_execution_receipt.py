"""Tests for governed sandbox execution receipt validation.

Purpose: prove sandbox receipts are independently reusable across worker and
adapter proof gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.sandbox_runner and scripts.validate_sandbox_execution_receipt.
Invariants:
  - Passing runner receipts validate.
  - Missing or malformed receipts fail closed.
  - Isolation and workspace-mutation requirements are explicit.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess

from gateway.sandbox_runner import (
    DockerRootlessSandboxRunner,
    SandboxCommandRequest,
)
from scripts.validate_sandbox_execution_receipt import (
    main,
    validate_sandbox_execution_receipt,
)


def test_validate_sandbox_execution_receipt_accepts_runner_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "sandbox-receipt.json"
    result = _write_runner_receipt(receipt_path, tmp_path, capability_id="computer.command.run")

    validation = validate_sandbox_execution_receipt(receipt_path, capability_prefix="computer.")

    assert result.status == "succeeded"
    assert validation.valid is True
    assert validation.receipt_id.startswith("sandbox-receipt-")
    assert validation.capability_id == "computer.command.run"
    assert validation.verification_status == "passed"
    assert validation.blockers == ()
    assert "sandbox receipt verified" in validation.detail


def test_validate_sandbox_execution_receipt_accepts_nested_evidence_envelope(tmp_path: Path) -> None:
    receipt_path = tmp_path / "sandbox-envelope.json"
    result = _write_runner_receipt(receipt_path, tmp_path, nested=True)

    validation = validate_sandbox_execution_receipt(receipt_path, capability_prefix="computer.")

    assert result.receipt.network_disabled is True
    assert validation.valid is True
    assert validation.receipt_id == result.receipt.receipt_id
    assert validation.blockers == ()


def test_validate_sandbox_execution_receipt_rejects_missing_file(tmp_path: Path) -> None:
    validation = validate_sandbox_execution_receipt(tmp_path / "missing.json")

    assert validation.valid is False
    assert validation.status == "failed"
    assert validation.receipt_id == ""
    assert validation.blockers == ("sandbox_receipt_unreadable",)
    assert "not found" in validation.detail


def test_validate_sandbox_execution_receipt_rejects_weak_isolation(tmp_path: Path) -> None:
    receipt_path = tmp_path / "weak-receipt.json"
    result = _write_runner_receipt(receipt_path, tmp_path)
    payload = asdict(result.receipt)
    payload["network_disabled"] = False
    payload["read_only_rootfs"] = False
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_sandbox_execution_receipt(receipt_path)

    assert validation.valid is False
    assert validation.blockers == ("sandbox_receipt_invalid",)
    assert "network_disabled_not_true" in validation.detail
    assert "read_only_rootfs_not_true" in validation.detail


def test_validate_sandbox_execution_receipt_rejects_nonzero_passed_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "nonzero-receipt.json"
    result = _write_runner_receipt(receipt_path, tmp_path)
    payload = asdict(result.receipt)
    payload["returncode"] = 7
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_sandbox_execution_receipt(receipt_path)

    assert validation.valid is False
    assert validation.blockers == ("sandbox_receipt_invalid",)
    assert "returncode_not_zero" in validation.detail


def test_validate_sandbox_execution_receipt_rejects_untyped_workspace_refs(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "bad-diff-receipt.json"
    result = _write_runner_receipt(receipt_path, tmp_path)
    payload = asdict(result.receipt)
    payload["changed_file_count"] = 1
    payload["changed_file_refs"] = ["plain:path"]
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_sandbox_execution_receipt(receipt_path)

    assert validation.valid is False
    assert validation.blockers == ("sandbox_receipt_invalid",)
    assert "changed_file_refs_not_workspace_diff" in validation.detail


def test_validate_sandbox_execution_receipt_rejects_workspace_changes_when_required(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "mutating-receipt.json"
    changed_file = tmp_path / "result.txt"

    def mutating_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        changed_file.write_text("changed", encoding="utf-8")
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        runner=mutating_runner,
        platform_system=lambda: "Linux",
    )
    result = runner.execute(_request())
    receipt_path.write_text(json.dumps(asdict(result.receipt)), encoding="utf-8")

    validation = validate_sandbox_execution_receipt(
        receipt_path,
        require_no_workspace_changes=True,
    )

    assert result.receipt.changed_file_count == 1
    assert validation.valid is False
    assert validation.blockers == ("sandbox_receipt_invalid",)
    assert "changed_file_count_not_zero" in validation.detail
    assert "changed_file_refs_not_empty" in validation.detail


def test_validate_sandbox_execution_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "sandbox-receipt.json"
    _write_runner_receipt(receipt_path, tmp_path)

    exit_code = main(["--receipt", str(receipt_path), "--capability-prefix", "computer.", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["status"] == "passed"
    assert payload["receipt_id"].startswith("sandbox-receipt-")
    assert payload["capability_id"] == "computer.command.run"
    assert payload["blockers"] == []


def _write_runner_receipt(
    path: Path,
    workspace_root: Path,
    *,
    capability_id: str = "computer.command.run",
    nested: bool = False,
):
    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(workspace_root),
        runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr=""),
        platform_system=lambda: "Linux",
    )
    result = runner.execute(_request(capability_id=capability_id))
    payload = {"receipt": asdict(result.receipt)} if nested else asdict(result.receipt)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return result


def _request(*, capability_id: str = "computer.command.run") -> SandboxCommandRequest:
    return SandboxCommandRequest(
        request_id="sandbox-request-validate",
        tenant_id="tenant-1",
        capability_id=capability_id,
        argv=("python", "--version"),
    )
