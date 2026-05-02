"""Gateway Document Worker - deterministic document/data contract.

Purpose: Hosts signed document-worker execution for deterministic extraction,
    summary, and generated artifact receipts.
Governance scope: supported format gating, no external send/sign/submit
    effects, parser-bound extraction, and receipt emission.
Dependencies: FastAPI, artifact parser registry, creative data/document helpers,
    and gateway canonical hashing.
Invariants:
  - Unsigned requests are rejected before parsing or generation.
  - Unsupported actions and formats fail closed.
  - The worker never sends, signs, or submits documents externally.
  - Extraction is parser/fingerprint based; summaries are deterministic.
  - Table extraction requires parser-backed table evidence.
  - Generated spreadsheets require rectangular row schemas.
  - Responses are signed and include receipt evidence.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature
from gateway.command_spine import canonical_hash
from mcoi_runtime.core.artifact_parsers import ArtifactParserRegistry, register_all_test_parsers
from skills.creative.data_analysis import analyze_csv
from skills.creative.document_gen import DocumentGenerator


@dataclass(frozen=True, slots=True)
class DocumentWorkerPolicy:
    """Policy envelope for one restricted document worker."""

    worker_id: str = "document-worker"
    allowed_actions: tuple[str, ...] = (
        "document.extract_text",
        "document.extract_tables",
        "document.summarize",
        "document.generate_docx",
        "document.generate_pdf",
        "spreadsheet.analyze",
        "spreadsheet.generate",
    )
    supported_inputs: tuple[str, ...] = ("pdf", "docx", "xlsx", "pptx", "csv", "md", "txt", "json")
    generated_formats: tuple[str, ...] = ("docx", "pdf", "csv")
    max_input_bytes: int = 10_000_000
    external_effects_allowed: bool = False

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _validate_text_tuple(self.allowed_actions, "allowed_actions")
        _validate_text_tuple(self.supported_inputs, "supported_inputs")
        _validate_text_tuple(self.generated_formats, "generated_formats")
        if self.max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be > 0")
        if self.external_effects_allowed is not False:
            raise ValueError("document worker must not allow external effects")


@dataclass(frozen=True, slots=True)
class DocumentActionRequest:
    """Signed request for one document worker action."""

    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    filename: str = ""
    content_base64: str = ""
    text: str = ""
    rows: tuple[dict[str, Any], ...] = ()
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.action, "action")
        if self.action != self.capability_id:
            raise ValueError("document action must match capability_id")
        object.__setattr__(self, "rows", tuple(dict(row) for row in self.rows))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DocumentActionReceipt:
    """Receipt proving document worker action and observed output."""

    receipt_id: str
    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    worker_id: str
    document_id: str
    parser_id: str
    input_hash: str
    text_hash: str
    summary_hash: str
    table_count: int
    row_count: int
    column_count: int
    artifact_ref: str
    artifact_hash: str
    forbidden_effects_observed: bool
    verification_status: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentActionResponse:
    """Signed document-worker response."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: DocumentActionReceipt
    error: str = ""


