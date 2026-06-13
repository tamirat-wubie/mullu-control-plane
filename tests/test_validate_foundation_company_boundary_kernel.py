"""Tests for the Foundation Mode company-boundary kernel validator.

Purpose: prove the company-boundary kernel remains a Foundation Mode
readiness and claim-control artifact without promoting legal, financial,
customer, infrastructure, deployment, IP, patent, trademark, compliance,
continuity, or external-obligation claims.
Governance scope: Foundation Mode, repository claim control, IP provenance,
secret exclusion, payment blocking, customer-access blocking, deployment
blocking, and external-obligation prevention.
Dependencies: scripts.validate_foundation_company_boundary_kernel.
Invariants: all authorization flags remain false; all surfaces remain
AwaitingEvidence; live values and promotion phrases are rejected.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_company_boundary_kernel import (  # noqa: E402
    AUTHORIZATION_FLAGS,
    BOUNDARY_SURFACE_IDS,
    DEFAULT_DOC_PATH,
    DEFAULT_LEDGER_PATH,
    DEFAULT_PACKET_PATH,
    FOUNDATION_MODE_ALLOWED_CLASSES,
    IP_PROVENANCE_CLASSES,
    MANDATORY_GATE_REQUIREMENTS,
    REQUIRED_DOC_PHRASES,
    TRIGGER_CLASSES,
    load_json_object,
    load_text,
    load_yaml_object,
    validate_artifacts,
    validate_ledger,
    validate_packet,
)


def _write_packet(tmp_path: Path, payload: dict[str, object]) -> Path:
    packet_path = tmp_path / "candidate.json"
    packet_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return packet_path


def _write_doc(tmp_path: Path, text: str) -> Path:
    doc_path = tmp_path / "candidate.md"
    doc_path.write_text(text, encoding="utf-8")
    return doc_path


def test_default_artifacts_pass() -> None:
    findings = validate_artifacts()

    assert findings == []
    assert DEFAULT_DOC_PATH.exists()
    assert DEFAULT_PACKET_PATH.exists()
    assert DEFAULT_LEDGER_PATH.exists()


def test_witness_contract_keeps_claims_blocked() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")

    assert payload["status"] == "AwaitingEvidence"
    assert tuple(payload["authorization_flags"].keys()) == AUTHORIZATION_FLAGS
    assert all(payload["authorization_flags"][flag] is False for flag in AUTHORIZATION_FLAGS)
    assert tuple(surface["surface_id"] for surface in payload["boundary_surfaces"]) == BOUNDARY_SURFACE_IDS
    assert tuple(payload["ip_provenance_classes"]) == IP_PROVENANCE_CLASSES
    assert tuple(payload["trigger_classes"]) == TRIGGER_CLASSES
    assert tuple(payload["foundation_mode_allowed_classes"]) == FOUNDATION_MODE_ALLOWED_CLASSES
    assert tuple(payload["mandatory_gate"]["requirements"]) == MANDATORY_GATE_REQUIREMENTS


def test_yaml_ledger_contract_keeps_surfaces_blocked() -> None:
    payload = load_yaml_object(DEFAULT_LEDGER_PATH, "company-boundary kernel ledger")

    assert payload["status"] == "AwaitingEvidence"
    assert payload["foundation_mode_required"] is True
    assert [item["flag_id"] for item in payload["authorization_flags"]] == list(AUTHORIZATION_FLAGS)
    assert all(item["allowed"] is False for item in payload["authorization_flags"])
    assert [item["surface_id"] for item in payload["promotion_surfaces"]] == list(BOUNDARY_SURFACE_IDS)
    assert [item["class_id"] for item in payload["ip_provenance_classes"]] == list(IP_PROVENANCE_CLASSES)
    assert [item["trigger_id"] for item in payload["trigger_classes"]] == list(TRIGGER_CLASSES)
    assert all(item["requires_gate"] is True for item in payload["trigger_classes"])
    assert payload["mandatory_gate"][0]["mode"] == "mandatory_preflight_gate"


def test_false_flag_drift_is_reported() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate["authorization_flags"]["company_formation_authorized"] = True
    candidate["authorization_flags"]["payment_activation_authorized"] = True
    candidate["authorization_flags"]["deployment_authorized"] = True

    findings = validate_packet(candidate)

    assert any("company_formation_authorized must remain false" in finding.message for finding in findings)
    assert any("payment_activation_authorized must remain false" in finding.message for finding in findings)
    assert any(finding.rule_id == "company_boundary_flag_value" for finding in findings)


def test_surface_state_and_type_drift_are_reported() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate["boundary_surfaces"][0]["state"] = "SolvedVerified"
    candidate["boundary_surfaces"][0]["surface_type"] = "active_entity_status"
    candidate["boundary_surfaces"] = candidate["boundary_surfaces"][:-1]

    findings = validate_packet(candidate)

    assert any("boundary surface inventory drifted" in finding.message for finding in findings)
    assert any("must remain AwaitingEvidence" in finding.message for finding in findings)
    assert any("surface type drifted" in finding.message for finding in findings)


def test_forbidden_live_values_are_reported() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate["boundary_surfaces"][2]["public_safe_note"] = (
        "Live control value at https://example.test with company_id=private and hash "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    findings = validate_packet(candidate)

    assert any("forbidden value pattern: url" in finding.message for finding in findings)
    assert any("forbidden value pattern: assignment_shape" in finding.message for finding in findings)
    assert any("forbidden value pattern: hash_like_value" in finding.message for finding in findings)


def test_promotion_phrase_is_reported() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate["boundary_surfaces"][5]["public_safe_note"] = "Customer access is ready."

    findings = validate_packet(candidate)

    assert any("forbidden promotion pattern: customer_access_open" in finding.message for finding in findings)
    assert any(finding.rule_id == "company_boundary_forbidden_promotion" for finding in findings)
    assert len(findings) >= 1


def test_yaml_ledger_promotion_drift_is_reported() -> None:
    payload = load_yaml_object(DEFAULT_LEDGER_PATH, "company-boundary kernel ledger")
    candidate = deepcopy(payload)
    candidate["authorization_flags"][0]["allowed"] = True
    candidate["promotion_surfaces"][0]["state"] = "SolvedVerified"
    candidate["non_authorization_rule"] = "Company is formed."

    findings = validate_ledger(candidate)

    assert any(finding.rule_id == "company_boundary_ledger_flags_state" for finding in findings)
    assert any(finding.rule_id == "company_boundary_ledger_surfaces_state" for finding in findings)
    assert any(finding.rule_id == "company_boundary_ledger_non_authorization" for finding in findings)
    assert any(finding.rule_id == "company_boundary_forbidden_promotion" for finding in findings)


def test_mandatory_gate_trigger_drift_is_reported() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate["mandatory_gate"]["mode"] = "optional_preflight"
    candidate["mandatory_gate"]["requirements"] = candidate["mandatory_gate"]["requirements"][:-1]
    candidate["trigger_classes"] = candidate["trigger_classes"][:-1]

    findings = validate_packet(candidate)

    assert any(finding.rule_id == "company_boundary_mandatory_gate_mode" for finding in findings)
    assert any(finding.rule_id == "company_boundary_mandatory_gate_requirements" for finding in findings)
    assert any(finding.rule_id == "company_boundary_trigger_classes" for finding in findings)


def test_foundation_work_scope_drift_is_reported() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate["foundation_mode_allowed_classes"] = candidate["foundation_mode_allowed_classes"][:-1]

    findings = validate_packet(candidate)

    assert any(finding.rule_id == "company_boundary_foundation_mode_allowed_classes" for finding in findings)
    assert all(finding.rule_id != "company_boundary_forbidden_promotion" for finding in findings)
    assert len(findings) >= 1


def test_yaml_mandatory_gate_and_allowed_scope_drift_is_reported() -> None:
    payload = load_yaml_object(DEFAULT_LEDGER_PATH, "company-boundary kernel ledger")
    candidate = deepcopy(payload)
    candidate["mandatory_gate"][0]["state"] = "SolvedVerified"
    candidate["trigger_classes"][0]["requires_gate"] = False
    candidate["foundation_mode_allowed_classes"][0]["allowed_without_promotion"] = False

    findings = validate_ledger(candidate)

    assert any(finding.rule_id == "company_boundary_ledger_mandatory_gate_state" for finding in findings)
    assert any(finding.rule_id == "company_boundary_ledger_trigger_classes_state" for finding in findings)
    assert any(finding.rule_id == "company_boundary_ledger_foundation_mode_allowed_classes_state" for finding in findings)


def test_doc_required_phrase_drift_is_reported(tmp_path: Path) -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "company-boundary kernel doc")
    candidate_text = doc_text.replace(REQUIRED_DOC_PHRASES[0], "Company Boundary Draft")
    doc_path = _write_doc(tmp_path, candidate_text)

    findings = validate_artifacts(doc_path=doc_path)

    assert any("doc missing required phrase" in finding.message for finding in findings)
    assert any(finding.rule_id == "company_boundary_doc_required_phrase" for finding in findings)
    assert "Mullu Control Plane Company Boundary Kernel" in doc_text


def test_missing_packet_root_and_next_action_drift_are_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "company-boundary kernel witness")
    candidate = deepcopy(payload)
    candidate.pop("blocked_claims")
    candidate["next_action"] = "promote now"
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any(finding.rule_id == "company_boundary_root_keys" for finding in findings)
    assert any(finding.rule_id == "company_boundary_blocked_claims" for finding in findings)
    assert any(finding.rule_id == "company_boundary_next_action" for finding in findings)
