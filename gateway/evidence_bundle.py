"""Gateway Evidence Bundle - command-ledger trust bundle projection.

Purpose: Build signed trust-ledger bundles from terminal command closure state.
Governance scope: gateway command evidence export and verification only.
Dependencies: gateway command spine and trust ledger contracts.
Invariants:
  - Bundles require a terminal closure certificate.
  - Required artifact classes are projected from ledger witnesses.
  - Bundle contents are signed by the trust ledger, not by route handlers.
  - Missing required evidence fails closed with explicit errors.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from gateway.command_spine import CommandLedger, canonical_hash
from gateway.trust_ledger import TrustLedger, TrustLedgerBundle, TrustLedgerBundleDraft, TrustLedgerEvidenceArtifact


def build_command_trust_bundle(
    *,
    command_ledger: CommandLedger,
    command_id: str,
    deployment_id: str,
    commit_sha: str,
    signing_secret: str,
    signature_key_id: str,
    clock: Callable[[], str],
    external_anchor_ref: str = "",
    external_anchor_status: str = "not_requested",
) -> TrustLedgerBundle:
    """Issue a signed trust-ledger bundle for one terminal command."""
    if not signing_secret:
        raise ValueError("trust ledger signing secret is required")
    command = command_ledger.get(command_id)
    if command is None:
        raise KeyError(f"unknown command_id: {command_id}")
    certificate = command_ledger.terminal_certificate_for(command_id)
    if certificate is None:
        raise ValueError("terminal certificate required")
    evidence_refs = _bundle_evidence_refs(command_ledger, command_id, certificate.certificate_id)
    artifacts = build_command_evidence_artifacts(command_ledger=command_ledger, command_id=command_id)
    metadata = {
        "artifact_count": len(artifacts),
        "artifact_root_hash": canonical_hash([artifact.to_json_dict() for artifact in artifacts]),
        "artifact_types": tuple(artifact.artifact_type for artifact in artifacts),
        "terminal_disposition": certificate.disposition.value,
    }
    draft = TrustLedgerBundleDraft(
        tenant_id=command.tenant_id,
        command_id=command.command_id,
        terminal_certificate_id=certificate.certificate_id,
        deployment_id=deployment_id,
        commit_sha=commit_sha,
        hash_chain_root=str(command_ledger.summary().get("last_event_hash", "")) or command.trace_id,
        evidence_refs=evidence_refs,
        issued_at=clock(),
        external_anchor_ref=external_anchor_ref,
        external_anchor_status=external_anchor_status,
        metadata=metadata,
    )
    return TrustLedger().issue(
        draft,
        signing_secret=signing_secret,
        signature_key_id=signature_key_id,
    )


def build_command_evidence_artifacts(
    *,
    command_ledger: CommandLedger,
    command_id: str,
) -> tuple[TrustLedgerEvidenceArtifact, ...]:
    """Project command ledger witnesses into trust-ledger artifact records."""
    command = command_ledger.get(command_id)
    if command is None:
        raise KeyError(f"unknown command_id: {command_id}")
    certificate = command_ledger.terminal_certificate_for(command_id)
    if certificate is None:
        raise ValueError("terminal certificate required")
    events = command_ledger.events_for(command_id)
    artifacts: list[TrustLedgerEvidenceArtifact] = [
        _artifact("command", command.command_id, asdict(command), f"proof://command/{command.command_id}"),
        _artifact(
            "terminal_certificate",
            certificate.certificate_id,
            asdict(certificate),
            f"proof://terminal-certificate/{certificate.certificate_id}",
        ),
    ]
    approval_event = next((event for event in reversed(events) if event.approval_id), None)
    if approval_event is not None:
        artifacts.append(_artifact(
            "approval",
            approval_event.approval_id,
            asdict(approval_event),
            f"proof://approval/{approval_event.approval_id}",
        ))
    execution_payload = _latest_event_detail(events, "proof_carrying_receipt") or _latest_event_detail(
        events,
        "execution_result",
    )
    if execution_payload is not None:
        execution_id = str(execution_payload.get("execution_id") or execution_payload.get("proof_receipt_id") or command_id)
        artifacts.append(_artifact(
            "execution_receipt",
            execution_id,
            execution_payload,
            f"proof://execution-receipt/{execution_id}",
        ))
    verification_payload = _latest_event_detail(events, "effect_verification")
    if verification_payload is not None:
        verification_id = str(verification_payload.get("verification_id") or f"verification-{command_id}")
        artifacts.append(_artifact(
            "verification_result",
            verification_id,
            verification_payload,
            f"proof://verification/{verification_id}",
        ))
    reconciliation_payload = _latest_event_detail(events, "effect_reconciliation")
    if reconciliation_payload is not None:
        reconciliation_id = str(reconciliation_payload.get("command_id") or command_id)
        artifacts.append(_artifact(
            "effect_reconciliation",
            reconciliation_id,
            reconciliation_payload,
            f"proof://effect-reconciliation/{reconciliation_id}",
            required=False,
        ))
    learning_payload = _latest_event_detail(events, "closure_learning_decision")
    if learning_payload is not None:
        learning_id = str(learning_payload.get("admission_id") or f"learning-{command_id}")
        artifacts.append(_artifact(
            "learning_decision",
            learning_id,
            learning_payload,
            f"proof://learning-decision/{learning_id}",
            required=False,
        ))
    missing = _missing_required_artifacts(artifacts)
    if missing:
        raise ValueError(f"trust bundle required artifacts missing:{','.join(missing)}")
    return tuple(artifacts)


def _bundle_evidence_refs(
    command_ledger: CommandLedger,
    command_id: str,
    terminal_certificate_id: str,
) -> tuple[str, ...]:
    refs = [f"proof://terminal-certificate/{terminal_certificate_id}"]
    refs.extend(f"proof://evidence/{record.evidence_id}" for record in command_ledger.evidence_for(command_id))
    return tuple(dict.fromkeys(refs))


def _artifact(
    artifact_type: str,
    artifact_id: str,
    payload: Any,
    evidence_ref: str,
    *,
    required: bool = True,
) -> TrustLedgerEvidenceArtifact:
    return TrustLedgerEvidenceArtifact(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        artifact_hash=f"sha256:{canonical_hash(payload)}",
        evidence_ref=evidence_ref,
        required=required,
    )


def _latest_event_detail(events: list[Any], key: str) -> dict[str, Any] | None:
    for event in reversed(events):
        value = event.detail.get(key)
        if isinstance(value, dict):
            return value
    return None


def _missing_required_artifacts(artifacts: list[TrustLedgerEvidenceArtifact]) -> tuple[str, ...]:
    required = {"command", "execution_receipt", "verification_result", "terminal_certificate"}
    observed = {artifact.artifact_type for artifact in artifacts if artifact.required}
    return tuple(sorted(required.difference(observed)))
