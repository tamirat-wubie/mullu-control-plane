"""Governed operations read model.

Purpose: unify loop registration, evidence, receipts, closure contracts, drift
checks, gaps, and readiness into one non-mutating operations snapshot.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: dataclasses, enum, and gateway command-spine canonical hashing.
Invariants:
  - Missing required evidence is emitted as a gap, never as success.
  - Closure requires explicit evidence and an approval boundary decision.
  - Drift checks compare declared state to observed state.
  - The snapshot is a read model and performs no external mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterable, Mapping

from gateway.command_spine import canonical_hash


class GapSeverity(StrEnum):
    """Bounded severity for one governed-operations gap."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class DriftStatus(StrEnum):
    """Declared-versus-observed state comparison result."""

    ALIGNED = "aligned"
    DRIFTED = "drifted"
    UNKNOWN = "unknown"


class ClosureStatus(StrEnum):
    """Closure result for one governed loop."""

    CLOSED = "closed"
    OPEN = "open"
    BLOCKED = "blocked"


class ReadinessClass(StrEnum):
    """Universal governed-operations readiness class."""

    CLASS_A = "class_a"
    CLASS_B = "class_b"
    CLASS_C = "class_c"
    CLASS_D = "class_d"


@dataclass(frozen=True, slots=True)
class ReceiptRecord:
    """Standard evidence receipt projected from existing subsystems."""

    receipt_id: str
    action: str
    actor: str
    authority: str
    input_hash: str
    output_hash: str
    evidence_refs: tuple[str, ...]
    policy_result: str
    timestamp: str
    status: str

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "action",
            "actor",
            "authority",
            "input_hash",
            "output_hash",
            "policy_result",
            "timestamp",
            "status",
        ):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "evidence_refs", _normalize_refs(self.evidence_refs, "evidence_refs"))


@dataclass(frozen=True, slots=True)
class ClosureContract:
    """Closure requirements for one governed loop."""

    contract_id: str
    completion_conditions: tuple[str, ...]
    required_evidence_refs: tuple[str, ...]
    rollback_path: str
    human_approval_boundary: str

    def __post_init__(self) -> None:
        for field_name in ("contract_id", "rollback_path", "human_approval_boundary"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "completion_conditions",
            _normalize_refs(self.completion_conditions, "completion_conditions"),
        )
        object.__setattr__(
            self,
            "required_evidence_refs",
            _normalize_refs(self.required_evidence_refs, "required_evidence_refs"),
        )


