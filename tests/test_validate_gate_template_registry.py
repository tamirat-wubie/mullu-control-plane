"""Tests for gate template registry validation.

Purpose: prove reusable gate templates cover capability passport gates and
cannot drift into execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_gate_template_registry, capability passports,
and gate template registry fixtures.
Invariants: every capability passport required gate resolves to one canonical
template; approval, receipt, rollback, connector, workspace, and external-send
gates keep explicit block conditions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.gate_template_registry import (
    GateTemplateRegistryError,
    build_gate_template_registry,
    gate_template_ids,
)
from scripts.validate_gate_template_registry import (
    DEFAULT_OUTPUT,
    DEFAULT_REGISTRY,
    REQUIRED_TEMPLATE_IDS,
    validate_gate_template_registry,
    write_gate_template_registry_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    registry_path = tmp_path / "gate_template_registry.json"
    registry_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registry_path


def _templates(payload: dict[str, object]) -> list[dict[str, object]]:
    templates = payload["templates"]
    assert isinstance(templates, list)
    return templates


def _template_by_id(payload: dict[str, object], gate_id: str) -> dict[str, object]:
    for template in _templates(payload):
        if template.get("gate_id") == gate_id:
            return template
    raise AssertionError(f"missing template {gate_id}")


def test_gate_template_registry_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_gate_template_registry()
    output_path = tmp_path / "gate-template-registry-validation.json"

    written_path = write_gate_template_registry_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.template_count == validation.passport_gate_count
    assert REQUIRED_TEMPLATE_IDS <= set(gate_template_ids())
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "gate_template_registry_validation.json"


def test_gate_template_registry_declares_expected_gate_semantics() -> None:
    registry = build_gate_template_registry()
    approval = _template_by_id(registry, "gate.approval.required")
    receipt = _template_by_id(registry, "gate.receipt.append")
    external_send = _template_by_id(registry, "gate.external.send")

    assert approval["operator_status_when_missing"] == "Needs approval"
    assert "execute_without_approval" in approval["blocks_when_missing"]
    assert "approval_decision_receipt" in approval["required_receipts"]
    assert "terminal_closure_certificate" in receipt["required_receipts"]
    assert "terminal_closure_overclaim" in receipt["blocks_when_missing"]
    assert "provider_receipt" in external_send["required_receipts"]
    assert "recipient_unapproved" in external_send["blocks_when_missing"]


def test_gate_template_registry_rejects_missing_passport_gate_template(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["templates"] = [
        template for template in _templates(payload) if template.get("gate_id") != "gate.connector.lease"
    ]
    payload["template_count"] = int(payload["template_count"]) - 1
    categories = payload["categories"]
    assert isinstance(categories, dict)
    categories["isolation"] = int(categories["isolation"]) - 1

    validation = validate_gate_template_registry(registry_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing required template ids ['gate.connector.lease']" in serialized_errors
    assert "capability passport gates missing templates ['gate.connector.lease']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_gate_template_registry_rejects_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["registry_is_not_execution_authority"] = False
    approval = _template_by_id(payload, "gate.approval.required")
    approval["operator_status_when_missing"] = "Ready"
    approval["blocks_when_missing"] = ["self_approval"]

    validation = validate_gate_template_registry(registry_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "registry_is_not_execution_authority must be true" in serialized_errors
    assert "gate.approval.required must map missing state to Needs approval" in serialized_errors
    assert "gate.approval.required must block execute_without_approval" in serialized_errors


def test_gate_template_registry_rejects_unused_template(tmp_path: Path) -> None:
    payload = _default_payload()
    extra = dict(_templates(payload)[0])
    extra["gate_id"] = "gate.unused.template"
    extra["display_name"] = "Unused template"
    payload["templates"].append(extra)  # type: ignore[index]
    payload["template_count"] = int(payload["template_count"]) + 1
    categories = payload["categories"]
    assert isinstance(categories, dict)
    categories[extra["category"]] = int(categories[extra["category"]]) + 1

    validation = validate_gate_template_registry(registry_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "templates not referenced by capability passports ['gate.unused.template']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_gate_template_registry_rejects_duplicate_static_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    import mcoi_runtime.app.gate_template_registry as registry_module

    first = dict(registry_module.GATE_TEMPLATES[0])
    monkeypatch.setattr(registry_module, "GATE_TEMPLATES", (first, first))

    with pytest.raises(GateTemplateRegistryError, match="duplicate gate template id"):
        registry_module.build_gate_template_registry()
