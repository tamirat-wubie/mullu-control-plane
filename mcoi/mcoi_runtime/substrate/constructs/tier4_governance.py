"""
Tier 4 — Governance Constructs (Authority & Validation).

Where lower tiers describe what exists, what changes, what composes, and what
coordinates, Tier 4 names *who has the right* to make claims and *how* those
claims are validated, accountable, and preserved.

These are the structural roots of Φ_gov. The Φ-operator wrappers in the
runtime call into Tier 4 constructs; Tier 4 constructs are the data side of
governance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from mcoi_runtime.substrate.constructs.tier1_foundational import (
    ConstructBase,
    ConstructType,
    Tier,
)


@dataclass
class Source(ConstructBase):
    """
    WHAT: constraint_origination — the authority that issues a constraint.

    A Source names where a Constraint comes from: an authority, with a scope
    and a legitimacy basis. Distinct from Constraint itself (which is the
    rule); Source is the rule's provenance.
    """

    type: ConstructType = ConstructType.SOURCE
    tier: Tier = Tier.GOVERNANCE

    origin_identifier: str = ""
    authority_kind: str = "delegated"  # primary | delegated | derived
    scope_description: str = ""
    legitimacy_basis: str = ""

    def __post_init__(self) -> None:
        if not self.origin_identifier:
            raise ValueError("Source requires origin_identifier")
        if self.authority_kind not in {"primary", "delegated", "derived"}:
            raise ValueError(f"invalid authority_kind: {self.authority_kind}")
        if not self.scope_description:
            raise ValueError("Source requires scope_description")
        if not self.legitimacy_basis:
            raise ValueError(
                "Source requires legitimacy_basis; "
                "unjustified authority is the same fabrication pattern as MUSIA_MODE"
            )
        if not self.invariants:
            self.invariants = (
                "origin_identified",
                "authority_classified",
                "scope_specified",
                "legitimacy_evidenced",
            )
        super().__post_init__()


@dataclass
class Binding(ConstructBase):
    """
    WHAT: causal_responsibility — agent is accountable for action's consequence.

    Binding names that an agent took an action and is therefore answerable for
    the resulting Change. Distinct from Causation (which names the mechanism)
    and from Source (which names rule origin).
    """

    type: ConstructType = ConstructType.BINDING
    tier: Tier = Tier.GOVERNANCE

    agent_identifier: str = ""
    action_description: str = ""
    consequence_change_id: Optional[UUID] = None
    accountability_kind: str = "direct"  # direct | delegated | shared

    def __post_init__(self) -> None:
        if not self.agent_identifier:
            raise ValueError("Binding requires agent_identifier")
        if not self.action_description:
            raise ValueError("Binding requires action_description")
        if self.consequence_change_id is None:
            raise ValueError("Binding requires consequence_change_id")
        if self.accountability_kind not in {"direct", "delegated", "shared"}:
            raise ValueError(
                f"invalid accountability_kind: {self.accountability_kind}"
            )
        if not self.invariants:
            self.invariants = (
                "agent_identified",
                "action_named",
                "consequence_referenced",
                "accountability_classified",
            )
        super().__post_init__()


@dataclass
class Validation(ConstructBase):
    """
    WHAT: pattern_verification — formal check that a Pattern holds given evidence.

    Validation pairs criteria, evidence, and a confidence-weighted decision.
    Distinct from Inference (Tier 5, generative) and Conservation (Tier 2,
    structural invariant). Validation is the *act* of verification.
    """

    type: ConstructType = ConstructType.VALIDATION
    tier: Tier = Tier.GOVERNANCE

    target_pattern_id: Optional[UUID] = None
    criteria: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: float = 0.0  # [0, 1]
    decision: str = "unknown"  # pass | fail | unknown | budget_unknown

    def __post_init__(self) -> None:
        if self.target_pattern_id is None:
            raise ValueError("Validation requires target_pattern_id")
        if not self.criteria:
            raise ValueError("Validation requires at least one criterion")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence {self.confidence} not in [0,1]")
        if self.decision not in {"pass", "fail", "unknown", "budget_unknown"}:
            raise ValueError(f"invalid decision: {self.decision}")
        # Mirror of v2 ProofState — no silent failures
        if self.decision == "fail" and not self.evidence_refs:
            raise ValueError(
                "Validation: fail decision requires evidence_refs (no silent rejection)"
            )
        if not self.invariants:
            self.invariants = (
                "target_referenced",
                "criteria_present",
                "confidence_bounded",
                "decision_classified",
                "fail_requires_evidence",
            )
        super().__post_init__()


@dataclass
class Evolution(ConstructBase):
    """
    WHAT: constraint_modification — proposed or applied change to a Constraint.

    Evolution names that a Constraint is being changed: from current form to
    proposed form, with justification and impact assessment. Distinct from
    Change (Tier 1) which is about state delta; Evolution is about *rule*
    delta.
    """

    type: ConstructType = ConstructType.EVOLUTION
    tier: Tier = Tier.GOVERNANCE

    current_constraint_id: Optional[UUID] = None
    proposed_constraint_id: Optional[UUID] = None
    justification: str = ""
    impact_assessment: str = ""
    status: str = "proposed"  # proposed | reviewed | applied | rejected

    def __post_init__(self) -> None:
        if self.current_constraint_id is None:
            raise ValueError("Evolution requires current_constraint_id")
        if self.proposed_constraint_id is None:
            raise ValueError("Evolution requires proposed_constraint_id")
        if self.current_constraint_id == self.proposed_constraint_id:
            raise ValueError(
                "Evolution: proposed must differ from current (no-op evolution)"
            )
        if not self.justification:
            raise ValueError("Evolution requires justification")
        if not self.impact_assessment:
            raise ValueError("Evolution requires impact_assessment")
        if self.status not in {"proposed", "reviewed", "applied", "rejected"}:
            raise ValueError(f"invalid status: {self.status}")
        if not self.invariants:
            self.invariants = (
                "current_proposed_distinct",
                "justification_present",
                "impact_assessed",
                "status_classified",
            )
        super().__post_init__()


@dataclass
class Integrity(ConstructBase):
    """
    WHAT: pattern_persistence — the discipline that core invariants survive change.

    Integrity names which Patterns must be preserved across all Evolutions,
    how violations are detected, and what repair is invoked. Distinct from
    Conservation (Tier 2, scoped to a Boundary) — Integrity applies
    system-wide.
    """

    type: ConstructType = ConstructType.INTEGRITY
    tier: Tier = Tier.GOVERNANCE

    core_invariant_pattern_ids: tuple[UUID, ...] = ()
    violation_detection_kind: str = "audit_log_scan"
    # audit_log_scan | continuous_monitor | scheduled_assertion | external_witness
    repair_protocol: str = ""

    def __post_init__(self) -> None:
        if not self.core_invariant_pattern_ids:
            raise ValueError(
                "Integrity requires at least one core invariant Pattern"
            )
        if len(set(self.core_invariant_pattern_ids)) != len(
            self.core_invariant_pattern_ids
        ):
            raise ValueError("Integrity: invariant pattern IDs must be distinct")
        valid_detection = {
            "audit_log_scan",
            "continuous_monitor",
            "scheduled_assertion",
            "external_witness",
        }
        if self.violation_detection_kind not in valid_detection:
            raise ValueError(
                f"invalid violation_detection_kind: {self.violation_detection_kind}"
            )
        if not self.repair_protocol:
            raise ValueError(
                "Integrity requires repair_protocol; "
                "an invariant without a repair plan is a hope, not a guarantee"
            )
        if not self.invariants:
            self.invariants = (
                "invariants_present",
                "invariants_distinct",
                "detection_classified",
                "repair_protocol_specified",
            )
        super().__post_init__()


# ---- DISAMBIGUATION ----


TIER4_RESPONSIBILITIES: dict[ConstructType, str] = {
    ConstructType.SOURCE:     "WHAT_ORIGINATES_CONSTRAINTS",
    ConstructType.BINDING:    "WHAT_ASSIGNS_RESPONSIBILITY",
    ConstructType.VALIDATION: "WHAT_VERIFIES_PATTERNS",
    ConstructType.EVOLUTION:  "WHAT_MODIFIES_CONSTRAINTS",
    ConstructType.INTEGRITY:  "WHAT_PRESERVES_PATTERNS_SYSTEM_WIDE",
}


def verify_tier4_disambiguation() -> None:
    seen: set[str] = set()
    for ct, resp in TIER4_RESPONSIBILITIES.items():
        if resp in seen:
            raise ValueError(f"tier 4 responsibility overlap detected: {resp}")
        seen.add(resp)


verify_tier4_disambiguation()
