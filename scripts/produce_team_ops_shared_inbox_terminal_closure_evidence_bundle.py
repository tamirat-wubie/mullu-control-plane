#!/usr/bin/env python3
"""Produce a TeamOps shared inbox terminal closure evidence bundle.

Purpose: sign a ready TeamOps terminal closure certificate into the canonical
trust-ledger bundle schema without external anchoring or production promotion.
Governance scope: TeamOps terminal closure, trust-ledger bundle signing,
certificate binding, evidence-ref canonicalization, and no-production-claim
constraints.
Dependencies: gateway.trust_ledger, schemas/trust_ledger_bundle.schema.json,
and scripts.validate_team_ops_shared_inbox_terminal_closure_certificate.
Invariants:
  - Only ready TeamOps terminal closure certificates can produce bundles.
  - Provider-observation receipt identity is preserved from the certificate.
  - Bundle evidence refs use the canonical proof:// scheme.
  - The signing secret is required but never serialized.
  - The bundle does not request external anchoring or claim production readiness.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.trust_ledger import TrustLedger, TrustLedgerBundleDraft  # noqa: E402
from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CERTIFICATE,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_REVIEW_PACKET,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_certificate,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "trust_ledger_bundle.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_evidence_bundle.json"
DEFAULT_TENANT_ID = "foundation-local-teamops"
DEFAULT_DEPLOYMENT_ID = "foundation-local-teamops-terminal-closure"
DEFAULT_SIGNATURE_KEY_ID = "teamops-local-trust-ledger-key"
WORKFLOW_ID = "team_ops.shared_inbox_triage"
SCHEMA_ID = "urn:mullusi:schema:trust-ledger-bundle:1"


def produce_team_ops_shared_inbox_terminal_closure_evidence_bundle(
    *,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
    signing_secret: str,
    signature_key_id: str = DEFAULT_SIGNATURE_KEY_ID,
    tenant_id: str = DEFAULT_TENANT_ID,
    deployment_id: str = DEFAULT_DEPLOYMENT_ID,
    commit_sha: str | None = None,
    issued_at: str | None = None,
) -> dict[str, Any]:
    """Produce one signed TeamOps terminal closure evidence bundle."""

    if not signing_secret:
        raise ValueError("TeamOps terminal closure evidence bundle signing secret is required")
    certificate_validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=source_review_packet_path,
        require_ready=True,
    )
    if not certificate_validation.valid or not certificate_validation.ready:
        raise RuntimeError("TeamOps terminal closure certificate not ready for evidence bundle signing")
    certificate = _load_json_object(certificate_path, "TeamOps terminal closure certificate")
    _assert_redacted(certificate)
    certificate_metadata = certificate.get("metadata", {}) if isinstance(certificate.get("metadata"), dict) else {}
    certificate_hash = _stable_hash(certificate)
    draft = TrustLedgerBundleDraft(
        tenant_id=tenant_id,
        command_id=WORKFLOW_ID,
        terminal_certificate_id=str(certificate["certificate_id"]),
        deployment_id=deployment_id,
        commit_sha=commit_sha or _current_commit_sha(),
        hash_chain_root=certificate_hash,
        evidence_refs=tuple(_bundle_evidence_refs(certificate)),
        issued_at=issued_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        external_anchor_ref="",
        external_anchor_status="not_requested",
        metadata={
            "source": "team_ops_shared_inbox_terminal_closure_evidence_bundle",
            "team_ops_terminal_closure_bundle": True,
            "source_certificate_path": _artifact_ref(certificate_path),
            "source_review_packet_path": _artifact_ref(source_review_packet_path),
            "source_certificate_hash": certificate_hash,
            "source_review_packet_id": str(certificate_metadata.get("source_review_packet_id", "")),
            "source_review_packet_hash": str(certificate_metadata.get("source_review_packet_hash", "")),
            "provider_observation_receipt_ref": str(certificate_metadata.get("provider_observation_receipt_ref", "")),
            "provider_observation_receipt_id": str(certificate_metadata.get("provider_observation_receipt_id", "")),
            "provider_observation_receipt_valid": (
                certificate_metadata.get("provider_observation_receipt_valid") is True
            ),
            "bundle_schema_id": SCHEMA_ID,
            "external_anchor_requested_by_producer": False,
            "external_message_sent_by_producer": False,
            "external_mailbox_write_performed_by_producer": False,
            "provider_mutation_performed_by_producer": False,
            "provider_call_performed_by_producer": False,
            "raw_message_content_serialized": False,
            "raw_provider_payload_serialized": False,
            "no_secret_values_serialized": True,
            "production_ready_claimed": False,
        },
    )
    bundle = TrustLedger().issue(
        draft,
        signing_secret=signing_secret,
        signature_key_id=signature_key_id,
    ).to_json_dict()
    _assert_redacted(bundle)
    schema_errors = _validate_schema_instance(_load_schema(schema_path), bundle)
    if schema_errors:
        raise RuntimeError(f"TeamOps terminal closure evidence bundle schema validation failed: {schema_errors}")
    return bundle


def write_team_ops_shared_inbox_terminal_closure_evidence_bundle(
    bundle: Mapping[str, Any],
    output_path: Path,
) -> Path:
    """Write one TeamOps terminal closure evidence bundle."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _bundle_evidence_refs(certificate: Mapping[str, Any]) -> list[str]:
    metadata = certificate.get("metadata", {}) if isinstance(certificate.get("metadata"), dict) else {}
    refs = [
        _proof_ref("command", WORKFLOW_ID),
        _proof_ref("terminal-certificate", str(certificate.get("certificate_id", ""))),
        _proof_ref("verification-result", str(certificate.get("verification_result_id", ""))),
        _proof_ref("effect-reconciliation", str(certificate.get("effect_reconciliation_id", ""))),
        _proof_ref("terminal-review", str(metadata.get("source_review_packet_id", ""))),
        _proof_ref("sent-message-observation", str(metadata.get("source_sent_message_observation_receipt_id", ""))),
        _proof_ref("provider-observation", str(metadata.get("provider_observation_receipt_id", ""))),
    ]
    for ref in certificate.get("evidence_refs", ()):
        if isinstance(ref, str) and ref.strip():
            refs.append(_proof_ref("evidence-ref", _short_hash(ref)))
    return list(dict.fromkeys(refs))