def create_document_worker_app(
    *,
    registry: ArtifactParserRegistry | None = None,
    generator: DocumentGenerator | None = None,
    policy: DocumentWorkerPolicy | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Create the restricted document worker FastAPI app."""
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_DOCUMENT_WORKER_SECRET", "")
    if not secret:
        raise ValueError("document worker signing secret is required")
    resolved_policy = policy or DocumentWorkerPolicy()
    resolved_registry = registry or _default_registry()
    resolved_generator = generator or DocumentGenerator()
    app = FastAPI(title="Mullu Document Worker", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": resolved_policy.worker_id,
            "governed": True,
        }

    @app.post("/document/execute")
    async def execute_document_action(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Document-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid document request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("document request body must be an object")
            document_request = document_action_request_from_mapping(raw)
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
            raise HTTPException(422, detail=str(exc)) from exc

        response = execute_document_request(
            document_request,
            registry=resolved_registry,
            generator=resolved_generator,
            policy=resolved_policy,
        )
        response_body = json.dumps(
            document_action_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Document-Response-Signature": response_signature},
        )

    app.state.document_policy = resolved_policy
    app.state.document_registry = resolved_registry
    return app


def execute_document_request(
    request: DocumentActionRequest,
    *,
    registry: ArtifactParserRegistry,
    generator: DocumentGenerator,
    policy: DocumentWorkerPolicy,
) -> DocumentActionResponse:
    """Execute one document action under policy."""
    try:
        denial = _policy_denial(request, policy)
    except ValueError as exc:
        denial = str(exc)
    if denial:
        return _blocked_response(request, policy, denial)

    try:
        if request.action in {"document.extract_text", "document.extract_tables", "document.summarize"}:
            result = _parse_document_action(request, registry=registry)
        elif request.action == "spreadsheet.analyze":
            result = _spreadsheet_analyze_action(request)
        elif request.action in {"document.generate_docx", "document.generate_pdf", "spreadsheet.generate"}:
            result = _generate_artifact_action(request, generator=generator)
        else:
            return _blocked_response(request, policy, "document action is not allowlisted")
    except ValueError as exc:
        return _blocked_response(request, policy, str(exc))

    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return DocumentActionResponse(
        request_id=request.request_id,
        status="succeeded",
        result=result,
        receipt=receipt,
        error="",
    )


def document_action_request_from_mapping(raw: dict[str, Any]) -> DocumentActionRequest:
    """Parse a document request payload into a typed request."""
    rows = raw.get("rows", ())
    if rows is None:
        rows = ()
    if not isinstance(rows, list | tuple):
        raise ValueError("rows must be an array")
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("rows entries must be objects")
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be an object")
    return DocumentActionRequest(
        request_id=str(raw["request_id"]),
        tenant_id=str(raw["tenant_id"]),
        capability_id=str(raw["capability_id"]),
        action=str(raw["action"]),
        filename=str(raw.get("filename", "")),
        content_base64=str(raw.get("content_base64", "")),
        text=str(raw.get("text", "")),
        rows=tuple(dict(row) for row in rows),
        title=str(raw.get("title", "")),
        metadata=dict(metadata),
    )


def document_action_response_payload(response: DocumentActionResponse) -> dict[str, Any]:
    """Serialize a document worker response."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": _json_ready(response.result),
        "receipt": {
            **asdict(response.receipt),
            "evidence_refs": list(response.receipt.evidence_refs),
        },
        "error": response.error,
    }


def _parse_document_action(request: DocumentActionRequest, *, registry: ArtifactParserRegistry) -> dict[str, Any]:
    filename = _require_text(request.filename, "filename")
    content = _decode_content(request)
    parsed = registry.auto_parse(_artifact_id(request), filename, content)
    if parsed is None:
        extension = _extension(filename)
        if extension not in {"md", "txt", "json"}:
            raise ValueError("no parser available for document")
        document_id = _artifact_id(request)
        parser_id = f"builtin-{extension}-text"
        text = content.decode("utf-8", errors="replace")
        tables: tuple[Any, ...] = ()
    else:
        document_id = parsed.artifact_id
        parser_id = parsed.parser_id
        text = parsed.text_content
        tables = tuple(parsed.tables or ())
    if request.action == "document.extract_tables" and not tables:
        raise ValueError("document table extraction requires parser table output")
    summary = _summarize_text(text)
    result = {
        "document_id": document_id,
        "parser_id": parser_id,
        "filename": filename,
        "text": text if request.action == "document.extract_text" else "",
        "text_hash": _sha256(text),
        "summary": summary if request.action == "document.summarize" else "",
        "summary_hash": _sha256(summary) if request.action == "document.summarize" else "",
        "tables": [_json_ready(table) for table in tables] if request.action == "document.extract_tables" else [],
        "table_count": len(tables),
        "row_count": _table_row_count(tables),
        "column_count": _table_column_count(tables),
        "input_hash": _sha256_bytes(content),
        "artifact_ref": "",
        "artifact_hash": "",
    }
    return result


