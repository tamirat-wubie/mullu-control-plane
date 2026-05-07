"""Document worker contract tests.

Tests: signed deterministic document/data worker execution, format gates,
receipts, and blocked external-effect attempts.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402
from gateway.document_worker import (  # noqa: E402
    DocumentWorkerPolicy,
    _default_registry,
    create_document_worker_app,
    document_action_request_from_mapping,
    execute_document_request,
)
from mcoi_runtime.core.artifact_parsers import ArtifactParserRegistry, register_all_test_parsers  # noqa: E402
from skills.creative.document_gen import DocumentGenerator  # noqa: E402


def _registry() -> ArtifactParserRegistry:
    registry = ArtifactParserRegistry()
    register_all_test_parsers(registry)
    return registry


def _payload(**overrides) -> dict:
    payload = {
        "request_id": "document-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "document.extract_text",
        "action": "document.extract_text",
        "filename": "policy.pdf",
        "content_base64": base64.b64encode(
            b"Policy text. Approval is required for external sends."
        ).decode("ascii"),
        "text": "",
        "rows": [],
        "title": "",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def _body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_document_worker_executes_signed_extract_text_request() -> None:
    secret = "document-secret"
    app = create_document_worker_app(signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload())

    response = client.post(
        "/document/execute",
        content=body,
        headers={"X-Mullu-Document-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Document-Response-Signature"],
        secret,
    )
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["result"]["text"] == "Policy text. Approval is required for external sends."
    assert payload["receipt"]["capability_id"] == "document.extract_text"
    assert payload["receipt"]["parser_id"] == "test-pdf"
    assert payload["receipt"]["verification_status"] == "passed"
    assert payload["receipt"]["evidence_refs"][0].startswith("document_action:")


def test_document_worker_rejects_bad_signature() -> None:
    app = create_document_worker_app(signing_secret="document-secret")
    client = TestClient(app)

    response = client.post(
        "/document/execute",
        content=_body(_payload()),
        headers={"X-Mullu-Document-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid document request signature"
    assert "X-Mullu-Document-Response-Signature" not in response.headers


def test_document_worker_extracts_tables_from_csv() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-table",
            capability_id="document.extract_tables",
            action="document.extract_tables",
            filename="budget.csv",
            content_base64=base64.b64encode(b"team,amount\ncore,10\nplatform,15\n").decode("ascii"),
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["table_count"] == 1
    assert response.result["tables"][0]["headers"] == ["team", "amount"]
    assert response.receipt.row_count == 2
    assert response.receipt.column_count == 2
    assert response.receipt.verification_status == "passed"


def test_document_worker_blocks_table_extraction_without_table_output() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-no-table",
            capability_id="document.extract_tables",
            action="document.extract_tables",
            filename="policy.pdf",
            content_base64=base64.b64encode(b"Policy text without table structure.").decode("ascii"),
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "document table extraction requires parser table output"
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.table_count == 0
    assert response.receipt.parser_id == ""


def test_document_worker_spreadsheet_analyze_uses_deterministic_csv_analysis() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-analyze",
            capability_id="spreadsheet.analyze",
            action="spreadsheet.analyze",
            filename="budget.csv",
            content_base64="",
            text="team,amount\ncore,10\nplatform,15\n",
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["summary"] == "2 rows, 2 columns. Numeric columns: 1. Text columns: 1"
    assert response.receipt.row_count == 2
    assert response.receipt.column_count == 2
    assert response.receipt.summary_hash
    assert response.receipt.forbidden_effects_observed is False


def test_document_worker_generates_pdf_artifact_receipt() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-pdf",
            capability_id="document.generate_pdf",
            action="document.generate_pdf",
            filename="summary.pdf",
            content_base64="",
            text="A governed closure summary.",
            title="Closure Summary",
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(clock=lambda: "2026-04-29T00:00:00+00:00"),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["artifact_ref"].startswith("artifact:pdf:")
    assert response.result["output_format"] == "pdf"
    assert response.receipt.artifact_hash
    assert response.receipt.verification_status == "passed"
    assert response.receipt.table_count == 0


def test_document_worker_blocks_non_rectangular_spreadsheet_generation() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-non-rectangular",
            capability_id="spreadsheet.generate",
            action="spreadsheet.generate",
            filename="report.csv",
            content_base64="",
            rows=[
                {"team": "core", "amount": 10},
                {"team": "platform", "extra": "unexpected"},
            ],
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "spreadsheet row schema mismatch at row 1"
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.artifact_hash == ""
    assert response.receipt.forbidden_effects_observed is False


def test_document_worker_blocks_unsupported_format_before_parser() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-format",
            filename="payload.exe",
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "document format is not supported"
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.parser_id == ""


def test_document_worker_blocks_external_effect_metadata() -> None:
    request = document_action_request_from_mapping(
        _payload(
            request_id="document-request-external",
            metadata={"send_external": True},
        )
    )

    response = execute_document_request(
        request,
        registry=_registry(),
        generator=DocumentGenerator(),
        policy=DocumentWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "document external effect is forbidden"
    assert response.receipt.forbidden_effects_observed is False
    assert response.receipt.verification_status == "blocked"


def test_document_worker_rejects_action_capability_mismatch() -> None:
    try:
        document_action_request_from_mapping(
            _payload(capability_id="document.extract_text", action="document.summarize")
        )
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "document action must match capability_id"
    assert "document.summarize" != "document.extract_text"
    assert error


def test_document_worker_rejects_unknown_default_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MULLU_DOCUMENT_WORKER_ADAPTER", "unknown")

    with pytest.raises(ValueError, match="unsupported document worker adapter"):
        _default_registry()

    assert "unknown" == "unknown"
    assert "MULLU_DOCUMENT_WORKER_ADAPTER".startswith("MULLU_")


def test_document_worker_production_adapter_requires_all_parsers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gateway.document_production_parsers as production_parsers

    monkeypatch.setenv("MULLU_DOCUMENT_WORKER_ADAPTER", "production")
    monkeypatch.setattr(
        production_parsers,
        "register_optional_production_parsers",
        lambda registry: 0,
    )

    with pytest.raises(ValueError, match="requires PDF, DOCX, XLSX, and PPTX parsers"):
        _default_registry()

    assert production_parsers.ProductionPDFParser().parser_id() == "production-pdf"
    assert production_parsers.ProductionDOCXParser().parser_id() == "production-docx"


def test_document_worker_optional_production_adapter_falls_back_to_test_parsers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gateway.document_production_parsers as production_parsers

    monkeypatch.setenv("MULLU_DOCUMENT_WORKER_ADAPTER", "optional-production")
    monkeypatch.setattr(
        production_parsers,
        "register_optional_production_parsers",
        lambda registry: 0,
    )

    registry = _default_registry()

    assert registry.parser_count > 0
    assert registry.get_parser("test-pdf").parser_id() == "test-pdf"
    assert registry.get_parser("test-docx").parser_id() == "test-docx"
