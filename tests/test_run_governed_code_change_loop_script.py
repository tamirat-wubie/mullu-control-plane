"""Purpose: test governed code-change loop CLI wrapper.
Governance scope: request JSON parsing, receipt persistence, closure gating,
    and explicit blocked return behavior.
Dependencies: scripts.run_governed_code_change_loop and subprocess fakes.
Invariants:
  - Receipt files identify themselves as non-terminal closure evidence.
  - --require-closure returns non-zero when SDLC evidence is missing.
  - Script tests avoid live Docker by using denied commands or fake runners.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import run_governed_code_change_loop as script


def _write_request(path: Path, **overrides: object) -> Path:
    payload = {
        "action_id": "script-loop-1",
        "tenant_id": "tenant-a",
        "actor_id": "operator-a",
        "repository": "repo-a",
        "commit_sha": "abc123",
        "command_id": "cmd-1",
        "argv": ["python", "-m", "task"],
        "cwd": "src",
        "allowed_paths": ["src"],
        "allowed_commands": [["python", "-m", "task"]],
        "expires_at": "2026-05-08T12:00:00+00:00",
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_run_from_file_writes_non_terminal_receipt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    request_path = _write_request(
        tmp_path / "request.json",
        observed_sdlc_receipt_refs={
            "implementation_receipt": "receipt://sdlc/implementation/1",
            "verification_receipt": "receipt://sdlc/verification/1",
            "recovery_handoff": "receipt://sdlc/recovery/1",
        },
    )
    output_path = tmp_path / "receipt.json"

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    result = script.run_from_file(
        request_path=request_path,
        output_path=output_path,
        workspace_root=workspace,
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.closure_allowed is True
    assert payload["status"] == "closure_ready"
    assert payload["receipt_is_not_terminal_closure"] is True
    assert payload["terminal_closure_required"] is True
    assert payload["code_worker_receipt_ref"].startswith("receipt://code-worker-receipt-")
    assert payload["command_result"]["receipt"]["metadata"]["sandbox_network_disabled"] is True


def test_main_require_closure_returns_blocked_when_sdlc_receipts_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    request_path = _write_request(
        tmp_path / "request.json",
        argv=["bash", "src/task.sh"],
        allowed_commands=[["bash", "src/task.sh"]],
    )
    output_path = tmp_path / "receipt.json"

    return_code = script.main(
        [
            "--request",
            str(request_path),
            "--output",
            str(output_path),
            "--workspace-root",
            str(workspace),
            "--require-closure",
            "--json",
        ]
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert return_code == 2
    assert payload["status"] == "blocked"
    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert "code_worker_status_blocked" in payload["closure_blockers"]
    assert "missing_sdlc_verification_receipt" in payload["closure_blockers"]


def test_load_request_rejects_non_receipt_sdlc_ref(tmp_path: Path) -> None:
    request_path = _write_request(
        tmp_path / "request.json",
        observed_sdlc_receipt_refs={
            "implementation_receipt": "sdlc/implementation/1",
        },
    )

    try:
        script.load_request(request_path)
    except ValueError as exc:
        assert "receipt:// refs" in str(exc)
    else:  # pragma: no cover - explicit fail path for contract clarity
        raise AssertionError("load_request accepted a non-receipt SDLC ref")


def test_load_request_reports_missing_required_field(tmp_path: Path) -> None:
    request_path = _write_request(tmp_path / "request.json")
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    del payload["allowed_commands"]
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        script.load_request(request_path)
    except ValueError as exc:
        assert "missing required governed code-change request field: allowed_commands" in str(exc)
    else:  # pragma: no cover - explicit fail path for contract clarity
        raise AssertionError("load_request accepted a request missing allowed_commands")


def test_main_reports_missing_required_field_without_traceback(
    tmp_path: Path,
    capsys,
) -> None:
    request_path = _write_request(tmp_path / "request.json")
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    del payload["argv"]
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    return_code = script.main(["--request", str(request_path), "--output", str(tmp_path / "receipt.json")])
    streams = capsys.readouterr()

    assert return_code == 1
    assert "missing required governed code-change request field: argv" in streams.err
    assert "Traceback" not in streams.err
