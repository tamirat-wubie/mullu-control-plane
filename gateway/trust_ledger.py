"""Gateway trust ledger.

Purpose: bind terminal closure, deployment, commit, audit root, and evidence
references into a signed evidence bundle and externally anchorable proof receipt.
Governance scope: signed trust bundles, terminal certificate anchoring, external
anchor readiness, and tamper-evident verification.
Dependencies: standard-library dataclasses, hashlib, hmac, and JSON serialization.
Invariants:
  - A trust bundle cannot be issued without a terminal certificate id.
  - A trust bundle cannot be signed without command, tenant, deployment, commit,
    hash-chain root, and evidence refs.
  - External anchoring binds the final terminal certificate, not only pre-closure audit records.
  - Verification recomputes both bundle hash and HMAC signature.
  - External anchor receipts bind typed artifact roots and never replace terminal closure.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any


EVIDENCE_ARTIFACT_TYPES = (
    "command",
    "approval",
    "execution_receipt",
    "verification_result",
    "effect_reconciliation",
    "terminal_certificate",
    "learning_decision",
    "deployment_witness",
)
EXTERNAL_ANCHOR_STATUSES = ("pending", "anchored", "failed")
EXTERNAL_ANCHOR_TARGETS = ("audit_chain", "transparency_log", "external_ledger", "regulatory_archive")


@dataclass(frozen=True, slots=True)
class TrustLedgerEvidenceArtifact:
    """Typed evidence item included in an external proof anchor."""

    artifact_type: str
    artifact_id: str
    artifact_hash: str
    evidence_ref: str
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.artifact_type not in EVIDENCE_ARTIFACT_TYPES:
            raise ValueError("artifact_type_invalid")
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.artifact_hash, "artifact_hash")
        _require_text(self.evidence_ref, "evidence_ref")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object for this evidence artifact."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class TrustLedgerBundleDraft:
    """Unsigned source material for one trust ledger evidence bundle."""

    tenant_id: str
    command_id: str
    terminal_certificate_id: str
    deployment_id: str
    commit_sha: str
    hash_chain_root: str
    evidence_refs: tuple[str, ...]
    issued_at: str
    external_anchor_ref: str = ""
    external_anchor_status: str = "not_requested"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.command_id, "command_id")
        _require_text(self.terminal_certificate_id, "terminal_certificate_id")
        _require_text(self.deployment_id, "deployment_id")
        _require_text(self.commit_sha, "commit_sha")
        _require_text(self.hash_chain_root, "hash_chain_root")
        _require_text(self.issued_at, "issued_at")
        object.__setattr__(self, "evidence_refs", _require_refs(self.evidence_refs))
        if self.external_anchor_status not in {"not_requested", "pending", "anchored", "failed"}:
            raise ValueError("external_anchor_status_invalid")
        if self.external_anchor_status == "anchored" and not self.external_anchor_ref:
            raise ValueError("anchored_bundle_requires_external_anchor_ref")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TrustLedgerBundle:
    """Signed evidence bundle published by the trust ledger."""

    bundle_id: str
    tenant_id: str
    command_id: str
    terminal_certificate_id: str
    deployment_id: str
    commit_sha: str
    hash_chain_root: str
    evidence_refs: list[str]
    issued_at: str
    external_anchor_ref: str
    external_anchor_status: str
    bundle_hash: str
    signature_key_id: str
    signature: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.bundle_id, "bundle_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.command_id, "command_id")
        _require_text(self.terminal_certificate_id, "terminal_certificate_id")
        _require_text(self.deployment_id, "deployment_id")
        _require_text(self.commit_sha, "commit_sha")
        _require_text(self.hash_chain_root, "hash_chain_root")
        _require_text(self.issued_at, "issued_at")
        _require_text(self.bundle_hash, "bundle_hash")
        _require_text(self.signature_key_id, "signature_key_id")
        _require_text(self.signature, "signature")
        object.__setattr__(self, "evidence_refs", list(_require_refs(tuple(self.evidence_refs))))
        if self.external_anchor_status not in {"not_requested", "pending", "anchored", "failed"}:
            raise ValueError("external_anchor_status_invalid")
        if self.external_anchor_status == "anchored" and not self.external_anchor_ref:
            raise ValueError("anchored_bundle_requires_external_anchor_ref")
        if not self.signature.startswith("hmac-sha256:"):
            raise ValueError("signature_not_hmac_sha256")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object for this signed bundle."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class TrustLedgerVerification:
    """Verification result for a trust ledger bundle."""

    bundle_id: str
    verified: bool
    reason: str
    expected_bundle_hash: str = ""
    observed_bundle_hash: str = ""
    signature_key_id: str = ""


@dataclass(frozen=True, slots=True)
class ExternalProofAnchorReceipt:
    """Signed receipt proving a trust bundle was prepared for external anchoring."""

    anchor_receipt_id: str
    bundle_id: str
    tenant_id: str
    command_id: str
    terminal_certificate_id: str
    anchor_target: str
    external_anchor_ref: str
    external_anchor_status: str
    bundle_hash: str
    artifact_root_hash: str
    hash_chain_root: str
    artifact_count: int
    required_artifact_types: list[str]
    anchored_at: str
    signature_key_id: str
    signature: str
    anchor_receipt_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.anchor_receipt_id, "anchor_receipt_id")
        _require_text(self.bundle_id, "bundle_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.command_id, "command_id")
        _require_text(self.terminal_certificate_id, "terminal_certificate_id")
        if self.anchor_target not in EXTERNAL_ANCHOR_TARGETS:
            raise ValueError("anchor_target_invalid")
        if self.external_anchor_status not in EXTERNAL_ANCHOR_STATUSES:
            raise ValueError("external_anchor_status_invalid")
        if self.external_anchor_status == "anchored" and not self.external_anchor_ref:
            raise ValueError("anchored_receipt_requires_external_anchor_ref")
        _require_text(self.bundle_hash, "bundle_hash")
        _require_text(self.artifact_root_hash, "artifact_root_hash")
        _require_text(self.hash_chain_root, "hash_chain_root")
        if self.artifact_count <= 0:
            raise ValueError("artifact_count_positive")
        object.__setattr__(self, "required_artifact_types", list(_require_refs(tuple(self.required_artifact_types))))
        _require_text(self.anchored_at, "anchored_at")
        _require_text(self.signature_key_id, "signature_key_id")
        _require_text(self.signature, "signature")
        _require_text(self.anchor_receipt_hash, "anchor_receipt_hash")
        if not self.signature.startswith("hmac-sha256:"):
            raise ValueError("signature_not_hmac_sha256")
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.metadata.get("anchor_receipt_is_not_terminal_closure") is not True:
            raise ValueError("anchor_receipt_non_terminal_marker_required")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object for this anchor receipt."""
        return _json_ready(asdict(self))


