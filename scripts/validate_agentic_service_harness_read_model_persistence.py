#!/usr/bin/env python3
"""Validate Agentic Service Harness read-model persistence rehearsal.

Purpose: prove the first Agentic Service Harness read models can be persisted
and replayed through a local append-only JSONL store before any dashboard,
mutation endpoint, external adapter, branch write, or pull-request path exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness_read_models.foundation.json,
schemas/agentic_service_harness_read_models.schema.json, gateway.command_spine,
and scripts.validate_agentic_service_harness_read_models.
Invariants:
  - The rehearsal writes only to an ephemeral local store unless an explicit
    test path is injected.
  - Store records are append-only, hash-chained, tenant/project scoped, and
    duplicate-rejecting.
  - Replayed read models remain schema-valid, read-only, non-terminal, and
    free of secret values or mutation authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from gateway.command_spine import canonical_hash  # noqa: E402
from scripts.validate_agentic_service_harness_read_models import (  # noqa: E402
    DEFAULT_SCHEMA,
    _validate_read_model_semantics,
    validate_agentic_service_harness_read_models,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "agentic_service_harness_read_models.foundation.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_read_model_persistence_validation.json"
)
GENESIS_HASH = "GENESIS"
ENTRY_KEYS = {
    "entry_id",
    "sequence",
    "record_kind",
    "record_id",
    "tenant_id",
    "project_id",
    "causal_ref",
    "payload_hash",
    "previous_entry_hash",
    "payload",
    "entry_hash",
}
COLLECTION_ID_FIELDS = {
    "account": ("accounts", "user_id"),
    "project": ("projects", "project_id"),
    "repository": ("repositories", "connection_id"),
    "run": ("runs", "run_id"),
    "approval": ("approvals", "gate_id"),
    "receipt": ("receipts", "receipt_id"),
    "evidence": ("evidence", "bundle_id"),
    "result_summary": ("result_summaries", "summary_id"),
    "workspace_allocation": ("workspace_allocations", "allocation_id"),
}
SINGLETON_KINDS = {
    "report_header",
    "projection_scope",
    "durable_entity_bindings",
    "permission_snapshot",
}
ALLOWED_RECORD_KINDS = set(COLLECTION_ID_FIELDS) | SINGLETON_KINDS
HEADER_FIELDS = (
    "report_id",
    "schema_version",
    "contract_ref",
    "generated_at",
    "validators",
    "next_action",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "can_mutate_secrets",
    "contains_secret_values",
    "no_secret_mutation",
    "secret_values_serialized",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)


class HarnessReadModelPersistenceError(ValueError):
    """Raised when the local persistence rehearsal fails closed."""


@dataclass(frozen=True, slots=True)
class AgenticServiceHarnessReadModelPersistenceValidation:
    """Validation report for the harness read-model persistence rehearsal."""

    ok: bool
    errors: tuple[str, ...]
    example_path: str
    schema_path: str
    persisted_record_count: int
    replayed_record_count: int
    chain_head: str
    duplicate_rejected: bool
    secret_rejected: bool
    rebuilt_matches_source: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


class AppendOnlyHarnessReadModelStore:
    """Local append-only JSONL store for harness read-model rehearsal records."""

    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self._entries = self._load_entries()
        self._seen_keys = {
            (str(entry["record_kind"]), str(entry["record_id"]))
            for entry in self._entries
        }

    @property
    def entries(self) -> tuple[dict[str, Any], ...]:
        """Return replayed entries in append order."""
        return tuple(dict(entry) for entry in self._entries)

    @property
    def chain_head(self) -> str:
        """Return the current hash-chain head."""
        if not self._entries:
            return GENESIS_HASH
        return str(self._entries[-1]["entry_hash"])

    def append(
        self,
        *,
        record_kind: str,
        record_id: str,
        tenant_id: str,
        project_id: str,
        payload: Mapping[str, Any],
        causal_ref: str,
    ) -> dict[str, Any]:
        """Append one tenant/project-scoped read-model record."""
        if record_kind not in ALLOWED_RECORD_KINDS:
            raise HarnessReadModelPersistenceError(f"unsupported record_kind: {record_kind}")
        if not record_id:
            raise HarnessReadModelPersistenceError("record_id is required")
        if not tenant_id:
            raise HarnessReadModelPersistenceError("tenant_id is required")
        if not project_id:
            raise HarnessReadModelPersistenceError("project_id is required")
        if not causal_ref:
            raise HarnessReadModelPersistenceError("causal_ref is required")
        if (record_kind, record_id) in self._seen_keys:
            raise HarnessReadModelPersistenceError(f"duplicate record: {record_kind}:{record_id}")
        payload_dict = dict(payload)
        _reject_sensitive_payload(payload_dict)

        payload_hash = canonical_hash(payload_dict)
        sequence = len(self._entries) + 1
        entry_without_hash = {
            "entry_id": f"harness-read-model-{sequence:04d}-{payload_hash[:12]}",
            "sequence": sequence,
            "record_kind": record_kind,
            "record_id": record_id,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "causal_ref": causal_ref,
            "payload_hash": payload_hash,
            "previous_entry_hash": self.chain_head,
            "payload": payload_dict,
        }
        entry = {
            **entry_without_hash,
            "entry_hash": canonical_hash(entry_without_hash),
        }

        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
        self._entries.append(entry)
        self._seen_keys.add((record_kind, record_id))
        return dict(entry)

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        previous_entry_hash = GENESIS_HASH
        seen_keys: set[tuple[str, str]] = set()
        for line_number, line in enumerate(self.store_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HarnessReadModelPersistenceError(f"invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(entry, dict):
                raise HarnessReadModelPersistenceError(f"entry at line {line_number} must be an object")
            _validate_loaded_entry(entry, line_number, previous_entry_hash, seen_keys)
            previous_entry_hash = str(entry["entry_hash"])
            entries.append(entry)
        return entries


def validate_agentic_service_harness_read_model_persistence(
    *,
    example_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> AgenticServiceHarnessReadModelPersistenceValidation:
    """Run the append-only persistence rehearsal against one read-model example."""
    errors: list[str] = []
    source_validation = validate_agentic_service_harness_read_models(
        schema_path=schema_path,
        example_paths=(example_path,),
    )
    errors.extend(f"source read model: {error}" for error in source_validation.errors)
    source_read_model = _load_json_object(example_path, errors)

    duplicate_rejected = False
    secret_rejected = False
    rebuilt_matches_source = False
    persisted_record_count = 0
    replayed_record_count = 0
    chain_head = GENESIS_HASH

    if source_read_model:
        with TemporaryDirectory(prefix="mullusi-harness-read-model-") as temp_dir:
            store_path = Path(temp_dir) / "harness-read-model-store.jsonl"
            try:
                store = AppendOnlyHarnessReadModelStore(store_path)
                persist_read_model_records(source_read_model, store, causal_ref=_path_label(example_path))
                persisted_record_count = len(store.entries)
                chain_head = store.chain_head
                duplicate_rejected = _exercise_duplicate_rejection(source_read_model, store)
                secret_rejected = _exercise_secret_rejection(source_read_model, store)

                replayed_store = AppendOnlyHarnessReadModelStore(store_path)
                replayed_record_count = len(replayed_store.entries)
                replayed_read_model = rebuild_read_model(replayed_store.entries)
                schema = _load_json_object(schema_path, errors)
                if schema:
                    errors.extend(
                        f"replayed read model: {error}"
                        for error in _validate_schema_instance(schema, replayed_read_model)
                    )
                _validate_read_model_semantics(
                    replayed_read_model,
                    errors,
                    "replayed read model",
                )
                rebuilt_matches_source = replayed_read_model == source_read_model
                if not rebuilt_matches_source:
                    errors.append("replayed read model does not match source read model")
            except HarnessReadModelPersistenceError as exc:
                errors.append(f"persistence rehearsal failed: {exc}")

    if not duplicate_rejected:
        errors.append("duplicate record rejection was not observed")
    if not secret_rejected:
        errors.append("secret-like payload rejection was not observed")

    return AgenticServiceHarnessReadModelPersistenceValidation(
        ok=not errors,
        errors=tuple(errors),
        example_path=_path_label(example_path),
        schema_path=_path_label(schema_path),
        persisted_record_count=persisted_record_count,
        replayed_record_count=replayed_record_count,
        chain_head=chain_head,
        duplicate_rejected=duplicate_rejected,
        secret_rejected=secret_rejected,
        rebuilt_matches_source=rebuilt_matches_source,
    )


def persist_read_model_records(
    read_model: Mapping[str, Any],
    store: AppendOnlyHarnessReadModelStore,
    *,
    causal_ref: str,
) -> None:
    """Persist one read-model envelope as explicit append-only typed records."""
    scope = _required_object(read_model.get("projection_scope"), "projection_scope")
    tenant_id = str(scope.get("tenant_id", ""))
    project_id = str(scope.get("project_id", ""))
    header = {field_name: read_model[field_name] for field_name in HEADER_FIELDS}
    store.append(
        record_kind="report_header",
        record_id=str(read_model.get("report_id", "")),
        tenant_id=tenant_id,
        project_id=project_id,
        payload=header,
        causal_ref=causal_ref,
    )
    store.append(
        record_kind="projection_scope",
        record_id=project_id,
        tenant_id=tenant_id,
        project_id=project_id,
        payload=scope,
        causal_ref=causal_ref,
    )
    store.append(
        record_kind="durable_entity_bindings",
        record_id=project_id,
        tenant_id=tenant_id,
        project_id=project_id,
        payload=_required_object(read_model.get("durable_entity_bindings"), "durable_entity_bindings"),
        causal_ref=causal_ref,
    )
    for record_kind, (collection_name, id_field) in COLLECTION_ID_FIELDS.items():
        for record in _objects(read_model.get(collection_name)):
            store.append(
                record_kind=record_kind,
                record_id=str(record.get(id_field, "")),
                tenant_id=tenant_id,
                project_id=project_id,
                payload=record,
                causal_ref=causal_ref,
            )
    store.append(
        record_kind="permission_snapshot",
        record_id=project_id,
        tenant_id=tenant_id,
        project_id=project_id,
        payload=_required_object(read_model.get("permission_snapshot"), "permission_snapshot"),
        causal_ref=causal_ref,
    )


def rebuild_read_model(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rebuild a read-model envelope from append-only rehearsal entries."""
    by_kind: dict[str, list[Mapping[str, Any]]] = {kind: [] for kind in ALLOWED_RECORD_KINDS}
    for entry in entries:
        by_kind.setdefault(str(entry["record_kind"]), []).append(entry)

    header = _single_payload(by_kind["report_header"], "report_header")
    projection_scope = _single_payload(by_kind["projection_scope"], "projection_scope")
    durable_entity_bindings = _single_payload(
        by_kind["durable_entity_bindings"],
        "durable_entity_bindings",
    )
    permission_snapshot = _single_payload(by_kind["permission_snapshot"], "permission_snapshot")
    rebuilt: dict[str, Any] = {field_name: header[field_name] for field_name in HEADER_FIELDS}
    rebuilt["projection_scope"] = projection_scope
    for record_kind, (collection_name, _id_field) in COLLECTION_ID_FIELDS.items():
        rebuilt[collection_name] = [dict(entry["payload"]) for entry in by_kind[record_kind]]
    rebuilt["durable_entity_bindings"] = durable_entity_bindings
    rebuilt["permission_snapshot"] = permission_snapshot
    return rebuilt


