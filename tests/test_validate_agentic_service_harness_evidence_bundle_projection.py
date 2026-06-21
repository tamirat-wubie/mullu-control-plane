"""Tests for the Agentic Service Harness EvidenceBundle projection validator.

Purpose: prove the EvidenceBundle projection groups reference-only command,
test, diff, policy, receipt, and source read-model evidence by AgentRun id
without enabling ingestion, append, adapter execution, branch writes, PR
creation, secret serialization, mutation routes, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_evidence_bundle_projection.
Invariants:
  - Valid default examples pass schema and semantic validation.
  - Missing source AgentRun ids, empty categories, authority flags, mutation
    routes, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_evidence_bundle_projection import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_CATEGORY_IDS,
    main,
    validate_agentic_service_harness_evidence_bundle_projection,
    write_evidence_bundle_projection_validation,
)


def test_evidence_bundle_projection_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_evidence_bundle_projection()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.bundle_count == 1
    assert validation.run_count == 1
    assert validation.read_models_source_ok is True
    assert validation.adapter_registry_source_ok is True
    assert validation.schema_path == "schemas/agentic_service_harness_evidence_bundle_projection.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_evidence_bundle_projection.foundation.json",
    )


def test_evidence_bundle_projection_preserves_agent_run_refs() -> None:
    payload = _default_payload()
    bundle = payload["bundles"][0]

    assert bundle["bundle_id"] == "bundle-run-read-model-foundation"
    assert bundle["run_id"] == "run-read-model-foundation"
    assert bundle["run_lookup_ref"] == "agent-run://run-read-model-foundation/evidence-bundle"
    assert bundle["source_evidence_bundle_id"] == "evidence-read-model-foundation"
    assert set(bundle["categories"]) == EXPECTED_CATEGORY_IDS
    assert "command://validator/agentic-service-harness-read-models" in bundle["categories"]["command_logs"]
    assert "test://pytest/test-agentic-service-harness-read-models" in bundle["categories"]["test_logs"]
    assert "diff://none/read-only-projection" in bundle["categories"]["diff_refs"]
    assert "receipt://agent-run/run-read-model-foundation/lifecycle/completed" in bundle["categories"]["receipt_refs"]
    assert "agent-run://run-read-model-foundation/read-only-query" in bundle["categories"]["source_read_models"]


def test_evidence_bundle_projection_rejects_unknown_agent_run(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["bundles"][0]["run_id"] = "run-missing"
    payload["bundles"][0]["bundle_id"] = "bundle-run-missing"
    payload["bundles"][0]["run_lookup_ref"] = "agent-run://run-missing/evidence-bundle"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_evidence_bundle_projection(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "does not match a source AgentRun" in serialized_errors
    assert "run-missing" in serialized_errors


def test_evidence_bundle_projection_rejects_missing_category_refs(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["bundles"][0]["categories"]["command_logs"] = []
    payload["bundles"][0]["categories"]["receipt_refs"] = ["receipt://harness/receipt-read-model-foundation"]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_evidence_bundle_projection(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "category command_logs must not be empty" in serialized_errors
    assert "category receipt_refs missing" in serialized_errors
    assert "receipt://agent-run/run-read-model-foundation/lifecycle/completed" in serialized_errors


def test_evidence_bundle_projection_rejects_authority_enablement(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["log_ingestion_enabled"] = True
    payload["authority_denials"]["receipt_store_append_enabled"] = True
    payload["bundles"][0]["runtime_collection_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_evidence_bundle_projection(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "log_ingestion_enabled" in serialized_errors
    assert "receipt_store_append_enabled" in serialized_errors
    assert "runtime_collection_enabled" in serialized_errors


def test_evidence_bundle_projection_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/harness/evidence-bundles"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_evidence_bundle_projection(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_evidence_bundle_projection_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["bundles"][0]["categories"]["source_read_models"].append(
        "github_pat_forbiddencredentialvalue"
    )
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_evidence_bundle_projection(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "source_read_models" in serialized_errors


def test_evidence_bundle_projection_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "evidence-bundle-projection-validation.json"
    validation = validate_agentic_service_harness_evidence_bundle_projection()

    written = write_evidence_bundle_projection_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["bundle_count"] == 1
    assert stdout_payload["run_count"] == 1


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_evidence_bundle_projection.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