def _spreadsheet_analyze_action(request: DocumentActionRequest) -> dict[str, Any]:
    csv_text = request.text
    if not csv_text and request.content_base64:
        csv_text = _decode_content(request).decode("utf-8", errors="replace")
    analysis = analyze_csv(csv_text)
    if not analysis.success:
        raise ValueError(analysis.error or "spreadsheet analysis failed")
    summary_hash = _sha256(analysis.summary)
    return {
        "document_id": _artifact_id(request),
        "parser_id": "csv-analysis",
        "filename": request.filename,
        "text": "",
        "text_hash": _sha256(csv_text),
        "summary": analysis.summary,
        "summary_hash": summary_hash,
        "tables": [],
        "table_count": 1,
        "row_count": analysis.row_count,
        "column_count": analysis.column_count,
        "analysis_hash": summary_hash,
        "input_hash": _sha256(csv_text),
        "artifact_ref": "",
        "artifact_hash": "",
    }


def _generate_artifact_action(request: DocumentActionRequest, *, generator: DocumentGenerator) -> dict[str, Any]:
    output_format = "csv" if request.action == "spreadsheet.generate" else request.action.rsplit("_", 1)[-1]
    if request.action == "spreadsheet.generate":
        artifact_text = _rows_to_csv(request.rows)
        title = request.title or "Generated spreadsheet"
    else:
        title = request.title or f"Generated {output_format.upper()} document"
        body = request.text or str(request.metadata.get("body", ""))
        if not body.strip():
            raise ValueError("document generation requires text")
        document = generator.generate_from_llm(
            output_format,
            body,
            body,
            tenant_id=request.tenant_id,
            identity_id=str(request.metadata.get("identity_id", "")),
            title=title,
        )
        artifact_text = document.body
    artifact_hash = _sha256(artifact_text)
    artifact_ref = f"artifact:{output_format}:{artifact_hash[:16]}"
    return {
        "document_id": _artifact_id(request),
        "parser_id": "document-generator",
        "filename": request.filename or f"{title}.{output_format}",
        "text": "",
        "text_hash": _sha256(artifact_text),
        "summary": "",
        "summary_hash": "",
        "tables": [],
        "table_count": 1 if request.action == "spreadsheet.generate" else 0,
        "row_count": len(request.rows),
        "column_count": len(request.rows[0]) if request.rows else 0,
        "input_hash": _sha256(canonical_hash({"text": request.text, "rows": request.rows, "title": title})),
        "artifact_ref": artifact_ref,
        "artifact_hash": artifact_hash,
        "output_format": output_format,
    }


def _blocked_response(request: DocumentActionRequest, policy: DocumentWorkerPolicy, reason: str) -> DocumentActionResponse:
    result = {
        "document_id": _artifact_id(request),
        "parser_id": "",
        "input_hash": "",
        "text_hash": "",
        "summary_hash": "",
        "table_count": 0,
        "row_count": 0,
        "column_count": 0,
        "artifact_ref": "",
        "artifact_hash": "",
        "error": reason,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="blocked")
    return DocumentActionResponse(
        request_id=request.request_id,
        status="blocked",
        result=result,
        receipt=receipt,
        error=reason,
    )


def _receipt_for(
    *,
    request: DocumentActionRequest,
    policy: DocumentWorkerPolicy,
    result: dict[str, Any],
    verification_status: str,
) -> DocumentActionReceipt:
    receipt_hash = canonical_hash({
        "request_id": request.request_id,
        "capability_id": request.capability_id,
        "action": request.action,
        "input_hash": result.get("input_hash", ""),
        "text_hash": result.get("text_hash", ""),
        "artifact_hash": result.get("artifact_hash", ""),
        "verification_status": verification_status,
    })
    return DocumentActionReceipt(
        receipt_id=f"document-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        capability_id=request.capability_id,
        action=request.action,
        worker_id=policy.worker_id,
        document_id=str(result.get("document_id", _artifact_id(request))),
        parser_id=str(result.get("parser_id", "")),
        input_hash=str(result.get("input_hash", "")),
        text_hash=str(result.get("text_hash", "")),
        summary_hash=str(result.get("summary_hash", "")),
        table_count=int(result.get("table_count", 0)),
        row_count=int(result.get("row_count", 0)),
        column_count=int(result.get("column_count", 0)),
        artifact_ref=str(result.get("artifact_ref", "")),
        artifact_hash=str(result.get("artifact_hash", "")),
        forbidden_effects_observed=False,
        verification_status=verification_status,
        evidence_refs=(f"document_action:{receipt_hash[:16]}",),
    )


