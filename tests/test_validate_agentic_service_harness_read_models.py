"""Tests for the Agentic Service Harness read-model validator.

Purpose: prove the first harness read-model schema remains read-only,
reference-consistent, redacted, and non-terminal before any UI, mutation
endpoint, or external adapter path is introduced.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_models.
Invariants:
  - Valid default examples pass schema and semantic validation.
  - Mutation flags, route strings, missing refs, secret-like payloads, and
    terminal closure claims fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_read_models import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_DURABLE_ENTITY_KINDS,
    EXPECTED_COLLECTIONS,
    main,
    validate_agentic_service_harness_read_models,
    write_agentic_service_harness_read_model_validation,
)


def test_agentic_service_harness_read_models_accept_default_example() -> None:
    validation = validate_agentic_service_harness_read_models()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.collection_count == len(EXPECTED_COLLECTIONS)
    assert validation.schema_path == "schemas/agentic_service_harness_read_models.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_read_models.foundation.json",
    )
    payload = _default_payload()
    observed_entity_kinds = {
        binding["entity_kind"]
        for binding in payload["durable_entity_bindings"]["entity_bindings"]
    }
    assert observed_entity_kinds == set(EXPECTED_DURABLE_ENTITY_KINDS)


def test_agentic_service_harness_read_models_reject_mutation_flag(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["projection_scope"]["mutation_endpoints_admitted"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation_endpoints_admitted" in serialized_errors
    assert "must remain false" in serialized_errors


def test_agentic_service_harness_read_models_reject_mutation_route_string(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/harness/tasks"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_agentic_service_harness_read_models_reject_missing_run_ref(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["projects"][0]["agent_run_ids"] = ["run-missing"]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "project project-agentic-service-harness run refs" in serialized_errors
    assert "run-missing" in serialized_errors


def test_agentic_service_harness_read_models_reject_secret_like_payload(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["accounts"][0]["serialized_secret_value"] = "ghp_examplecredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_agentic_service_harness_read_models_reject_terminal_closure_claim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["receipts"][0]["terminal_closure"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure" in serialized_errors
    assert "must be false" in serialized_errors


def test_agentic_service_harness_read_models_reject_missing_durable_binding(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["durable_entity_bindings"]["entity_bindings"] = [
        binding
        for binding in payload["durable_entity_bindings"]["entity_bindings"]
        if binding["entity_kind"] != "ApprovalRequest"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "durable entity bindings missing" in serialized_errors
    assert "ApprovalRequest" in serialized_errors


def test_agentic_service_harness_read_models_reject_enabled_durable_append(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["durable_entity_bindings"]["append_enabled"] = True
    payload["durable_entity_bindings"]["entity_bindings"][0]["append_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "durable_entity_bindings.append_enabled" in serialized_errors
    assert "durable entity binding User append_enabled" in serialized_errors


def test_agentic_service_harness_read_models_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "agentic_service_harness_read_models_validation.json"
    validation = validate_agentic_service_harness_read_models()

    written = write_agentic_service_harness_read_model_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["collection_count"] == len(EXPECTED_COLLECTIONS)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_read_models.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
