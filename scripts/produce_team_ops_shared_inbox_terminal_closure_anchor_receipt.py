#!/usr/bin/env python3
"""Produce a local TeamOps terminal closure anchor receipt wrapper.

Purpose: turn a ready TeamOps terminal closure anchor preflight into a pending
trust-ledger anchor receipt without remote submission or ledger append.
Governance scope: TeamOps anchor receipt creation, source-preflight binding,
trust-ledger signature verification, and no-remote-effect enforcement.
Dependencies: gateway.trust_ledger,
schemas/team_ops_shared_inbox_terminal_closure_anchor_receipt.schema.json,
schemas/trust_ledger_anchor_receipt.schema.json, and
scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_preflight.
Invariants:
  - A ready TeamOps anchor preflight is required before anchor receipt creation.
  - The receipt status remains pending and external_anchor_ref remains empty.
  - Remote submission, ledger append, provider calls, and production claims stay false.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.trust_ledger import (  # noqa: E402
    ExternalProofAnchorReceipt,
    TrustLedger,
    TrustLedgerBundle,
    TrustLedgerEvidenceArtifact,
    _artifact_root_hash,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_preflight import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PREFLIGHT,
    REQUIRED_ARTIFACT_TYPES,
    _artifact_objects,
    _project_anchor_artifacts,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_BUNDLE,
    DEFAULT_REVIEW_PACKET,
)
from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CERTIFICATE,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_preflight import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_anchor_preflight,
)


SCHEMA_PATH = REPO_ROOT / "schemas" / "team_ops_shared_inbox_terminal_closure_anchor_receipt.schema.json"
TRUST_LEDGER_ANCHOR_RECEIPT_SCHEMA_PATH = REPO_ROOT / "schemas" / "trust_ledger_anchor_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_anchor_receipt.json"
DEFAULT_SIGNATURE_KEY_ID = "teamops-anchor-key"


@dataclass(frozen=True, slots=True)
class TeamOpsTerminalClosureAnchorReceiptStep:
    """One TeamOps terminal closure anchor receipt creation step."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready step."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class TeamOpsTerminalClosureAnchorReceipt:
    """TeamOps wrapper around a pending trust-ledger anchor receipt."""

    schema_version: int
    receipt_id: str
    created_at: str
    ready: bool
    solver_outcome: str
    proof_state: str
    preflight_path: str
    source_preflight_receipt_id: str
    bundle_path: str
    bundle_id: str
    command_id: str
    terminal_certificate_id: str
    bundle_hash: str
    anchor_target: str
    external_anchor_status: str
    external_anchor_ref: str
    operator_authority_ref: str
    anchor_receipt_id: str
    anchor_receipt_hash: str
    artifact_root_hash: str
    artifact_count: int
    required_artifact_types: tuple[str, ...]
    anchor_receipt: dict[str, Any]
    artifacts: tuple[dict[str, Any], ...]
    step_count: int
    steps: tuple[TeamOpsTerminalClosureAnchorReceiptStep, ...]
    blockers: tuple[str, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready receipt wrapper."""

        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "created_at": self.created_at,
            "ready": self.ready,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "preflight_path": self.preflight_path,
            "source_preflight_receipt_id": self.source_preflight_receipt_id,
            "bundle_path": self.bundle_path,
            "bundle_id": self.bundle_id,
            "command_id": self.command_id,
            "terminal_certificate_id": self.terminal_certificate_id,
            "bundle_hash": self.bundle_hash,
            "anchor_target": self.anchor_target,
            "external_anchor_status": self.external_anchor_status,
            "external_anchor_ref": self.external_anchor_ref,
            "operator_authority_ref": self.operator_authority_ref,
            "anchor_receipt_id": self.anchor_receipt_id,
            "anchor_receipt_hash": self.anchor_receipt_hash,
            "artifact_root_hash": self.artifact_root_hash,
            "artifact_count": self.artifact_count,
            "required_artifact_types": list(self.required_artifact_types),
            "anchor_receipt": self.anchor_receipt,
            "artifacts": list(self.artifacts),
            "step_count": self.step_count,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "metadata": self.metadata,
        }


def produce_team_ops_shared_inbox_terminal_closure_anchor_receipt(
    *,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    bundle_path: Path = DEFAULT_BUNDLE,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    bundle_signing_secret: str,
    anchor_signing_secret: str,
    signature_key_id: str = DEFAULT_SIGNATURE_KEY_ID,
    created_at: str | None = None,
) -> TeamOpsTerminalClosureAnchorReceipt:
    """Produce a pending local anchor receipt from a ready TeamOps preflight."""

    steps: list[TeamOpsTerminalClosureAnchorReceiptStep] = []
    hard_blockers: set[str] = set()

    def add_step(name: str, passed: bool, detail: str, *, hard: bool = False) -> None:
        steps.append(TeamOpsTerminalClosureAnchorReceiptStep(name=name, passed=passed, detail=detail))
        if hard and not passed:
            hard_blockers.add(name)

    preflight = _load_json_object(preflight_path)
    bundle_payload = _load_json_object(bundle_path)
    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=source_review_packet_path,
        bundle_signing_secret=bundle_signing_secret,
        require_ready=True,
    )
    preflight_valid = validation.valid and validation.ready
    add_step(
        "preflight_validation",
        preflight_valid,
        "preflight_valid=true" if preflight_valid else f"preflight_invalid:{','.join(validation.errors)}",
        hard=True,
    )
    preflight_ready = preflight.get("ready") is True and preflight.get("proof_state") == "Pass"
    add_step(
        "preflight_ready",
        preflight_ready,
        "preflight_ready=true" if preflight_ready else "preflight_ready_required",
        hard=True,
    )
    source_binding_ok = _source_binding_ok(preflight, bundle_payload)
    add_step(
        "source_binding",
        source_binding_ok,
        "source_binding=preflight_bundle" if source_binding_ok else "preflight_bundle_binding_mismatch",
        hard=True,
    )

    artifacts = tuple(preflight.get("artifacts", ())) if preflight_valid else ()
    artifact_objects = _artifact_objects(artifacts) if artifacts else ()
    projected_artifacts = _project_anchor_artifacts(bundle_payload) if preflight_valid else ()
    artifact_root_hash = _artifact_root_hash(artifact_objects) if artifact_objects else ""
    artifact_projection_ok = bool(artifact_objects) and artifacts == projected_artifacts
    add_step(
        "artifact_projection",
        artifact_projection_ok,
        (
            f"artifact_count={len(artifact_objects)} artifact_root_hash={artifact_root_hash}"
            if artifact_projection_ok
            else "artifact_projection_mismatch"
        ),
        hard=True,
    )

    created_at_value = created_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    anchor_receipt: ExternalProofAnchorReceipt | None = None
    anchor_signature_ok = False
    if preflight_valid and source_binding_ok and artifact_projection_ok and anchor_signing_secret and signature_key_id.strip():
        bundle = _bundle_from_payload(bundle_payload)
        anchor_receipt = TrustLedger().anchor_bundle(
            bundle,
            artifacts=artifact_objects,
            anchor_target=str(preflight.get("anchor_target", "")),
            external_anchor_ref="",
            external_anchor_status="pending",
            anchored_at=created_at_value,
            signing_secret=anchor_signing_secret,
            signature_key_id=signature_key_id,
        )
        verification = TrustLedger().verify_anchor_receipt(
            anchor_receipt,
            bundle=bundle,
            artifacts=artifact_objects,
            signing_secret=anchor_signing_secret,
        )
        anchor_signature_ok = verification.verified
        anchor_signature_detail = verification.reason
    else:
        anchor_signature_detail = "anchor_receipt_inputs_missing"
    add_step(
        "anchor_receipt_signature",
        anchor_signature_ok,
        anchor_signature_detail,
        hard=True,
    )

    pending_boundary_ok = (
        anchor_receipt is not None
        and anchor_receipt.external_anchor_status == "pending"
        and anchor_receipt.external_anchor_ref == ""
    )
    add_step(
        "pending_boundary",
        pending_boundary_ok,
        "external_anchor_status=pending external_anchor_ref=empty" if pending_boundary_ok else "pending_boundary_required",
        hard=True,
    )
    effect_boundary_ok = True
    add_step(
        "effect_boundary",
        effect_boundary_ok,
        "remote_submit_executed=false ledger_append_executed=false provider_call_performed=false",
        hard=True,
    )

    blockers = tuple(step.name for step in steps if not step.passed)
    ready = not blockers
    metadata = {
        "source": "team_ops_shared_inbox_terminal_closure_anchor_receipt",
        "preflight_ready_required": True,
        "anchor_receipt_created": anchor_receipt is not None,
        "anchor_bundle_called": anchor_receipt is not None,
        "remote_submit_executed": False,
        "ledger_append_executed": False,
        "provider_call_performed": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "raw_message_content_serialized": False,
        "raw_provider_payload_serialized": False,
        "no_secret_values_serialized": True,
        "production_ready_claimed": False,
        "requires_separate_remote_submission_preflight": True,
    }
    anchor_payload = anchor_receipt.to_json_dict() if anchor_receipt is not None else _empty_anchor_receipt_payload()
    seed = {
        "schema_version": 1,
        "created_at": created_at_value,
        "source_preflight_receipt_id": str(preflight.get("receipt_id", "")),
        "bundle_id": str(preflight.get("bundle_id", "")),
        "anchor_receipt_id": str(anchor_payload.get("anchor_receipt_id", "")),
        "anchor_receipt_hash": str(anchor_payload.get("anchor_receipt_hash", "")),
        "artifact_root_hash": artifact_root_hash,
        "steps": [step.as_dict() for step in steps],
    }
    receipt_id = f"teamops-shared-inbox-terminal-anchor-receipt-{_stable_hash(seed)[:16]}"
    receipt = TeamOpsTerminalClosureAnchorReceipt(
        schema_version=1,
        receipt_id=receipt_id,
        created_at=created_at_value,
        ready=ready,
        solver_outcome=_solver_outcome(ready=ready, hard_blockers=hard_blockers),
        proof_state="Pass" if ready else ("Fail" if hard_blockers else "Unknown"),
        preflight_path=_path_label(preflight_path),
        source_preflight_receipt_id=str(preflight.get("receipt_id", "")),
        bundle_path=_path_label(bundle_path),
        bundle_id=str(preflight.get("bundle_id", "")),
        command_id=str(preflight.get("command_id", "")),
        terminal_certificate_id=str(preflight.get("terminal_certificate_id", "")),
        bundle_hash=str(preflight.get("bundle_hash", "")),
        anchor_target=str(preflight.get("anchor_target", "")),
        external_anchor_status=str(anchor_payload.get("external_anchor_status", "")),
        external_anchor_ref=str(anchor_payload.get("external_anchor_ref", "")),
        operator_authority_ref=str(preflight.get("operator_authority_ref", "")),
        anchor_receipt_id=str(anchor_payload.get("anchor_receipt_id", "")),
        anchor_receipt_hash=str(anchor_payload.get("anchor_receipt_hash", "")),
        artifact_root_hash=artifact_root_hash,
        artifact_count=len(artifact_objects),
        required_artifact_types=REQUIRED_ARTIFACT_TYPES,
        anchor_receipt=anchor_payload,
        artifacts=tuple(artifact.to_json_dict() for artifact in artifact_objects),
        step_count=len(steps),
        steps=tuple(steps),
        blockers=blockers,
        metadata=metadata,
    )
    _assert_redacted(receipt.as_dict())
    return receipt


def write_team_ops_shared_inbox_terminal_closure_anchor_receipt(
    receipt: TeamOpsTerminalClosureAnchorReceipt,
    output_path: Path,
) -> Path:
    """Write one schema-validated TeamOps anchor receipt wrapper."""

    payload = receipt.as_dict()
    _assert_redacted(payload)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    if errors:
        raise ValueError("team_ops_terminal_closure_anchor_receipt_schema_validation_failed:" + ";".join(errors))
    trust_errors = _validate_schema_instance(_load_schema(TRUST_LEDGER_ANCHOR_RECEIPT_SCHEMA_PATH), payload["anchor_receipt"])
    if trust_errors:
        raise ValueError("trust_ledger_anchor_receipt_schema_validation_failed:" + ";".join(trust_errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _bundle_from_payload(payload: Mapping[str, Any]) -> TrustLedgerBundle:
    return TrustLedgerBundle(
        bundle_id=str(payload["bundle_id"]),
        tenant_id=str(payload["tenant_id"]),
        command_id=str(payload["command_id"]),
        terminal_certificate_id=str(payload["terminal_certificate_id"]),
        deployment_id=str(payload["deployment_id"]),
        commit_sha=str(payload["commit_sha"]),
        hash_chain_root=str(payload["hash_chain_root"]),
        evidence_refs=[str(ref) for ref in payload["evidence_refs"]],
        issued_at=str(payload["issued_at"]),
        external_anchor_ref=str(payload["external_anchor_ref"]),
        external_anchor_status=str(payload["external_anchor_status"]),
        bundle_hash=str(payload["bundle_hash"]),
        signature_key_id=str(payload["signature_key_id"]),
        signature=str(payload["signature"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _source_binding_ok(preflight: Mapping[str, Any], bundle: Mapping[str, Any]) -> bool:
    fields = ("bundle_id", "command_id", "terminal_certificate_id", "bundle_hash")
    return all(preflight.get(field_name) == bundle.get(field_name) for field_name in fields)


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ValueError("TeamOps terminal closure anchor receipt input JSON root must be an object")
    return payload


def _empty_anchor_receipt_payload() -> dict[str, Any]:
    return {
        "anchor_receipt_id": "",
        "bundle_id": "",
        "tenant_id": "",
        "command_id": "",
        "terminal_certificate_id": "",
        "anchor_target": "transparency_log",
        "external_anchor_ref": "",
        "external_anchor_status": "pending",
        "bundle_hash": "",
        "artifact_root_hash": "",
        "hash_chain_root": "",
        "artifact_count": 0,
        "required_artifact_types": [],
        "anchored_at": "",
        "signature_key_id": "",
        "signature": "hmac-sha256:missing",
        "anchor_receipt_hash": "",
        "metadata": {"anchor_receipt_is_not_terminal_closure": True},
    }


def _solver_outcome(*, ready: bool, hard_blockers: set[str]) -> str:
    if ready:
        return "SolvedVerified"
    if hard_blockers:
        return "GovernanceBlocked"
    return "AwaitingEvidence"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError(f"TeamOps terminal closure anchor receipt contains secret marker: {marker}")


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    import hashlib

    return hashlib.sha256(encoded).hexdigest()


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps anchor receipt production arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps terminal closure anchor receipt.")
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--bundle-signing-secret", default=os.environ.get("MULLU_TEAMOPS_TRUST_LEDGER_SECRET", ""))
    parser.add_argument("--anchor-signing-secret", default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_SECRET", ""))
    parser.add_argument("--signature-key-id", default=DEFAULT_SIGNATURE_KEY_ID)
    parser.add_argument("--created-at")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure anchor receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_terminal_closure_anchor_receipt(
            preflight_path=Path(args.preflight),
            bundle_path=Path(args.bundle),
            certificate_path=Path(args.certificate),
            source_review_packet_path=Path(args.source_review_packet),
            bundle_signing_secret=args.bundle_signing_secret,
            anchor_signing_secret=args.anchor_signing_secret,
            signature_key_id=args.signature_key_id,
            created_at=args.created_at,
        )
        write_team_ops_shared_inbox_terminal_closure_anchor_receipt(receipt, Path(args.output))
    except Exception as exc:
        if args.json:
            print(json.dumps({"ready": False, "solver_outcome": "GovernanceBlocked", "error": str(exc)}, indent=2))
        else:
            print(f"TeamOps terminal closure anchor receipt failed: {exc}")
        return 2 if args.strict else 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    elif receipt.ready:
        print(f"TeamOps terminal closure anchor receipt ready: {receipt.receipt_id}")
    else:
        print(f"TeamOps terminal closure anchor receipt blocked: {list(receipt.blockers)}")
    return 0 if receipt.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