@dataclass(frozen=True, slots=True)
class LoopRegistration:
    """Registered governed operations loop."""

    loop_id: str
    system_ref: str
    purpose: str
    owner: str
    declared_state: str
    closure_contract: ClosureContract
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("loop_id", "system_ref", "purpose", "owner", "declared_state"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "evidence_refs", _normalize_refs(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DriftCheck:
    """Declared state compared with observed state."""

    drift_id: str
    loop_id: str
    declared_state: str
    observed_state: str
    status: DriftStatus
    evidence_refs: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable drift check."""
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


@dataclass(frozen=True, slots=True)
class GapRecord:
    """First-class governed operations gap."""

    gap_id: str
    severity: GapSeverity
    source: str
    evidence_missing: tuple[str, ...]
    blocker_type: str
    owner: str
    closure_condition: str

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable gap record."""
        payload = asdict(self)
        payload["severity"] = self.severity.value
        payload["evidence_missing"] = list(self.evidence_missing)
        return payload


@dataclass(frozen=True, slots=True)
class LoopClosureResult:
    """Closure evaluation for one loop registration."""

    loop_id: str
    status: ClosureStatus
    closed: bool
    missing_evidence_refs: tuple[str, ...]
    drift_status: DriftStatus
    closure_evidence_refs: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable closure result."""
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["drift_status"] = self.drift_status.value
        payload["missing_evidence_refs"] = list(self.missing_evidence_refs)
        payload["closure_evidence_refs"] = list(self.closure_evidence_refs)
        return payload


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    """Unified governed operations readiness snapshot."""

    snapshot_id: str
    generated_at: str
    readiness_class: ReadinessClass
    readiness_status: str
    loop_count: int
    closed_loop_count: int
    blocking_gap_count: int
    gap_count: int
    drift_count: int
    loops: tuple[LoopRegistration, ...]
    receipts: tuple[ReceiptRecord, ...]
    closure_results: tuple[LoopClosureResult, ...]
    drift_checks: tuple[DriftCheck, ...]
    gaps: tuple[GapRecord, ...]
    evidence_refs: tuple[str, ...]
    snapshot_hash: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON snapshot."""
        payload = asdict(self)
        payload["readiness_class"] = self.readiness_class.value
        payload["loops"] = [_loop_to_json(loop) for loop in self.loops]
        payload["receipts"] = [_receipt_to_json(receipt) for receipt in self.receipts]
        payload["closure_results"] = [result.to_json_dict() for result in self.closure_results]
        payload["drift_checks"] = [check.to_json_dict() for check in self.drift_checks]
        payload["gaps"] = [gap.to_json_dict() for gap in self.gaps]
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


class GovernedOperationsKernel:
    """Build non-mutating governed operations readiness snapshots."""

    def build_snapshot(
        self,
        *,
        loops: Iterable[LoopRegistration],
        receipts: Iterable[ReceiptRecord] = (),
        observed_states: Mapping[str, str] | None = None,
        generated_at: str,
    ) -> ReadinessSnapshot:
        """Evaluate registered loops into one readiness snapshot."""
        _require_text(generated_at, "generated_at")
        loop_tuple = tuple(loops)
        receipt_tuple = tuple(receipts)
        if not loop_tuple:
            raise ValueError("loops_required")
        observed = {str(key): str(value) for key, value in (observed_states or {}).items()}
        evidence_refs = _evidence_index(loop_tuple, receipt_tuple)

        closure_results: list[LoopClosureResult] = []
        drift_checks: list[DriftCheck] = []
        gaps: list[GapRecord] = []
        for loop in loop_tuple:
            observed_state = observed.get(loop.loop_id, "")
            drift_check = _drift_check(loop, observed_state)
            drift_checks.append(drift_check)
            missing_evidence = tuple(
                ref for ref in loop.closure_contract.required_evidence_refs
                if ref not in evidence_refs
            )
            loop_gaps = _loop_gaps(loop, drift_check, missing_evidence)
            gaps.extend(loop_gaps)
            closure_status = _closure_status(loop_gaps, missing_evidence, drift_check)
            closure_results.append(LoopClosureResult(
                loop_id=loop.loop_id,
                status=closure_status,
                closed=closure_status == ClosureStatus.CLOSED,
                missing_evidence_refs=missing_evidence,
                drift_status=drift_check.status,
                closure_evidence_refs=tuple(
                    ref for ref in loop.closure_contract.required_evidence_refs
                    if ref in evidence_refs
                ),
            ))

        readiness_class, readiness_status = _readiness(
            closure_results=tuple(closure_results),
            gaps=tuple(gaps),
        )
        unsigned = ReadinessSnapshot(
            snapshot_id="pending",
            generated_at=generated_at,
            readiness_class=readiness_class,
            readiness_status=readiness_status,
            loop_count=len(loop_tuple),
            closed_loop_count=sum(1 for result in closure_results if result.closed),
            blocking_gap_count=sum(1 for gap in gaps if gap.severity == GapSeverity.BLOCKING),
            gap_count=len(gaps),
            drift_count=sum(1 for check in drift_checks if check.status == DriftStatus.DRIFTED),
            loops=loop_tuple,
            receipts=receipt_tuple,
            closure_results=tuple(closure_results),
            drift_checks=tuple(drift_checks),
            gaps=tuple(gaps),
            evidence_refs=tuple(sorted(evidence_refs)),
            snapshot_hash="",
        )
        snapshot_hash = canonical_hash(unsigned.to_json_dict())
        return replace(
            unsigned,
            snapshot_id=f"governed-operations-{snapshot_hash[:16]}",
            snapshot_hash=snapshot_hash,
        )


def default_loop_registry() -> tuple[LoopRegistration, ...]:
    """Return the v1 Mullu governed-operations loop registry."""
    return (
        _loop(
            "deployment_witness",
            "gateway.deployment_witness",
            "Bind deployment publication claims to health, witness, proof, and domain evidence.",
            "ops",
            "witnessed",
            ("health_pass", "witness_pass", "proof_verify_pass", "domain_declared"),
            ("deployment_witness:current", "runtime_health:pass", "proof_verify:pass", "domain:declared"),
            "revert publication workflow or keep Foundation Mode deferral",
        ),
        _loop(
            "runtime_conformance",
            "gateway.runtime_conformance",
            "Bind runtime readiness to signed conformance evidence.",
            "ops",
            "conformant",
            ("conformance_certificate_signed", "core_canaries_evaluated"),
            ("runtime_conformance:current",),
            "retain previous conformance certificate and block promotion",
        ),
        _loop(
            "audit_proof_verification",
            "gateway.audit_trace_verifier",
            "Bind audit and proof claims to anchor and proof verification evidence.",
            "quality",
            "verified",
            ("audit_anchor_present", "proof_verification_passed"),
            ("audit_anchor:current", "proof_verify:pass"),
            "keep proof claim AwaitingEvidence until anchor or proof recovers",
        ),
        _loop(
            "authority_obligations",
            "gateway.authority_obligation_mesh",
            "Bind authority readiness to clear responsibility debt.",
            "governance",
            "clear",
            ("responsibility_debt_clear", "approval_boundary_decided"),
            ("authority:witness",),
            "escalate overdue obligations and block effect-bearing promotion",
        ),
        _loop(
            "cognitive_outcome_loop",
            "mcoi.intelligence_coordination_episode",
            "Bind symbolic outcome claims to episode receipts and verification.",
            "quality",
            "closed",
            ("episode_receipt_present", "outcome_verification_present"),
            ("cognitive_outcome:receipt", "cognitive_outcome:verification"),
            "retain outcome as AwaitingEvidence and block learning promotion",
        ),
        _loop(
            "governed_code_change_loop",
            "software_dev.governed_code_change_loop",
            "Bind code-change closure to tests, validators, receipts, and rollback evidence.",
            "engineering",
            "closed",
            ("tests_passed", "validators_passed", "rollback_path_documented"),
            ("code_change:tests", "code_change:validators", "code_change:rollback"),
            "revert only task-owned changes or open incident handoff",
        ),
        _loop(
            "adapter_promotion_loop",
            "gateway.connector_certification",
            "Bind adapter promotion to certification, redaction, timeout, retry, and rollback evidence.",
            "engineering",
            "certified",
            ("adapter_certification_passed", "receipt_contract_present", "rollback_path_present"),
            ("adapter:certification", "adapter:receipt_contract", "adapter:rollback"),
            "keep adapter in sandbox or pilot state",
        ),
    )


def receipt_from_projection(
    *,
    receipt_id: str,
    action: str,
    actor: str,
    authority: str,
    evidence_refs: Iterable[str],
    policy_result: str,
    timestamp: str,
    status: str,
    input_payload: Mapping[str, Any] | None = None,
    output_payload: Mapping[str, Any] | None = None,
) -> ReceiptRecord:
    """Create a standard receipt from an existing subsystem projection."""
    return ReceiptRecord(
        receipt_id=receipt_id,
        action=action,
        actor=actor,
        authority=authority,
        input_hash=canonical_hash(dict(input_payload or {})),
        output_hash=canonical_hash(dict(output_payload or {})),
        evidence_refs=tuple(evidence_refs),
        policy_result=policy_result,
        timestamp=timestamp,
        status=status,
    )


def _loop(
    loop_id: str,
    system_ref: str,
    purpose: str,
    owner: str,
    declared_state: str,
    completion_conditions: tuple[str, ...],
    required_evidence_refs: tuple[str, ...],
    rollback_path: str,
) -> LoopRegistration:
    return LoopRegistration(
        loop_id=loop_id,
        system_ref=system_ref,
        purpose=purpose,
        owner=owner,
        declared_state=declared_state,
        closure_contract=ClosureContract(
            contract_id=f"{loop_id}_closure_v1",
            completion_conditions=completion_conditions,
            required_evidence_refs=required_evidence_refs,
            rollback_path=rollback_path,
            human_approval_boundary="read_only",
        ),
    )


def _drift_check(loop: LoopRegistration, observed_state: str) -> DriftCheck:
    if not observed_state.strip():
        status = DriftStatus.UNKNOWN
    elif observed_state == loop.declared_state:
        status = DriftStatus.ALIGNED
    else:
        status = DriftStatus.DRIFTED
    drift_hash = canonical_hash({
        "loop_id": loop.loop_id,
        "declared_state": loop.declared_state,
        "observed_state": observed_state,
        "status": status.value,
    })
    return DriftCheck(
        drift_id=f"drift-{drift_hash[:16]}",
        loop_id=loop.loop_id,
        declared_state=loop.declared_state,
        observed_state=observed_state or "unknown",
        status=status,
        evidence_refs=loop.evidence_refs,
    )


def _loop_gaps(
    loop: LoopRegistration,
    drift_check: DriftCheck,
    missing_evidence: tuple[str, ...],
) -> tuple[GapRecord, ...]:
    gaps: list[GapRecord] = []
    if missing_evidence:
        gaps.append(_gap(
            loop,
            severity=GapSeverity.BLOCKING,
            evidence_missing=missing_evidence,
            blocker_type="evidence_missing",
            closure_condition="required_evidence_refs_present",
        ))
    if drift_check.status == DriftStatus.DRIFTED:
        gaps.append(_gap(
            loop,
            severity=GapSeverity.BLOCKING,
            evidence_missing=(),
            blocker_type="runtime_drift",
            closure_condition=f"observed_state_matches:{loop.declared_state}",
        ))
    if drift_check.status == DriftStatus.UNKNOWN:
        gaps.append(_gap(
            loop,
            severity=GapSeverity.WARNING,
            evidence_missing=(),
            blocker_type="observed_state_unknown",
            closure_condition="observed_state_present",
        ))
    if not _approval_boundary_satisfied(loop.closure_contract.human_approval_boundary):
        gaps.append(_gap(
            loop,
            severity=GapSeverity.BLOCKING,
            evidence_missing=(),
            blocker_type="approval_boundary_unresolved",
            closure_condition="human_approval_boundary_satisfied",
        ))
    return tuple(gaps)


def _gap(
    loop: LoopRegistration,
    *,
    severity: GapSeverity,
    evidence_missing: tuple[str, ...],
    blocker_type: str,
    closure_condition: str,
) -> GapRecord:
    gap_hash = canonical_hash({
        "loop_id": loop.loop_id,
        "severity": severity.value,
        "evidence_missing": evidence_missing,
        "blocker_type": blocker_type,
        "closure_condition": closure_condition,
    })
    return GapRecord(
        gap_id=f"gap-{gap_hash[:16]}",
        severity=severity,
        source=loop.loop_id,
        evidence_missing=evidence_missing,
        blocker_type=blocker_type,
        owner=loop.owner,
        closure_condition=closure_condition,
    )


def _closure_status(
    gaps: tuple[GapRecord, ...],
    missing_evidence: tuple[str, ...],
    drift_check: DriftCheck,
) -> ClosureStatus:
    if any(gap.severity == GapSeverity.BLOCKING for gap in gaps):
        return ClosureStatus.BLOCKED
    if missing_evidence or drift_check.status != DriftStatus.ALIGNED or gaps:
        return ClosureStatus.OPEN
    return ClosureStatus.CLOSED


def _readiness(
    *,
    closure_results: tuple[LoopClosureResult, ...],
    gaps: tuple[GapRecord, ...],
) -> tuple[ReadinessClass, str]:
    if any(gap.severity == GapSeverity.BLOCKING for gap in gaps):
        return ReadinessClass.CLASS_D, "blocked"
    if gaps:
        return ReadinessClass.CLASS_B, "verified_with_gaps"
    if all(result.closed for result in closure_results):
        return ReadinessClass.CLASS_A, "closed"
    return ReadinessClass.CLASS_C, "degraded"


def _evidence_index(
    loops: tuple[LoopRegistration, ...],
    receipts: tuple[ReceiptRecord, ...],
) -> set[str]:
    refs: set[str] = set()
    for loop in loops:
        refs.update(loop.evidence_refs)
    for receipt in receipts:
        refs.add(receipt.receipt_id)
        refs.update(receipt.evidence_refs)
    return refs


def _approval_boundary_satisfied(value: str) -> bool:
    return value in {"not_required", "read_only", "satisfied"}


def _loop_to_json(loop: LoopRegistration) -> dict[str, Any]:
    payload = asdict(loop)
    payload["evidence_refs"] = list(loop.evidence_refs)
    payload["closure_contract"]["completion_conditions"] = list(loop.closure_contract.completion_conditions)
    payload["closure_contract"]["required_evidence_refs"] = list(loop.closure_contract.required_evidence_refs)
    return payload


def _receipt_to_json(receipt: ReceiptRecord) -> dict[str, Any]:
    payload = asdict(receipt)
    payload["evidence_refs"] = list(receipt.evidence_refs)
    return payload


def _normalize_refs(values: Iterable[str], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    refs = tuple(str(value).strip() for value in values if str(value).strip())
    if not refs and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return refs


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
