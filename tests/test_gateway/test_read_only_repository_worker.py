"""Read-only repository worker tests.

Purpose: verify the first Foundation Mode worker path runs through the worker
mesh without mutation, network, secret, or spend authority.
Governance scope: repository path boundary, deterministic worker receipts,
scan bounds, and redacted evidence output.
Dependencies: gateway.read_only_repository_worker and gateway.worker_mesh.
Invariants:
  - Repository inspection dispatch uses the worker mesh lease and receipt path.
  - Paths outside the repository fail closed.
  - Mutation and network inputs are rejected before scanning.
  - Secret-like matched values are redacted from worker output.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.command_spine import canonical_hash
from gateway.read_only_repository_worker import (
    REPOSITORY_INSPECT_CAPABILITY,
    REPOSITORY_INSPECT_OPERATION,
    build_read_only_repository_inspection_lease,
    create_read_only_repository_inspection_handler,
    inspect_repository_request,
)
from gateway.worker_mesh import NetworkedWorkerMesh, WorkerDispatchRequest
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
WORKER_MESH_SCHEMA_PATH = ROOT / "schemas" / "worker_mesh.schema.json"


def test_read_only_repository_worker_dispatches_schema_valid_receipt(tmp_path: Path) -> None:
    repository_root = _repository_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_repository_inspection_handler(repository_root),
    )
    request = _request(
        {
            "paths": ["gateway"],
            "patterns": ["*.py"],
            "query": "WorkerLease",
            "max_files": 10,
            "max_bytes_per_file": 4096,
        }
    )

    receipt = mesh.dispatch(lease.lease_id, request)
    envelope = {"lease": asdict(lease), "request": asdict(request), "receipt": asdict(receipt)}
    errors = _validate_schema_instance(_load_schema(WORKER_MESH_SCHEMA_PATH), envelope)

    assert errors == []
    assert receipt.status == "succeeded"
    assert receipt.reason == "succeeded"
    assert receipt.evidence_refs[0].startswith("repository-inspect:boundary:")
    assert receipt.output_hash


def test_read_only_repository_worker_redacts_secret_like_matches(tmp_path: Path) -> None:
    repository_root = _repository_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_repository_inspection_handler(repository_root),
    )

    request = _request({"paths": ["gateway"], "patterns": ["*.py"], "query": "API_TOKEN"})
    handler_result = inspect_repository_request(repository_root.resolve(), request)
    receipt = mesh.dispatch(lease.lease_id, request)
    excerpt = handler_result.output["findings"][0]["matches"][0]["excerpt"]

    assert handler_result.status == "succeeded"
    assert "API_TOKEN=[REDACTED]" in excerpt
    assert "super-secret-value" not in excerpt
    assert receipt.status == "succeeded"
    assert "repository-inspect:result:" in receipt.evidence_refs[1]
    assert receipt.output_hash
    assert "super-secret-value" not in str(receipt)


def test_read_only_repository_worker_rejects_path_boundary_violation(tmp_path: Path) -> None:
    repository_root = _repository_fixture(tmp_path)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_repository_inspection_handler(repository_root),
    )

    receipt = mesh.dispatch(
        lease.lease_id,
        _request({"paths": [str(outside_file)], "patterns": ["*.txt"], "query": "outside"}),
    )

    assert receipt.status == "failed"
    assert receipt.reason == "path_boundary_violation"
    assert receipt.evidence_refs == []
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_read_only_repository_worker_rejects_mutation_and_network_inputs(tmp_path: Path) -> None:
    repository_root = _repository_fixture(tmp_path)
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        create_read_only_repository_inspection_handler(repository_root),
    )

    mutation_receipt = mesh.dispatch(
        lease.lease_id,
        _request({"paths": ["gateway"], "write": {"path": "gateway/example.py"}}),
    )
    network_receipt = mesh.dispatch(
        lease.lease_id,
        replace(_request({"paths": ["gateway"], "url": "https://example.invalid"}), request_id="repo-worker-2"),
    )

    assert mutation_receipt.status == "failed"
    assert mutation_receipt.reason == "mutation_input_forbidden"
    assert network_receipt.status == "failed"
    assert network_receipt.reason == "network_input_forbidden"


def _lease():
    return build_read_only_repository_inspection_lease(
        tenant_id="tenant-repo-worker",
        lease_id="lease-repo-worker",
        issued_at="2026-06-16T12:00:00+00:00",
        expires_at="2026-06-16T12:30:00+00:00",
    )


def _request(payload: dict[str, object]) -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id="repo-worker-1",
        tenant_id="tenant-repo-worker",
        capability=REPOSITORY_INSPECT_CAPABILITY,
        operation=REPOSITORY_INSPECT_OPERATION,
        command_id="cmd-repo-worker",
        input_hash=canonical_hash(payload),
        payload=payload,
        requested_at="2026-06-16T12:01:00+00:00",
    )


def _repository_fixture(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    gateway_dir = repository_root / "gateway"
    gateway_dir.mkdir(parents=True)
    (gateway_dir / "worker.py").write_text(
        "class WorkerLease:\n"
        "    pass\n"
        "API_TOKEN=super-secret-value\n",
        encoding="utf-8",
    )
    (repository_root / ".git").mkdir()
    (repository_root / ".git" / "config").write_text("secret", encoding="utf-8")
    return repository_root
