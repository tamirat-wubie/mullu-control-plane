"""Tests for deployment publication operator input request validation.

Purpose: prove operator input requests are schema-backed and semantically
checked before operators rely on them.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_deployment_publication_operator_input_request.
Invariants:
  - Publication allowance matches readiness and missing inputs.
  - Blocked requests preserve required inputs and blocked actions.
  - Validation reports are bounded and public-safe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_deployment_publication_operator_input_request import (  # noqa: E402
    main,
    validate_deployment_publication_operator_input_request,
    write_deployment_publication_operator_input_request_validation,
)

SCHEMA_PATH = _ROOT / "schemas" / "deployment_publication_operator_input_request.schema.json"


def test_validate_operator_input_request_accepts_blocked_request(tmp_path: Path) -> None:
    request_path = tmp_path / "deployment_publication_operator_input_request.json"
    request_path.write_text(json.dumps(_blocked_request()), encoding="utf-8")

    validation = validate_deployment_publication_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is True
    assert validation.publication_allowed is False
    assert validation.errors == ()
    assert validation.next_action == "bind DNS target"
    assert validation.request_path == "deployment_publication_operator_input_request.json"


def test_validate_operator_input_request_rejects_publication_drift(tmp_path: Path) -> None:
    request_path = tmp_path / "deployment_publication_operator_input_request.json"
    payload = _blocked_request()
    payload["publication_allowed"] = True
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("publication_allowed must equal" in error for error in validation.errors)


def test_validate_operator_input_request_rejects_ready_drift(tmp_path: Path) -> None:
    request_path = tmp_path / "deployment_publication_operator_input_request.json"
    payload = _ready_request()
    payload["blocked_actions"] = ["dns_publication"]
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("publication_allowed must equal" in error for error in validation.errors)


def test_validate_operator_input_request_cli_writes_report(tmp_path: Path, capsys) -> None:
    request_path = tmp_path / "deployment_publication_operator_input_request.json"
    output_path = tmp_path / "deployment_publication_operator_input_request_validation.json"
    request_path.write_text(json.dumps(_blocked_request()), encoding="utf-8")
    validation = validate_deployment_publication_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_deployment_publication_operator_input_request_validation(
        validation,
        output_path,
    )
    exit_code = main(
        [
            "--request",
            str(request_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-blocked",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["publication_allowed"] is False
    assert stdout_payload["next_action"] == "bind DNS target"
    assert captured.err == ""


def _blocked_request() -> dict[str, object]:
    return {
        "request_id": "deployment-publication-operator-input-request-0123456789abcdef",
        "packet_id": "deployment-publication-evidence-packet-0123456789abcdef",
        "gateway_host": "api.mullusi.com",
        "gateway_url": "https://api.mullusi.com",
        "ready": False,
        "publication_allowed": False,
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "required_inputs": [
            {
                "input_id": "deployment-publication-input-0123456789ab",
                "blocker": "deployment_dns_not_verified",
                "input_kind": "dns_origin_target",
                "required_name": "MULLU_GATEWAY_DNS_TARGET",
                "current_state": "missing",
                "evidence_source": "gateway_dns_target_binding_receipt",
                "next_action": "bind DNS target",
            }
        ],
        "blocked_actions": [
            "dns_publication",
            "gateway_publication_workflow_dispatch",
            "deployment_status_publication_claim",
        ],
        "source_artifacts": {
            "deployment_publication_evidence_packet": "D:/packet/deployment_publication_evidence_packet.json"
        },
        "no_secret_values_serialized": True,
        "next_action": "bind DNS target",
    }


def _ready_request() -> dict[str, object]:
    return {
        "request_id": "deployment-publication-operator-input-request-fedcba9876543210",
        "packet_id": "deployment-publication-evidence-packet-fedcba9876543210",
        "gateway_host": "api.mullusi.com",
        "gateway_url": "https://api.mullusi.com",
        "ready": True,
        "publication_allowed": True,
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "required_inputs": [],
        "blocked_actions": [],
        "source_artifacts": {
            "deployment_publication_evidence_packet": "D:/packet/deployment_publication_evidence_packet.json"
        },
        "no_secret_values_serialized": True,
        "next_action": "run deployment witness preflight before approved publication dispatch",
    }
