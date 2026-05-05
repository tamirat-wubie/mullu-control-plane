"""Gateway capability capsule installer.

Purpose: compose certification handoff evidence, capsule compilation, and
    governed registry admission into one deterministic operator receipt.
Governance scope: orchestration only; executable admission remains owned by
    GovernedCapabilityRegistry.install.
Dependencies: capability forge handoff installers, domain capsule compiler,
    governed capability registry, and command-spine canonical hashing.
Invariants:
  - Certification evidence is installed before capsule compilation.
  - Registry admission is delegated to GovernedCapabilityRegistry.install.
  - The receipt records the causal chain and is not admission authority.
  - Rejected admissions still return an audit receipt when compilation runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterable

from gateway.capability_forge import (
    CapabilityCertificationHandoff,
    CapabilityHandoffEvidenceInstallBatch,
    install_certification_handoff_evidence_batch,
)
from gateway.command_spine import canonical_hash
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    CapsuleAdmissionStatus,
    CapsuleCompilationResult,
    CapsuleInstallationRecord,
    DomainCapsule,
)
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry
from mcoi_runtime.core.invariants import stable_identifier


_ADMISSION_AUTHORITY = "GovernedCapabilityRegistry.install"
_CERTIFICATION_EVIDENCE_MANIFEST_TYPE = "capability_certification_evidence_manifest"


@dataclass(frozen=True, slots=True)
class CapabilityCapsuleAdmissionReceipt:
    """Hash-stamped audit receipt for one capsule admission orchestration."""

    receipt_id: str
    capsule_id: str
    compilation_id: str
    installation_id: str
    admission_status: str
    installed_capability_ids: tuple[str, ...]
    handoff_hashes: tuple[str, ...]
    batch_hash: str
    artifact_ids: tuple[str, ...]
    certification_evidence_manifest_id: str
    registry_capability_count: int
    registry_artifact_count: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    recorded_at: str
    admission_authority: str = _ADMISSION_AUTHORITY
    receipt_is_not_admission_authority: bool = True
    receipt_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "capsule_id",
            "compilation_id",
            "installation_id",
            "admission_status",
            "batch_hash",
            "recorded_at",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.admission_status not in {status.value for status in CapsuleAdmissionStatus}:
            raise ValueError("capsule_admission_receipt_status_invalid")
        object.__setattr__(self, "installed_capability_ids", _string_tuple(self.installed_capability_ids))
        object.__setattr__(self, "handoff_hashes", _string_tuple(self.handoff_hashes))
        object.__setattr__(self, "artifact_ids", _string_tuple(self.artifact_ids))
        object.__setattr__(self, "warnings", _string_tuple(self.warnings))
        object.__setattr__(self, "errors", _string_tuple(self.errors))
        if len(self.handoff_hashes) != len(self.installed_capability_ids):
            raise ValueError("capsule_admission_receipt_handoff_relation_mismatch")
        if self.admission_status == CapsuleAdmissionStatus.INSTALLED.value and not self.certification_evidence_manifest_id:
            raise ValueError("capsule_admission_receipt_certification_manifest_required")
        if self.admission_authority != _ADMISSION_AUTHORITY:
            raise ValueError("capsule_admission_receipt_authority_invalid")
        if self.receipt_is_not_admission_authority is not True:
            raise ValueError("capsule_admission_receipt_must_not_claim_authority")
        if self.receipt_hash:
            _require_text(self.receipt_hash, "receipt_hash")


@dataclass(frozen=True, slots=True)
class CapabilityCapsuleInstallationOutcome:
    """Full deterministic outcome for capsule admission orchestration."""

    evidence_batch: CapabilityHandoffEvidenceInstallBatch
    compilation_result: CapsuleCompilationResult
    installation_record: CapsuleInstallationRecord
    receipt: CapabilityCapsuleAdmissionReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_batch, CapabilityHandoffEvidenceInstallBatch):
            raise ValueError("evidence_batch must be CapabilityHandoffEvidenceInstallBatch")
        if not isinstance(self.compilation_result, CapsuleCompilationResult):
            raise ValueError("compilation_result must be CapsuleCompilationResult")
        if not isinstance(self.installation_record, CapsuleInstallationRecord):
            raise ValueError("installation_record must be CapsuleInstallationRecord")
        if not isinstance(self.receipt, CapabilityCapsuleAdmissionReceipt):
            raise ValueError("receipt must be CapabilityCapsuleAdmissionReceipt")
        if self.receipt.batch_hash != self.evidence_batch.batch_hash:
            raise ValueError("capsule_installation_outcome_batch_hash_mismatch")
        if self.receipt.compilation_id != self.compilation_result.compilation_id:
            raise ValueError("capsule_installation_outcome_compilation_id_mismatch")
        if self.receipt.installation_id != self.installation_record.installation_id:
            raise ValueError("capsule_installation_outcome_installation_id_mismatch")
        if self.receipt.installed_capability_ids != self.evidence_batch.installed_capability_ids:
            raise ValueError("capsule_installation_outcome_capability_relation_mismatch")


def install_certified_capsule_with_handoff_evidence(
    *,
    capsule: DomainCapsule,
    registry_entries: Iterable[CapabilityRegistryEntry],
    handoffs: Iterable[CapabilityCertificationHandoff],
    registry: GovernedCapabilityRegistry,
    clock: Callable[[], str],
    require_production_ready: bool = True,
    compiler: DomainCapsuleCompiler | None = None,
) -> CapabilityCapsuleInstallationOutcome:
    """Install a capsule by composing existing governed capability fabric gates.

    Error contract:
      - handoff batch installation errors from install_certification_handoff_evidence_batch.
      - capsule_admission_registry_type_invalid when registry is not a governed registry.
      - capsule_admission_compiler_type_invalid when compiler is not a capsule compiler.
      - receipt relation errors if an impossible outcome relation is constructed.
    """
    if not isinstance(registry, GovernedCapabilityRegistry):
        raise ValueError("capsule_admission_registry_type_invalid")
    active_compiler = compiler or DomainCapsuleCompiler(clock=clock)
    if not isinstance(active_compiler, DomainCapsuleCompiler):
        raise ValueError("capsule_admission_compiler_type_invalid")

    evidence_batch = install_certification_handoff_evidence_batch(
        registry_entries,
        handoffs,
        require_production_ready=require_production_ready,
    )
    compilation_result = active_compiler.compile(capsule, evidence_batch.registry_entries)
    installation_record = registry.install(compilation_result, evidence_batch.registry_entries)
    receipt = _stamp_receipt(
        _receipt(
            evidence_batch=evidence_batch,
            compilation_result=compilation_result,
            installation_record=installation_record,
            registry=registry,
        )
    )
    return CapabilityCapsuleInstallationOutcome(
        evidence_batch=evidence_batch,
        compilation_result=compilation_result,
        installation_record=installation_record,
        receipt=receipt,
    )


def _receipt(
    *,
    evidence_batch: CapabilityHandoffEvidenceInstallBatch,
    compilation_result: CapsuleCompilationResult,
    installation_record: CapsuleInstallationRecord,
    registry: GovernedCapabilityRegistry,
) -> CapabilityCapsuleAdmissionReceipt:
    receipt_seed = {
        "capsule_id": compilation_result.capsule_id,
        "batch_hash": evidence_batch.batch_hash,
        "compilation_id": compilation_result.compilation_id,
        "installation_id": installation_record.installation_id,
    }
    return CapabilityCapsuleAdmissionReceipt(
        receipt_id=stable_identifier("capability-capsule-admission", receipt_seed),
        capsule_id=compilation_result.capsule_id,
        compilation_id=compilation_result.compilation_id,
        installation_id=installation_record.installation_id,
        admission_status=installation_record.status.value,
        installed_capability_ids=evidence_batch.installed_capability_ids,
        handoff_hashes=evidence_batch.handoff_hashes,
        batch_hash=evidence_batch.batch_hash,
        artifact_ids=tuple(artifact.artifact_id for artifact in compilation_result.artifacts),
        certification_evidence_manifest_id=_certification_evidence_manifest_id(compilation_result),
        registry_capability_count=registry.capability_count,
        registry_artifact_count=registry.artifact_count,
        warnings=_unique_strings((*compilation_result.warnings, *installation_record.warnings)),
        errors=_unique_strings((*compilation_result.errors, *installation_record.errors)),
        recorded_at=installation_record.installed_at,
    )


def _certification_evidence_manifest_id(compilation_result: CapsuleCompilationResult) -> str:
    for artifact in compilation_result.artifacts:
        if artifact.artifact_type == _CERTIFICATION_EVIDENCE_MANIFEST_TYPE:
            return artifact.artifact_id
    return ""


def _stamp_receipt(
    receipt: CapabilityCapsuleAdmissionReceipt,
) -> CapabilityCapsuleAdmissionReceipt:
    payload = asdict(replace(receipt, receipt_hash=""))
    return replace(receipt, receipt_hash=canonical_hash(payload))


def _string_tuple(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _unique_strings(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


def _require_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name}_required")
    return normalized
