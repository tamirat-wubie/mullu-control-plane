"""Closure-gated external-effect staging for CDG-RCCM.

This module does not provide connector authority. It only enforces that an
injected executor cannot be called before a current closure certificate and
explicit authority references exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

from .contracts import (
    EvidenceScope,
    ProjectionCertificate,
    SettlementLevel,
    stable_hash,
)


class EffectStatus(StrEnum):
    STAGED = "staged"
    AUTHORIZED = "authorized"
    EXECUTED = "executed"
    VERIFIED = "verified"
    COMPENSATED = "compensated"
    RECOVERY_REQUIRED = "recovery_required"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EffectPlan:
    effect_id: str
    idempotency_key: str
    action_name: str
    payload: Mapping[str, Any]
    authority_refs: tuple[str, ...]
    preconditions: tuple[str, ...] = ()
    compensation_name: str = ""
    irreversible: bool = False

    def __post_init__(self) -> None:
        for field_name in ("effect_id", "idempotency_key", "action_name"):
            value = getattr(self, field_name)
            if type(value) is not str or not value:
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        if not self.authority_refs or any(
            type(ref) is not str or not ref for ref in self.authority_refs
        ):
            raise ValueError("authority_refs must contain non-empty strings")
        if any(type(item) is not str or not item for item in self.preconditions):
            raise ValueError("preconditions must contain non-empty strings")
        if type(self.irreversible) is not bool:
            raise ValueError("irreversible must be a bool")


@dataclass(frozen=True, slots=True)
class EffectReceipt:
    receipt_id: str
    effect_id: str
    status: EffectStatus
    closure_certificate_id: str
    execution_result: Any = None
    verification_result: Any = None
    reason: str = ""
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorldObservation:
    """Physical observation capable of promoting closure to world verification."""

    observation_id: str
    observed_value: Any
    evidence_refs: tuple[str, ...]
    evidence_scope: EvidenceScope = EvidenceScope.PHYSICALLY_VERIFIED
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if type(self.observation_id) is not str or not self.observation_id:
            raise ValueError("observation_id must be a non-empty string")
        if not self.evidence_refs or any(
            type(ref) is not str or not ref for ref in self.evidence_refs
        ):
            raise ValueError("evidence_refs must contain non-empty strings")
        if self.evidence_scope is not EvidenceScope.PHYSICALLY_VERIFIED:
            raise ValueError("world verification requires physically verified evidence")
        if (
            type(self.confidence) not in (int, float)
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("confidence must be between 0.0 and 1.0")


def issue_world_verified_certificate(
    *,
    closure_certificate: ProjectionCertificate,
    observation: WorldObservation,
) -> ProjectionCertificate:
    """Promote a current closure certificate only after physical observation."""

    if not closure_certificate.valid:
        raise ValueError("closure_certificate_stale")
    if closure_certificate.level < SettlementLevel.CLOSURE_CERTIFIED:
        raise ValueError("closure_certificate_level_insufficient")
    payload = {
        "closure_certificate_id": closure_certificate.certificate_id,
        "observation_id": observation.observation_id,
        "observed_value": observation.observed_value,
        "evidence_refs": observation.evidence_refs,
        "confidence": observation.confidence,
    }
    return ProjectionCertificate(
        certificate_id=stable_hash("cdg-world-certificate", payload),
        component_id=closure_certificate.component_id,
        projection_name=closure_certificate.projection_name,
        level=SettlementLevel.WORLD_VERIFIED,
        epoch_id=closure_certificate.epoch_id,
        state_hash=stable_hash("cdg-world-state", payload),
        rule_hash=closure_certificate.rule_hash,
        input_hash=closure_certificate.input_hash,
        dependency_certificate_ids=tuple(
            dict.fromkeys(
                (
                    *closure_certificate.dependency_certificate_ids,
                    closure_certificate.certificate_id,
                )
            )
        ),
        assumptions=closure_certificate.assumptions,
        evidence_refs=tuple(
            dict.fromkeys(
                (*closure_certificate.evidence_refs, *observation.evidence_refs)
            )
        ),
        evidence_scope=EvidenceScope.PHYSICALLY_VERIFIED,
        confidence=min(
            float(closure_certificate.confidence),
            float(observation.confidence),
        ),
        value=observation.observed_value,
        audit_digest=stable_hash("cdg-world-audit", payload),
    )


class ClosureGatedEffectCommitter:
    """Idempotent effect committer that accepts only closure-certified work.

    Pre-execution blockers are deliberately not cached. A caller may repair
    missing closure or recovery evidence and retry the same idempotency key.
    Once execution is attempted, its terminal receipt is cached so retries do
    not duplicate the effect.
    """

    def __init__(self) -> None:
        self._receipts_by_idempotency_key: dict[str, EffectReceipt] = {}

    def commit(
        self,
        *,
        plan: EffectPlan,
        closure_certificate: ProjectionCertificate,
        executor: Callable[[EffectPlan], Any],
        verifier: Callable[[EffectPlan, Any], tuple[bool, Any]],
        compensator: Callable[[EffectPlan, Any], Any] | None = None,
    ) -> EffectReceipt:
        existing = self._receipts_by_idempotency_key.get(plan.idempotency_key)
        if existing is not None:
            return existing
        if not closure_certificate.valid:
            return self._blocked_receipt(
                plan,
                closure_certificate,
                "closure_certificate_stale",
            )
        if closure_certificate.level < SettlementLevel.CLOSURE_CERTIFIED:
            return self._blocked_receipt(
                plan,
                closure_certificate,
                "closure_certificate_level_insufficient",
            )
        if plan.irreversible and compensator is None:
            return self._blocked_receipt(
                plan,
                closure_certificate,
                "irreversible_effect_requires_recovery_handler",
            )

        try:
            execution_result = executor(plan)
        except Exception:
            receipt = self._receipt(
                plan,
                closure_certificate,
                EffectStatus.RECOVERY_REQUIRED,
                reason="effect_execution_fault",
            )
            self._receipts_by_idempotency_key[plan.idempotency_key] = receipt
            return receipt

        try:
            verified, verification_result = verifier(plan, execution_result)
        except Exception as exc:
            verified = False
            verification_result = f"verification_fault:{type(exc).__name__}"

        if verified:
            receipt = self._receipt(
                plan,
                closure_certificate,
                EffectStatus.VERIFIED,
                execution_result=execution_result,
                verification_result=verification_result,
            )
            self._receipts_by_idempotency_key[plan.idempotency_key] = receipt
            return receipt

        if compensator is not None:
            try:
                compensation_result = compensator(plan, execution_result)
                receipt = self._receipt(
                    plan,
                    closure_certificate,
                    EffectStatus.COMPENSATED,
                    execution_result=execution_result,
                    verification_result={
                        "verification": verification_result,
                        "compensation": compensation_result,
                    },
                    reason="effect_verification_failed_and_compensated",
                )
            except Exception:
                receipt = self._receipt(
                    plan,
                    closure_certificate,
                    EffectStatus.RECOVERY_REQUIRED,
                    execution_result=execution_result,
                    verification_result=verification_result,
                    reason="effect_compensation_fault",
                )
        else:
            receipt = self._receipt(
                plan,
                closure_certificate,
                EffectStatus.RECOVERY_REQUIRED,
                execution_result=execution_result,
                verification_result=verification_result,
                reason="effect_verification_failed_without_compensation",
            )
        self._receipts_by_idempotency_key[plan.idempotency_key] = receipt
        return receipt

    def _blocked_receipt(
        self,
        plan: EffectPlan,
        certificate: ProjectionCertificate,
        reason: str,
    ) -> EffectReceipt:
        return self._receipt(
            plan,
            certificate,
            EffectStatus.BLOCKED,
            reason=reason,
        )

    @staticmethod
    def _receipt(
        plan: EffectPlan,
        certificate: ProjectionCertificate,
        status: EffectStatus,
        *,
        execution_result: Any = None,
        verification_result: Any = None,
        reason: str = "",
    ) -> EffectReceipt:
        payload = {
            "effect_id": plan.effect_id,
            "idempotency_key": plan.idempotency_key,
            "action_name": plan.action_name,
            "status": status.value,
            "closure_certificate_id": certificate.certificate_id,
            "reason": reason,
        }
        return EffectReceipt(
            receipt_id=stable_hash("cdg-effect-receipt", payload),
            effect_id=plan.effect_id,
            status=status,
            closure_certificate_id=certificate.certificate_id,
            execution_result=execution_result,
            verification_result=verification_result,
            reason=reason,
            evidence_refs=(
                f"certificate:{certificate.certificate_id}",
                *(f"authority:{ref}" for ref in plan.authority_refs),
            ),
        )
