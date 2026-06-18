"""Tests for Personal Assistant runtime boundary collection.

Purpose: prove runtime boundary collection binds Personal Assistant runtime
source, capability pack, and policy matrix evidence without granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_runtime_boundary and checked-in
Personal Assistant Foundation Mode fixtures.
Invariants:
  - SolvedVerified requires runtime modules to remain connector-free.
  - Capability drift keeps the receipt AwaitingEvidence.
  - Runtime authority markers are rejected before closure.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_runtime_boundary import (  # noqa: E402
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_POLICY_MATRIX,
    DEFAULT_RUNTIME_DIR,
    collect_personal_assistant_runtime_boundary,
    main,
)


FIXED_NOW = datetime(2026, 6, 17, 13, 0, tzinfo=UTC)


def _copy_runtime_dir(tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "personal_assistant"
    shutil.copytree(DEFAULT_RUNTIME_DIR, runtime_dir)
    return runtime_dir


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_runtime_boundary_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_runtime_boundary(now_utc=FIXED_NOW)
    summary = receipt["runtime_boundary_summary"]  # type: ignore[index]
    module_records = receipt["module_records"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["runtime_boundary_closed"] is True
    assert summary["no_forbidden_imports"] is True
    assert summary["no_forbidden_calls"] is True
    assert all(record["module_boundary_closed"] is True for record in module_records)


def test_runtime_boundary_blocks_forbidden_runtime_import(tmp_path: Path) -> None:
    runtime_dir = _copy_runtime_dir(tmp_path)
    target = runtime_dir / "read_only.py"
    target.write_text(target.read_text(encoding="utf-8") + "\nimport requests\n", encoding="utf-8")

    receipt = collect_personal_assistant_runtime_boundary(
        runtime_dir=runtime_dir,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        policy_matrix_path=DEFAULT_POLICY_MATRIX,
        now_utc=FIXED_NOW,
    )
    read_only_record = [record for record in receipt["module_records"] if record["module_name"] == "read_only.py"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert read_only_record["forbidden_import_count"] == 1
    assert read_only_record["module_boundary_closed"] is False


def test_runtime_boundary_blocks_runtime_authority_marker(tmp_path: Path) -> None:
    runtime_dir = _copy_runtime_dir(tmp_path)
    target = runtime_dir / "planner.py"
    target.write_text(target.read_text(encoding="utf-8") + '\nAUTHORITY_DRIFT = {"memory_write_allowed": True}\n', encoding="utf-8")

    receipt = collect_personal_assistant_runtime_boundary(
        runtime_dir=runtime_dir,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        policy_matrix_path=DEFAULT_POLICY_MATRIX,
        now_utc=FIXED_NOW,
    )
    planner_record = [record for record in receipt["module_records"] if record["module_name"] == "planner.py"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert planner_record["runtime_authority_marker_count"] == 1
    assert receipt["runtime_boundary_summary"]["no_runtime_authority_markers"] is False  # type: ignore[index]
    assert receipt["runtime_boundary_summary"]["runtime_boundary_closed"] is False  # type: ignore[index]


def test_runtime_boundary_blocks_capability_mutation_drift(tmp_path: Path) -> None:
    capability_pack = json.loads(DEFAULT_CAPABILITY_PACK.read_text(encoding="utf-8"))
    capability_pack["capabilities"][0]["extensions"]["governed_record"]["world_mutating"] = True
    capability_pack_path = _write_json(tmp_path, "capability_pack.json", capability_pack)

    receipt = collect_personal_assistant_runtime_boundary(
        runtime_dir=DEFAULT_RUNTIME_DIR,
        capability_pack_path=capability_pack_path,
        policy_matrix_path=DEFAULT_POLICY_MATRIX,
        now_utc=FIXED_NOW,
    )
    first_capability = receipt["capability_runtime_records"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert first_capability["world_mutating"] is True
    assert first_capability["runtime_boundary_closed"] is False
    assert receipt["runtime_boundary_summary"]["capability_pack_non_mutating"] is False  # type: ignore[index]


def test_runtime_boundary_cli_writes_receipt(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "runtime_boundary.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["receipt_id"] == payload["receipt_id"]
    assert payload["runtime_boundary_summary"]["runtime_boundary_closed"] is True
    assert output_path.exists()
