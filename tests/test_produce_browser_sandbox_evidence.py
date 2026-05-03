"""Tests for browser sandbox evidence production.

Purpose: prove browser sandbox evidence is emitted by the governed sandbox
runner and remains blocked when the runner cannot establish isolation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.produce_browser_sandbox_evidence.
Invariants:
  - Passing evidence comes from DockerRootlessSandboxRunner.
  - Non-Linux execution fails closed without launching Docker.
  - The evidence receipt is browser-capability bound.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.produce_browser_sandbox_evidence import (  # noqa: E402
    main,
    produce_browser_sandbox_evidence,
)


def test_browser_sandbox_evidence_uses_rootless_runner_receipt(tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    output_path = tmp_path / "browser-sandbox-evidence.json"

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = args[0]
        captured["shell"] = kwargs["shell"]
        captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(args[0], 0, stdout="Python 3.13", stderr="")

    result = produce_browser_sandbox_evidence(
        output_path=output_path,
        workspace_root=tmp_path,
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert payload["status"] == "passed"
    assert payload["probe"]["capability_id"] == "browser.extract_text"
    assert payload["receipt"]["verification_status"] == "passed"
    assert payload["receipt"]["network_disabled"] is True
    assert payload["receipt"]["read_only_rootfs"] is True
    assert payload["receipt"]["workspace_mount"] == "/workspace"
    assert "--read-only" in captured["argv"]
    assert captured["shell"] is False
    assert captured["timeout"] == 120


def test_browser_sandbox_evidence_blocks_on_non_linux_without_launch(tmp_path: Path) -> None:
    launched = False
    output_path = tmp_path / "browser-sandbox-evidence.json"

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal launched
        launched = True
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    result = produce_browser_sandbox_evidence(
        output_path=output_path,
        workspace_root=tmp_path,
        runner=fake_runner,
        platform_system=lambda: "Windows",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert result.status == "failed"
    assert launched is False
    assert "browser_sandbox_runner_linux_only" in result.blockers
    assert payload["receipt"]["verification_status"] == "blocked"
    assert payload["receipt"]["forbidden_effects_observed"] is True
    assert payload["blockers"] == list(result.blockers)


def test_browser_sandbox_evidence_cli_outputs_json_for_blocked_probe(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_path = tmp_path / "browser-sandbox-evidence.json"
    monkeypatch.setattr("scripts.produce_browser_sandbox_evidence.platform.system", lambda: "Windows")

    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert stdout_payload["status"] == "failed"
    assert stdout_payload["receipt_id"] == file_payload["receipt"]["receipt_id"]
    assert "browser_sandbox_probe_blocked" in stdout_payload["blockers"]
    assert file_payload["receipt"]["verification_status"] == "blocked"
    assert file_payload["receipt"]["capability_id"] == "browser.extract_text"
