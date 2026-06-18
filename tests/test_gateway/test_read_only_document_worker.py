"""Read-only document worker tests.

Purpose: verify the Foundation Mode document worker runs through the worker
mesh without mutation, network, secret, spend, or rich parsing authority.
Governance scope: document path boundary, format allowlist, deterministic
worker receipts, scan bounds, and redacted evidence output.
Dependencies: gateway.read_only_document_worker and gateway.worker_mesh.
Invariants:
  - Document inspection dispatch uses the worker mesh lease and receipt path.
  - Paths outside the document root fail closed.
  - Unsupported rich formats fail closed.
  - Secret-like matched values are redacted from worker output.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.command_spine import canonical_hash
from gateway.read_only_document_worker import (
    DOCUMENT_INSPECT_CAPABILITY,
    DOCUMENT_INSPECT_OPERATION,
    build_read_only_document_inspection_lease,
    create_read_only_document_inspection_handler,
    inspect_document_request,
)
from gateway.worker_mesh import NetworkedWorkerMesh, WorkerDispatchRequest
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
WORKER_MESH_SCHEMA_PATH = ROOT / "schemas" / "worker_mesh.schema.json"


def test_read_only_document_worker_dispatches_schema_valid_receipt(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )
    request = _request(
        {
            "documents": ["notes.md"],
            "query": "governance",
            "max_documents": 5,
            "max_bytes_per_document": 4096,
        }
    )

    receipt = mesh.dispatch(lease.lease_id, request)
    envelope = {"lease": asdict(lease), "request": asdict(request), "receipt": asdict(receipt)}
    errors = _validate_schema_instance(_load_schema(WORKER_MESH_SCHEMA_PATH), envelope)

    assert errors == []
    assert receipt.status == "succeeded"
    assert receipt.reason == "succeeded"
    assert receipt.evidence_refs[0].startswith("document-inspect:boundary:")
    assert receipt.output_hash


def test_read_only_document_worker_redacts_secret_like_matches(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )

    request = _request({"documents": ["notes.md"], "query": "API_TOKEN"})
    handler_result = inspect_document_request(document_root.resolve(), request)
    receipt = mesh.dispatch(lease.lease_id, request)
    excerpt = handler_result.output["documents"][0]["matches"][0]["excerpt"]

    assert handler_result.status == "succeeded"
    assert "API_TOKEN=[REDACTED]" in excerpt
    assert "document-secret-value" not in excerpt
    assert receipt.status == "succeeded"
    assert "document-inspect:result:" in receipt.evidence_refs[1]
    assert receipt.output_hash
    assert "document-secret-value" not in str(receipt)


def test_read_only_document_worker_rejects_path_boundary_violation(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("outside", encoding="utf-8")
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )

    receipt = mesh.dispatch(
        lease.lease_id,
        _request({"documents": [str(outside_file)], "query": "outside"}),
    )

    assert receipt.status == "failed"
    assert receipt.reason == "document_path_boundary_violation"
    assert receipt.evidence_refs == []
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_read_only_document_worker_rejects_unsupported_format(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )

    receipt = mesh.dispatch(
        lease.lease_id,
        _request({"documents": ["draft.docx"], "query": "governance"}),
    )

    assert receipt.status == "failed"
    assert receipt.reason == "document_format_not_supported"
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_read_only_document_worker_reports_text_decode_failure(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    (document_root / "latin1.md").write_bytes(b"\xff\xfeinvalid-utf8")
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )

    receipt = mesh.dispatch(
        lease.lease_id,
        _request({"documents": ["latin1.md"], "query": "invalid"}),
    )

    assert receipt.status == "failed"
    assert receipt.reason == "document_text_decode_failed"
    assert receipt.evidence_refs == []
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_read_only_document_worker_rejects_mutation_and_network_inputs(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )

    mutation_receipt = mesh.dispatch(
        lease.lease_id,
        _request({"documents": ["notes.md"], "write": {"path": "notes.md"}}),
    )
    network_receipt = mesh.dispatch(
        lease.lease_id,
        replace(_request({"documents": ["notes.md"], "url": "https://example.invalid"}), request_id="doc-worker-2"),
    )

    assert mutation_receipt.status == "failed"
    assert mutation_receipt.reason == "mutation_input_forbidden"
    assert network_receipt.status == "failed"
    assert network_receipt.reason == "network_input_forbidden"


def test_read_only_document_worker_rejects_secret_like_input_values(tmp_path: Path) -> None:
    document_root = _document_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-17T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_document_inspection_handler(document_root),
    )

    receipt = mesh.dispatch(
        lease.lease_id,
        _request({"documents": ["notes.md"], "query": "API_TOKEN=document-secret-value"}),
    )

    assert receipt.status == "failed"
    assert receipt.reason == "secret_input_forbidden"
    assert receipt.evidence_refs == []
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def _lease():
    return build_read_only_document_inspection_lease(
        tenant_id="tenant-doc-worker",
        lease_id="lease-doc-worker",
        issued_at="2026-06-17T12:00:00+00:00",
        expires_at="2026-06-17T12:30:00+00:00",
    )


def _request(payload: dict[str, object]) -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id="doc-worker-1",
        tenant_id="tenant-doc-worker",
        capability=DOCUMENT_INSPECT_CAPABILITY,
        operation=DOCUMENT_INSPECT_OPERATION,
        command_id="cmd-doc-worker",
        input_hash=canonical_hash(payload),
        payload=payload,
        requested_at="2026-06-17T12:01:00+00:00",
    )


def _document_fixture(tmp_path: Path) -> Path:
    document_root = tmp_path / "documents"
    document_root.mkdir(parents=True)
    (document_root / "notes.md").write_text(
        "# Notes\n"
        "governance line\n"
        "API_TOKEN=document-secret-value\n",
        encoding="utf-8",
    )
    (document_root / "draft.docx").write_bytes(b"PK\x03\x04binary-docx-placeholder")
    return document_root
