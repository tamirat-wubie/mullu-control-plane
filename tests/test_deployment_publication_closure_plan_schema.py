"""Tests for deployment publication closure plan schema validation.

Purpose: prove deployment closure plans are schema-backed and semantically
checked before aggregate promotion planning consumes them.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_deployment_publication_closure_plan_schema and
schemas/deployment_publication_closure_plan.schema.json.
Invariants:
  - Valid deployment closure plans pass schema and count validation.
  - Count drift fails closed.
  - Production publication and status mutation actions require proof gates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_deployment_publication_closure_plan_schema import (  # noqa: E402
    main,
    validate_deployment_publication_closure_plan_schema,
    write_deployment_publication_closure_plan_schema_validation,
)

SCHEMA_PATH = _ROOT / "schemas" / "deployment_publication_closure_plan.schema.json"


def test_deployment_closure_plan_schema_accepts_valid_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.plan_path == "deployment_publication_closure_plan.json"
    assert validation.schema_path == "schemas/deployment_publication_closure_plan.schema.json"
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 2
    assert validation.blocker_count == 2
    assert str(tmp_path) not in json.dumps(validation.as_dict(), sort_keys=True)


def test_deployment_closure_plan_schema_rejects_count_drift(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    payload = _valid_plan()
    payload["action_count"] = 99
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert validation.action_count == 2
    assert "action_count does not match actions length" in validation.errors


def test_deployment_closure_plan_schema_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    plan_path.write_text(
        '{"plan_id": "deployment-publication-closure-plan-x", "score": Infinity}',
        encoding="utf-8",
    )

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "deployment closure plan JSON parse failed" in validation.errors
    assert "Infinity" not in serialized_errors


def test_deployment_closure_plan_schema_rejects_missing_publication_proof(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    payload = _valid_plan()
    payload["actions"][0]["evidence_required"] = ["deployment_witness.json"]
    del payload["actions"][0]["approval_required"]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("approval_required" in error for error in validation.errors)
    assert any("gateway_publication_readiness.json" in error for error in validation.errors)
    assert any("operator_approval_ref" in error for error in validation.errors)


def test_deployment_closure_plan_schema_rejects_uncovered_blocker(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    payload = _valid_plan()
    payload["blockers"].append("deployment_authority_responsibility_debt_present")
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert validation.blocker_count == 3
    assert any("deployment_authority_responsibility_debt_present" in error for error in validation.errors)


def test_deployment_closure_plan_schema_accepts_runtime_input_actions(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    payload = _valid_plan()
    payload["blockers"] = [
        "deployment_witness_secret_missing",
        "deployment_dns_not_verified",
    ]
    payload["action_count"] = 2
    payload["actions"] = [
        {
            "action_id": "provision-deployment-witness-secret",
            "blocker": "deployment_witness_secret_missing",
            "action_type": "secret-binding",
            "command": (
                "Provision GitHub Actions secret MULLU_DEPLOYMENT_WITNESS_SECRET; "
                "do not print or serialize the secret value."
            ),
            "evidence_required": [
                "gh_secret_list_presence:MULLU_DEPLOYMENT_WITNESS_SECRET",
                "deployment_witness_preflight",
            ],
            "risk_level": "high",
            "approval_required": True,
        },
        {
            "action_id": "verify-gateway-dns",
            "blocker": "deployment_dns_not_verified",
            "action_type": "dns-verification",
            "command": (
                "python scripts/emit_gateway_dns_target_binding_receipt.py "
                "--gateway-host \"$MULLU_GATEWAY_HOST\" "
                "--gateway-url \"$MULLU_GATEWAY_URL\" "
                "--expected-environment \"$MULLU_EXPECTED_RUNTIME_ENV\" "
                "--record-type \"$MULLU_GATEWAY_DNS_RECORD_TYPE\" "
                "--target \"$MULLU_GATEWAY_DNS_TARGET\" "
                "--provider \"$MULLU_DNS_PROVIDER\" "
                "--output .change_assurance/gateway_dns_target_binding_receipt.json "
                "--json && "
                "python scripts/validate_gateway_dns_target_binding_receipt.py "
                "--receipt .change_assurance/gateway_dns_target_binding_receipt.json "
                "--output .change_assurance/gateway_dns_target_binding_receipt_validation.json "
                "--require-ready && "
                "python scripts/collect_gateway_dns_resolution_receipt.py "
                "--host \"$MULLU_GATEWAY_HOST\" "
                "--output .change_assurance/gateway_dns_resolution_receipt.json "
                "--json && "
                "python scripts/validate_gateway_dns_resolution_receipt.py "
                "--receipt .change_assurance/gateway_dns_resolution_receipt.json "
                "--output .change_assurance/gateway_dns_resolution_receipt_validation.json "
                "--require-resolved"
            ),
            "evidence_required": [
                "gateway_dns_target_binding_receipt",
                "gateway_dns_target_binding_validation",
                "dns_resolution_receipt",
                "dns_resolution_receipt_validation",
                "deployment_witness_preflight",
            ],
            "risk_level": "high",
            "approval_required": True,
        },
    ]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 2


def test_deployment_closure_plan_schema_rejects_secret_serialization_gap(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    payload = _valid_plan()
    payload["blockers"] = ["deployment_witness_secret_missing"]
    payload["action_count"] = 1
    payload["actions"] = [
        {
            "action_id": "provision-deployment-witness-secret",
            "blocker": "deployment_witness_secret_missing",
            "action_type": "secret-binding",
            "command": "Provision GitHub Actions secret MULLU_DEPLOYMENT_WITNESS_SECRET.",
            "evidence_required": ["deployment_witness_preflight"],
            "risk_level": "high",
            "approval_required": True,
        }
    ]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("secret presence evidence" in error for error in validation.errors)
    assert any("no-secret-serialization guard" in error for error in validation.errors)


def test_deployment_closure_plan_schema_accepts_upstream_gate_action(tmp_path: Path) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    payload = _valid_plan()
    payload["blockers"] = ["deployment_upstream_api_gate_not_ready"]
    payload["action_count"] = 1
    payload["actions"] = [
        {
            "action_id": "close-upstream-api-readiness-gate",
            "blocker": "deployment_upstream_api_gate_not_ready",
            "action_type": "upstream-gate-closure",
            "command": (
                "python scripts/emit_deployment_upstream_blocker_receipt.py "
                "--target-gateway-url \"$MULLU_GATEWAY_URL\" "
                "--output .change_assurance/deployment_upstream_blocker_receipt.json && "
                "python scripts/validate_deployment_upstream_blocker_receipt.py "
                "--receipt .change_assurance/deployment_upstream_blocker_receipt.json "
                "--output .change_assurance/deployment_upstream_blocker_receipt_validation.json "
                "--require-ready"
            ),
            "evidence_required": [
                "deployment_upstream_blocker_receipt",
                "deployment_upstream_blocker_validation",
                "upstream_recovery_completion_witness",
                "api_runtime_host_readiness",
                "dns_publication_authority",
            ],
            "risk_level": "high",
            "approval_required": True,
        }
    ]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 1


def test_deployment_closure_plan_schema_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    plan_path = tmp_path / "deployment_publication_closure_plan.json"
    output_path = tmp_path / "schema_validation.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")
    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_deployment_publication_closure_plan_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--plan",
            str(plan_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["action_count"] == 2


def _valid_plan() -> dict[str, object]:
    return {
        "plan_id": "deployment-publication-closure-plan-0123456789abcdef",
        "source_readiness_path": ".change_assurance/general_agent_promotion_readiness.json",
        "deployment_status_path": "DEPLOYMENT_STATUS.md",
        "source_ready": False,
        "action_count": 2,
        "blockers": [
            "deployment_witness_not_published",
            "production_health_not_declared",
        ],
        "actions": [
            {
                "action_id": "deployment-witness-publish-with-approval",
                "blocker": "deployment_witness_not_published",
                "action_type": "publish-witness",
                "command": (
                    "python scripts/publish_gateway_publication.py "
                    "--gateway-url \"$MULLU_GATEWAY_URL\" "
                    "--dispatch-witness --dispatch "
                    "--receipt-output .change_assurance/gateway_publication_receipt.json"
                ),
                "evidence_required": [
                    "gateway_publication_readiness.json",
                    "gateway_publication_receipt.json",
                    "deployment_witness.json",
                    "operator_approval_ref",
                ],
                "risk_level": "high",
                "approval_required": True,
            },
            {
                "action_id": "declare-public-production-health",
                "blocker": "production_health_not_declared",
                "action_type": "status-update",
                "command": (
                    "Update DEPLOYMENT_STATUS.md only after deployment_witness.json "
                    "has deployment_claim=published and public health equals <gateway_url>/health."
                ),
                "evidence_required": [
                    "deployment_witness.json",
                    "https_health_probe_receipt",
                    "deployment_publication_closure_validation",
                ],
                "risk_level": "high",
                "approval_required": True,
            },
        ],
    }
