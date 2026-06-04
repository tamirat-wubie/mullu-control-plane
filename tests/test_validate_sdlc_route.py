"""Purpose: verify governed SDLC route validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.route_sdlc and scripts.validate_sdlc_route.
Invariants:
  - SDLC route fixtures validate.
  - Route matching is deterministic and boundary-aware.
  - Route validation emits explicit receipts.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout

from scripts import route_sdlc
from scripts import validate_sdlc_route as validator


def test_ci_failure_routes_to_failing_pr_sequence() -> None:
    receipt = route_sdlc.route_request("CI failed on the SDLC Governance Gate for a PR")

    assert receipt.sequence_name == "failing_pr"
    assert receipt.fallback_used is False
    assert receipt.skills[:4] == (
        "sdlc-ci-failure-triage",
        "sdlc-change-impact-audit",
        "sdlc-test-contract-authoring",
        "sdlc-pr-readiness-closure",
    )
    assert "sdlc-governance-receipt-auditor" in receipt.skills


def test_release_prepare_does_not_trigger_short_pr_signal() -> None:
    receipt = route_sdlc.route_request("Prepare release deployment witness and rollback")

    assert receipt.sequence_name == "release_or_deployment"
    assert "sdlc-release-witness-closure" in receipt.skills
    assert "sdlc-rollback-recovery-plan" in receipt.skills
    assert "sdlc-pr-readiness-closure" not in receipt.skills
    assert receipt.fallback_used is False


def test_unknown_request_uses_router_fallback() -> None:
    receipt = route_sdlc.route_request("organize the next symbolic delivery step")

    assert receipt.sequence_name is None
    assert receipt.fallback_used is True
    assert receipt.skills == ("sdlc-skill-router",)
    assert receipt.routes == ()


def test_route_fixtures_validate_current_contract() -> None:
    report = validator.build_validation_report()
    errors = validator.validate_route_contract()

    assert errors == []
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["check_count"] == 4
    assert len(report["example_paths"]) == len(validator.REQUIRED_EXAMPLES)


def test_route_fixture_rejects_missing_expected_skill(tmp_path) -> None:
    payload = validator.load_json_object(validator.EXAMPLE_DIR / "ci_failure_route.json")
    invalid_payload = copy.deepcopy(payload)
    invalid_payload["expected_skills"] = ["sdlc-release-witness-closure"]
    fixture_path = tmp_path / "invalid_route.json"
    fixture_path.write_text(json.dumps(invalid_payload), encoding="utf-8")

    errors = validator.validate_route_fixture(fixture_path)

    assert any("route missing expected skills" in error for error in errors)
    assert "sdlc-release-witness-closure" in errors[0]
    assert invalid_payload["route_id"] == "sdlc_route_ci_failure_001"


def test_cli_json_route_and_validation_receipt() -> None:
    route_stdout = io.StringIO()
    validation_stdout = io.StringIO()

    with redirect_stdout(route_stdout):
        route_exit = validator.main(["--route", "CI failed on the SDLC Governance Gate for a PR"])
    with redirect_stdout(validation_stdout):
        validation_exit = validator.main(["--json"])

    route_payload = json.loads(route_stdout.getvalue())
    validation_payload = json.loads(validation_stdout.getvalue())
    assert route_exit == 0
    assert validation_exit == 0
    assert route_payload["sequence_name"] == "failing_pr"
    assert validation_payload["receipt_id"] == "sdlc_route_validation_receipt"
    assert validation_payload["valid"] is True