class TrustLedger:
    """Issue and verify signed evidence bundles."""

    def issue(
        self,
        draft: TrustLedgerBundleDraft,
        *,
        signing_secret: str,
        signature_key_id: str,
    ) -> TrustLedgerBundle:
        """Create a signed bundle from verified closure evidence."""
        _require_text(signing_secret, "signing_secret")
        _require_text(signature_key_id, "signature_key_id")
        bundle_hash = _bundle_hash_from_draft(draft)
        unsigned = TrustLedgerBundle(
            bundle_id=f"trust-bundle-{bundle_hash[:16]}",
            tenant_id=draft.tenant_id,
            command_id=draft.command_id,
            terminal_certificate_id=draft.terminal_certificate_id,
            deployment_id=draft.deployment_id,
            commit_sha=draft.commit_sha,
            hash_chain_root=draft.hash_chain_root,
            evidence_refs=list(draft.evidence_refs),
            issued_at=draft.issued_at,
            external_anchor_ref=draft.external_anchor_ref,
            external_anchor_status=draft.external_anchor_status,
            bundle_hash=bundle_hash,
            signature_key_id=signature_key_id,
            signature="hmac-sha256:unsigned",
            metadata=draft.metadata,
        )
        return replace(unsigned, signature=_signature(unsigned, signing_secret=signing_secret))

    def verify(self, bundle: TrustLedgerBundle, *, signing_secret: str) -> TrustLedgerVerification:
        """Verify the bundle hash and HMAC signature."""
        if not signing_secret:
            return TrustLedgerVerification(bundle.bundle_id, False, "signing_secret_required")
        expected_hash = _bundle_hash(bundle)
        if not hmac.compare_digest(expected_hash, bundle.bundle_hash):
            return TrustLedgerVerification(
                bundle.bundle_id,
                False,
                "bundle_hash_mismatch",
                expected_bundle_hash=expected_hash,
                observed_bundle_hash=bundle.bundle_hash,
                signature_key_id=bundle.signature_key_id,
            )
        expected_signature = _signature(bundle, signing_secret=signing_secret)
        if not hmac.compare_digest(expected_signature, bundle.signature):
            return TrustLedgerVerification(
                bundle.bundle_id,
                False,
                "signature_mismatch",
                expected_bundle_hash=expected_hash,
                observed_bundle_hash=bundle.bundle_hash,
                signature_key_id=bundle.signature_key_id,
            )
        return TrustLedgerVerification(
            bundle.bundle_id,
            True,
            "verified",
            expected_bundle_hash=expected_hash,
            observed_bundle_hash=bundle.bundle_hash,
            signature_key_id=bundle.signature_key_id,
        )

    def anchor_bundle(
        self,
        bundle: TrustLedgerBundle,
        *,
        artifacts: tuple[TrustLedgerEvidenceArtifact, ...],
        anchor_target: str,
        external_anchor_ref: str,
        external_anchor_status: str,
        anchored_at: str,
        signing_secret: str,
        signature_key_id: str,
    ) -> ExternalProofAnchorReceipt:
        """Create a signed external proof anchor receipt for a bundle."""
        _require_text(signing_secret, "signing_secret")
        _require_text(signature_key_id, "signature_key_id")
        artifacts = _require_artifacts(artifacts)
        if anchor_target not in EXTERNAL_ANCHOR_TARGETS:
            raise ValueError("anchor_target_invalid")
        if external_anchor_status not in EXTERNAL_ANCHOR_STATUSES:
            raise ValueError("external_anchor_status_invalid")
        if external_anchor_status == "anchored" and not external_anchor_ref:
            raise ValueError("anchored_receipt_requires_external_anchor_ref")
        artifact_root = _artifact_root_hash(artifacts)
        required_types = tuple(sorted({artifact.artifact_type for artifact in artifacts if artifact.required}))
        missing_types = _missing_required_anchor_types(required_types)
        if missing_types:
            raise ValueError(f"anchor_required_artifacts_missing:{','.join(missing_types)}")
        _require_anchor_artifact_identity(bundle, artifacts)
        anchor_receipt_digest = _stable_hash(
            {
                "bundle_id": bundle.bundle_id,
                "artifact_root_hash": artifact_root,
                "target": anchor_target,
            },
        )
        receipt = ExternalProofAnchorReceipt(
            anchor_receipt_id=f"trust-anchor-receipt-{anchor_receipt_digest[:16]}",
            bundle_id=bundle.bundle_id,
            tenant_id=bundle.tenant_id,
            command_id=bundle.command_id,
            terminal_certificate_id=bundle.terminal_certificate_id,
            anchor_target=anchor_target,
            external_anchor_ref=external_anchor_ref,
            external_anchor_status=external_anchor_status,
            bundle_hash=bundle.bundle_hash,
            artifact_root_hash=artifact_root,
            hash_chain_root=bundle.hash_chain_root,
            artifact_count=len(artifacts),
            required_artifact_types=list(required_types),
            anchored_at=anchored_at,
            signature_key_id=signature_key_id,
            signature="hmac-sha256:unsigned",
            anchor_receipt_hash="pending",
            metadata={
                "anchor_receipt_is_not_terminal_closure": True,
                "bundle_signature_key_id": bundle.signature_key_id,
            },
        )
        receipt_hash = _anchor_receipt_hash(receipt)
        stamped = replace(receipt, anchor_receipt_hash=receipt_hash)
        return replace(stamped, signature=_anchor_signature(stamped, signing_secret=signing_secret))

    def verify_anchor_receipt(
        self,
        receipt: ExternalProofAnchorReceipt,
        *,
        bundle: TrustLedgerBundle,
        artifacts: tuple[TrustLedgerEvidenceArtifact, ...],
        signing_secret: str,
    ) -> TrustLedgerVerification:
        """Verify an external anchor receipt against bundle, artifacts, and signature."""
        if not signing_secret:
            return TrustLedgerVerification(receipt.bundle_id, False, "signing_secret_required")
        if receipt.bundle_id != bundle.bundle_id:
            return TrustLedgerVerification(receipt.bundle_id, False, "anchor_bundle_mismatch")
        if receipt.bundle_hash != bundle.bundle_hash:
            return TrustLedgerVerification(receipt.bundle_id, False, "anchor_bundle_hash_mismatch")
        checked_artifacts = _require_artifacts(artifacts)
        if receipt.artifact_count != len(checked_artifacts):
            return TrustLedgerVerification(receipt.bundle_id, False, "artifact_count_mismatch")
        missing_types = _missing_required_anchor_types(tuple(receipt.required_artifact_types))
        if missing_types:
            return TrustLedgerVerification(
                receipt.bundle_id,
                False,
                f"anchor_required_artifacts_missing:{','.join(missing_types)}",
                signature_key_id=receipt.signature_key_id,
            )
        try:
            _require_anchor_artifact_identity(bundle, checked_artifacts)
        except ValueError as exc:
            return TrustLedgerVerification(
                receipt.bundle_id,
                False,
                str(exc),
                signature_key_id=receipt.signature_key_id,
            )
        expected_artifact_root = _artifact_root_hash(checked_artifacts)
        if expected_artifact_root != receipt.artifact_root_hash:
            return TrustLedgerVerification(
                receipt.bundle_id,
                False,
                "artifact_root_hash_mismatch",
                expected_bundle_hash=expected_artifact_root,
                observed_bundle_hash=receipt.artifact_root_hash,
                signature_key_id=receipt.signature_key_id,
            )
        expected_receipt_hash = _anchor_receipt_hash(receipt)
        if expected_receipt_hash != receipt.anchor_receipt_hash:
            return TrustLedgerVerification(
                receipt.bundle_id,
                False,
                "anchor_receipt_hash_mismatch",
                expected_bundle_hash=expected_receipt_hash,
                observed_bundle_hash=receipt.anchor_receipt_hash,
                signature_key_id=receipt.signature_key_id,
            )
        expected_signature = _anchor_signature(receipt, signing_secret=signing_secret)
        if not hmac.compare_digest(expected_signature, receipt.signature):
            return TrustLedgerVerification(
                receipt.bundle_id,
                False,
                "anchor_signature_mismatch",
                expected_bundle_hash=expected_receipt_hash,
                observed_bundle_hash=receipt.anchor_receipt_hash,
                signature_key_id=receipt.signature_key_id,
            )
        return TrustLedgerVerification(
            receipt.bundle_id,
            True,
            "anchor_verified",
            expected_bundle_hash=expected_receipt_hash,
            observed_bundle_hash=receipt.anchor_receipt_hash,
            signature_key_id=receipt.signature_key_id,
        )


