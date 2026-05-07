#!/usr/bin/env python3
"""Static authority directory sync adapter.

Purpose: normalize a static YAML or JSON authority directory file into the
directory sync batch and receipt described by docs/54_authority_directory_sync.md.
Governance scope: ownership bindings, approval policies, escalation policies,
source evidence, duplicate rejection, and deterministic receipt generation.
Dependencies: standard-library JSON, hashing, argparse, pathlib.
Invariants:
  - Source file content is hashed before parsing.
  - Missing tenant/source identity rejects the batch.
  - Duplicate ownership, approval policy, or escalation policy keys are rejected.
  - Store writes happen only when apply mode is explicitly requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gateway.authority_obligation_mesh import (
    ApprovalPolicy,
    AuthorityObligationMeshStore,
    EscalationPolicy,
    TeamOwnership,
    build_authority_obligation_mesh_store_from_env,
)


@dataclass(frozen=True, slots=True)
class DirectorySyncReceipt:
    """Deterministic receipt for one static authority directory sync batch."""

    receipt_id: str
    tenant_id: str
    batch_id: str
    source_system: str
    source_ref: str
    source_hash: str
    applied_ownership_count: int
    applied_approval_policy_count: int
    applied_escalation_policy_count: int
    rejected_record_count: int
    apply_mode: str = "dry_run"
    persisted: bool = False
    rejected_records: tuple[dict[str, str], ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = (
        "authority:ownership_read_model",
        "authority:policy_read_model",
        "runtime_conformance:authority_configuration",
    )

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable receipt payload."""
        payload = asdict(self)
        payload["rejected_records"] = [dict(item) for item in self.rejected_records]
        return payload


def sync_static_authority_directory(source_path: Path) -> tuple[dict[str, Any], DirectorySyncReceipt]:
    """Load one static directory file and return normalized batch plus receipt."""
    resolved_source_path = source_path.resolve()
    raw_text = resolved_source_path.read_text(encoding="utf-8")
    source_hash = f"sha256:{_sha256(raw_text)}"
    parsed = _parse_static_document(raw_text)
    tenant_id = _required_text(parsed, "tenant_id")
    source_system = str(parsed.get("source_system") or "static_yaml")
    source_ref = str(parsed.get("source_ref") or resolved_source_path.as_uri())
    batch_seed = {
        "tenant_id": tenant_id,
        "source_system": source_system,
        "source_ref": source_ref,
        "source_hash": source_hash,
    }
    batch_id = str(parsed.get("batch_id") or f"directory-batch-{_stable_hash(batch_seed)[:16]}")

    ownership, rejected_ownership = _normalize_records(
        parsed.get("ownership_bindings", ()),
        record_type="ownership_binding",
        required_fields=("resource_ref", "owner_team", "primary_owner_id", "fallback_owner_id", "escalation_team"),
        key_fields=("resource_ref",),
    )
    approval_policies, rejected_approval = _normalize_records(
        parsed.get("approval_policies", ()),
        record_type="approval_policy",
        required_fields=(
            "policy_id",
            "capability",
            "risk_tier",
            "required_roles",
            "required_approver_count",
            "separation_of_duty",
            "timeout_seconds",
            "escalation_policy_id",
        ),
        key_fields=("policy_id",),
    )
    escalation_policies, rejected_escalation = _normalize_records(
        parsed.get("escalation_policies", ()),
        record_type="escalation_policy",
        required_fields=(
            "policy_id",
            "notify_after_seconds",
            "escalate_after_seconds",
            "incident_after_seconds",
            "fallback_owner_id",
            "escalation_team",
        ),
        key_fields=("policy_id",),
    )
    normalized_batch = {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "source_system": source_system,
        "source_ref": source_ref,
        "source_hash": source_hash,
        "people": tuple(parsed.get("people", ())),
        "teams": tuple(parsed.get("teams", ())),
        "role_assignments": tuple(parsed.get("role_assignments", ())),
        "ownership_bindings": tuple({**item, "tenant_id": tenant_id} for item in ownership),
        "approval_policies": tuple({**item, "tenant_id": tenant_id} for item in approval_policies),
        "escalation_policies": tuple({**item, "tenant_id": tenant_id} for item in escalation_policies),
    }
    rejected = (*rejected_ownership, *rejected_approval, *rejected_escalation)
    receipt_seed = {
        "batch_id": batch_id,
        "source_hash": source_hash,
        "applied_ownership_count": len(ownership),
        "applied_approval_policy_count": len(approval_policies),
        "applied_escalation_policy_count": len(escalation_policies),
        "rejected_records": rejected,
    }
    receipt = DirectorySyncReceipt(
        receipt_id=f"authority-directory-sync-{_stable_hash(receipt_seed)[:16]}",
        tenant_id=tenant_id,
        batch_id=batch_id,
        source_system=source_system,
        source_ref=source_ref,
        source_hash=source_hash,
        applied_ownership_count=len(ownership),
        applied_approval_policy_count=len(approval_policies),
        applied_escalation_policy_count=len(escalation_policies),
        rejected_record_count=len(rejected),
        rejected_records=tuple(rejected),
    )
    return normalized_batch, receipt


