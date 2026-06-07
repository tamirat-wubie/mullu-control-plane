"""Tests for deployment publication evidence packet validation.

Purpose: prove one-command deployment evidence packets are schema-backed and
semantically checked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_deployment_publication_evidence_packet and
schemas/deployment_publication_evidence_packet.schema.json.
Invariants:
  - Packet readiness matches blockers plus validation status.
  - Required artifact references remain explicit.
  - Dispatch command remains a plan, not downloaded artifact proof.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_deployment_publication_evidence_packet import (  # noqa: E402
    main,
    validate_deployment_publication_evidence_packet,
    write_deployment_publication_evidence_packet_validation,
)

SCHEMA_PATH = _ROOT / "schemas" / "deployment_publication_evidence_packet.schema.json"


def test_validate_deployment_publication_evidence_packet_accepts_blocked_packet(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    packet_path.write_text(json.dumps(_valid_blocked_packet()), encoding="utf-8")

    validation = validate_deployment_publication_evidence_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.errors == ()
    assert validation.next_action == "close blocker: deployment_dns_not_verified"
    assert validation.packet_path == "deployment_publication_evidence_packet.json"


def test_validate_deployment_publication_evidence_packet_rejects_ready_drift(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    payload = _valid_blocked_packet()
    payload["ready"] = True
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_evidence_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("ready must equal" in error for error in validation.errors)


def test_validate_deployment_publication_evidence_packet_rejects_missing_artifact(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    payload = _valid_blocked_packet()
    del payload["artifacts"]["deployment_publication_evidence_packet_validation"]
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_evidence_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("deployment_publication_evidence_packet_validation" in error for error in validation.errors)


def test_validate_deployment_publication_evidence_packet_rejects_download_command(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    payload = _valid_blocked_packet()
    payload["dispatch_command"] = ["gh", "run", "download", "1234"]
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_evidence_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("dispatch plan" in error for error in validation.errors)
    assert any("artifact download" in error for error in validation.errors)


def test_validate_deployment_publication_evidence_packet_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    output_path = tmp_path / "deployment_publication_evidence_packet_validation.json"
    packet_path.write_text(json.dumps(_valid_blocked_packet()), encoding="utf-8")
    validation = validate_deployment_publication_evidence_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_deployment_publication_evidence_packet_validation(validation, output_path)
    exit_code = main(
        [
            "--packet",
            str(packet_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is False
    assert stdout_payload["next_action"] == "close blocker: deployment_dns_not_verified"


def _valid_blocked_packet() -> dict[str, object]:
    artifact_path = "D:/packet/artifact.json"
    return {
        "packet_id": "deployment-publication-evidence-packet-0123456789abcdef",
        "output_dir": "D:/packet",
        "gateway_host": "api.mullusi.com",
        "gateway_url": "https://api.mullusi.com",
        "expected_environment": "pilot",
        "ready": False,
        "blockers": [
            "deployment_dns_not_verified",
            "deployment_upstream_api_gate_not_ready",
        ],
        "artifacts": {
            "deployment_publication_closure_plan": artifact_path,
            "deployment_publication_closure_plan_schema_validation": artifact_path,
            "deployment_publication_evidence_packet": artifact_path,
            "deployment_publication_evidence_packet_validation": artifact_path,
            "deployment_upstream_blocker_receipt": artifact_path,
            "deployment_upstream_blocker_validation": artifact_path,
            "gateway_dns_resolution_receipt": artifact_path,
            "gateway_dns_resolution_validation": artifact_path,
            "gateway_dns_target_binding_receipt": artifact_path,
            "gateway_dns_target_binding_validation": artifact_path,
            "gateway_publication_dispatch_plan": artifact_path,
            "gateway_publication_readiness": artifact_path,
        },
        "validation_status": {
            "deployment_publication_closure_plan_schema": True,
            "deployment_upstream_blocker": False,
            "gateway_dns_resolution": False,
            "gateway_dns_target_binding": False,
        },
        "dispatch_command": [
            "gh",
            "workflow",
            "run",
            "gateway-publication.yml",
            "--repo",
            "tamirat-wubie/mullu-control-plane",
        ],
    }
