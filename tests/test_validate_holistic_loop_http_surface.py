"""Purpose: verify holistic loop HTTP surface validation.
Governance scope: route method boundary, payload blockers, and validator CLI.
Dependencies: FastAPI and scripts.validate_holistic_loop_http_surface.
Invariants:
  - Current default app validates.
  - Accidental mutation methods are rejected.
  - Missing-evidence blockers are mandatory.
"""

from __future__ import annotations

import copy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.loops import router
from scripts import validate_holistic_loop_http_surface as validator


def test_current_holistic_loop_http_surface_passes() -> None:
    errors = validator.validate_http_surface()

    assert errors == []
    assert validator.LOOP_READ_MODEL_PATH == "/api/v1/loops/read-model"
    assert "GET" not in validator.MUTATION_METHODS


def test_route_method_validation_rejects_mutation_route() -> None:
    app = FastAPI()
    app.include_router(router)

    @app.post(validator.LOOP_READ_MODEL_PATH)
    def forbidden_mutation() -> dict[str, bool]:
        return {"mutated": True}

    errors = validator.validate_route_methods(app)

    assert any("mutation methods" in error for error in errors)
    assert "POST" in errors[0]
    assert len(errors) == 1


def test_payload_validation_requires_missing_evidence_blockers() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["open_blockers"] = []

    errors = validator.validate_payload(invalid_payload)

    assert any("missing evidence lacks blocker" in error for error in errors)
    assert invalid_payload["loops"][0]["missing_evidence"]
    assert invalid_payload["loops"][0]["open_blockers"] == []


def test_payload_validation_requires_missing_authority_blockers() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["open_blockers"] = [
        blocker
        for blocker in invalid_payload["loops"][0]["open_blockers"]
        if not blocker.startswith("missing_authority:")
    ]

    errors = validator.validate_payload(invalid_payload)

    assert any("missing authority lacks blocker" in error for error in errors)
    assert invalid_payload["loops"][0]["missing_authority"]
    assert all(
        not blocker.startswith("missing_authority:")
        for blocker in invalid_payload["loops"][0]["open_blockers"]
    )


def test_payload_validation_requires_authority_bindings() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    removed_binding = invalid_payload["loops"][0]["authority_bindings"].pop()

    errors = validator.validate_payload(invalid_payload)

    assert any("missing authority binding" in error for error in errors)
    assert removed_binding["authority_ref"] in invalid_payload["loops"][0]["required_authority"]
    assert removed_binding not in invalid_payload["loops"][0]["authority_bindings"]


def test_payload_validation_requires_evidence_bindings() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    removed_binding = invalid_payload["loops"][0]["evidence_bindings"].pop()

    errors = validator.validate_payload(invalid_payload)

    assert any("missing evidence binding" in error for error in errors)
    assert removed_binding["evidence_ref"] in invalid_payload["loops"][0]["required_evidence"]
    assert removed_binding not in invalid_payload["loops"][0]["evidence_bindings"]


def test_payload_validation_requires_closure_condition_bindings() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    removed_binding = invalid_payload["loops"][0]["closure_condition_bindings"].pop()

    errors = validator.validate_payload(invalid_payload)

    assert any("missing closure condition binding" in error for error in errors)
    assert removed_binding["closure_ref"] in invalid_payload["loops"][0]["closure_conditions"]
    assert removed_binding not in invalid_payload["loops"][0]["closure_condition_bindings"]