def write_sync_receipt(receipt: DirectorySyncReceipt, output_path: Path) -> Path:
    """Write one directory sync receipt JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_normalized_batch(batch: dict[str, Any], output_path: Path) -> Path:
    """Write one replayable normalized authority directory batch."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(batch, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def mark_receipt_persisted(receipt: DirectorySyncReceipt) -> DirectorySyncReceipt:
    """Return a receipt variant that records successful apply-mode persistence."""
    return DirectorySyncReceipt(
        receipt_id=receipt.receipt_id,
        tenant_id=receipt.tenant_id,
        batch_id=receipt.batch_id,
        source_system=receipt.source_system,
        source_ref=receipt.source_ref,
        source_hash=receipt.source_hash,
        applied_ownership_count=receipt.applied_ownership_count,
        applied_approval_policy_count=receipt.applied_approval_policy_count,
        applied_escalation_policy_count=receipt.applied_escalation_policy_count,
        apply_mode="apply",
        persisted=True,
        rejected_record_count=receipt.rejected_record_count,
        rejected_records=receipt.rejected_records,
        evidence_refs=receipt.evidence_refs,
    )


def apply_static_authority_directory(
    batch: dict[str, Any],
    store: AuthorityObligationMeshStore,
) -> None:
    """Persist accepted static directory records through authority mesh store contracts."""
    for ownership in batch["ownership_bindings"]:
        store.save_ownership(TeamOwnership(
            tenant_id=str(ownership["tenant_id"]),
            resource_ref=str(ownership["resource_ref"]),
            owner_team=str(ownership["owner_team"]),
            primary_owner_id=str(ownership["primary_owner_id"]),
            fallback_owner_id=str(ownership["fallback_owner_id"]),
            escalation_team=str(ownership["escalation_team"]),
        ))
    for policy in batch["approval_policies"]:
        store.save_approval_policy(ApprovalPolicy(
            policy_id=str(policy["policy_id"]),
            tenant_id=str(policy["tenant_id"]),
            capability=str(policy["capability"]),
            risk_tier=str(policy["risk_tier"]),
            required_roles=tuple(str(role) for role in policy["required_roles"]),
            required_approver_count=int(policy["required_approver_count"]),
            separation_of_duty=bool(policy["separation_of_duty"]),
            timeout_seconds=int(policy["timeout_seconds"]),
            escalation_policy_id=str(policy["escalation_policy_id"]),
        ))
    for policy in batch["escalation_policies"]:
        store.save_escalation_policy(EscalationPolicy(
            policy_id=str(policy["policy_id"]),
            tenant_id=str(policy["tenant_id"]),
            notify_after_seconds=int(policy["notify_after_seconds"]),
            escalate_after_seconds=int(policy["escalate_after_seconds"]),
            incident_after_seconds=int(policy["incident_after_seconds"]),
            fallback_owner_id=str(policy["fallback_owner_id"]),
            escalation_team=str(policy["escalation_team"]),
        ))


