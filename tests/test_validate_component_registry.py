"""Tests for the Mullu Component Harness registry validator.

Purpose: prove the first component registry remains canonical, dependency
consistent, proof-aware, receipt-aware, and non-executing before router binding
or live authority is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_registry.
Invariants:
  - Default foundation registry validates.
  - Duplicate identity, alias, dependency, authority, proof, receipt, and
    guardrail drift fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_component_registry import (  # noqa: E402
    DEFAULT_EXAMPLES,
    REQUIRED_COMPONENT_BUNDLE_IDS,
    REQUIRED_FOUNDATION_COMPONENT_IDS,
    main,
    validate_component_registry,
    write_component_registry_validation,
)


def test_component_registry_accepts_default_foundation_example() -> None:
    validation = validate_component_registry()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.registry_count == 1
    assert validation.component_count >= len(REQUIRED_FOUNDATION_COMPONENT_IDS)
    assert validation.bundle_count >= len(REQUIRED_COMPONENT_BUNDLE_IDS)
    assert validation.schema_path == "schemas/component_registry.schema.json"
    assert validation.example_paths == ("examples/component_registry.foundation.json",)


def test_component_registry_rejects_duplicate_component_id(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"].append(deepcopy(payload["components"][0]))
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "duplicate component ids" in serialized_errors
    assert "governance_core" in serialized_errors


def test_component_registry_rejects_alias_collision(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"][1]["aliases"].append("governance")
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "alias governance claimed" in serialized_errors
    assert "agentic_service_harness" in serialized_errors


def test_component_registry_rejects_missing_dependency(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"][2]["dependencies"] = ["missing_component"]
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "dependency missing_component is not registered" in serialized_errors
    assert "component snet" in serialized_errors


def test_component_registry_rejects_live_authority_flag(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"][2]["authority"]["can_execute"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority.can_execute must remain false" in serialized_errors
    assert "expected const False" in serialized_errors


def test_component_registry_rejects_live_action_state_words(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"][0]["lifecycle_state"] = "approved_live_action"
    payload["components"][1]["wiring_state"] = "live_action_enabled"
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "lifecycle_state approved_live_action is blocked in foundation" in serialized_errors
    assert "wiring_state live_action_enabled is blocked in foundation" in serialized_errors


def test_component_registry_rejects_proof_bound_without_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"][2]["proof_surface"]["evidence_refs"] = []
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "proof_bound surface must include evidence_refs" in serialized_errors
    assert "component snet" in serialized_errors


def test_component_registry_rejects_proof_surface_evidence_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["components"][2]["proof_surface"]["evidence_refs"] = [
        "docs/40_proof_coverage_matrix.md#unlisted_surface"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "proof_surface evidence_refs missing from component evidence_refs" in serialized_errors
    assert "unlisted_surface" in serialized_errors


def test_component_registry_rejects_declared_proof_without_surface_id(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["components"][-1]["proof_surface"] = {
        "evidence_refs": [],
        "status": "declared",
        "surface_id": None,
    }
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "declared proof_surface must name surface_id" in serialized_errors
    assert "component nested_mind_bridge" in serialized_errors


def test_component_registry_rejects_receipt_required_without_proof_binding(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["components"][-1]["receipt_required"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt_required components must be proof_bound" in serialized_errors
    assert "component nested_mind_bridge" in serialized_errors


def test_component_registry_rejects_foundation_guardrail_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["registry_guardrails"]["live_execution_enabled"] = True
    payload["registry_guardrails"]["public_customer_ready_claimed"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "registry_guardrails.live_execution_enabled must be False" in serialized_errors
    assert "registry_guardrails.public_customer_ready_claimed must be False" in serialized_errors


def test_component_registry_rejects_bundle_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["component_bundles"][0]["components"].append("missing_component")
    payload["component_bundles"][0]["blocked_actions"].remove("terminal_closure")
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "bundle personal_assistant_v0 component missing_component is not registered" in serialized_errors
    assert "bundle personal_assistant_v0 must block terminal_closure" in serialized_errors


def test_component_registry_rejects_validator_declaration_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["validators"][0]["command"] = "python scripts/validate_component_registry.py --unchecked"
    payload["validators"][1]["required_for_closure"] = False
    example_path = _write_example(tmp_path, payload)

    validation = validate_component_registry(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "validator component_registry_validator command must be" in serialized_errors
    assert "validator component_registry_tests must be required_for_closure" in serialized_errors


def test_component_registry_cli_fails_closed_without_strict(
    tmp_path: Path,
    capsys,
) -> None:
    payload = _default_payload()
    payload["components"][0]["authority"]["can_execute"] = True
    example_path = _write_example(tmp_path, payload)
    output_path = tmp_path / "invalid_component_registry_validation.json"

    exit_code = main(["--example", str(example_path), "--output", str(output_path)])
    captured = capsys.readouterr()
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert "COMPONENT REGISTRY INVALID" in captured.out
    assert written_payload["ok"] is False


def test_component_registry_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "component_registry_validation.json"
    validation = validate_component_registry()

    written = write_component_registry_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["required_component_count"] == len(REQUIRED_FOUNDATION_COMPONENT_IDS)
    assert stdout_payload["bundle_count"] == len(REQUIRED_COMPONENT_BUNDLE_IDS)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_registry.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
