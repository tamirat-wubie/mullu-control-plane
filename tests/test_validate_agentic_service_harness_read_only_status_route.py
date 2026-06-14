"""Tests for Agentic Service Harness read-only status route validation.

Purpose: prove the route implementation validator catches missing GET routes,
mutation routes, and incomplete projection modules.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_only_status_route.
Invariants:
  - The default implementation validates.
  - Missing GET route, mutation route siblings, and missing module invariants
    fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_read_only_status_route import (  # noqa: E402
    DEFAULT_PRODUCER_MODULE,
    DEFAULT_ROUTE_MODULE,
    DEFAULT_SERVER,
    REQUIRED_RESPONSE_FIELDS,
    ROUTE_PATH,
    main,
    validate_read_only_status_route,
)


def test_read_only_status_route_accepts_default_implementation() -> None:
    validation = validate_read_only_status_route()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.route_path == ROUTE_PATH
    assert validation.server_path == "gateway/server.py"
    assert validation.route_module_path == "gateway/agentic_service_harness_status.py"
    assert validation.producer_module_path == "gateway/agentic_service_harness_read_model_producer.py"
    assert validation.required_response_field_count == len(REQUIRED_RESPONSE_FIELDS)
    assert validation.validator_count >= 1


def test_read_only_status_route_rejects_missing_get_route(tmp_path: Path) -> None:
    server_path = _write_server(
        tmp_path,
        DEFAULT_SERVER.read_text(encoding="utf-8").replace(
            f'@app.get("{ROUTE_PATH}")',
            '@app.get("/api/v1/harness/other-status")',
        ),
    )

    validation = validate_read_only_status_route(server_path=server_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "GET route must appear exactly once, observed 0" in serialized_errors
    assert validation.route_path == ROUTE_PATH


def test_read_only_status_route_rejects_harness_mutation_route(tmp_path: Path) -> None:
    server_path = _write_server(
        tmp_path,
        DEFAULT_SERVER.read_text(encoding="utf-8")
        + '\n@app.post("/api/v1/harness/tasks")\ndef forbidden_harness_task():\n    return {}\n',
    )

    validation = validate_read_only_status_route(server_path=server_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden harness_mutation_route" in serialized_errors
    assert "GET route must appear exactly once" not in serialized_errors


def test_read_only_status_route_rejects_missing_runtime_source_binding(tmp_path: Path) -> None:
    server_path = _write_server(
        tmp_path,
        DEFAULT_SERVER.read_text(encoding="utf-8").replace(
            "read_model_source=agentic_service_harness_read_model_source,",
            "",
        ),
    )

    validation = validate_read_only_status_route(server_path=server_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing server_runtime_source_term: read_model_source=agentic_service_harness_read_model_source" in serialized_errors
    assert validation.server_path == "server.py"


def test_read_only_status_route_rejects_missing_runtime_producer_binding(tmp_path: Path) -> None:
    server_path = _write_server(
        tmp_path,
        DEFAULT_SERVER.read_text(encoding="utf-8").replace(
            "runtime_producer=AgenticServiceHarnessRuntimeReadModelProducer()",
            "",
        ),
    )

    validation = validate_read_only_status_route(server_path=server_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing server_runtime_source_term: runtime_producer=AgenticServiceHarnessRuntimeReadModelProducer()" in serialized_errors
    assert validation.server_path == "server.py"


def test_read_only_status_route_rejects_missing_module_invariant(tmp_path: Path) -> None:
    module_path = tmp_path / "agentic_service_harness_status.py"
    module_path.write_text(
        DEFAULT_ROUTE_MODULE.read_text(encoding="utf-8").replace(
            "secret_value_serialization_not_allowed",
            "secret_serialization_gap",
        ),
        encoding="utf-8",
    )

    validation = validate_read_only_status_route(route_module_path=module_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing route_module_term: secret_value_serialization_not_allowed" in serialized_errors
    assert validation.route_module_path == "agentic_service_harness_status.py"


def test_read_only_status_route_rejects_missing_producer_invariant(tmp_path: Path) -> None:
    producer_path = tmp_path / "agentic_service_harness_read_model_producer.py"
    producer_path.write_text(
        DEFAULT_PRODUCER_MODULE.read_text(encoding="utf-8").replace(
            "project_contract_to_read_model",
            "project_contract_gap",
        ),
        encoding="utf-8",
    )

    validation = validate_read_only_status_route(producer_module_path=producer_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing producer_module_term: project_contract_to_read_model" in serialized_errors
    assert validation.producer_module_path == "agentic_service_harness_read_model_producer.py"


def test_read_only_status_route_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["route_path"] == ROUTE_PATH


def _write_server(tmp_path: Path, server_text: str) -> Path:
    server_path = tmp_path / "server.py"
    server_path.write_text(server_text, encoding="utf-8")
    return server_path
