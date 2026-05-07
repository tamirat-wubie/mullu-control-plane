"""Tests for the physical capability promotion receipt emitter.

Purpose: verify operators can emit a schema-backed physical promotion receipt
from the same Forge, handoff, registry-install, and preflight chain used by
runtime admission.
Governance scope: physical promotion receipt CLI, explicit safety refs, schema
validation, and bounded blocked output.
Dependencies: scripts.emit_physical_capability_promotion_receipt and
schemas/physical_capability_promotion_receipt.schema.json.
Invariants:
  - Fixture refs are opt-in.
  - Missing live safety refs block receipt emission.
  - Emitted receipts validate against the public schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_physical_capability_promotion_receipt import (
    emit_physical_capability_promotion_receipt,
    main,
    write_physical_capability_promotion_receipt,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


SCHEMA_PATH = Path("schemas/physical_capability_promotion_receipt.schema.json")


def test_emit_physical_capability_promotion_receipt_accepts_fixture_refs(tmp_path: Path) -> None:
    output_path = tmp_path / "physical-promotion-receipt.json"

    receipt, errors = emit_physical_capability_promotion_receipt(use_fixture_refs=True)
    written = write_physical_capability_promotion_receipt(receipt, output_path) if receipt else None
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert errors == ()
    assert receipt is not None
    assert written == output_path
    assert receipt.promotion_status == "ready"
    assert receipt.preflight_ready is True
    assert payload["receipt_id"] == receipt.receipt_id
    assert "simulation_ref" in payload["forge_requirement_keys"]
    assert "deployment_witness_ref" in payload["registry_physical_safety_evidence_keys"]
    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), payload) == []


def test_emit_physical_capability_promotion_receipt_blocks_missing_refs() -> None:
    receipt, errors = emit_physical_capability_promotion_receipt()

    assert receipt is None
    assert errors
    assert "live_read_receipt_ref_required" in errors


def test_emit_physical_capability_promotion_receipt_blocks_missing_physical_safety_refs() -> None:
    receipt, errors = emit_physical_capability_promotion_receipt(
        live_read_receipt_ref="proof://physical.unlock_door/live-read",
        live_write_receipt_ref="proof://physical.unlock_door/live-write",
        worker_deployment_ref="proof://physical.unlock_door/worker",
        recovery_evidence_ref="proof://physical.unlock_door/recovery",
    )

    assert receipt is None
    assert errors
    assert any(error.startswith("physical_live_safety_evidence_refs_incomplete:") for error in errors)


def test_emit_physical_capability_promotion_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "physical-promotion-receipt.json"

    exit_code = main(["--use-fixture-refs", "--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["ready"] is True
    assert stdout_payload["receipt_id"] == written_payload["receipt_id"]
    assert written_payload["promotion_status"] == "ready"
    assert written_payload["receipt_is_not_admission_authority"] is True
    assert written_payload["receipt_is_not_terminal_closure"] is True


def test_emit_physical_capability_promotion_receipt_cli_strict_blocks_missing_refs(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "physical-promotion-receipt.json"

    exit_code = main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output_path.exists() is False
    assert stdout_payload["ready"] is False
    assert "live_read_receipt_ref_required" in stdout_payload["errors"]
