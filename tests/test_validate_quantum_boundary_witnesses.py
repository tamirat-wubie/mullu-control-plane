"""Test the aggregate quantum boundary witness validator.

Purpose: verify aggregate validation for the Foundation Mode quantum witnesses.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: foundation example JSON files and aggregate validator functions.
Invariants: no live QPU execution, no source emission, no simulator runtime
invocation, no credential access, no result claim, and no terminal closure.
"""

from __future__ import annotations

import json
import pathlib

from scripts.validate_quantum_boundary_witnesses import (
    FIXTURE_CATALOG_EXAMPLE,
    FIXTURE_CATALOG_ID,
    FIXTURE_SERIALIZER_BOUNDARY_EXAMPLE,
    FIXTURE_SERIALIZER_BOUNDARY_ID,
    LOCAL_SIMULATOR_BOUNDARY_ID,
    LOCAL_SIMULATOR_EXAMPLE,
    OPENQASM_PLANNING_EXAMPLE,
    OPENQASM_PLANNING_ID,
    QUANTUM_BOUNDARY_REVIEW_PACKET_EXAMPLE,
    QUANTUM_BOUNDARY_REVIEW_PACKET_ID,
    UNIVERSAL_BOUNDARY_EXAMPLE,
    UNIVERSAL_BOUNDARY_ID,
    main,
    validate_witnesses,
)


def _payload(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payload(path: pathlib.Path, payload: dict) -> pathlib.Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_quantum_boundary_witness_aggregate_passes_all_foundation_examples() -> None:
    result = validate_witnesses()

    assert result["passed"] is True
    assert result["witness_count"] == 6
    assert [witness["binding_id"] for witness in result["witnesses"]] == [
        UNIVERSAL_BOUNDARY_ID,
        OPENQASM_PLANNING_ID,
        LOCAL_SIMULATOR_BOUNDARY_ID,
        FIXTURE_CATALOG_ID,
        FIXTURE_SERIALIZER_BOUNDARY_ID,
        QUANTUM_BOUNDARY_REVIEW_PACKET_ID,
    ]
    assert result["errors"] == []


def test_cli_json_reports_all_witnesses(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 0
    assert captured.err == ""
    assert result["passed"] is True
    assert result["witness_count"] == 6
    assert len(result["invariants"]) >= 10


def test_aggregate_rejects_openqasm_source_emission(tmp_path: pathlib.Path) -> None:
    payload = _payload(OPENQASM_PLANNING_EXAMPLE)
    payload["effect_boundary"]["openqasm_file_written"] = True
    altered_path = _write_payload(tmp_path / "openqasm-invalid.json", payload)

    result = validate_witnesses({OPENQASM_PLANNING_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{OPENQASM_PLANNING_ID}: effect_boundary.openqasm_file_written must be false" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == OPENQASM_PLANNING_ID
    )["passed"] is False


def test_aggregate_rejects_simulator_runtime_invocation(tmp_path: pathlib.Path) -> None:
    payload = _payload(LOCAL_SIMULATOR_EXAMPLE)
    payload["effect_boundary"]["simulator_runtime_invoked"] = True
    altered_path = _write_payload(tmp_path / "simulator-invalid.json", payload)

    result = validate_witnesses({LOCAL_SIMULATOR_BOUNDARY_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{LOCAL_SIMULATOR_BOUNDARY_ID}: effect_boundary.simulator_runtime_invoked must be false" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == LOCAL_SIMULATOR_BOUNDARY_ID
    )["errors"] == ["effect_boundary.simulator_runtime_invoked must be false"]


def test_aggregate_rejects_parent_boundary_live_qpu_authority(tmp_path: pathlib.Path) -> None:
    payload = _payload(UNIVERSAL_BOUNDARY_EXAMPLE)
    payload["denied_authorities"]["live_qpu_execution_enabled"] = True
    altered_path = _write_payload(tmp_path / "universal-invalid.json", payload)

    result = validate_witnesses({UNIVERSAL_BOUNDARY_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{UNIVERSAL_BOUNDARY_ID}: denied_authorities.live_qpu_execution_enabled must be false" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == UNIVERSAL_BOUNDARY_ID
    )["passed"] is False


def test_aggregate_reports_non_object_json_as_validation_error(tmp_path: pathlib.Path) -> None:
    altered_path = tmp_path / "not-object.json"
    altered_path.write_text(json.dumps(["not", "a", "witness"]), encoding="utf-8")

    result = validate_witnesses({OPENQASM_PLANNING_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{OPENQASM_PLANNING_ID}: {altered_path} must contain a JSON object" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == OPENQASM_PLANNING_ID
    )["errors"] == [f"{altered_path} must contain a JSON object"]


def test_aggregate_rejects_fixture_executable_generation(tmp_path: pathlib.Path) -> None:
    payload = _payload(FIXTURE_CATALOG_EXAMPLE)
    payload["effect_boundary"]["executable_fixture_written"] = True
    altered_path = _write_payload(tmp_path / "fixture-catalog-invalid.json", payload)

    result = validate_witnesses({FIXTURE_CATALOG_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{FIXTURE_CATALOG_ID}: effect_boundary.executable_fixture_written must be false" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == FIXTURE_CATALOG_ID
    )["passed"] is False


def test_aggregate_rejects_fixture_serializer_execution(tmp_path: pathlib.Path) -> None:
    payload = _payload(FIXTURE_SERIALIZER_BOUNDARY_EXAMPLE)
    payload["effect_boundary"]["serializer_executed"] = True
    altered_path = _write_payload(tmp_path / "fixture-serializer-invalid.json", payload)

    result = validate_witnesses({FIXTURE_SERIALIZER_BOUNDARY_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{FIXTURE_SERIALIZER_BOUNDARY_ID}: effect_boundary.serializer_executed must be false" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == FIXTURE_SERIALIZER_BOUNDARY_ID
    )["passed"] is False


def test_aggregate_rejects_review_packet_implementation_authority(tmp_path: pathlib.Path) -> None:
    payload = _payload(QUANTUM_BOUNDARY_REVIEW_PACKET_EXAMPLE)
    payload["implementation_allowed"] = True
    altered_path = _write_payload(tmp_path / "review-packet-invalid.json", payload)

    result = validate_witnesses({QUANTUM_BOUNDARY_REVIEW_PACKET_ID: altered_path})

    assert result["passed"] is False
    assert result["witness_count"] == 6
    assert any(
        f"{QUANTUM_BOUNDARY_REVIEW_PACKET_ID}: implementation_allowed must be false" == error
        for error in result["errors"]
    )
    assert next(
        witness for witness in result["witnesses"] if witness["binding_id"] == QUANTUM_BOUNDARY_REVIEW_PACKET_ID
    )["passed"] is False
