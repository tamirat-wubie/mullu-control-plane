"""Package verified OrgOS event artifacts into a terminal trust-ledger anchor export.

Purpose: merge optional, verified OrgOS event-receipt artifacts with a real
    terminal trust-ledger bundle and emit the standard anchor export files.
Governance scope: OrgOS evidence attachment to terminal closure anchoring only.
Dependencies: gateway.trust_ledger and trust-ledger JSON schemas.
Invariants:
  - OrgOS artifacts are supporting evidence only; they are never terminal closure.
  - A terminal trust-ledger bundle and required terminal artifacts must already exist.
  - Duplicate artifact identities fail closed.
  - Generated export payloads are schema-validated before any output publish.
  - Output publish stages all files and rolls back partial replaces on failure.
  - Output uses the canonical trust-ledger bundle, anchor receipt, artifacts, and package files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.trust_ledger import TrustLedger, TrustLedgerBundle, TrustLedgerEvidenceArtifact  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"
ANCHOR_RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_anchor_receipt.schema.json"
ARTIFACTS_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_evidence_artifacts.schema.json"
PACKAGE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_export_package.schema.json"


def package_orgos_anchor_export(
    *,
    bundle_path: Path,
    base_artifacts_path: Path,
    orgos_artifacts_path: Path,
    output_dir: Path,
    anchor_target: str,
    external_anchor_ref: str,
    external_anchor_status: str,
    anchored_at: str,
    signing_secret: str,
    signature_key_id: str,
    created_at: str,
    strict: bool = False,
) -> dict[str, Any]:
    """Create a standard trust-ledger anchor export that includes OrgOS evidence."""
    if not signing_secret:
        return _report(valid=False, reason="signing_secret_required")
    bundle_payload = _read_json_object(bundle_path, "bundle")
    base_payload = _read_json_array(base_artifacts_path, "base_artifacts")
    orgos_payload = _read_json_array(orgos_artifacts_path, "orgos_artifacts")
    read_error = _first_error(bundle_payload, base_payload, orgos_payload)
    if read_error:
        return _report(valid=False, **read_error)

    schema_errors = _schema_errors(
        bundle_payload["payload"],
        base_payload["payload"],
        orgos_payload["payload"],
    )
    if schema_errors:
        return _report(
            valid=False,
            reason="schema_validation_failed",
            schema_valid=False,
            schema_errors=schema_errors if strict else schema_errors[:10],
        )
    try:
        bundle = _bundle_from_payload(bundle_payload["payload"])
        base_artifacts = _artifacts_from_payload(base_payload["payload"])
        orgos_artifacts = _artifacts_from_payload(orgos_payload["payload"])
        _require_orgos_artifacts(orgos_artifacts)
        merged_artifacts = _merge_artifacts(base_artifacts, orgos_artifacts)
        receipt = TrustLedger().anchor_bundle(
            bundle,
            artifacts=merged_artifacts,
            anchor_target=anchor_target,
            external_anchor_ref=external_anchor_ref,
            external_anchor_status=external_anchor_status,
            anchored_at=anchored_at,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
        )
        package = TrustLedger().package_anchor_export(
            bundle=bundle,
            receipt=receipt,
            artifacts=merged_artifacts,
            created_at=created_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _report(valid=False, reason=str(exc), schema_valid=True)

    bundle_output = bundle.to_json_dict()
    receipt_output = receipt.to_json_dict()
    artifacts_output = [artifact.to_json_dict() for artifact in merged_artifacts]
    package_output = package.to_json_dict()
    package_errors = _validate_schema_instance(_load_schema(PACKAGE_SCHEMA_PATH), package_output)
    if package_errors:
        return _report(
            valid=False,
            reason="package_schema_validation_failed",
            schema_valid=True,
            schema_errors=package_errors,
            bundle_id=bundle.bundle_id,
            anchor_receipt_id=receipt.anchor_receipt_id,
            package_id=package.package_id,
            artifact_count=len(merged_artifacts),
            orgos_artifact_count=len(orgos_artifacts),
        )
    output_schema_errors = _generated_export_schema_errors(
        bundle_output=bundle_output,
        receipt_output=receipt_output,
        artifacts_output=artifacts_output,
    )
    if output_schema_errors:
        return _report(
            valid=False,
            reason="generated_export_schema_validation_failed",
            schema_valid=True,
            schema_errors=output_schema_errors if strict else output_schema_errors[:10],
            bundle_id=bundle.bundle_id,
            anchor_receipt_id=receipt.anchor_receipt_id,
            package_id=package.package_id,
            artifact_count=len(merged_artifacts),
            orgos_artifact_count=len(orgos_artifacts),
        )
    try:
        output_files = _publish_anchor_export_files(
            output_dir,
            bundle_output=bundle_output,
            receipt_output=receipt_output,
            artifacts_output=artifacts_output,
            package_output=package_output,
        )
    except RuntimeError as exc:
        return _report(
            valid=False,
            reason=str(exc),
            schema_valid=True,
            bundle_id=bundle.bundle_id,
            anchor_receipt_id=receipt.anchor_receipt_id,
            package_id=package.package_id,
            artifact_count=len(merged_artifacts),
            orgos_artifact_count=len(orgos_artifacts),
        )
    return _report(
        valid=True,
        reason="packaged",
        schema_valid=True,
        schema_errors=[],
        bundle_id=bundle.bundle_id,
        anchor_receipt_id=receipt.anchor_receipt_id,
        package_id=package.package_id,
        artifact_count=len(merged_artifacts),
        orgos_artifact_count=len(orgos_artifacts),
        output_files=output_files,
    )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    loaded = _read_json(path, label)
    if loaded.get("reason"):
        return loaded
    if not isinstance(loaded["payload"], dict):
        return {
            "valid": False,
            "reason": f"{label}_json_must_be_object",
            "schema_valid": False,
            "schema_errors": [f"{label} JSON must be an object"],
        }
    return loaded


def _read_json_array(path: Path, label: str) -> dict[str, Any]:
    loaded = _read_json(path, label)
    if loaded.get("reason"):
        return loaded
    if not isinstance(loaded["payload"], list):
        return {
            "valid": False,
            "reason": f"{label}_json_must_be_array",
            "schema_valid": False,
            "schema_errors": [f"{label} JSON must be an array"],
        }
    return loaded


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return {"reason": "", "payload": json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "valid": False,
            "reason": f"{label}_read_failed",
            "schema_valid": False,
            "schema_errors": [type(exc).__name__],
        }


def _first_error(*loaded_payloads: dict[str, Any]) -> dict[str, Any] | None:
    for loaded in loaded_payloads:
        if loaded.get("reason"):
            return {
                "reason": str(loaded["reason"]),
                "schema_valid": bool(loaded.get("schema_valid", False)),
                "schema_errors": list(loaded.get("schema_errors", [])),
            }
    return None


def _schema_errors(
    bundle_payload: dict[str, Any],
    base_artifacts_payload: list[Any],
    orgos_artifacts_payload: list[Any],
) -> list[str]:
    errors = [
        f"bundle:{error}"
        for error in _validate_schema_instance(_load_schema(BUNDLE_SCHEMA_PATH), bundle_payload)
    ]
    errors.extend(
        f"base_artifacts:{error}"
        for error in _validate_schema_instance(_load_schema(ARTIFACTS_SCHEMA_PATH), base_artifacts_payload)
    )
    errors.extend(
        f"orgos_artifacts:{error}"
        for error in _validate_schema_instance(_load_schema(ARTIFACTS_SCHEMA_PATH), orgos_artifacts_payload)
    )
    return errors


def _generated_export_schema_errors(
    *,
    bundle_output: dict[str, Any],
    receipt_output: dict[str, Any],
    artifacts_output: list[Any],
) -> list[str]:
    errors = [
        f"bundle:{error}"
        for error in _validate_schema_instance(_load_schema(BUNDLE_SCHEMA_PATH), bundle_output)
    ]
    errors.extend(
        f"anchor_receipt:{error}"
        for error in _validate_schema_instance(_load_schema(ANCHOR_RECEIPT_SCHEMA_PATH), receipt_output)
    )
    errors.extend(
        f"artifacts:{error}"
        for error in _validate_schema_instance(_load_schema(ARTIFACTS_SCHEMA_PATH), artifacts_output)
    )
    return errors


def _bundle_from_payload(payload: dict[str, Any]) -> TrustLedgerBundle:
    return TrustLedgerBundle(
        bundle_id=str(payload["bundle_id"]),
        tenant_id=str(payload["tenant_id"]),
        command_id=str(payload["command_id"]),
        terminal_certificate_id=str(payload["terminal_certificate_id"]),
        deployment_id=str(payload["deployment_id"]),
        commit_sha=str(payload["commit_sha"]),
        hash_chain_root=str(payload["hash_chain_root"]),
        evidence_refs=list(payload["evidence_refs"]),
        issued_at=str(payload["issued_at"]),
        external_anchor_ref=str(payload["external_anchor_ref"]),
        external_anchor_status=str(payload["external_anchor_status"]),
        bundle_hash=str(payload["bundle_hash"]),
        signature_key_id=str(payload["signature_key_id"]),
        signature=str(payload["signature"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _artifacts_from_payload(payload: list[Any]) -> tuple[TrustLedgerEvidenceArtifact, ...]:
    artifacts: list[TrustLedgerEvidenceArtifact] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"artifact_{index}_json_must_be_object")
        artifacts.append(
            TrustLedgerEvidenceArtifact(
                artifact_type=str(item["artifact_type"]),
                artifact_id=str(item["artifact_id"]),
                artifact_hash=str(item["artifact_hash"]),
                evidence_ref=str(item["evidence_ref"]),
                required=bool(item.get("required", True)),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return tuple(artifacts)


def _require_orgos_artifacts(artifacts: tuple[TrustLedgerEvidenceArtifact, ...]) -> None:
    if not artifacts:
        raise ValueError("orgos_event_receipt_artifact_required")
    for artifact in artifacts:
        if artifact.artifact_type != "orgos_event_receipt":
            raise ValueError("orgos_artifact_type_invalid")
        if artifact.required:
            raise ValueError("orgos_event_receipt_must_be_optional")
        if artifact.metadata.get("event_receipt_is_not_terminal_closure") is not True:
            raise ValueError("orgos_event_receipt_non_terminal_marker_required")


def _merge_artifacts(
    base_artifacts: tuple[TrustLedgerEvidenceArtifact, ...],
    orgos_artifacts: tuple[TrustLedgerEvidenceArtifact, ...],
) -> tuple[TrustLedgerEvidenceArtifact, ...]:
    seen: set[tuple[str, str]] = set()
    merged: list[TrustLedgerEvidenceArtifact] = []
    for artifact in (*base_artifacts, *orgos_artifacts):
        key = (artifact.artifact_type, artifact.artifact_id)
        if key in seen:
            raise ValueError("duplicate_trust_ledger_artifact_identity")
        seen.add(key)
        merged.append(artifact)
    return tuple(merged)


def _report(
    *,
    valid: bool,
    reason: str,
    schema_valid: bool = True,
    schema_errors: list[str] | None = None,
    bundle_id: str = "",
    anchor_receipt_id: str = "",
    package_id: str = "",
    artifact_count: int = 0,
    orgos_artifact_count: int = 0,
    output_files: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors or [],
        "bundle_id": bundle_id,
        "anchor_receipt_id": anchor_receipt_id,
        "package_id": package_id,
        "artifact_count": artifact_count,
        "orgos_artifact_count": orgos_artifact_count,
        "output_files": output_files or {},
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _publish_anchor_export_files(
    output_dir: Path,
    *,
    bundle_output: dict[str, Any],
    receipt_output: dict[str, Any],
    artifacts_output: list[Any],
    package_output: dict[str, Any],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_payloads: tuple[tuple[str, str, Any], ...] = (
        ("bundle", "bundle.json", bundle_output),
        ("anchor_receipt", "anchor_receipt.json", receipt_output),
        ("artifacts", "artifacts.json", artifacts_output),
        ("package", "package.json", package_output),
    )
    marker = _publish_marker(file_payloads)
    staged_paths: dict[str, Path] = {}
    output_paths: dict[str, Path] = {}
    backup_paths: dict[Path, Path] = {}
    replaced_paths: set[Path] = set()
    created_paths: set[Path] = set()
    try:
        for label, file_name, payload in file_payloads:
            staged_path = output_dir / f".{file_name}.{marker}.tmp"
            _write_json(staged_path, payload)
            staged_paths[label] = staged_path
            output_paths[label] = output_dir / file_name
        for label, target_path in output_paths.items():
            if target_path.exists():
                backup_path = output_dir / f".{target_path.name}.{marker}.bak"
                os.replace(target_path, backup_path)
                backup_paths[target_path] = backup_path
            else:
                created_paths.add(target_path)
            os.replace(staged_paths[label], target_path)
            replaced_paths.add(target_path)
        for backup_path in backup_paths.values():
            backup_path.unlink(missing_ok=True)
    except OSError as exc:
        rollback_errors = _rollback_anchor_export_publish(
            staged_paths=tuple(staged_paths.values()),
            backup_paths=backup_paths,
            replaced_paths=replaced_paths,
            created_paths=created_paths,
        )
        reason = f"anchor_export_publish_failed:{type(exc).__name__}"
        if rollback_errors:
            reason = f"{reason}:rollback_failed:{','.join(rollback_errors)}"
        raise RuntimeError(reason) from exc
    return {label: str(path) for label, path in output_paths.items()}


def _rollback_anchor_export_publish(
    *,
    staged_paths: tuple[Path, ...],
    backup_paths: dict[Path, Path],
    replaced_paths: set[Path],
    created_paths: set[Path],
) -> list[str]:
    errors: list[str] = []
    for staged_path in staged_paths:
        errors.extend(_unlink_safely(staged_path))
    for target_path in replaced_paths:
        errors.extend(_unlink_safely(target_path))
    for target_path, backup_path in backup_paths.items():
        if backup_path.exists():
            try:
                os.replace(backup_path, target_path)
            except OSError as exc:
                errors.append(f"restore:{target_path.name}:{type(exc).__name__}")
    for target_path in created_paths:
        if target_path.exists():
            errors.extend(_unlink_safely(target_path))
    for backup_path in backup_paths.values():
        errors.extend(_unlink_safely(backup_path))
    return errors


def _unlink_safely(path: Path) -> list[str]:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        return [f"unlink:{path.name}:{type(exc).__name__}"]
    return []


def _publish_marker(file_payloads: tuple[tuple[str, str, Any], ...]) -> str:
    payload = {
        "pid": os.getpid(),
        "files": [(label, file_name, payload) for label, file_name, payload in file_payloads],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package OrgOS evidence into a trust-ledger anchor export")
    parser.add_argument("--bundle", required=True, type=Path, help="Path to a signed terminal trust-ledger bundle JSON")
    parser.add_argument("--base-artifacts", required=True, type=Path, help="Path to required terminal artifact array JSON")
    parser.add_argument("--orgos-artifacts", required=True, type=Path, help="Path to verified OrgOS artifact array JSON")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for bundle, receipt, artifacts, and package files")
    parser.add_argument("--anchor-target", default="transparency_log")
    parser.add_argument("--external-anchor-ref", default="")
    parser.add_argument("--external-anchor-status", default="pending")
    parser.add_argument("--anchored-at", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument(
        "--signing-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_SECRET", ""),
        help="HMAC signing secret; defaults to MULLU_TRUST_LEDGER_ANCHOR_SECRET",
    )
    parser.add_argument(
        "--signature-key-id",
        default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_KEY_ID", "anchor-key"),
    )
    parser.add_argument("--strict", action="store_true", help="Return all schema errors")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    report = package_orgos_anchor_export(
        bundle_path=args.bundle,
        base_artifacts_path=args.base_artifacts,
        orgos_artifacts_path=args.orgos_artifacts,
        output_dir=args.output_dir,
        anchor_target=args.anchor_target,
        external_anchor_ref=args.external_anchor_ref,
        external_anchor_status=args.external_anchor_status,
        anchored_at=args.anchored_at,
        signing_secret=args.signing_secret,
        signature_key_id=args.signature_key_id,
        created_at=args.created_at,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "packaged" if report["valid"] else "invalid"
        print(f"orgos anchor export {status}: {report['reason']}")
        if report.get("package_id"):
            print(f"package_id: {report['package_id']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
