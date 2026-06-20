"""Tests for Personal Assistant skill readiness catalog collection.

Purpose: prove skill readiness catalog collection binds every registered skill
to lane evidence and authority coverage without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_skill_readiness_catalog and
checked-in Personal Assistant foundation fixtures.
Invariants:
  - SolvedVerified requires every skill to bind to a solved readiness lane.
  - P4/P5 skills remain approval guarded.
  - Any execution or authority drift preserves AwaitingEvidence.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_skill_readiness_catalog import (  # noqa: E402
    DEFAULT_AUTHORITY_COVERAGE,
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_READINESS_INDEX,
    DEFAULT_SKILL_REGISTRY,
    collect_personal_assistant_skill_readiness_catalog,
    main,
)


FIXED_NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_skill_readiness_catalog_closes_from_checked_in_evidence() -> None:
    catalog = collect_personal_assistant_skill_readiness_catalog(now_utc=FIXED_NOW)
    summary = catalog["catalog_summary"]  # type: ignore[index]
    first_record = catalog["skill_records"][0]  # type: ignore[index]

    assert catalog["proof_state"] == "Pass"
    assert catalog["solver_outcome"] == "SolvedVerified"
    assert summary["catalog_closed"] is True
    assert summary["skill_count"] == summary["registered_skill_count"] == 17
    assert summary["all_skills_lane_bound"] is True
    assert summary["all_skills_non_executable"] is True
    assert first_record["readiness_lane_state"] == "SolvedVerified"
    assert first_record["authority_covered"] is True


def test_skill_readiness_catalog_blocks_missing_lane_binding(tmp_path: Path) -> None:
    readiness_index = json.loads(DEFAULT_READINESS_INDEX.read_text(encoding="utf-8"))
    readiness_index["lane_records"] = [
        record for record in readiness_index["lane_records"] if record["lane_id"] != "draft_projection"
    ]
    readiness_path = _write_json(tmp_path, "readiness_index.json", readiness_index)

    catalog = collect_personal_assistant_skill_readiness_catalog(
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        readiness_index_path=readiness_path,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    draft_record = [record for record in catalog["skill_records"] if record["mode"] == "draft_only"][0]  # type: ignore[index]

    assert catalog["proof_state"] == "Fail"
    assert catalog["solver_outcome"] == "AwaitingEvidence"
    assert draft_record["readiness_bound"] is False
    assert draft_record["readiness_lane_state"] == "AwaitingEvidence"
    assert catalog["catalog_summary"]["all_skills_lane_bound"] is False  # type: ignore[index]


def test_skill_readiness_catalog_blocks_authority_coverage_drift(tmp_path: Path) -> None:
    authority = json.loads(DEFAULT_AUTHORITY_COVERAGE.read_text(encoding="utf-8"))
    authority["skill_authority_records"][0]["authority_covered"] = False
    authority_path = _write_json(tmp_path, "authority_coverage.json", authority)

    catalog = collect_personal_assistant_skill_readiness_catalog(
        skill_registry_path=DEFAULT_SKILL_REGISTRY,
        readiness_index_path=DEFAULT_READINESS_INDEX,
        authority_coverage_path=authority_path,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert catalog["proof_state"] == "Fail"
    assert catalog["solver_outcome"] == "AwaitingEvidence"
    assert catalog["skill_records"][0]["authority_covered"] is False  # type: ignore[index]
    assert catalog["catalog_summary"]["all_skills_authority_covered"] is False  # type: ignore[index]


def test_skill_readiness_catalog_blocks_p4_approval_drift(tmp_path: Path) -> None:
    registry = json.loads(DEFAULT_SKILL_REGISTRY.read_text(encoding="utf-8"))
    registry["skills"][2]["requires_approval"] = False
    registry_path = _write_json(tmp_path, "skill_registry.json", registry)

    catalog = collect_personal_assistant_skill_readiness_catalog(
        skill_registry_path=registry_path,
        readiness_index_path=DEFAULT_READINESS_INDEX,
        authority_coverage_path=DEFAULT_AUTHORITY_COVERAGE,
        capability_pack_path=DEFAULT_CAPABILITY_PACK,
        now_utc=FIXED_NOW,
    )

    assert catalog["proof_state"] == "Fail"
    assert catalog["solver_outcome"] == "AwaitingEvidence"
    assert catalog["skill_records"][2]["p4_p5_approval_guarded"] is False  # type: ignore[index]
    assert catalog["catalog_summary"]["p4_p5_skills_require_approval"] is False  # type: ignore[index]


def test_skill_readiness_catalog_cli_writes_catalog(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "skill_readiness_catalog.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(captured.out)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["solver_outcome"] == "SolvedVerified"
    assert printed["catalog_id"] == payload["catalog_id"]
    assert payload["catalog_summary"]["catalog_closed"] is True
