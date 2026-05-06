"""Physical worker canary producer tests.

Purpose: verify the producer writes a deterministic canary artifact for
operator handoff and change-assurance use.
Governance scope: physical worker canary artifact persistence.
Dependencies: scripts.produce_physical_worker_canary.
Invariants:
  - The written artifact preserves canary id, status, blockers, and hash.
  - The artifact remains sandbox-only.
  - Strict CLI returns success for a passing canary.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_physical_worker_canary import main, produce_physical_worker_canary


ROOT = Path(__file__).resolve().parent.parent
TEST_OUTPUT_DIR = ROOT / ".change_assurance"


def test_produce_physical_worker_canary_writes_artifact() -> None:
    output_path = TEST_OUTPUT_DIR / "physical_worker_canary_test.json"

    artifact = produce_physical_worker_canary(output_path=output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert artifact.passed is True
    assert payload["canary_id"] == artifact.canary_id
    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["sandbox_output"]["physical_effect_applied"] is False
    assert payload["artifact_hash"] == artifact.artifact_hash


def test_physical_worker_canary_cli_strict_passes() -> None:
    output_path = TEST_OUTPUT_DIR / "physical_worker_canary_cli_test.json"
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["metadata"]["physical_worker_canary_blocks_without_receipt"] is True
    assert payload["worker_mesh_envelope"]["receipt"]["metadata"]["physical_action_receipt_validated"] is True
