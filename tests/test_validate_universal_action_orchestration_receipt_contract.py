"""Purpose: verify the Universal Action Orchestration validation receipt contract.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_universal_action_orchestration_receipt_contract.
Invariants:
  - UAO validation receipts are schema-backed non-terminal witnesses.
  - Pass and fail receipt shapes remain causally consistent.
  - Host-local path ancestry is rejected from receipt path labels.
  - The UAO validation receipt writer path boundary is preflight-enforced.
  - The UAO validation receipt artifact-scope boundary is preflight-enforced.
"""

from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout
from pathlib import Path

from scripts import validate_universal_action_orchestration_receipt_contract as validator


def test_universal_action_orchestration_validation_receipt_contract_passes() -> None:
    errors = validator.validate_contract()
    schema = validator.load_schema(validator.DEFAULT_SCHEMA_PATH)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:universal-action-orchestration-validation-receipt:1"
    assert schema["title"] == "Universal Action Orchestration Validation Receipt"
    assert "safe_path_label" in schema["$defs"]
    assert "check_result" in schema["$defs"]
    assert schema["properties"]["schema_path"]["const"] == validator.CANONICAL_UAO_SCHEMA_PATH_LABEL
    assert schema["properties"]["document_path"]["const"] == validator.CANONICAL_UAO_DOCUMENT_PATH_LABEL
    assert tuple(
        item["const"] for item in schema["properties"]["example_paths"]["prefixItems"]
    ) == validator.CANONICAL_UAO_EXAMPLE_PATH_LABELS
    assert validator.validate_receipt_writer_boundary() == []
    assert validator.validate_receipt_canonical_scope_boundary() == []


def test_sample_receipts_are_non_terminal_and_count_consistent() -> None:
    passed_receipt, failed_receipt = validator.build_sample_receipts()

    assert validator.validate_receipt(passed_receipt) == []
    assert validator.validate_receipt(failed_receipt) == []
    assert passed_receipt["terminal_closure_required"] is True
    assert passed_receipt["receipt_is_not_terminal_closure"] is True
    assert passed_receipt["check_count"] == len(passed_receipt["checks"])
    assert failed_receipt["error_count"] == len(failed_receipt["errors"])
    assert failed_receipt["schema_path"] == validator.CANONICAL_UAO_SCHEMA_PATH_LABEL
    assert tuple(failed_receipt["example_paths"]) == validator.CANONICAL_UAO_EXAMPLE_PATH_LABELS


def test_receipt_contract_rejects_identity_and_status_drift() -> None:
    passed_receipt, _ = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["receipt_id"] = "wrong"
    invalid_receipt["valid"] = False
    invalid_receipt["status"] = "passed"
    invalid_receipt["check_count"] = 999

    errors = validator.validate_receipt(invalid_receipt)

    assert len(errors) >= 4
    assert "receipt_id is invalid" in errors
    assert "receipt status must be failed for valid=False" in errors
    assert "check_count does not match checks length" in errors
    assert "valid must match aggregate check outcomes" in errors


def test_receipt_contract_rejects_host_local_path_labels() -> None:
    passed_receipt, _ = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["schema_path"] = "C:\\Users\\operator\\secret.schema.json"
    invalid_receipt["example_paths"] = ["../outside.json"]
    invalid_receipt["errors"] = ["leaked path C:\\Users\\operator\\private.json"]
    invalid_receipt["error_count"] = 1
    invalid_receipt["valid"] = False
    invalid_receipt["status"] = "failed"
    for check in invalid_receipt["checks"]:
        check["passed"] = False

    errors = validator.validate_receipt(invalid_receipt)

    assert len(errors) >= 3
    assert "schema_path must not contain a host-local absolute path" in errors
    assert "example_paths[0] must not contain parent-directory traversal" in errors
    assert "errors[0] must not contain a host-local absolute path" in errors


def test_receipt_contract_rejects_canonical_artifact_drift() -> None:
    passed_receipt, _ = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["schema_path"] = "schemas/alternate_universal_action_orchestration.schema.json"
    invalid_receipt["document_path"] = "docs/alternate-universal-action-orchestration.md"
    invalid_receipt["example_paths"] = list(reversed(invalid_receipt["example_paths"]))

    errors = validator.validate_receipt(invalid_receipt)

    assert "schema_path must reference canonical UAO schema artifact" in errors
    assert "document_path must reference canonical UAO doctrine artifact" in errors
    assert "example_paths must preserve canonical UAO example fixture order" in errors
    assert len(errors) >= 3


def test_receipt_writer_boundary_rejects_escape_and_non_json() -> None:
    workspace_receipt_path = validator.resolve_validation_receipt_path(Path(".tmp/uao-validation-receipt.json"))

    assert workspace_receipt_path.suffix == ".json"
    assert validator.WORKSPACE_ROOT.resolve() in workspace_receipt_path.parents
    assert validator.validate_receipt_writer_boundary() == []


def test_receipt_scope_boundary_rejects_noncanonical_example_set() -> None:
    noncanonical_report = validator.build_validation_report(
        validator.UAO_SCHEMA_PATH,
        (validator.UAO_EXAMPLE_PATHS[0],),
        validator.UAO_DOCUMENT_PATH,
    )

    assert validator.validate_receipt_canonical_scope_boundary() == []
    assert validator.validate_validation_receipt_scope(
        validator.UAO_SCHEMA_PATH,
        (validator.UAO_EXAMPLE_PATHS[0],),
        validator.UAO_DOCUMENT_PATH,
    ) == ["receipt scope example_paths must preserve the canonical UAO fixture set and order"]
    assert validator.validate_validation_receipt_report_scope(noncanonical_report) == [
        "receipt report example_paths must bind the canonical UAO fixture set and order",
        "receipt report example_count must match the canonical UAO fixture count",
    ]


def test_receipt_contract_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "universal_action_orchestration_validation_receipt_schema" in output
    assert "universal_action_orchestration_validation_receipt_writer_boundary" in output
    assert "universal_action_orchestration_validation_receipt_scope_boundary" in output
    assert "STATUS: passed" in output
