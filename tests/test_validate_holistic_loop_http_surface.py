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
