"""Tests for the Agentic Service Harness GitHub repo task service validator.

Purpose: prove the GitHub repo task service contract remains read-only,
contract-only, redacted, and non-terminal before any live adapter, branch write,
pull-request creation, or mutation route is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_repo_task_service.
Invariants:
  - Valid default examples pass schema and semantic validation.
  - Adapter execution, branch writes, PR creation, mutation route strings,
    missing adapter descriptors, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_github_repo_task_service import (  # noqa: E402
    DEFAULT_EXAMPLES,
    REQUIRED_ADAPTER_KINDS,
    main,
    validate_agentic_service_harness_github_repo_task_service,
    write_github_repo_task_service_validation,
)


def test_github_repo_task_service_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_github_repo_task_service()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.required_adapter_kind_count == len(REQUIRED_ADAPTER_KINDS)
    assert validation.schema_path == "schemas/agentic_service_harness_github_repo_task_service.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_github_repo_task_service.foundation.json",
    )
    payload = _default_payload()
    observed_kinds = {descriptor["adapter_kind"] for descriptor in payload["adapter_descriptors"]}
    assert observed_kinds == set(REQUIRED_ADAPTER_KINDS)
    assert payload["repository_metadata_probe"]["live_probe_executed"] is False
    assert payload["task_service"]["allowed_action_classes"] == ["read_only"]


def test_github_repo_task_service_rejects_adapter_execution(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["adapter_descriptors"][0]["executes_adapter"] = True
    payload["task_service"]["executes_adapter"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_service(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "executes_adapter" in serialized_errors
    assert "must be false" in serialized_errors


def test_github_repo_task_service_rejects_branch_and_pr_effects(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["repository_metadata_probe"]["creates_branch"] = True
    payload["task_service"]["opens_pull_request"] = True
    payload["authority_denials"]["branch_write_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_service(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "creates_branch" in serialized_errors
    assert "opens_pull_request" in serialized_errors
    assert "branch_write_enabled" in serialized_errors


def test_github_repo_task_service_rejects_missing_adapter_kind(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["adapter_descriptors"] = [
        descriptor
        for descriptor in payload["adapter_descriptors"]
        if descriptor["adapter_kind"] != "codex_style_coding"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_service(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "adapter descriptors missing" in serialized_errors
    assert "codex_style_coding" in serialized_errors


def test_github_repo_task_service_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/github/tasks"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_service(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_github_repo_task_service_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["repository_metadata_probe"]["serialized_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_service(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_repo_task_service_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-repo-task-service-validation.json"
    validation = validate_agentic_service_harness_github_repo_task_service()

    written = write_github_repo_task_service_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["required_adapter_kind_count"] == len(REQUIRED_ADAPTER_KINDS)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_github_repo_task_service.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
