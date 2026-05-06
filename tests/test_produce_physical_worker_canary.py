"""Physical worker canary CLI tests.

Purpose: verify the offline canary producer writes a deterministic artifact.
Governance scope: CLI output, strict failure behavior, and artifact evidence.
Dependencies: scripts.produce_physical_worker_canary.
Invariants:
  - The CLI writes the full canary artifact.
  - Strict mode succeeds only when the canary passes.
  - JSON summary omits raw handler internals.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_physical_worker_canary import main


def test_produce_physical_worker_canary_writes_artifact(capsys) -> None:
    output_path = Path(".change_assurance") / "physical_worker_canary_cli_test.json"

    exit_code = main(["--strict", "--json", "--output", str(output_path)])
    captured = capsys.readouterr()
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    summary = json.loads(captured.out)

    assert exit_code == 0
    assert artifact["status"] == "passed"
    assert artifact["blocked_dispatch_receipt"]["reason"] == "physical_action_receipt_required"
    assert artifact["worker_mesh_envelope"]["receipt"]["status"] == "succeeded"
    assert summary["canary_id"] == artifact["canary_id"]


def test_produce_physical_worker_canary_artifact_is_hash_bound() -> None:
    output_path = Path(".change_assurance") / "physical_worker_canary_cli_test.json"

    exit_code = main(["--strict", "--output", str(output_path)])
    artifact = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert len(artifact["artifact_hash"]) == 64
    assert artifact["canary_id"].startswith("physical-worker-canary-")
    assert artifact["metadata"]["no_physical_effect_applied"] is True