def _bundle_hash_from_draft(draft: TrustLedgerBundleDraft) -> str:
    return _stable_hash({
        "tenant_id": draft.tenant_id,
        "command_id": draft.command_id,
        "terminal_certificate_id": draft.terminal_certificate_id,
        "deployment_id": draft.deployment_id,
        "commit_sha": draft.commit_sha,
        "hash_chain_root": draft.hash_chain_root,
        "evidence_refs": tuple(draft.evidence_refs),
        "issued_at": draft.issued_at,
        "external_anchor_ref": draft.external_anchor_ref,
        "external_anchor_status": draft.external_anchor_status,
        "metadata": draft.metadata,
    })


def _bundle_hash(bundle: TrustLedgerBundle) -> str:
    return _stable_hash({
        "tenant_id": bundle.tenant_id,
        "command_id": bundle.command_id,
        "terminal_certificate_id": bundle.terminal_certificate_id,
        "deployment_id": bundle.deployment_id,
        "commit_sha": bundle.commit_sha,
        "hash_chain_root": bundle.hash_chain_root,
        "evidence_refs": tuple(bundle.evidence_refs),
        "issued_at": bundle.issued_at,
        "external_anchor_ref": bundle.external_anchor_ref,
        "external_anchor_status": bundle.external_anchor_status,
        "metadata": bundle.metadata,
    })


