"""Tests for personal-assistant foundation evidence collection.

Purpose: prove aggregate foundation evidence can be collected without enabling
connector, deployment, or assistant execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_foundation_evidence and checked-in
personal-assistant evidence fixtures.
Invariants:
  - SolvedVerified requires console, public probe, component witness, and no-effect closure.
  - Drifted source evidence preserves AwaitingEvidence.
  - Raw private payloads are not serialized.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_foundation_evidence import (  # noqa: E402
    DEFAULT_COMPONENT_WITNESS,
    DEFAULT_CONSOLE_READ_MODEL,
    DEFAULT_PUBLIC_CONSOLE_PROBE,
    collect_personal_assistant_foundation_evidence,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_foundation_evidence_closes_from_checked_in_evidence() -> None:
    receipt = collect_personal_assistant_foundation_evidence(now_utc=FIXED_NOW)
    summary = receipt["summary"]  # type: ignore[index]
    boundary = receipt["effect_boundary"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["evidence_item_count"] == 3
    assert summary["foundation_evidence_closed"] is True
    assert boundary["execution_allowed"] is False
    assert boundary["raw_private_payloads_serialized"] is False


def test_foundation_evidence_preserves_awaiting_evidence_when_public_probe_opens(tmp_path: Path) -> None:
    public_probe = json.loads(DEFAULT_PUBLIC_CONSOLE_PROBE.read_text(encoding="utf-8"))
    public_probe["proof_state"] = "Fail"
    public_probe["solver_outcome"] = "AwaitingEvidence"
    public_probe["summary"]["probe_closed"] = False
    public_probe_path = _write_json(tmp_path, "public_probe.json", public_probe)

    receipt = collect_personal_assistant_foundation_evidence(
        console_read_model_path=DEFAULT_CONSOLE_READ_MODEL,
        public_console_probe_path=public_probe_path,
        component_witness_path=DEFAULT_COMPONENT_WITNESS,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["foundation_evidence_closed"] is False  # type: ignore[index]
    assert receipt["summary"]["public_console_probe_verified"] is False  # type: ignore[index]


def test_foundation_evidence_blocks_effect_boundary_drift(tmp_path: Path) -> None:
    console = json.loads(DEFAULT_CONSOLE_READ_MODEL.read_text(encoding="utf-8"))
    console["lane_status"]["execution_allowed"] = True
    console_path = _write_json(tmp_path, "console.json", console)

    receipt = collect_personal_assistant_foundation_evidence(
        console_read_model_path=console_path,
        public_console_probe_path=DEFAULT_PUBLIC_CONSOLE_PROBE,
        component_witness_path=DEFAULT_COMPONENT_WITNESS,
        now_utc=FIXED_NOW,
    )
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["no_effect_boundary_verified"] is False  # type: ignore[index]
    assert receipt["effect_boundary"]["execution_allowed"] is True  # type: ignore[index]
    assert "access_token" not in serialized
    assert "client_secret" not in serialized


def test_foundation_evidence_cli_writes_closed_receipt(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    output_path = tmp_path / "personal_assistant_foundation_evidence.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["summary"]["foundation_evidence_closed"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert len(payload["evidence_items"]) == 3
    assert captured.err == ""
