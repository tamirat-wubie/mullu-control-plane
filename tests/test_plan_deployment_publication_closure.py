"""Tests for deployment publication closure planning.

Purpose: prove deployment promotion blockers become explicit publication actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_deployment_publication_closure.
Invariants:
  - Planning does not mutate deployment status.
  - Publication and health actions require approval.
  - Unknown deployment blockers remain manual-review items.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_deployment_publication_closure import (  # noqa: E402
    main,
    plan_deployment_publication_closure,
    write_deployment_publication_closure_plan,
)


def test_deployment_closure_plan_maps_publication_blockers(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    deployment_status_path = tmp_path / "DEPLOYMENT_STATUS.md"
    readiness_path.write_text(json.dumps(_blocked_readiness()), encoding="utf-8")
    deployment_status_path.write_text("**Deployment witness state:** `not-published`\n", encoding="utf-8")

    plan = plan_deployment_publication_closure(
        readiness_path,
        deployment_status_path,
        **_missing_receipt_paths(tmp_path),
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.source_ready is False
    assert plan.source_readiness_path == "general_agent_promotion_readiness.json"
    assert plan.deployment_status_path == "DEPLOYMENT_STATUS.md"
    assert plan.plan_id.startswith("deployment-publication-closure-plan-")
    assert plan.plan_id != "deployment-publication-closure-plan-02"
    assert plan.action_count == 3
    assert str(tmp_path) not in json.dumps(plan.as_dict(), sort_keys=True)
    assert plan.blockers == (
        "deployment_witness_not_published",
        "production_health_not_declared",
        "deployment_dns_not_verified",
    )
    assert actions_by_blocker["deployment_witness_not_published"].approval_required is True
    assert actions_by_blocker["deployment_witness_not_published"].risk_level == "high"
    assert "publish_gateway_publication.py" in actions_by_blocker["deployment_witness_not_published"].command
    assert "deployment_witness.json" in actions_by_blocker["production_health_not_declared"].evidence_required
    assert "DEPLOYMENT_STATUS.md" in actions_by_blocker["production_health_not_declared"].command


def test_deployment_closure_plan_preserves_unknown_deployment_blocker(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    readiness_path.write_text(
        json.dumps({"ready": False, "blockers": ["deployment_custom_unknown"]}),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(
        readiness_path,
        **_missing_receipt_paths(tmp_path),
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.action_count == 2
    assert actions_by_blocker["deployment_custom_unknown"].action_type == "manual-review"
    assert actions_by_blocker["deployment_custom_unknown"].approval_required is True
    assert actions_by_blocker["deployment_dns_not_verified"].action_type == "dns-verification"


def test_deployment_closure_plan_maps_gateway_readiness_steps(tmp_path: Path) -> None:
    readiness_path = tmp_path / "gateway_publication_readiness.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready": False,
                "steps": [
                    {
                        "name": "deployment witness secret",
                        "passed": False,
                        "detail": "missing=MULLU_DEPLOYMENT_WITNESS_SECRET",
                    },
                    {
                        "name": "dns resolution",
                        "passed": False,
                        "detail": "failed:resolution_error",
                    },
                    {
                        "name": "runtime witness secret",
                        "passed": True,
                        "detail": "present",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(
        readiness_path,
        **_missing_receipt_paths(tmp_path),
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.action_count == 2
    assert plan.blockers == (
        "deployment_witness_secret_missing",
        "deployment_dns_not_verified",
    )
    assert actions_by_blocker["deployment_witness_secret_missing"].action_type == "secret-binding"
    assert actions_by_blocker["deployment_witness_secret_missing"].approval_required is True
    assert "do not print or serialize" in actions_by_blocker["deployment_witness_secret_missing"].command
    assert actions_by_blocker["deployment_dns_not_verified"].action_type == "dns-verification"
    assert "MULLU_GATEWAY_DNS_TARGET" in actions_by_blocker["deployment_dns_not_verified"].command
    assert "MULLU_GATEWAY_DNS_RECORD_TYPE" in actions_by_blocker["deployment_dns_not_verified"].command
    assert "MULLU_DNS_PROVIDER" in actions_by_blocker["deployment_dns_not_verified"].command
    assert "A, AAAA, or CNAME" in actions_by_blocker["deployment_dns_not_verified"].command
    assert "gateway_dns_target_binding_receipt" in actions_by_blocker[
        "deployment_dns_not_verified"
    ].evidence_required
    assert "gateway_dns_target_binding_validation" in actions_by_blocker[
        "deployment_dns_not_verified"
    ].evidence_required
    assert "deployment_witness_preflight" in actions_by_blocker["deployment_dns_not_verified"].evidence_required
    assert "dns_resolution_receipt_validation" in actions_by_blocker["deployment_dns_not_verified"].evidence_required
    assert "emit_gateway_dns_target_binding_receipt.py" in actions_by_blocker[
        "deployment_dns_not_verified"
    ].command
    assert "validate_gateway_dns_target_binding_receipt.py" in actions_by_blocker[
        "deployment_dns_not_verified"
    ].command
    assert "collect_gateway_dns_resolution_receipt.py" in actions_by_blocker["deployment_dns_not_verified"].command
    assert "validate_gateway_dns_resolution_receipt.py" in actions_by_blocker["deployment_dns_not_verified"].command
    assert "--require-resolved" in actions_by_blocker["deployment_dns_not_verified"].command
    assert ".change_assurance/gateway_dns_resolution_receipt.json" in actions_by_blocker["deployment_dns_not_verified"].command
    assert ".change_assurance/gateway_dns_resolution_receipt_validation.json" in actions_by_blocker["deployment_dns_not_verified"].command


def test_deployment_closure_plan_maps_responsibility_debt_blockers(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready": False,
                "blockers": [
                    "deployment_runtime_responsibility_debt_present",
                    "deployment_authority_responsibility_debt_present",
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(
        readiness_path,
        **_missing_receipt_paths(tmp_path),
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.action_count == 3
    assert actions_by_blocker[
        "deployment_runtime_responsibility_debt_present"
    ].action_type == "responsibility-debt-closure"
    assert actions_by_blocker[
        "deployment_authority_responsibility_debt_present"
    ].approval_required is True
    assert "/authority/responsibility" in actions_by_blocker[
        "deployment_authority_responsibility_debt_present"
    ].command
    assert actions_by_blocker["deployment_dns_not_verified"].approval_required is True


def test_deployment_closure_plan_maps_kubeconfig_secret_step(tmp_path: Path) -> None:
    readiness_path = tmp_path / "gateway_publication_readiness.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready": False,
                "steps": [
                    {
                        "name": "kubeconfig secret",
                        "passed": False,
                        "detail": "missing=MULLU_KUBECONFIG_B64",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(
        readiness_path,
        **_missing_receipt_paths(tmp_path),
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}
    action = actions_by_blocker["deployment_kubeconfig_secret_missing"]

    assert plan.action_count == 2
    assert plan.blockers == (
        "deployment_kubeconfig_secret_missing",
        "deployment_dns_not_verified",
    )
    assert action.action_id == "provision-gateway-publication-kubeconfig"
    assert action.action_type == "secret-binding"
    assert action.approval_required is True
    assert action.risk_level == "high"
    assert "MULLU_KUBECONFIG_B64" in action.command
    assert "do not print or serialize" in action.command
    assert "gh_secret_list_presence:MULLU_KUBECONFIG_B64" in action.evidence_required


def test_deployment_closure_plan_maps_upstream_blocker_receipt(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    upstream_receipt_path = tmp_path / "deployment_upstream_blocker_receipt.json"
    readiness_path.write_text(json.dumps({"ready": False, "blockers": []}), encoding="utf-8")
    upstream_receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "deployment-upstream-blocker-0123456789abcdef",
                "target_gateway_host": "api.mullusi.com",
                "target_gateway_url": "https://api.mullusi.com",
                "upstream_repository": "mullusi/mullusi-site",
                "upstream_gate": "api-production-readiness-gate",
                "upstream_state": "AwaitingEvidence",
                "api_provisioning_allowed": False,
                "dns_publication_allowed": False,
                "ready": False,
                "checked_at_utc": "2026-05-24T12:00:00Z",
                "blockers": ["private_recovery_inventory_missing"],
                "evidence_refs": ["issue-330-comment-4530008851"],
                "next_actions": ["complete private recovery inventory outside Git"],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(
        readiness_path,
        upstream_blocker_receipt_path=upstream_receipt_path,
        dns_target_binding_receipt_path=tmp_path / "missing_dns_target_binding_receipt.json",
        dns_resolution_receipt_path=tmp_path / "missing_dns_resolution_receipt.json",
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}
    action = actions_by_blocker["deployment_upstream_api_gate_not_ready"]

    assert plan.action_count == 2
    assert plan.blockers == (
        "deployment_upstream_api_gate_not_ready",
        "deployment_dns_not_verified",
    )
    assert action.action_id == "close-upstream-api-readiness-gate"
    assert action.action_type == "upstream-gate-closure"
    assert action.approval_required is True
    assert "emit_deployment_upstream_blocker_receipt.py" in action.command
    assert "validate_deployment_upstream_blocker_receipt.py" in action.command
    assert "deployment_upstream_blocker_receipt" in action.evidence_required
    assert "dns_publication_authority" in action.evidence_required


def test_deployment_closure_plan_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    output_path = tmp_path / "deployment_publication_closure_plan.json"
    readiness_path.write_text(json.dumps(_blocked_readiness()), encoding="utf-8")
    missing_upstream_receipt_path = tmp_path / "missing_upstream_receipt.json"
    plan = plan_deployment_publication_closure(
        readiness_path,
        **_missing_receipt_paths(tmp_path),
    )

    written = write_deployment_publication_closure_plan(plan, output_path)
    exit_code = main(
        [
            "--readiness",
            str(readiness_path),
            "--upstream-blocker-receipt",
            str(missing_upstream_receipt_path),
            "--dns-target-binding-receipt",
            str(tmp_path / "missing_dns_target_binding_receipt.json"),
            "--dns-resolution-receipt",
            str(tmp_path / "missing_dns_resolution_receipt.json"),
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
    assert payload["action_count"] == 3
    assert stdout_payload["plan_id"] == payload["plan_id"]
    assert "production_health_not_declared" in payload["blockers"]


def test_deployment_closure_plan_maps_not_ready_dns_receipts(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    dns_target_receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    dns_resolution_receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    readiness_path.write_text(json.dumps({"ready": False, "blockers": []}), encoding="utf-8")
    dns_target_receipt_path.write_text(json.dumps(_dns_target_receipt(ready=False)), encoding="utf-8")
    dns_resolution_receipt_path.write_text(
        json.dumps(_dns_resolution_receipt(resolved=False)),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(
        readiness_path,
        upstream_blocker_receipt_path=tmp_path / "missing_upstream_receipt.json",
        dns_target_binding_receipt_path=dns_target_receipt_path,
        dns_resolution_receipt_path=dns_resolution_receipt_path,
    )
    action = plan.actions[0]

    assert plan.action_count == 1
    assert plan.blockers == ("deployment_dns_not_verified",)
    assert action.action_id == "verify-gateway-dns"
    assert action.action_type == "dns-verification"
    assert action.approval_required is True
    assert "gateway_dns_target_binding_receipt" in action.evidence_required
    assert "dns_resolution_receipt_validation" in action.evidence_required


def test_deployment_closure_plan_skips_ready_dns_receipts(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    dns_target_receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    dns_resolution_receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    readiness_path.write_text(json.dumps({"ready": False, "blockers": []}), encoding="utf-8")
    dns_target_receipt_path.write_text(json.dumps(_dns_target_receipt(ready=True)), encoding="utf-8")
    dns_resolution_receipt_path.write_text(json.dumps(_dns_resolution_receipt(resolved=True)), encoding="utf-8")

    plan = plan_deployment_publication_closure(
        readiness_path,
        upstream_blocker_receipt_path=tmp_path / "missing_upstream_receipt.json",
        dns_target_binding_receipt_path=dns_target_receipt_path,
        dns_resolution_receipt_path=dns_resolution_receipt_path,
    )

    assert plan.action_count == 0
    assert plan.blockers == ()
    assert plan.source_ready is False
    assert str(tmp_path) not in json.dumps(plan.as_dict(), sort_keys=True)


def test_deployment_closure_plan_rejects_nonfinite_readiness_json(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    readiness_path.write_text('{"ready": false, "score": Infinity}', encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        plan_deployment_publication_closure(readiness_path)

    assert "promotion readiness JSON parse failed" in str(excinfo.value)
    assert "Infinity" not in str(excinfo.value)
    assert readiness_path.exists()


def _blocked_readiness() -> dict[str, object]:
    return {
        "ready": False,
        "blockers": [
            "adapter_evidence_not_closed",
            "deployment_witness_not_published",
            "production_health_not_declared",
        ],
    }


def _missing_receipt_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "upstream_blocker_receipt_path": tmp_path / "missing_upstream_receipt.json",
        "dns_target_binding_receipt_path": tmp_path / "missing_dns_target_binding_receipt.json",
        "dns_resolution_receipt_path": tmp_path / "missing_dns_resolution_receipt.json",
    }


def _dns_target_receipt(*, ready: bool) -> dict[str, object]:
    return {
        "receipt_id": "gateway-dns-target-binding-0123456789abcdef",
        "gateway_host": "api.mullusi.com",
        "gateway_url": "https://api.mullusi.com",
        "expected_environment": "pilot",
        "record_type": "CNAME" if ready else "",
        "target": "gateway-origin.example.net" if ready else "",
        "target_kind": "hostname" if ready else "missing",
        "provider": "example-dns" if ready else "",
        "binding_state": "bound" if ready else "missing-target",
        "ready": ready,
        "checked_at_utc": "2026-06-01T00:00:00Z",
        "next_action": (
            "publish DNS record and rerun gateway DNS resolution receipt"
            if ready
            else "select gateway origin target before DNS publication"
        ),
    }


def _dns_resolution_receipt(*, resolved: bool) -> dict[str, object]:
    return {
        "receipt_id": "gateway-dns-resolution-0123456789abcdef",
        "host": "api.mullusi.com",
        "checked_at_utc": "2026-06-01T00:00:00Z",
        "resolved": resolved,
        "addresses": ["203.0.113.10"] if resolved else [],
        "error": None if resolved else "resolution_error",
        "next_action": (
            "rerun deployment witness preflight with endpoint probes enabled"
            if resolved
            else "publish a DNS A, AAAA, or CNAME record for the gateway host, then rerun this receipt"
        ),
    }