def _signature(bundle: TrustLedgerBundle, *, signing_secret: str) -> str:
    payload = asdict(bundle)
    payload["signature"] = ""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hmac.new(signing_secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def _artifact_root_hash(artifacts: tuple[TrustLedgerEvidenceArtifact, ...]) -> str:
    payload = [
        {
            "artifact_type": artifact.artifact_type,
            "artifact_id": artifact.artifact_id,
            "artifact_hash": artifact.artifact_hash,
            "evidence_ref": artifact.evidence_ref,
            "required": artifact.required,
            "metadata": artifact.metadata,
        }
        for artifact in sorted(artifacts, key=lambda item: (item.artifact_type, item.artifact_id))
    ]
    return _stable_hash({"artifacts": payload})


def _anchor_receipt_hash(receipt: ExternalProofAnchorReceipt) -> str:
    payload = asdict(receipt)
    payload["signature"] = ""
    payload["anchor_receipt_hash"] = ""
    return _stable_hash(payload)


def _anchor_signature(receipt: ExternalProofAnchorReceipt, *, signing_secret: str) -> str:
    payload = asdict(receipt)
    payload["signature"] = ""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hmac.new(signing_secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name}_required")


def _require_refs(values: tuple[str, ...]) -> tuple[str, ...]:
    refs = tuple(values)
    if not refs:
        raise ValueError("evidence_refs_required")
    for ref in refs:
        _require_text(ref, "evidence_ref")
    return refs


def _require_artifacts(values: tuple[TrustLedgerEvidenceArtifact, ...]) -> tuple[TrustLedgerEvidenceArtifact, ...]:
    artifacts = tuple(values)
    if not artifacts:
        raise ValueError("evidence_artifacts_required")
    for artifact in artifacts:
        if not isinstance(artifact, TrustLedgerEvidenceArtifact):
            raise ValueError("evidence_artifact_contract_invalid")
    return artifacts


def _missing_required_anchor_types(required_types: tuple[str, ...]) -> tuple[str, ...]:
    required = {"command", "execution_receipt", "verification_result", "terminal_certificate"}
    return tuple(sorted(required.difference(required_types)))


def _require_anchor_artifact_identity(
    bundle: TrustLedgerBundle,
    artifacts: tuple[TrustLedgerEvidenceArtifact, ...],
) -> None:
    command_artifact_ids = {
        artifact.artifact_id
        for artifact in artifacts
        if artifact.artifact_type == "command"
    }
    terminal_certificate_artifact_ids = {
        artifact.artifact_id
        for artifact in artifacts
        if artifact.artifact_type == "terminal_certificate"
    }
    if command_artifact_ids != {bundle.command_id}:
        raise ValueError("command_artifact_id_mismatch")
    if terminal_certificate_artifact_ids != {bundle.terminal_certificate_id}:
        raise ValueError("terminal_certificate_artifact_id_mismatch")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