def _policy_denial(request: DocumentActionRequest, policy: DocumentWorkerPolicy) -> str:
    if request.action not in policy.allowed_actions:
        return "document action is not allowlisted"
    if not policy.external_effects_allowed and any(
        flag in request.metadata
        for flag in ("send_external", "sign_document", "submit_document")
    ):
        return "document external effect is forbidden"
    if request.action in {"document.extract_text", "document.extract_tables", "document.summarize", "spreadsheet.analyze"}:
        ext = _extension(request.filename)
        if ext and ext not in policy.supported_inputs:
            return "document format is not supported"
        content = _decode_content(request)
        if not content:
            return "document input is required"
        if len(content) > policy.max_input_bytes:
            return "document input exceeds size limit"
    if request.action in {"document.generate_docx", "document.generate_pdf", "spreadsheet.generate"}:
        output_format = "csv" if request.action == "spreadsheet.generate" else request.action.rsplit("_", 1)[-1]
        if output_format not in policy.generated_formats:
            return "document output format is not supported"
    return ""


def _decode_content(request: DocumentActionRequest) -> bytes:
    if request.content_base64:
        try:
            return base64.b64decode(request.content_base64.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("document content_base64 is invalid") from exc
    return request.text.encode("utf-8")


def _summarize_text(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 240:
        return compact
    return compact[:237].rstrip() + "..."


def _rows_to_csv(rows: tuple[dict[str, Any], ...]) -> str:
    if not rows:
        raise ValueError("spreadsheet generation requires rows")
    headers = tuple(str(key) for key in rows[0])
    if not headers:
        raise ValueError("spreadsheet generation requires columns")
    _validate_rectangular_rows(rows, headers)
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return handle.getvalue()


def _validate_rectangular_rows(rows: tuple[dict[str, Any], ...], headers: tuple[str, ...]) -> None:
    expected = set(headers)
    for index, row in enumerate(rows):
        actual = {str(key) for key in row}
        if actual != expected:
            raise ValueError(f"spreadsheet row schema mismatch at row {index}")


def _artifact_id(request: DocumentActionRequest) -> str:
    return f"document-{canonical_hash({'request_id': request.request_id, 'filename': request.filename})[:16]}"


def _table_row_count(tables: tuple[Any, ...]) -> int:
    if not tables:
        return 0
    table = tables[0]
    if isinstance(table, Mapping) and "row_count" in table:
        return int(table["row_count"])
    return 0


def _table_column_count(tables: tuple[Any, ...]) -> int:
    if not tables:
        return 0
    table = tables[0]
    if isinstance(table, Mapping) and "headers" in table:
        return len(table["headers"])
    return 0


def _extension(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value


def _default_registry() -> ArtifactParserRegistry:
    registry = ArtifactParserRegistry()
    parser_set = os.environ.get("MULLU_DOCUMENT_WORKER_ADAPTER", "").strip().lower()
    if parser_set in {"production", "optional-production"}:
        from gateway.document_production_parsers import register_optional_production_parsers

        registered_count = register_optional_production_parsers(registry)
        if parser_set == "production" and registered_count < 4:
            raise ValueError("production document worker requires PDF, DOCX, XLSX, and PPTX parsers")
        if registered_count:
            return registry
    elif parser_set and parser_set != "test":
        raise ValueError(f"unsupported document worker adapter: {parser_set}")
    register_all_test_parsers(registry)
    return registry


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validate_text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field_name} must contain at least one item")
    for value in values:
        _require_text(value, field_name)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_DOCUMENT_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-document-worker-secret"
    return create_document_worker_app(signing_secret=secret)


app = _default_app()
