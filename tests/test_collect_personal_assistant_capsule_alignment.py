"""Tests for Personal Assistant capsule alignment collection.

Purpose: prove capsule alignment collection binds capsule refs, capability
pack ids, schema refs, and authority coverage without granting execution
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_capsule_alignment and checked-in
Personal Assistant foundation fixtures.
Invariants:
  - SolvedVerified requires capsule refs to match capability pack ids.
  - Missing schema refs keep the receipt AwaitingEvidence.
  - Capability production overclaim keeps the receipt AwaitingEvidence.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_capsule_alignment import (  # noqa: E402
    DEFAULT_AUTHORITY_COVERAGE,
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_CAPSULE,
    DEFAULT_PROTOCOL_MANIFEST,
    collect_personal_assistant_capsule_alignment,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 18, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_capsule_alignment_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_capsule_alignment(now_utc=FIXED_NOW)
    summary = receipt["alignment_summary"]  # type: ignore[index]
    first_capability = receipt["capability_binding_records"][0]  # type: ignore[index]
    first_schema = receipt["schema_binding_records"][0]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["capsule_alignment_closed"] is True
    assert summary["capsule_refs_match_pack"] is True
    assert first_capability["alignment_covered"] is True
    assert first_schema["manifest_bound"] is True
    assert first_schema["file_bound"] is True


def test_capsule_alignment_blocks_missing_capsule_ref(tmp_path: Path) -> None:
    capsule = json.loads(DEFAULT_CAPSULE.read_text(encoding="utf-8"))
    capsule["capability_refs"] = capsule["capability_refs"][:-1]
    capsule_path = _write_json(tmp_path, "capsule.json", capsule)

    receipt = collect_personal_assistant_capsule_alignment(
        capsule_path=capsule_path,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        protocol_manifest_path=DEFAULT_PROTOCOL_MANIFEST,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["alignment_summary"]["capsule_refs_match_pack"] is False  # type: ignore[index]
    assert receipt["alignment_summary"]["capsule_alignment_closed"] is False  # type: ignore[index]


def test_capsule_alignment_blocks_schema_manifest_drift(tmp_path: Path) -> None:
    manifest = json.loads(DEFAULT_PROTOCOL_MANIFEST.read_text(encoding="utf-8"))
    manifest["schemas"] = [
        record for record in manifest["schemas"] if record.get("path") != "schemas/personal_assistant_plan.schema.json"
    ]
    manifest_path = _write_json(tmp_path, "manifest.json", manifest)

    receipt = collect_personal_assistant_capsule_alignment(
        capsule_path=DEFAULT_CAPSULE,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        protocol_manifest_path=manifest_path,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        now_utc=FIXED_NOW,
    )

    plan_record = [
        record
        for record in receipt["schema_binding_records"]  # type: ignore[index]
        if record["schema_ref"] == "schemas/personal_assistant_plan.schema.json"
    ][0]

    assert receipt["proof_state"] == "Fail"
    assert plan_record["manifest_bound"] is False
    assert receipt["alignment_summary"]["all_schema_refs_bound"] is False  # type: ignore[index]
    assert receipt["alignment_summary"]["capsule_alignment_closed"] is False  # type: ignore[index]


def test_capsule_alignment_blocks_capability_production_overclaim(tmp_path: Path) -> None:
    capability_pack = json.loads(DEFAULT_CAPABILITY_PACK.read_text(encoding="utf-8"))
    capability_pack["capabilities"][0]["metadata"]["production_ready"] = True
    capability_pack_path = _write_json(tmp_path, "capability_pack.json", capability_pack)

    receipt = collect_personal_assistant_capsule_alignment(
        capsule_path=DEFAULT_CAPSULE,
        capability_pack_path=capability_pack_path,
        protocol_manifest_path=DEFAULT_PROTOCOL_MANIFEST,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["capability_binding_records"][0]["production_ready"] is True  # type: ignore[index]
    assert receipt["capability_binding_records"][0]["alignment_covered"] is False  # type: ignore[index]
    assert receipt["alignment_summary"]["capsule_alignment_closed"] is False  # type: ignore[index]


def test_capsule_alignment_cli_writes_receipt(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "capsule_alignment.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["receipt_id"] == payload["receipt_id"]
    assert payload["alignment_summary"]["capsule_alignment_closed"] is True
    assert output_path.exists()
