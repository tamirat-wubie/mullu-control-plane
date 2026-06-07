"""Tests for deployment publication operator input requests.

Purpose: prove blocked publication packets become public-safe operator input
requests.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.emit_deployment_publication_operator_input_request.
Invariants:
  - Missing DNS and upstream inputs are explicit.
  - Secret values and DNS target values are not serialized.
  - Ready packets do not block publication actions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_deployment_publication_operator_input_request import (  # noqa: E402
    emit_deployment_publication_operator_input_request,
    main,
    write_deployment_publication_operator_input_request,
)

SCHEMA_PATH = _ROOT / "schemas" / "deployment_publication_operator_input_request.schema.json"


def test_operator_input_request_reports_dns_and_upstream_blockers(tmp_path: Path) -> None:
    packet_path = _write_blocked_packet(tmp_path)

    request = emit_deployment_publication_operator_input_request(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )
    required_names = {item.required_name for item in request.required_inputs}
    input_kinds = {item.input_kind for item in request.required_inputs}
    rendered = json.dumps(request.as_dict(), sort_keys=True)

    assert request.request_id.startswith("deployment-publication-operator-input-request-")
    assert request.ready is False
    assert request.publication_allowed is False
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert request.no_secret_values_serialized is True
    assert set(request.blocked_actions) == {
        "deployment_status_publication_claim",
        "dns_publication",
        "gateway_publication_workflow_dispatch",
    }
    assert {
        "MULLU_GATEWAY_DNS_TARGET",
        "MULLU_GATEWAY_DNS_RECORD_TYPE",
        "MULLU_DNS_PROVIDER",
        "UPSTREAM_API_READINESS_REPORT",
        "runtime_host_ready",
        "recovery_witness_not_ready",
    } <= required_names
    assert {
        "dns_origin_target",
        "dns_record_type",
        "dns_provider",
        "public_dns_resolution",
        "upstream_readiness_report",
        "upstream_evidence",
    } <= input_kinds
    assert "secret-value" not in rendered
    assert "203.0.113.10" not in rendered


def test_operator_input_request_cli_writes_report(tmp_path: Path, capsys) -> None:
    packet_path = _write_blocked_packet(tmp_path)
    output_path = tmp_path / "operator_input_request.json"
    request = emit_deployment_publication_operator_input_request(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_deployment_publication_operator_input_request(request, output_path)
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
    assert payload["publication_allowed"] is False
    assert payload["required_inputs"]
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def test_operator_input_request_allows_ready_packet(tmp_path: Path) -> None:
    packet_path = _write_ready_packet(tmp_path)

    request = emit_deployment_publication_operator_input_request(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert request.ready is True
    assert request.publication_allowed is True
    assert request.solver_outcome == "SolvedVerified"
    assert request.proof_state == "Pass"
    assert request.required_inputs == ()
    assert request.blocked_actions == ()


def _write_blocked_packet(tmp_path: Path) -> Path:
    upstream_receipt = tmp_path / "deployment_upstream_blocker_receipt.json"
    dns_target_receipt = tmp_path / "gateway_dns_target_binding_receipt.json"
    dns_resolution_receipt = tmp_path / "gateway_dns_resolution_receipt.json"
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    upstream_receipt.write_text(
        json.dumps(
            {
                "ready": False,
                "evidence_refs": ["upstream-readiness-report:upstream_api_readiness.json"],
                "blockers": [
                    "recovery_witness_not_ready",
                    "manual_evidence_missing:runtime_host_ready",
                ],
            }
        ),
        encoding="utf-8",
    )
    dns_target_receipt.write_text(
        json.dumps(
            {
                "ready": False,
                "binding_state": "missing-target",
                "record_type": "",
                "target": "",
                "provider": "",
            }
        ),
        encoding="utf-8",
    )
    dns_resolution_receipt.write_text(
        json.dumps({"resolved": False, "error": "resolution_error"}),
        encoding="utf-8",
    )
    packet_path.write_text(
        json.dumps(
            {
                "packet_id": "deployment-publication-evidence-packet-0123456789abcdef",
                "gateway_host": "api.mullusi.com",
                "gateway_url": "https://api.mullusi.com",
                "ready": False,
                "blockers": [
                    "deployment_dns_not_verified",
                    "deployment_upstream_api_gate_not_ready",
                ],
                "artifacts": {
                    "deployment_upstream_blocker_receipt": str(upstream_receipt),
                    "gateway_dns_resolution_receipt": str(dns_resolution_receipt),
                    "gateway_dns_target_binding_receipt": str(dns_target_receipt),
                },
            }
        ),
        encoding="utf-8",
    )
    return packet_path


def _write_ready_packet(tmp_path: Path) -> Path:
    packet_path = tmp_path / "deployment_publication_evidence_packet.json"
    packet_path.write_text(
        json.dumps(
            {
                "packet_id": "deployment-publication-evidence-packet-fedcba9876543210",
                "gateway_host": "api.mullusi.com",
                "gateway_url": "https://api.mullusi.com",
                "ready": True,
                "blockers": [],
                "artifacts": {},
            }
        ),
        encoding="utf-8",
    )
    return packet_path