def _proof_ref(kind: str, identity: str) -> str:
    cleaned_identity = identity.strip().replace("\\", "/")
    if not cleaned_identity:
        cleaned_identity = "missing"
    return f"proof://teamops/{kind}/{cleaned_identity}"


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _current_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown-local-commit"
    return result.stdout.strip() or "unknown-local-commit"


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing")
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _artifact_ref(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix().replace("\\", "/")
    resolved_path = path.resolve(strict=False)
    try:
        relative_label = os.path.relpath(str(resolved_path), str(REPO_ROOT)).replace(os.sep, "/")
    except ValueError:
        return path.name
    if relative_label == "." or relative_label.startswith("../") or relative_label.startswith("..\\"):
        return path.name
    return relative_label


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError(f"TeamOps terminal closure evidence bundle contains secret marker: {marker}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps terminal closure evidence bundle arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps terminal closure evidence bundle.")
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--signing-secret", default=os.environ.get("MULLU_TEAMOPS_TRUST_LEDGER_SECRET", ""))
    parser.add_argument("--signature-key-id", default=DEFAULT_SIGNATURE_KEY_ID)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--deployment-id", default=DEFAULT_DEPLOYMENT_ID)
    parser.add_argument("--commit-sha")
    parser.add_argument("--issued-at")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure evidence bundle production."""

    args = parse_args(argv)
    try:
        bundle = produce_team_ops_shared_inbox_terminal_closure_evidence_bundle(
            certificate_path=Path(args.certificate),
            source_review_packet_path=Path(args.source_review_packet),
            schema_path=Path(args.schema),
            signing_secret=args.signing_secret,
            signature_key_id=args.signature_key_id,
            tenant_id=args.tenant_id,
            deployment_id=args.deployment_id,
            commit_sha=args.commit_sha,
            issued_at=args.issued_at,
        )
        write_team_ops_shared_inbox_terminal_closure_evidence_bundle(bundle, Path(args.output))
    except (OSError, RuntimeError, ValueError) as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "bundle_written": False,
                        "error": str(exc),
                        "solver_outcome": "GovernanceBlocked",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"TeamOps terminal closure evidence bundle failed: {exc}")
        return 2
    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
    else:
        print(f"TeamOps terminal closure evidence bundle written: {bundle['bundle_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
