"""Tests for physical capability promotion preflight.

Purpose: prove fixture-only physical packs cannot become production claims
without full live safety evidence and production maturity evidence.
Governance scope: physical promotion preflight, blocker derivation, strict CLI
behavior, and sandbox-only separation.
Dependencies: scripts.preflight_physical_capability_promotion.
Invariants:
  - Checked-in physical fixture pack is blocked for live promotion by default.
  - Fully evidenced physical live capability passes preflight.
  - Sandbox-only physical pack does not create a production claim.
  - CLI writes a deterministic preflight report.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.preflight_physical_capability_promotion import (
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_CAPSULE,
    main,
    preflight_physical_capability_promotion,
    write_physical_promotion_preflight_report,
)


def test_physical_capability_promotion_preflight_blocks_live_fixture_by_default() -> None:
    report = preflight_physical_capability_promotion()
    steps = {step.name: step for step in report.steps}

    assert report.ready is False
    assert report.readiness_level == "blocked"
    assert report.physical_capability_count == 2
    assert report.sandbox_only_capabilities == ("physical.sandbox_replay",)
    assert report.live_physical_candidates == ("physical.unlock_door",)
    assert report.production_claim_capabilities == ()
    assert "live physical safety evidence complete" in report.blockers
    assert "physical production readiness gate" in report.blockers
    assert steps["physical production evidence projection"].passed is True
    assert "physical.unlock_door:physical_live_safety_evidence_required" in steps[
        "live physical safety evidence complete"
    ].detail
    assert "physical.unlock_door:production_ready_required" in steps[
        "physical production readiness gate"
    ].detail


def test_physical_capability_promotion_preflight_passes_with_full_evidence(tmp_path: Path) -> None:
    capsule_path, pack_path = _promoted_physical_pack(tmp_path)

    report = preflight_physical_capability_promotion(
        capsule_path=capsule_path,
        capability_pack_path=pack_path,
    )
    steps = {step.name: step for step in report.steps}

    assert report.ready is True
    assert report.readiness_level == "physical-production-ready"
    assert report.sandbox_only_capabilities == ("physical.sandbox_replay",)
    assert report.live_physical_candidates == ("physical.unlock_door",)
    assert report.production_claim_capabilities == ("physical.unlock_door",)
    assert report.blockers == ()
    assert all(step.passed for step in report.steps)
    assert "live_physical_capabilities=['physical.unlock_door']" in steps[
        "physical production evidence projection"
    ].detail
    assert "physical_policy_passed=True" in steps["physical production evidence projection"].detail


def test_physical_capability_promotion_preflight_allows_sandbox_only_pack(tmp_path: Path) -> None:
    capsule_path, pack_path = _sandbox_only_physical_pack(tmp_path)

    report = preflight_physical_capability_promotion(
        capsule_path=capsule_path,
        capability_pack_path=pack_path,
    )

    assert report.ready is True
    assert report.readiness_level == "physical-sandbox-only"
    assert report.physical_capability_count == 1
    assert report.sandbox_only_capabilities == ("physical.sandbox_replay",)
    assert report.live_physical_candidates == ()
    assert report.production_claim_capabilities == ()
    assert report.blockers == ()


def test_physical_capability_promotion_preflight_cli_outputs_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "physical-preflight.json"
    report = preflight_physical_capability_promotion()

    written = write_physical_promotion_preflight_report(report, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert exit_code == 2
    assert stdout_payload["ready"] is False
    assert written_payload["readiness_level"] == "blocked"
    assert written_payload["sandbox_only_capabilities"] == ["physical.sandbox_replay"]
    assert written_payload["live_physical_candidates"] == ["physical.unlock_door"]
    assert "physical production readiness gate" in written_payload["blockers"]


def _promoted_physical_pack(tmp_path: Path) -> tuple[Path, Path]:
    capsule = _load_json(DEFAULT_CAPSULE)
    pack = _load_json(DEFAULT_CAPABILITY_PACK)
    for capability in pack["capabilities"]:
        if capability["capability_id"] != "physical.unlock_door":
            continue
        extensions = capability.setdefault("extensions", {})
        extensions["physical_live_safety_evidence"] = _full_live_safety_evidence()
        extensions["capability_maturity_evidence"] = {
            "sandbox_receipt_valid": True,
            "live_read_receipt_valid": True,
            "live_write_receipt_valid": True,
            "worker_deployment_bound": True,
            "recovery_evidence_present": True,
            "evidence_refs": [
                "proof://capabilities/physical.unlock_door/sandbox",
                "proof://capabilities/physical.unlock_door/live-read",
                "proof://capabilities/physical.unlock_door/live-write",
                "proof://capabilities/physical.unlock_door/worker",
                "proof://capabilities/physical.unlock_door/recovery",
            ],
        }
    return _write_candidate(tmp_path, capsule, pack)


def _sandbox_only_physical_pack(tmp_path: Path) -> tuple[Path, Path]:
    capsule = _load_json(DEFAULT_CAPSULE)
    pack = _load_json(DEFAULT_CAPABILITY_PACK)
    capsule["capability_refs"] = ["physical.sandbox_replay"]
    pack["capabilities"] = [
        capability
        for capability in pack["capabilities"]
        if capability["capability_id"] == "physical.sandbox_replay"
    ]
    return _write_candidate(tmp_path, capsule, pack)


def _write_candidate(tmp_path: Path, capsule: dict, pack: dict) -> tuple[Path, Path]:
    capsule_path = tmp_path / "physical.json"
    pack_path = tmp_path / "capability_pack.json"
    capsule_path.write_text(json.dumps(capsule, indent=2, sort_keys=True), encoding="utf-8")
    pack_path.write_text(json.dumps(pack, indent=2, sort_keys=True), encoding="utf-8")
    return capsule_path, pack_path


def _full_live_safety_evidence() -> dict[str, str]:
    return {
        "physical_action_receipt_ref": "physical-action-receipt-0123456789abcdef",
        "simulation_ref": "proof://physical/simulation-pass",
        "operator_approval_ref": "approval:physical-live",
        "manual_override_ref": "manual-override:physical-live",
        "emergency_stop_ref": "emergency-stop:physical-live",
        "sensor_confirmation_ref": "sensor-confirmation:physical-live",
        "deployment_witness_ref": "deployment-witness:physical-live",
    }


def _load_json(path: Path) -> dict:
    return copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