def write_agentic_service_harness_read_model_persistence_validation(
    validation: AgenticServiceHarnessReadModelPersistenceValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic persistence rehearsal validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_loaded_entry(
    entry: Mapping[str, Any],
    line_number: int,
    expected_previous_hash: str,
    seen_keys: set[tuple[str, str]],
) -> None:
    unexpected = sorted(set(entry) - ENTRY_KEYS)
    missing = sorted(ENTRY_KEYS - set(entry))
    if unexpected:
        raise HarnessReadModelPersistenceError(f"line {line_number} has unexpected fields: {unexpected}")
    if missing:
        raise HarnessReadModelPersistenceError(f"line {line_number} missing fields: {missing}")
    if entry["sequence"] != line_number:
        raise HarnessReadModelPersistenceError(f"line {line_number} sequence mismatch")
    record_kind = str(entry["record_kind"])
    record_id = str(entry["record_id"])
    if record_kind not in ALLOWED_RECORD_KINDS:
        raise HarnessReadModelPersistenceError(f"line {line_number} unsupported record_kind: {record_kind}")
    if (record_kind, record_id) in seen_keys:
        raise HarnessReadModelPersistenceError(f"line {line_number} duplicate record: {record_kind}:{record_id}")
    seen_keys.add((record_kind, record_id))
    payload = entry["payload"]
    if not isinstance(payload, dict):
        raise HarnessReadModelPersistenceError(f"line {line_number} payload must be an object")
    _reject_sensitive_payload(payload)
    if entry["payload_hash"] != canonical_hash(payload):
        raise HarnessReadModelPersistenceError(f"line {line_number} payload_hash mismatch")
    if entry["previous_entry_hash"] != expected_previous_hash:
        raise HarnessReadModelPersistenceError(f"line {line_number} previous_entry_hash mismatch")
    entry_without_hash = dict(entry)
    entry_hash = entry_without_hash.pop("entry_hash")
    if entry_hash != canonical_hash(entry_without_hash):
        raise HarnessReadModelPersistenceError(f"line {line_number} entry_hash mismatch")


def _reject_sensitive_payload(payload: Any, path: str = "payload") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower not in ALLOWED_SECRET_KEYS and any(
                token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS
            ):
                raise HarnessReadModelPersistenceError(f"forbidden sensitive key at {path}.{key_text}")
            _reject_sensitive_payload(value, f"{path}.{key_text}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _reject_sensitive_payload(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
            if pattern.search(payload):
                raise HarnessReadModelPersistenceError(f"forbidden sensitive value at {path}")


def _exercise_duplicate_rejection(
    read_model: Mapping[str, Any],
    store: AppendOnlyHarnessReadModelStore,
) -> bool:
    scope = _required_object(read_model.get("projection_scope"), "projection_scope")
    try:
        store.append(
            record_kind="projection_scope",
            record_id=str(scope.get("project_id", "")),
            tenant_id=str(scope.get("tenant_id", "")),
            project_id=str(scope.get("project_id", "")),
            payload=scope,
            causal_ref="duplicate-rejection-rehearsal",
        )
    except HarnessReadModelPersistenceError:
        return True
    return False


def _exercise_secret_rejection(
    read_model: Mapping[str, Any],
    store: AppendOnlyHarnessReadModelStore,
) -> bool:
    scope = _required_object(read_model.get("projection_scope"), "projection_scope")
    try:
        store.append(
            record_kind="receipt",
            record_id="receipt-secret-rejection",
            tenant_id=str(scope.get("tenant_id", "")),
            project_id=str(scope.get("project_id", "")),
            payload={"receipt_id": "receipt-secret-rejection", "access_token": "ghp_forbidden"},
            causal_ref="secret-rejection-rehearsal",
        )
    except HarnessReadModelPersistenceError:
        return True
    return False


def _single_payload(entries: Sequence[Mapping[str, Any]], record_kind: str) -> dict[str, Any]:
    if len(entries) != 1:
        raise HarnessReadModelPersistenceError(f"{record_kind} requires exactly one record")
    payload = entries[0].get("payload")
    if not isinstance(payload, dict):
        raise HarnessReadModelPersistenceError(f"{record_kind} payload must be an object")
    return dict(payload)


def _required_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HarnessReadModelPersistenceError(f"{label} must be an object")
    return dict(value)


def _objects(value: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(value, list):
        raise HarnessReadModelPersistenceError("read-model collection must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise HarnessReadModelPersistenceError("read-model collection item must be an object")
        yield dict(item)


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{_path_label(path)} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{_path_label(path)} must be a JSON object")
        return {}
    return payload


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the read-model persistence rehearsal validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_agentic_service_harness_read_model_persistence(
        example_path=args.example,
        schema_path=args.schema,
    )
    if args.write_report:
        write_agentic_service_harness_read_model_persistence_validation(
            validation,
            args.output,
        )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ MODEL PERSISTENCE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ MODEL PERSISTENCE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
