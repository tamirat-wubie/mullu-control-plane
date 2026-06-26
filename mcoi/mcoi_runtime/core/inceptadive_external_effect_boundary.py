"""External-effect boundary advisory for InceptaDive.

Purpose: derive governed evidence and authority obligations for candidate
actions that may cross file, connector, public, tenant, financial, legal, or
production boundaries.
Governance scope: advisory classification only; this module cannot approve,
dispatch, execute, mutate memory, or replace a governance verdict.
Dependencies: action taxonomy, shared shadow types, deterministic identifiers,
and runtime invariant helpers.
Invariants: output is redacted, bounded, deterministic, and always carries
execution_authority=false.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Sequence

from mcoi_runtime.core.inceptadive_action_taxonomy import classify_shadow_action
from mcoi_runtime.core.inceptadive_shadow_types import ShadowContext, ShadowSeverity, severity_rank
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier

_PROOF_TERMS = frozenset({"approved", "approval", "verified", "receipt", "evidence", "review", "proof"})


@dataclass(frozen=True)
class ExternalEffectBoundaryAdvisory:
    """Redacted advisory describing effect-bearing obligations."""

    advisory_id: str
    request_id: str
    context_hash: str
    action_families: tuple[str, ...]
    authority_obligations: tuple[str, ...]
    evidence_obligations: tuple[str, ...]
    missing_authority_obligations: tuple[str, ...]
    missing_evidence_obligations: tuple[str, ...]
    required_evidence_ref_count: int
    authority_receipt_count: int
    retrieval_receipt_count: int
    external_side_effect: bool
    strict_preflight_required: bool
    recommended_outcome: str
    recommended_action: str
    execution_authority: bool = False
    connector_dispatch_authority: bool = False
    memory_write_authority: bool = False
    governance_verdict_authority: bool = False

    def __post_init__(self) -> None:
        if not self.advisory_id.strip():
            raise RuntimeCoreInvariantError("external-effect advisory_id must be non-empty")
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("external-effect request_id must be non-empty")
        if not self.context_hash.strip():
            raise RuntimeCoreInvariantError("external-effect context_hash must be non-empty")
        if (
            self.execution_authority
            or self.connector_dispatch_authority
            or self.memory_write_authority
            or self.governance_verdict_authority
        ):
            raise RuntimeCoreInvariantError("external-effect advisory cannot carry authority")

    @property
    def awaiting_evidence(self) -> bool:
        return self.recommended_outcome == "AwaitingEvidence"

    def to_dict(self) -> dict[str, object]:
        """Return a redacted read model without raw request or receipt refs."""

        return {
            "advisory_id": self.advisory_id,
            "request_id": self.request_id,
            "context_hash": self.context_hash,
            "action_families": list(self.action_families),
            "authority_obligations": list(self.authority_obligations),
            "evidence_obligations": list(self.evidence_obligations),
            "missing_authority_obligations": list(self.missing_authority_obligations),
            "missing_evidence_obligations": list(self.missing_evidence_obligations),
            "required_evidence_ref_count": self.required_evidence_ref_count,
            "authority_receipt_count": self.authority_receipt_count,
            "retrieval_receipt_count": self.retrieval_receipt_count,
            "external_side_effect": self.external_side_effect,
            "strict_preflight_required": self.strict_preflight_required,
            "awaiting_evidence": self.awaiting_evidence,
            "recommended_outcome": self.recommended_outcome,
            "recommended_action": self.recommended_action,
            "execution_authority": False,
            "connector_dispatch_authority": False,
            "memory_write_authority": False,
            "governance_verdict_authority": False,
            "raw_request_text_exposed": False,
            "private_memory_exposed": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ExternalEffectBoundaryAdvisory":
        """Rebuild a redacted advisory from persisted JSONL metadata."""

        try:
            _reject_true_persisted_flags(
                value,
                (
                    "execution_authority",
                    "connector_dispatch_authority",
                    "memory_write_authority",
                    "governance_verdict_authority",
                    "raw_request_text_exposed",
                    "private_memory_exposed",
                ),
            )
            return cls(
                advisory_id=_mapping_text(value, "advisory_id"),
                request_id=_mapping_text(value, "request_id"),
                context_hash=_mapping_text(value, "context_hash"),
                action_families=_tuple_text_object(value.get("action_families")),
                authority_obligations=_tuple_text_object(value.get("authority_obligations")),
                evidence_obligations=_tuple_text_object(value.get("evidence_obligations")),
                missing_authority_obligations=_tuple_text_object(value.get("missing_authority_obligations")),
                missing_evidence_obligations=_tuple_text_object(value.get("missing_evidence_obligations")),
                required_evidence_ref_count=_mapping_int(value, "required_evidence_ref_count"),
                authority_receipt_count=_mapping_int(value, "authority_receipt_count"),
                retrieval_receipt_count=_mapping_int(value, "retrieval_receipt_count"),
                external_side_effect=_mapping_bool(value, "external_side_effect"),
                strict_preflight_required=_mapping_bool(value, "strict_preflight_required"),
                recommended_outcome=_mapping_text(value, "recommended_outcome"),
                recommended_action=_mapping_text(value, "recommended_action"),
                execution_authority=False,
                connector_dispatch_authority=False,
                memory_write_authority=False,
                governance_verdict_authority=False,
            )
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            raise RuntimeCoreInvariantError(f"invalid persisted ExternalEffectBoundaryAdvisory: {exc}") from exc


def build_external_effect_boundary_advisory(
    context: ShadowContext,
    *,
    required_evidence_refs: Sequence[str] | None = None,
    authority_receipt_refs: Sequence[str] | None = None,
) -> ExternalEffectBoundaryAdvisory:
    """Build a redacted advisory for effect-bearing candidate action boundaries.

    Input contract: caller supplies a shadow context plus optional evidence and
    authority receipt references. Output contract: redacted obligation summary.
    Error contract: invalid context propagates explicit invariant errors.
    """

    checked = context.with_integrity()
    required_evidence_count = _non_empty_count(required_evidence_refs)
    authority_receipt_count = _non_empty_count(authority_receipt_refs)
    classification = classify_shadow_action(checked)
    text_tokens = frozenset(_word_tokens(checked.text_surface()))
    action_families = classification.action_families
    authority_obligations = _authority_obligations(classification.authority_required)
    evidence_obligations = _evidence_obligations(action_families, classification.evidence_required)
    evidence_present = bool(
        required_evidence_count
        or checked.retrieval_receipt_ids
        or text_tokens.intersection(_PROOF_TERMS)
    )
    missing_authority = () if authority_receipt_count or not authority_obligations else authority_obligations
    missing_evidence = () if evidence_present or not evidence_obligations else evidence_obligations
    recommended_outcome, recommended_action = _recommendation(
        classification_blocked=classification.blocked_by_authority,
        strict_preflight_required=classification.strict_preflight_required,
        missing_authority=missing_authority,
        missing_evidence=missing_evidence,
        external_side_effect=classification.external_side_effect,
        context=checked,
    )
    advisory_id = stable_identifier(
        "inceptadive-external-effect-advisory",
        {
            "request_id": checked.request_id,
            "context_hash": checked.context_hash,
            "families": action_families,
            "missing_authority": missing_authority,
            "missing_evidence": missing_evidence,
            "outcome": recommended_outcome,
        },
    )
    return ExternalEffectBoundaryAdvisory(
        advisory_id=advisory_id,
        request_id=checked.request_id,
        context_hash=checked.context_hash,
        action_families=action_families,
        authority_obligations=authority_obligations,
        evidence_obligations=evidence_obligations,
        missing_authority_obligations=missing_authority,
        missing_evidence_obligations=missing_evidence,
        required_evidence_ref_count=required_evidence_count,
        authority_receipt_count=authority_receipt_count,
        retrieval_receipt_count=len(checked.retrieval_receipt_ids),
        external_side_effect=classification.external_side_effect,
        strict_preflight_required=classification.strict_preflight_required,
        recommended_outcome=recommended_outcome,
        recommended_action=recommended_action,
        execution_authority=False,
        connector_dispatch_authority=False,
        memory_write_authority=False,
        governance_verdict_authority=False,
    )


def _authority_obligations(authority_required: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in authority_required if str(item).strip()))


def _evidence_obligations(action_families: Sequence[str], evidence_required: bool) -> tuple[str, ...]:
    if not evidence_required:
        return ()
    obligations: list[str] = []
    for family in action_families:
        obligations.append(f"{family}:evidence_ref")
    return tuple(dict.fromkeys(obligations))


def _recommendation(
    *,
    classification_blocked: bool,
    strict_preflight_required: bool,
    missing_authority: tuple[str, ...],
    missing_evidence: tuple[str, ...],
    external_side_effect: bool,
    context: ShadowContext,
) -> tuple[str, str]:
    if classification_blocked:
        return (
            "GovernanceBlocked",
            "keep candidate blocked until component authority evidence is upgraded",
        )
    if missing_authority or missing_evidence:
        return (
            "AwaitingEvidence",
            "attach governed authority and evidence receipts before any external-effect execution path",
        )
    if strict_preflight_required or external_side_effect or severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH):
        return (
            "SolvedUnverified",
            "continue to strict preflight and Mullu governance; this advisory grants no execution authority",
        )
    return (
        "SolvedUnverified",
        "no external-effect obligation found; continue through normal governance",
    )


def _non_empty_count(values: Sequence[str] | None) -> int:
    return sum(1 for value in values or () if str(value).strip())


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_#.-]+", value.lower()))


def _tuple_text_object(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise RuntimeCoreInvariantError("expected a list or tuple of text values")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _mapping_text(value: Mapping[str, object], key: str, *, default: str = "") -> str:
    return str(value.get(key, default) or default)


def _mapping_bool(value: Mapping[str, object], key: str, *, default: bool = False) -> bool:
    item = value.get(key, default)
    if not isinstance(item, bool):
        raise RuntimeCoreInvariantError(f"{key} must be a boolean")
    return item


def _mapping_int(value: Mapping[str, object], key: str, *, default: int = 0) -> int:
    item = value.get(key, default)
    if not isinstance(item, int) or isinstance(item, bool):
        raise RuntimeCoreInvariantError(f"{key} must be an integer")
    if item < 0:
        raise RuntimeCoreInvariantError(f"{key} must not be negative")
    return item


def _reject_true_persisted_flags(value: Mapping[str, object], flag_names: Sequence[str]) -> None:
    for flag_name in flag_names:
        if flag_name in value and value[flag_name] is not False:
            raise RuntimeCoreInvariantError(f"{flag_name} must be false")
