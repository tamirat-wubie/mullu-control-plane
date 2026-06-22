"""Purpose: verify public demo surface validation.

Governance scope: local public-demo readiness checks for sandbox, federation,
replay, SDK, benchmark, compliance, and proof coverage witnesses.
Dependencies: scripts.validate_public_demo_surfaces and local FastAPI app.
Invariants: validation is local, deterministic, and reports bounded failures.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_first_usable_demo_packet import (
    DEFAULT_PACKET as FIRST_USABLE_DEMO_PACKET_PATH,
    validate_first_usable_demo_packet,
)
from scripts.validate_public_demo_surfaces import (
    REPO_ROOT,
    PublicDemoSurfaceReport,
    validate_openapi_source,
    validate_public_demo_surfaces,
    write_report,
)


def test_public_demo_surface_validator_passes_locally() -> None:
    report = validate_public_demo_surfaces()
    check_ids = {check.check_id for check in report.checks}

    assert report.ready is True
    assert report.report_hash.startswith("sha256:")
    assert report.to_dict()["failed_count"] == 0
    assert {"http_demo_routes", "openapi_source", "proof_coverage"} <= check_ids


def test_public_demo_surface_report_hash_is_deterministic() -> None:
    first = validate_public_demo_surfaces()
    second = PublicDemoSurfaceReport(ready=first.ready, checks=first.checks)

    assert first.report_hash == second.report_hash
    assert first.to_dict()["report_hash"] == second.report_hash
    assert first.to_dict(include_hash=False)["ready"] is True


def test_public_demo_surface_report_writes_json(tmp_path: Path) -> None:
    report = validate_public_demo_surfaces()
    output_path = tmp_path / "public_demo_surface_validation.json"

    write_report(output_path, report)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert payload["governed"] is True
    assert payload["ready"] is True
    assert payload["report_hash"] == report.report_hash


def test_openapi_source_check_is_bounded() -> None:
    check = validate_openapi_source()

    assert check.check_id == "openapi_source"
    assert check.passed is True
    assert "/api/v1/federation/summary" in check.details["required_paths"]
    assert check.errors == ()


def test_first_usable_demo_packet_validates_as_public_demo_evidence() -> None:
    validation = validate_first_usable_demo_packet()

    assert validation.valid, validation.errors
    assert validation.packet_id == "first_usable_demo_packet_v1"
    assert validation.solver_outcome == "SolvedVerified"


def test_first_usable_demo_packet_rejects_execution_authority(tmp_path: Path) -> None:
    packet = json.loads(FIRST_USABLE_DEMO_PACKET_PATH.read_text(encoding="utf-8"))
    packet["current_authority"] = copy.deepcopy(packet["current_authority"])
    packet["current_authority"]["execution_allowed"] = True
    packet_path = tmp_path / "first_usable_demo_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")

    validation = validate_first_usable_demo_packet(packet_path=packet_path)

    assert not validation.valid
    assert "current_authority.execution_allowed must be false" in validation.errors


def test_first_usable_demo_packet_rejects_live_connector_readiness_claim(tmp_path: Path) -> None:
    packet = json.loads(FIRST_USABLE_DEMO_PACKET_PATH.read_text(encoding="utf-8"))
    packet["readiness_index"] = copy.deepcopy(packet["readiness_index"])
    packet["readiness_index"]["live_connector"] = "ready"
    packet_path = tmp_path / "first_usable_demo_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")

    validation = validate_first_usable_demo_packet(packet_path=packet_path)

    assert not validation.valid
    assert "readiness_index.live_connector must remain blocked" in validation.errors


def test_first_usable_demo_packet_rejects_secret_like_values(tmp_path: Path) -> None:
    packet = json.loads(FIRST_USABLE_DEMO_PACKET_PATH.read_text(encoding="utf-8"))
    packet["next_safe_actions"] = list(packet["next_safe_actions"])
    packet["next_safe_actions"].append("Bearer secret-worker-key-value")
    packet_path = tmp_path / "first_usable_demo_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")

    validation = validate_first_usable_demo_packet(packet_path=packet_path)

    assert not validation.valid
    assert any(error.endswith("contains secret-like value") for error in validation.errors)


def test_public_demo_surface_validator_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "public_demo_surface_validation.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_public_demo_surfaces.py"),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert completed.returncode == 0
    assert output_path.exists()
    assert payload["ready"] is True
    assert "public_demo_surface_validation" in str(output_path)
