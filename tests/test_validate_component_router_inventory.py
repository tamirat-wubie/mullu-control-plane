"""Tests for the Mullu Component Harness router inventory validator.

Purpose: prove selected component-owned route families remain bound to
registered components and proof surfaces without enabling execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_router_inventory.
Invariants:
  - Default foundation router inventory validates.
  - Bound routes are declared and proof-classified.
  - Prefix drift, stale routes, duplicate ownership, guardrail drift, and
    validator drift fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_component_router_inventory import (  # noqa: E402
    DEFAULT_INVENTORY,
    main,
    validate_component_router_inventory,
    write_component_router_inventory_validation,
)


def test_component_router_inventory_accepts_default_foundation_example() -> None:
    validation = validate_component_router_inventory()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.route_binding_count == 10
    assert validation.bound_route_count == 32
    assert validation.route_family_classification_count == 78
    assert validation.classified_route_count == validation.discovered_route_count
    assert validation.discovered_route_count >= validation.bound_route_count
    assert validation.unclassified_route_count == 0


def test_component_router_inventory_rejects_unregistered_component(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][0]["component_id"] = "missing_component"
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "route binding component missing_component is not registered" in serialized_errors
    assert "registered components missing route binding entries" in serialized_errors


def test_component_router_inventory_rejects_stale_expected_route(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][1]["expected_routes"] = ["/api/v1/harness/missing"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "expected route /api/v1/harness/missing is not declared" in serialized_errors
    assert "unrecorded routes under prefixes" in serialized_errors


def test_component_router_inventory_rejects_prefix_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][3]["route_prefixes"] = ["/api/v1/console"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "component inceptadive_shadow has unrecorded routes under prefixes" in serialized_errors
    assert "/api/v1/console/personal-assistant" in serialized_errors


def test_component_router_inventory_rejects_proof_surface_mismatch(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][4]["proof_surface_ids"] = ["operator_console_read_models"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "expected route /api/v1/assistant/finance-ops/plans maps to assistant_kernel_planning" in serialized_errors
    assert "expected route /api/v1/assistant/profiles maps to assistant_kernel_planning" in serialized_errors


def test_component_router_inventory_rejects_duplicate_route_ownership(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][5]["expected_routes"].append("/api/v1/assistant/profiles")
    payload["route_bindings"][5]["route_prefixes"].append("/api/v1/assistant/profiles")
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "route /api/v1/assistant/profiles is bound by both personal_assistant and teamops_shared_inbox" in serialized_errors
    assert "teamops_shared_inbox" in serialized_errors


def test_component_router_inventory_rejects_no_declared_route_with_routes(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][2]["expected_routes"] = ["/api/v1/snet/read-model"]
    payload["route_bindings"][2]["route_prefixes"] = ["/api/v1/snet"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "component snet no_declared_route binding must not list route_prefixes" in serialized_errors
    assert "component snet no_declared_route binding must not list expected_routes" in serialized_errors


def test_component_router_inventory_records_nested_mind_missing_evidence() -> None:
    payload = _default_payload()
    nested_mind_binding = next(
        binding
        for binding in payload["route_bindings"]
        if binding["component_id"] == "nested_mind_bridge"
    )

    assert nested_mind_binding["binding_state"] == "no_declared_route"
    assert nested_mind_binding["proof_surface_ids"] == []
    assert set(nested_mind_binding["missing_evidence"]) == {
        "proof_matrix_surface",
        "memory_topology_activation_witness",
    }
    assert "memory_topology_activation" in nested_mind_binding["blocked_actions"]


def test_component_router_inventory_rejects_unbound_empty_proof_without_missing_evidence(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    nested_mind_binding = next(
        binding
        for binding in payload["route_bindings"]
        if binding["component_id"] == "nested_mind_bridge"
    )
    del nested_mind_binding["missing_evidence"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "component nested_mind_bridge no_declared_route binding without proof_surface_ids" in serialized_errors
    assert "must list missing_evidence" in serialized_errors


def test_component_router_inventory_rejects_guardrail_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["live_execution_enabled"] = True
    payload["route_bindings"][0]["can_enable_live_action"] = True
    payload["route_bindings"][0]["blocked_actions"].remove("terminal_closure")
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_enabled must be False" in serialized_errors
    assert "binding cannot enable live action" in serialized_errors
    assert "binding must block terminal_closure" in serialized_errors


def test_component_router_inventory_rejects_validator_declaration_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["validators"][0]["command"] = "python scripts/validate_component_router_inventory.py --unchecked"
    payload["validators"][1]["required_for_closure"] = False
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "validator component_router_inventory_validator command must be" in serialized_errors
    assert "validator component_router_inventory_tests must be required_for_closure" in serialized_errors


def test_component_router_inventory_rejects_missing_route_family_classification(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    removed = payload["route_family_classifications"].pop()
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "declared route surfaces missing family classification" in serialized_errors
    assert removed["surface_id"] in serialized_errors


def test_component_router_inventory_rejects_route_family_count_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_family_classifications"][0]["declared_route_count"] += 1
    payload["route_family_classifications"][0]["sample_routes"] = ["/missing-route"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "declared_route_count must be" in serialized_errors
    assert "sample routes are not declared for this surface" in serialized_errors
    assert "/missing-route" in serialized_errors


def test_component_router_inventory_rejects_route_family_authority_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_family_classifications"][0]["classification_is_not_execution_authority"] = False
    payload["route_family_classifications"][0]["can_enable_live_action"] = True
    payload["route_family_classifications"][0]["blocked_actions"].remove("route_execution")
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "must not be execution authority" in serialized_errors
    assert "cannot enable live action" in serialized_errors
    assert "must block route_execution" in serialized_errors


def test_component_router_inventory_rejects_selected_family_binding_level_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    family = next(
        item
        for item in payload["route_family_classifications"]
        if item["surface_id"] == "component_harness_read_model"
    )
    family["binding_level"] = "platform_family_classified"
    family["component_ids"] = ["snet"]
    inventory_path = _write_inventory(tmp_path, payload)

    validation = validate_component_router_inventory(inventory_path=inventory_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "must use selected_component_bound" in serialized_errors
    assert "must include at least one bound component" in serialized_errors


def test_component_router_inventory_writer_and_cli_fail_closed(
    tmp_path: Path,
    capsys,
) -> None:
    payload = _default_payload()
    payload["route_bindings"][1]["expected_routes"] = ["/api/v1/harness/missing"]
    inventory_path = _write_inventory(tmp_path, payload)
    output_path = tmp_path / "component_router_inventory_validation.json"
    validation = validate_component_router_inventory(inventory_path=inventory_path)

    written = write_component_router_inventory_validation(validation, output_path)
    exit_code = main(["--inventory", str(inventory_path), "--output", str(output_path)])
    captured = capsys.readouterr()
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert exit_code == 2
    assert "COMPONENT ROUTER INVENTORY INVALID" in captured.out
    assert written_payload["ok"] is False


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8")))


def _write_inventory(tmp_path: Path, payload: dict[str, object]) -> Path:
    inventory_path = tmp_path / "component_router_inventory.foundation.json"
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")
    return inventory_path
