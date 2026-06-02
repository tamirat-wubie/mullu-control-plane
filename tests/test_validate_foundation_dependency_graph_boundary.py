"""Tests for the Foundation Mode dependency-graph boundary validator.

Purpose: prove dependency-graph preparation stays local and does not authorize
graph completeness, dependency contract readiness, import readiness, package
install, version-lock readiness, service dependency binding, provider binding,
vulnerability scan pass, runtime dependency readiness, owner approval, test
pass, refactor approval, implementation approval, external publication, or
deployment.
Governance scope: Foundation Mode, dependency-graph surface inventory,
private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_dependency_graph_boundary.
Invariants: dependency-graph surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_dependency_graph_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_dependency_graph_boundary,
    validate_packet,
)


def test_foundation_dependency_graph_boundary_artifacts_pass() -> None:
    assert validate_foundation_dependency_graph_boundary() == []


def test_dependency_graph_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["dependency_graph_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["dependency_graph_complete_claimed"] is False
    assert payload["dependency_contract_ready_claimed"] is False
    assert payload["package_install_allowed"] is False
    assert payload["external_provider_bound"] is False
    assert payload["vulnerability_scan_pass_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_dependency_graph_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")
    candidate = deepcopy(payload)
    candidate["dependency_graph_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "dependency_graph_root_value_invalid" for finding in findings)


def test_witness_rejects_package_provider_and_runtime_readiness() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")
    candidate = deepcopy(payload)
    candidate["package_install_allowed"] = True
    candidate["external_provider_bound"] = True
    candidate["runtime_dependency_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "dependency_graph_root_value_invalid" for finding in findings)


def test_witness_rejects_scan_test_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")
    candidate = deepcopy(payload)
    candidate["vulnerability_scan_pass_claimed"] = True
    candidate["test_pass_claimed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "dependency_graph_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")
    candidate = deepcopy(payload)
    candidate["dependency_graph_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "dependency_graph_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "dependency_graph_surface_state_invalid" for finding in findings)


def test_witness_rejects_package_secret_scan_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")
    candidate = deepcopy(payload)
    candidate["dependency_graph_surfaces"][0]["public_safe_note"] = (
        "package_name=private secret=value vulnerability_scan_pass=true test_pass=true"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "dependency_graph_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_dependency_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "dependency-graph witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "dependency graph is complete and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "dependency_graph_forbidden_promotion_phrase" for finding in findings)
