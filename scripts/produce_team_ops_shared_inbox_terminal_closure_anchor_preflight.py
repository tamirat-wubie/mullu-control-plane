#!/usr/bin/env python3
"""Produce a TeamOps terminal closure anchor preflight receipt.

Purpose: verify a signed TeamOps terminal closure evidence bundle is ready for
a later trust-ledger anchor receipt without creating that receipt, appending a
submission ledger, or calling a remote endpoint.
Governance scope: TeamOps terminal closure anchoring preflight, proof artifact
projection, operator authority evidence, and no-effect boundary enforcement.
Dependencies: gateway.trust_ledger,
schemas/team_ops_shared_inbox_terminal_closure_anchor_preflight.schema.json,
and scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.
Invariants:
  - Preflight never calls TrustLedger.anchor_bundle.
  - Preflight never writes anchor receipts or submission ledgers.
  - Preflight never calls providers, mailboxes, or remote transparency logs.
  - Secret values are accepted only as presence checks and are never serialized.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.trust_ledger import (  # noqa: E402
    EXTERNAL_ANCHOR_TARGETS,
    TrustLedgerEvidenceArtifact,
    _artifact_root_hash,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_BUNDLE,
    DEFAULT_REVIEW_PACKET,
    WORKFLOW_ID,
)
from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CERTIFICATE,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)


SCHEMA_PATH = REPO_ROOT / "schemas" / "team_ops_shared_inbox_terminal_closure_anchor_preflight.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_anchor_preflight.json"
DEFAULT_ANCHOR_TARGET = "transparency_log"
DEFAULT_SIGNATURE_KEY_ID = "teamops-anchor-key"
REQUIRED_ARTIFACT_TYPES = ("command", "execution_receipt", "verification_result", "terminal_certificate")


@dataclass(frozen=True, slots=True)
class TeamOpsTerminalClosureAnchorPreflightStep:
    """One TeamOps terminal closure anchor preflight step."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready step."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class TeamOpsTerminalClosureAnchorPreflight:
    """TeamOps terminal closure anchor preflight receipt."""

    schema_version: int
    receipt_id: str
    checked_at: str
    ready: bool
    solver_outcome: str
    proof_state: str
    bundle_path: str
    bundle_id: str
    command_id: str
    terminal_certificate_id: str
    bundle_hash: str
    anchor_target: str
    planned_external_anchor_status: str
    planned_external_anchor_ref: str
    operator_authority_ref: str
    anchor_signing_secret_present: bool
    signature_key_id_present: bool
    artifact_count: int
    artifact_root_hash: str
    required_artifact_types: tuple[str, ...]
    artifacts: tuple[dict[str, Any], ...]
    step_count: int
    steps: tuple[TeamOpsTerminalClosureAnchorPreflightStep, ...]
    blockers: tuple[str, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready receipt."""

        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "checked_at": self.checked_at,
            "ready": self.ready,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "bundle_path": self.bundle_path,
            "bundle_id": self.bundle_id,
            "command_id": self.command_id,
            "terminal_certificate_id": self.terminal_certificate_id,
            "bundle_hash": self.bundle_hash,
            "anchor_target": self.anchor_target,
            "planned_external_anchor_status": self.planned_external_anchor_status,
            "planned_external_anchor_ref": self.planned_external_anchor_ref,
            "operator_authority_ref": self.operator_authority_ref,
            "anchor_signing_secret_present": self.anchor_signing_secret_present,
            "signature_key_id_present": self.signature_key_id_present,
            "artifact_count": self.artifact_count,
            "artifact_root_hash": self.artifact_root_hash,
            "required_artifact_types": list(self.required_artifact_types),
            "artifacts": list(self.artifacts),
            "step_count": self.step_count,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "metadata": self.metadata,
        }


def produce_team_ops_shared_inbox_terminal_closure_anchor_preflight(
    *,
    bundle_path: Path = DEFAULT_BUNDLE,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    bundle_signing_secret: str,
    anchor_signing_secret: str,
    signature_key_id: str = DEFAULT_SIGNATURE_KEY_ID,
    operator_authority_ref: str = "",
    anchor_target: str = DEFAULT_ANCHOR_TARGET,
    checked_at: str | None = None,
) -> TeamOpsTerminalClosureAnchorPreflight:
    """Produce a no-effect anchor preflight for a TeamOps evidence bundle."""

    steps: list[TeamOpsTerminalClosureAnchorPreflightStep] = []
    hard_blockers: set[str] = set()

    def add_step(name: str, passed: bool, detail: str, *, hard: bool = False) -> None:
        steps.append(TeamOpsTerminalClosureAnchorPreflightStep(name=name, passed=passed, detail=detail))
        if hard and not passed:
            hard_blockers.add(name)

    bundle_validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=source_review_packet_path,
        signing_secret=bundle_signing_secret,
        require_ready=True,
    )
    bundle_valid = bundle_validation.valid and bundle_validation.ready
    add_step(
        "bundle_validation",
        bundle_valid,
        "bundle_ready=true" if bundle_valid else f"bundle_invalid:{','.join(bundle_validation.errors)}",
        hard=True,
    )
    bundle = _load_bundle(bundle_path) if bundle_valid else {}

    anchor_status_ok = bundle.get("external_anchor_status") == "not_requested" and bundle.get("external_anchor_ref") == ""
    add_step(
        "bundle_anchor_status",
        anchor_status_ok,
        "bundle_anchor_status=not_requested" if anchor_status_ok else "bundle_anchor_status_must_be_not_requested",
        hard=True,
    )

    anchor_target_ok = anchor_target in EXTERNAL_ANCHOR_TARGETS
    add_step(
        "anchor_target",
        anchor_target_ok,
        f"anchor_target={anchor_target}" if anchor_target_ok else "anchor_target_invalid",
        hard=True,
    )

    authority_ok = _authority_ref_allowed(operator_authority_ref)
    add_step(
        "operator_authority",
        authority_ok,
        "operator_authority_ref_present=true" if authority_ok else "operator_authority_ref_required",
    )

    anchor_secret_present = bool(anchor_signing_secret)
    add_step(
        "anchor_signing_secret",
        anchor_secret_present,
        "anchor_signing_secret_present=true" if anchor_secret_present else "anchor_signing_secret_required",
    )

    signature_key_present = bool(signature_key_id.strip())
    add_step(
        "signature_key_id",
        signature_key_present,
        "signature_key_id_present=true" if signature_key_present else "signature_key_id_required",
    )

    artifacts = _project_anchor_artifacts(bundle) if bundle_valid else ()
    artifact_types = tuple(sorted({artifact["artifact_type"] for artifact in artifacts if artifact["required"]}))
    artifact_projection_ok = set(REQUIRED_ARTIFACT_TYPES).issubset(artifact_types)
    artifact_root_hash = _artifact_root_hash(_artifact_objects(artifacts)) if artifacts else ""
    add_step(
        "artifact_projection",
        artifact_projection_ok,
        (
            f"artifact_count={len(artifacts)} artifact_root_hash={artifact_root_hash}"
            if artifact_projection_ok
            else "required_anchor_artifacts_missing"
        ),
        hard=bundle_valid,
    )

    effect_boundary_ok = True
    add_step(
        "effect_boundary",
        effect_boundary_ok,
        "anchor_receipt_created=false remote_submit_executed=false ledger_append_executed=false",
        hard=True,
    )

    blockers = tuple(step.name for step in steps if not step.passed)
    ready = not blockers
    solver_outcome = _solver_outcome(ready=ready, hard_blockers=hard_blockers)
    proof_state = "Pass" if ready else ("Fail" if hard_blockers else "Unknown")
    metadata = {
        "source": "team_ops_shared_inbox_terminal_closure_anchor_preflight",
        "preflight_only": True,
        "anchor_receipt_created": False,
        "anchor_bundle_called": False,
        "remote_submit_executed": False,
        "ledger_append_executed": False,
        "provider_call_performed": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "raw_message_content_serialized": False,
        "raw_provider_payload_serialized": False,
        "no_secret_values_serialized": True,
        "production_ready_claimed": False,
        "requires_operator_confirmation_for_anchor": True,
    }
    checked_at_value = checked_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    seed = {
        "schema_version": 1,
        "checked_at": checked_at_value,
        "ready": ready,
        "solver_outcome": solver_outcome,
        "proof_state": proof_state,
        "bundle_path": _path_label(bundle_path),
        "bundle_id": str(bundle.get("bundle_id", "")),
        "command_id": str(bundle.get("command_id", "")),
        "terminal_certificate_id": str(bundle.get("terminal_certificate_id", "")),
        "bundle_hash": str(bundle.get("bundle_hash", "")),
        "anchor_target": anchor_target,
        "planned_external_anchor_status": "pending",
        "planned_external_anchor_ref": "",
        "operator_authority_ref": operator_authority_ref,
        "anchor_signing_secret_present": anchor_secret_present,
        "signature_key_id_present": signature_key_present,
        "artifact_count": len(artifacts),
        "artifact_root_hash": artifact_root_hash,
        "required_artifact_types": REQUIRED_ARTIFACT_TYPES,
        "artifacts": artifacts,
        "steps": [step.as_dict() for step in steps],
        "blockers": blockers,
        "metadata": metadata,
    }
    receipt_id = f"teamops-shared-inbox-terminal-anchor-preflight-{_stable_hash(seed)[:16]}"
    return TeamOpsTerminalClosureAnchorPreflight(
        schema_version=1,
        receipt_id=receipt_id,
        checked_at=checked_at_value,
        ready=ready,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        bundle_path=_path_label(bundle_path),
        bundle_id=str(bundle.get("bundle_id", "")),
        command_id=str(bundle.get("command_id", "")),
        terminal_certificate_id=str(bundle.get("terminal_certificate_id", "")),
        bundle_hash=str(bundle.get("bundle_hash", "")),
        anchor_target=anchor_target,
        planned_external_anchor_status="pending",
        planned_external_anchor_ref="",
        operator_authority_ref=operator_authority_ref,
        anchor_signing_secret_present=anchor_secret_present,
        signature_key_id_present=signature_key_present,
        artifact_count=len(artifacts),
        artifact_root_hash=artifact_root_hash,
        required_artifact_types=REQUIRED_ARTIFACT_TYPES,
        artifacts=tuple(artifacts),
        step_count=len(steps),
        steps=tuple(steps),
        blockers=blockers,
        metadata=metadata,
    )


def write_team_ops_shared_inbox_terminal_closure_anchor_preflight(
    preflight: TeamOpsTerminalClosureAnchorPreflight,
    output_path: Path,
) -> Path:
    """Write one schema-validated TeamOps anchor preflight receipt."""

    payload = preflight.as_dict()
    _assert_redacted(payload)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    if errors:
        raise RuntimeError(
            "team_ops_terminal_closure_anchor_preflight_schema_validation_failed:"
            + ";".join(errors[:10])
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _project_anchor_artifacts(bundle: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    bundle_hash = str(bundle.get("bundle_hash", ""))
    command_id = str(bundle.get("command_id", ""))
    terminal_certificate_id = str(bundle.get("terminal_certificate_id", ""))
    refs = [str(ref) for ref in bundle.get("evidence_refs", []) if isinstance(ref, str)]
    artifacts = [
        _artifact(
            artifact_type="command",
            artifact_id=command_id,
            evidence_ref=_find_ref(refs, "/command/") or f"proof://teamops/command/{command_id}",
            required=True,
            bundle_hash=bundle_hash,
        ),
        _artifact(
            artifact_type="execution_receipt",
            artifact_id=_artifact_id("teamops-send-execution", _find_ref(refs, "/evidence-ref/")),
            evidence_ref=_find_ref(refs, "/evidence-ref/") or f"proof://teamops/evidence-ref/{_short_hash(bundle_hash)}",
            required=True,
            bundle_hash=bundle_hash,
        ),
        _artifact(
            artifact_type="verification_result",
            artifact_id=_artifact_id("teamops-verification", _find_ref(refs, "/verification-result/")),
            evidence_ref=_find_ref(refs, "/verification-result/") or f"proof://teamops/verification-result/{_short_hash(bundle_hash)}",
            required=True,
            bundle_hash=bundle_hash,
        ),
        _artifact(
            artifact_type="terminal_certificate",
            artifact_id=terminal_certificate_id,
            evidence_ref=(
                _find_ref(refs, "/terminal-certificate/")
                or f"proof://teamops/terminal-certificate/{terminal_certificate_id}"
            ),
            required=True,
            bundle_hash=bundle_hash,
        ),
        _artifact(
            artifact_type="effect_reconciliation",
            artifact_id=_artifact_id("teamops-effect", _find_ref(refs, "/effect-reconciliation/")),
            evidence_ref=(
                _find_ref(refs, "/effect-reconciliation/")
                or f"proof://teamops/effect-reconciliation/{_short_hash(bundle_hash)}"
            ),
            required=False,
            bundle_hash=bundle_hash,
        ),
        _artifact(
            artifact_type="approval",
            artifact_id=_artifact_id("teamops-terminal-review", _find_ref(refs, "/terminal-review/")),
            evidence_ref=_find_ref(refs, "/terminal-review/") or f"proof://teamops/terminal-review/{_short_hash(bundle_hash)}",
            required=False,
            bundle_hash=bundle_hash,
        ),
    ]
    return tuple(artifacts)


def _artifact(
    *,
    artifact_type: str,
    artifact_id: str,
    evidence_ref: str,
    required: bool,
    bundle_hash: str,
) -> dict[str, Any]:
    return TrustLedgerEvidenceArtifact(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        artifact_hash=f"sha256:{_stable_hash({'artifact_type': artifact_type, 'artifact_id': artifact_id, 'evidence_ref': evidence_ref, 'bundle_hash': bundle_hash})}",
        evidence_ref=evidence_ref,
        required=required,
        metadata={"source_bundle_hash": bundle_hash, "team_ops_anchor_preflight_artifact": True},
    ).to_json_dict()


def _artifact_objects(artifacts: tuple[dict[str, Any], ...]) -> tuple[TrustLedgerEvidenceArtifact, ...]:
    return tuple(
        TrustLedgerEvidenceArtifact(
            artifact_type=str(artifact["artifact_type"]),
            artifact_id=str(artifact["artifact_id"]),
            artifact_hash=str(artifact["artifact_hash"]),
            evidence_ref=str(artifact["evidence_ref"]),
            required=bool(artifact["required"]),
            metadata=dict(artifact.get("metadata", {})),
        )
        for artifact in artifacts
    )


def _load_bundle(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ValueError("TeamOps terminal closure evidence bundle JSON root must be an object")
    return payload


def _find_ref(refs: list[str], marker: str) -> str:
    for ref in refs:
        if marker in ref:
            return ref
    return ""


def _artifact_id(prefix: str, ref: str) -> str:
    return f"{prefix}-{_short_hash(ref or prefix)}"


def _authority_ref_allowed(value: str) -> bool:
    if not value or value.strip() != value or len(value) > 256:
        return False
    if any(character.isspace() or ord(character) < 32 for character in value):
        return False
    return value.startswith(("proof://", "authority://"))


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
            raise ValueError(f"TeamOps terminal closure anchor preflight contains secret marker: {marker}")


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps anchor preflight arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps terminal closure anchor preflight.")
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--bundle-signing-secret", default=os.environ.get("MULLU_TEAMOPS_TRUST_LEDGER_SECRET", ""))
    parser.add_argument("--anchor-signing-secret", default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_SECRET", ""))
    parser.add_argument("--signature-key-id", default=DEFAULT_SIGNATURE_KEY_ID)
    parser.add_argument(
        "--operator-authority-ref",
        default=os.environ.get("MULLU_TEAMOPS_ANCHOR_AUTHORITY_REF", ""),
    )
    parser.add_argument("--anchor-target", default=DEFAULT_ANCHOR_TARGET)
    parser.add_argument("--checked-at")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure anchor preflight."""

    args = parse_args(argv)
    try:
        preflight = produce_team_ops_shared_inbox_terminal_closure_anchor_preflight(
            bundle_path=Path(args.bundle),
            certificate_path=Path(args.certificate),
            source_review_packet_path=Path(args.source_review_packet),
            bundle_signing_secret=args.bundle_signing_secret,
            anchor_signing_secret=args.anchor_signing_secret,
            signature_key_id=args.signature_key_id,
            operator_authority_ref=args.operator_authority_ref,
            anchor_target=args.anchor_target,
            checked_at=args.checked_at,
        )
        write_team_ops_shared_inbox_terminal_closure_anchor_preflight(preflight, Path(args.output))
    except (OSError, RuntimeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ready": False, "solver_outcome": "GovernanceBlocked", "error": str(exc)}, indent=2))
        else:
            print(f"TeamOps terminal closure anchor preflight failed: {exc}")
        return 2
    if args.json:
        print(json.dumps(preflight.as_dict(), indent=2, sort_keys=True))
    elif preflight.ready:
        print(f"TeamOps terminal closure anchor preflight ready: {preflight.receipt_id}")
    else:
        print(f"TeamOps terminal closure anchor preflight blocked: {list(preflight.blockers)}")
    return 0 if preflight.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