def test_payload_validation_rejects_closure_condition_binding_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["closure_condition_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("closure condition binding 0 read_only must be true" in error for error in errors)
    assert any("closure condition binding 0 terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_payload_validation_rejects_binding_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["evidence_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("read_only must be true" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_payload_validation_rejects_authority_binding_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["authority_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("authority binding 0 read_only must be true" in error for error in errors)
    assert any("authority binding 0 terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_payload_validation_requires_risk_binding_to_match_risk_class() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["risk_binding"]["risk_ref"] = "different_risk"

    errors = validator.validate_payload(invalid_payload)

    assert any("risk_binding risk_ref must match risk_class" in error for error in errors)
    assert invalid_payload["loops"][0]["risk_binding"]["risk_ref"] == "different_risk"
    assert invalid_payload["loops"][0]["risk_class"] != "different_risk"


def test_payload_validation_rejects_risk_binding_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["risk_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("risk_binding read_only must be true" in error for error in errors)
    assert any("risk_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_payload_validation_requires_rollback_binding_to_match_policy() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["rollback_binding"]["rollback_ref"] = "different_policy"

    errors = validator.validate_payload(invalid_payload)

    assert any("rollback_binding rollback_ref must match rollback_policy" in error for error in errors)
    assert invalid_payload["loops"][0]["rollback_binding"]["rollback_ref"] == "different_policy"
    assert invalid_payload["loops"][0]["rollback_policy"] != "different_policy"


def test_payload_validation_rejects_rollback_binding_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["rollback_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("rollback_binding read_only must be true" in error for error in errors)
    assert any("rollback_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_payload_validation_requires_learning_binding_to_match_policy() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["learning_binding"]["learning_ref"] = "different_policy"

    errors = validator.validate_payload(invalid_payload)

    assert any("learning_binding learning_ref must match learning_policy" in error for error in errors)
    assert invalid_payload["loops"][0]["learning_binding"]["learning_ref"] == "different_policy"
    assert invalid_payload["loops"][0]["learning_policy"] != "different_policy"


def test_payload_validation_rejects_learning_binding_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["learning_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("learning_binding read_only must be true" in error for error in errors)
    assert any("learning_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_payload_validation_requires_mode_binding_to_match_projected_mode() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["mode_binding"]["projected_mode"] = "real"

    errors = validator.validate_payload(invalid_payload)

    assert any("mode_binding projected_mode must match mode" in error for error in errors)
    assert invalid_payload["loops"][0]["mode_binding"]["projected_mode"] == "real"
    assert invalid_payload["loops"][0]["mode"] != "real"


def test_payload_validation_requires_status_binding_to_match_projected_status() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["status_binding"]["projected_status"] = "verified"

    errors = validator.validate_payload(invalid_payload)

    assert any("status_binding projected_status must match status" in error for error in errors)
    assert invalid_payload["loops"][0]["status"] == "blocked"
    assert invalid_payload["loops"][0]["status_binding"]["projected_status"] == "verified"


def test_payload_validation_requires_status_binding_blockers_to_match() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["status_binding"]["blocker_refs"] = ["different_gap"]

    errors = validator.validate_payload(invalid_payload)

    assert any("status_binding blocker_refs must match open blockers" in error for error in errors)
    assert invalid_payload["loops"][0]["open_blockers"]
    assert invalid_payload["loops"][0]["status_binding"]["blocker_refs"] == ["different_gap"]


def test_payload_validation_rejects_status_binding_transition_or_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["status_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["status_transition"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("status_binding read_only must be true" in error for error in errors)
    assert any("status_binding status_transition must be false" in error for error in errors)
    assert any("status_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["status_transition"] is True


def test_payload_validation_requires_transition_binding_blockers_to_match() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["transition_bindings"][0]["blocker_refs"] = ["different_gap"]

    errors = validator.validate_payload(invalid_payload)

    assert any("transition binding 0 blocker_refs must match open blockers" in error for error in errors)
    assert invalid_payload["loops"][0]["open_blockers"]
    assert invalid_payload["loops"][0]["transition_bindings"][0]["blocker_refs"] == ["different_gap"]


def test_payload_validation_requires_transition_binding_declared_refs_and_rollback() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["transition_bindings"][0]
    invalid_binding["required_authority_refs"] = ["undeclared_authority"]
    invalid_binding["required_evidence_refs"] = ["undeclared_evidence"]
    invalid_binding["rollback_refs"] = ["different_policy"]

    errors = validator.validate_payload(invalid_payload)

    assert any("unexpected authority ref: undeclared_authority" in error for error in errors)
    assert any("unexpected evidence ref: undeclared_evidence" in error for error in errors)
    assert any("rollback_refs must include rollback_policy" in error for error in errors)


def test_payload_validation_rejects_transition_binding_execution_or_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["transition_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["executes_transition"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("transition binding 0 read_only must be true" in error for error in errors)
    assert any("transition binding 0 executes_transition must be false" in error for error in errors)
    assert any("transition binding 0 terminal_closure must be false" in error for error in errors)


def test_payload_validation_requires_receipt_lineage_to_match_receipts_and_blockers() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["receipt_lineage_bindings"][0]
    invalid_binding["receipt_hash"] = "sha256:9999999999999999999999999999999999999999999999999999999999999999"
    invalid_binding["blocker_refs"] = ["different_gap"]

    errors = validator.validate_payload(invalid_payload)

    assert any("receipt_hash must match step receipt" in error for error in errors)
    assert any("receipt lineage binding 0 blocker_refs must match open blockers" in error for error in errors)
    assert invalid_payload["loops"][0]["open_blockers"]


def test_payload_validation_requires_receipt_lineage_declared_refs() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["receipt_lineage_bindings"][0]
    invalid_binding["required_evidence_refs"] = ["undeclared_evidence"]
    invalid_binding["observed_evidence_refs"] = ["unexpected_observed_evidence"]
    invalid_binding["source_receipt_refs"] = ["different_receipt"]

    errors = validator.validate_payload(invalid_payload)

    assert any("unexpected evidence ref: undeclared_evidence" in error for error in errors)
    assert any("observed_evidence_refs must match evidence_refs" in error for error in errors)
    assert any("source_receipt_refs must include receipt_ref" in error for error in errors)


def test_payload_validation_rejects_receipt_lineage_emission_or_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["receipt_lineage_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["emits_receipt"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("receipt lineage binding 0 read_only must be true" in error for error in errors)
    assert any("receipt lineage binding 0 emits_receipt must be false" in error for error in errors)
    assert any("receipt lineage binding 0 terminal_closure must be false" in error for error in errors)


def test_payload_validation_requires_closure_evidence_pack_to_match_loop_inputs() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    pack = invalid_payload["loops"][0]["closure_evidence_pack"]
    pack["required_evidence_refs"] = ["undeclared_evidence"]
    pack["observed_evidence_refs"] = ["unexpected_evidence"]
    pack["missing_authority_refs"] = ["different_authority"]
    pack["blocker_refs"] = ["different_gap"]
    pack["receipt_lineage_refs"] = ["different_lineage"]
    pack["evidence_complete"] = True
    pack["authority_complete"] = True
    pack["closure_blocked"] = False

    errors = validator.validate_payload(invalid_payload)

    assert any("required_evidence_refs must match required_evidence" in error for error in errors)
    assert any("observed_evidence_refs must match evidence_refs" in error for error in errors)
    assert any("missing_authority_refs must match missing_authority" in error for error in errors)
    assert any("blocker_refs must match open_blockers" in error for error in errors)
    assert any("receipt_lineage_refs must match receipt lineage bindings" in error for error in errors)
    assert any("evidence_complete must match closure_report" in error for error in errors)
    assert any("authority_complete must match missing_authority" in error for error in errors)
    assert any("closure_blocked must match open_blockers" in error for error in errors)


def test_payload_validation_rejects_closure_evidence_pack_emission_or_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    pack = invalid_payload["loops"][0]["closure_evidence_pack"]
    pack["read_only"] = False
    pack["emits_receipt"] = True
    pack["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("closure_evidence_pack read_only must be true" in error for error in errors)
    assert any("closure_evidence_pack emits_receipt must be false" in error for error in errors)
    assert any("closure_evidence_pack terminal_closure must be false" in error for error in errors)


def test_payload_validation_requires_operator_closure_readiness_view_to_match_loop_inputs() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    view = invalid_payload["loops"][0]["operator_closure_readiness_view"]
    view["projected_status"] = "verified"
    view["blocker_refs"] = ["different_gap"]
    view["evidence_gap_refs"] = ["different_evidence"]
    view["authority_gap_refs"] = ["different_authority"]
    view["closure_condition_refs"] = ["different_closure"]
    view["rollback_ref"] = "different_rollback"
    view["rollback_available"] = False
    view["readiness_state"] = "ready_for_terminal_closure_review"
    view["next_proof_action"] = "run_loop_specific_terminal_closure_workflow"
    view["next_proof_refs"] = ["different_ref"]

    errors = validator.validate_payload(invalid_payload)

    assert any("projected_status must match status" in error for error in errors)
    assert any("blocker_refs must match open_blockers" in error for error in errors)
    assert any("evidence_gap_refs must match missing_evidence" in error for error in errors)
    assert any("authority_gap_refs must match missing_authority" in error for error in errors)
    assert any("closure_condition_refs must match closure_conditions" in error for error in errors)
    assert any("rollback_ref must match rollback_policy" in error for error in errors)
    assert any("rollback_available must match closure_report" in error for error in errors)
    assert any("readiness_state must match blockers" in error for error in errors)
    assert any("next_proof_action must match blockers" in error for error in errors)
    assert any("next_proof_refs must include closure_evidence_pack" in error for error in errors)
    assert any("next_proof_refs must include closure_report" in error for error in errors)


def test_payload_validation_rejects_operator_closure_readiness_view_mutation_or_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    view = invalid_payload["loops"][0]["operator_closure_readiness_view"]
    view["read_only"] = False
    view["mutation_route"] = True
    view["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("operator_closure_readiness_view read_only must be true" in error for error in errors)
    assert any("operator_closure_readiness_view mutation_route must be false" in error for error in errors)
    assert any("operator_closure_readiness_view terminal_closure must be false" in error for error in errors)


def test_payload_validation_rejects_mode_binding_transition_or_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_binding = invalid_payload["loops"][0]["mode_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["mode_transition"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("mode_binding read_only must be true" in error for error in errors)
    assert any("mode_binding mode_transition must be false" in error for error in errors)
    assert any("mode_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["mode_transition"] is True


def test_payload_validation_rejects_step_receipt_terminal_closure_claim() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_receipt = invalid_payload["loops"][0]["step_receipts"][0]
    invalid_receipt["metadata"]["read_only"] = False
    invalid_receipt["metadata"]["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("step receipt 0 read_only must be true" in error for error in errors)
    assert any("step receipt 0 terminal_closure must be false" in error for error in errors)
    assert invalid_receipt["metadata"]["terminal_closure"] is True


def test_payload_validation_requires_step_receipt_errors_to_match_blockers() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["step_receipts"][0]["errors"] = ["different_gap"]

    errors = validator.validate_payload(invalid_payload)

    assert any("step receipt 0 errors must match open blockers" in error for error in errors)
    assert invalid_payload["loops"][0]["open_blockers"]
    assert invalid_payload["loops"][0]["step_receipts"][0]["errors"] == ["different_gap"]


def test_payload_validation_rejects_terminal_closure_report() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_closure = invalid_payload["loops"][0]["closure_report"]
    invalid_closure["closed"] = True
    invalid_closure["metadata"]["terminal_closure"] = True

    errors = validator.validate_payload(invalid_payload)

    assert any("closure_report closed must be false" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert invalid_closure["closed"] is True


def test_payload_validation_requires_closure_gaps_to_match_blockers() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["loops"][0]["closure_report"]["unresolved_gaps"] = ["different_gap"]

    errors = validator.validate_payload(invalid_payload)

    assert any("unresolved_gaps must match open blockers" in error for error in errors)
    assert invalid_payload["loops"][0]["open_blockers"]
    assert invalid_payload["loops"][0]["closure_report"]["unresolved_gaps"] == ["different_gap"]


def test_payload_validation_requires_non_terminal_flags() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(validator.LOOP_READ_MODEL_PATH)
    invalid_payload = copy.deepcopy(response.json())
    invalid_payload["report_is_not_terminal_closure"] = False
    invalid_payload["terminal_closure_required"] = False

    errors = validator.validate_payload(invalid_payload)

    assert "report_is_not_terminal_closure must be true" in errors
    assert "terminal_closure_required must be true" in errors
    assert len(errors) >= 2


def test_cli_passes(capsys) -> None:  # noqa: ANN001
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] holistic_loop_http_no_mutation_methods" in streams.out
    assert streams.err == ""