def _parse_static_document(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("static directory root must be mapping")
    except json.JSONDecodeError:
        pass
    return _parse_bounded_yaml(raw_text)


def _parse_bounded_yaml(raw_text: str) -> dict[str, Any]:
    document: dict[str, Any] = {}
    current_key = ""
    current_item: dict[str, Any] | None = None
    for raw_line in raw_text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            current_item = None
            if value.strip():
                document[current_key] = _parse_scalar(value.strip())
            else:
                document[current_key] = []
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if not current_key:
                raise ValueError("list item without parent key")
            item_text = stripped[2:].strip()
            current_item = {}
            document.setdefault(current_key, []).append(current_item)
            if item_text:
                key, value = _split_mapping_line(item_text)
                current_item[key] = _parse_scalar(value)
            continue
        if current_item is not None and ":" in stripped:
            key, value = _split_mapping_line(stripped)
            current_item[key] = _parse_scalar(value)
            continue
        raise ValueError("unsupported static directory YAML line")
    return document


def _split_mapping_line(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError("expected static directory mapping line")
    key, value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ValueError("mapping key is required")
    return key, value.strip()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return tuple(_parse_scalar(part.strip()) for part in inner.split(","))
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _normalize_records(
    raw_records: Any,
    *,
    record_type: str,
    required_fields: tuple[str, ...],
    key_fields: tuple[str, ...],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, str], ...]]:
    if raw_records in (None, ""):
        return (), ()
    if not isinstance(raw_records, (list, tuple)):
        return (), ({"record_type": record_type, "reason": "records_must_be_list"},)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            rejected.append({"record_type": record_type, "index": str(index), "reason": "record_must_be_mapping"})
            continue
        missing = tuple(field for field in required_fields if field not in raw_record or raw_record[field] in ("", ()))
        if missing:
            rejected.append({
                "record_type": record_type,
                "index": str(index),
                "reason": f"missing_fields:{','.join(missing)}",
            })
            continue
        key = tuple(str(raw_record[field]) for field in key_fields)
        if key in seen_keys:
            rejected.append({"record_type": record_type, "index": str(index), "reason": "duplicate_key"})
            continue
        seen_keys.add(key)
        accepted.append(dict(raw_record))
    return tuple(accepted), tuple(rejected)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _stable_hash(payload: dict[str, Any]) -> str:
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the static authority directory sync CLI contract."""
    parser = argparse.ArgumentParser(description="Normalize a static authority directory file.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--receipt-output", type=Path, default=Path(".change_assurance/authority_directory_sync.json"))
    parser.add_argument("--batch-output", type=Path, help="Write the normalized batch for replay and review.")
    parser.add_argument("--apply", action="store_true", help="Persist accepted records through the authority mesh store.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for static authority directory sync."""
    args = parse_args(argv)
    try:
        batch, receipt = sync_static_authority_directory(args.source)
        if args.batch_output:
            batch_written = write_normalized_batch(batch, args.batch_output)
            print(f"authority directory normalized batch written: {batch_written}")
        if args.apply:
            apply_static_authority_directory(batch, build_authority_obligation_mesh_store_from_env())
            receipt = mark_receipt_persisted(receipt)
        written = write_sync_receipt(receipt, args.receipt_output)
        print(f"authority directory sync receipt written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"authority directory sync failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "source_unavailable"
    message = str(exc)
    if message in {
        "unsupported static directory YAML line",
        "static directory file must be JSON or YAML",
        "static directory JSON root must be mapping",
        "static directory YAML root must be mapping",
        "static directory source must be a mapping",
    }:
        return message
    return "invalid_static_directory"


if __name__ == "__main__":
    raise SystemExit(main())
