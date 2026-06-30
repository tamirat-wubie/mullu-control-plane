"""Gateway policy prover.

Purpose: Evaluate explicit policy invariants against bounded cases and emit
    schema-backed proof reports with counterexamples.
Governance scope: policy invariant validation, counterexample reporting,
    evidence anchoring, and non-mutating proof witnesses.
Dependencies: dataclasses and canonical command-spine hashing.
Invariants:
  - Proof reports are derived from explicit cases, never assumed.
  - A violated invariant must emit a concrete counterexample.
  - The prover is read-only and cannot weaken policy to prove success.
  - Empty invariant or case sets are rejected before proof emission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Mapping

from gateway.command_spine import canonical_hash


@dataclass(frozen=True, slots=True)
class PolicyProofInvariant:
    """One decidable invariant over bounded policy cases."""

    invariant_id: str
    description: str
    required_fields: tuple[str, ...]
    expected_values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.invariant_id.strip():
            raise ValueError("invariant_id_required")
        if not self.description.strip():
            raise ValueError("invariant_description_required")
        object.__setattr__(self, "invariant_id", self.invariant_id.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "required_fields", tuple(str(field) for field in self.required_fields))
        object.__setattr__(self, "expected_values", dict(self.expected_values))


@dataclass(frozen=True, slots=True)
class PolicyProofCase:
    """Bounded input case used to search for policy counterexamples."""

    case_id: str
    subject_id: str
    attributes: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id_required")
        if not self.subject_id.strip():
            raise ValueError("subject_id_required")
        object.__setattr__(self, "case_id", self.case_id.strip())
        object.__setattr__(self, "subject_id", self.subject_id.strip())
        object.__setattr__(self, "attributes", dict(self.attributes))
        object.__setattr__(self, "evidence_refs", _normalize_evidence_refs(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class PolicyCounterexample:
    """Concrete invariant violation discovered by the prover."""

    invariant_id: str
    case_id: str
    subject_id: str
    reason: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", _normalize_evidence_refs(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class PolicyProofReport:
    """Hash-bound policy proof report."""

    report_id: str
    policy_id: str
    status: str
    invariant_count: int
    case_count: int
    counterexample_count: int
    proven_invariants: tuple[str, ...]
    counterexamples: tuple[PolicyCounterexample, ...]
    evidence_refs: tuple[str, ...]
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"proved", "counterexample_found"}:
            raise ValueError("policy_proof_status_invalid")
        if self.counterexample_count != len(self.counterexamples):
            raise ValueError("counterexample_count_mismatch")
        if self.status == "proved" and self.counterexamples:
            raise ValueError("proved_report_cannot_have_counterexamples")
        if self.status == "counterexample_found" and not self.counterexamples:
            raise ValueError("counterexample_report_requires_counterexamples")
        object.__setattr__(self, "proven_invariants", tuple(self.proven_invariants))
        object.__setattr__(self, "counterexamples", tuple(self.counterexamples))
        object.__setattr__(self, "evidence_refs", _normalize_evidence_refs(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class PolicyTransitionVerdict(StrEnum):
    """VCPP v2 transition-proof verdict."""

    ALLOW = "ALLOW"
    ALLOW_WITH_ENFORCED_OBLIGATIONS = "ALLOW_WITH_ENFORCED_OBLIGATIONS"
    DENY_HARD = "DENY_HARD"
    DENY_AUTHORITY = "DENY_AUTHORITY"
    DENY_INVARIANT = "DENY_INVARIANT"
    DENY_EVIDENCE = "DENY_EVIDENCE"
    UNKNOWN_BLOCKED = "UNKNOWN_BLOCKED"
    CONFLICT_BLOCKED = "CONFLICT_BLOCKED"
    STALE_CONTEXT_BLOCKED = "STALE_CONTEXT_BLOCKED"
    LEASE_EXPIRED_REPROVE = "LEASE_EXPIRED_REPROVE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    SIMULATE_FIRST = "SIMULATE_FIRST"


class PolicyTransitionEffect(StrEnum):
    """Policy effect over a proposed transition."""

    PERMIT = "permit"
    DENY = "deny"
    REQUIRE = "require"
    INVARIANT = "invariant"


class PolicyEvidenceTrust(StrEnum):
    """Trust lattice for transition evidence."""

    UNTRUSTED = "untrusted"
    SELF_CLAIMED = "self_claimed"
    OBSERVED = "observed"
    SIGNED = "signed"
    MULTI_WITNESSED = "multi_witnessed"
    LEDGERED = "ledgered"
    ROOT_AUTHORITY = "root_authority"


class PolicyObligationPhase(StrEnum):
    """Execution phase for an enforceable policy obligation."""

    PRE = "pre"
    IN_FLIGHT = "in_flight"
    POST = "post"
    CONTINUING = "continuing"


class PolicyPrecedenceLayer(StrEnum):
    """Formal policy precedence lattice, strongest first by rank."""

    IMMUTABLE_INVARIANT = "immutable_invariant"
    LEGAL_SAFETY = "legal_safety"
    RESOURCE_OWNER = "resource_owner"
    ORGANIZATION_GOVERNANCE = "organization_governance"
    WORKFLOW_GATE = "workflow_gate"
    ROLE_PERMISSION = "role_permission"
    USER_PREFERENCE = "user_preference"
    OPTIMIZATION_HINT = "optimization_hint"


class PolicyLeaseStatus(StrEnum):
    """Execution lease verification status."""

    ACTIVE = "active"
    LEASE_EXPIRED_REPROVE = "lease_expired_reprove"
    STATE_HASH_MISMATCH = "state_hash_mismatch"
    POLICY_HASH_MISMATCH = "policy_hash_mismatch"


_EVIDENCE_TRUST_RANK = {
    PolicyEvidenceTrust.UNTRUSTED: 0,
    PolicyEvidenceTrust.SELF_CLAIMED: 1,
    PolicyEvidenceTrust.OBSERVED: 2,
    PolicyEvidenceTrust.SIGNED: 3,
    PolicyEvidenceTrust.MULTI_WITNESSED: 4,
    PolicyEvidenceTrust.LEDGERED: 5,
    PolicyEvidenceTrust.ROOT_AUTHORITY: 6,
}

_PRECEDENCE_RANK = {
    PolicyPrecedenceLayer.IMMUTABLE_INVARIANT: 100,
    PolicyPrecedenceLayer.LEGAL_SAFETY: 90,
    PolicyPrecedenceLayer.RESOURCE_OWNER: 80,
    PolicyPrecedenceLayer.ORGANIZATION_GOVERNANCE: 70,
    PolicyPrecedenceLayer.WORKFLOW_GATE: 60,
    PolicyPrecedenceLayer.ROLE_PERMISSION: 50,
    PolicyPrecedenceLayer.USER_PREFERENCE: 40,
    PolicyPrecedenceLayer.OPTIMIZATION_HINT: 10,
}

_ALLOWING_VERDICTS = {
    PolicyTransitionVerdict.ALLOW,
    PolicyTransitionVerdict.ALLOW_WITH_ENFORCED_OBLIGATIONS,
}


@dataclass(frozen=True, slots=True)
class PolicyEvidenceRequirement:
    """Evidence required by a transition policy."""

    requirement_id: str
    evidence_type: str
    minimum_trust: PolicyEvidenceTrust = PolicyEvidenceTrust.OBSERVED
    scope_symbol: str = ""
    binds_transition: bool = False

    def __post_init__(self) -> None:
        _require_text(self.requirement_id, "requirement_id")
        _require_text(self.evidence_type, "evidence_type")
        object.__setattr__(self, "requirement_id", self.requirement_id.strip())
        object.__setattr__(self, "evidence_type", self.evidence_type.strip())
        object.__setattr__(self, "scope_symbol", self.scope_symbol.strip())
        object.__setattr__(self, "minimum_trust", PolicyEvidenceTrust(str(self.minimum_trust)))


@dataclass(frozen=True, slots=True)
class PolicyEvidence:
    """Trusted evidence candidate used by the transition prover."""

    evidence_id: str
    evidence_type: str
    issuer: str
    subject_id: str
    scope_symbols: tuple[str, ...]
    trust_level: PolicyEvidenceTrust
    issued_at: str = ""
    expires_at: str = ""
    event_hash_binding: str = ""
    evidence_ref: str = ""

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "evidence_type", "issuer", "subject_id"):
            _require_text(str(getattr(self, field_name)), field_name)
        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
        object.__setattr__(self, "evidence_type", self.evidence_type.strip())
        object.__setattr__(self, "issuer", self.issuer.strip())
        object.__setattr__(self, "subject_id", self.subject_id.strip())
        object.__setattr__(self, "scope_symbols", _normalize_text_tuple(self.scope_symbols, "scope_symbols"))
        object.__setattr__(self, "trust_level", PolicyEvidenceTrust(str(self.trust_level)))
        object.__setattr__(self, "issued_at", self.issued_at.strip())
        object.__setattr__(self, "expires_at", self.expires_at.strip())
        object.__setattr__(self, "event_hash_binding", self.event_hash_binding.strip())
        object.__setattr__(self, "evidence_ref", self.evidence_ref.strip())


@dataclass(frozen=True, slots=True)
class PolicyObligation:
    """Obligation attached to an allowed or conditionally allowed transition."""

    obligation_id: str
    phase: PolicyObligationPhase
    description: str
    satisfied: bool = False
    enforceable: bool = False
    compensation_ref: str = ""

    def __post_init__(self) -> None:
        _require_text(self.obligation_id, "obligation_id")
        _require_text(self.description, "description")
        object.__setattr__(self, "obligation_id", self.obligation_id.strip())
        object.__setattr__(self, "phase", PolicyObligationPhase(str(self.phase)))
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "compensation_ref", self.compensation_ref.strip())


@dataclass(frozen=True, slots=True)
class PolicyTransitionPolicy:
    """One typed policy over activated symbols and state deltas."""

    policy_id: str
    description: str
    effect: PolicyTransitionEffect
    coverage_symbols: tuple[str, ...]
    precedence_layer: PolicyPrecedenceLayer = PolicyPrecedenceLayer.ROLE_PERMISSION
    required_delta_paths: tuple[str, ...] = ()
    forbidden_delta_paths: tuple[str, ...] = ()
    invariant_delta_paths: tuple[str, ...] = ()
    required_evidence: tuple[PolicyEvidenceRequirement, ...] = ()
    obligations: tuple[PolicyObligation, ...] = ()
    requires_simulation: bool = False

    def __post_init__(self) -> None:
        _require_text(self.policy_id, "policy_id")
        _require_text(self.description, "description")
        object.__setattr__(self, "policy_id", self.policy_id.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "effect", PolicyTransitionEffect(str(self.effect)))
        object.__setattr__(self, "coverage_symbols", _normalize_text_tuple(self.coverage_symbols, "coverage_symbols"))
        object.__setattr__(self, "precedence_layer", PolicyPrecedenceLayer(str(self.precedence_layer)))
        object.__setattr__(self, "required_delta_paths", _normalize_text_tuple(self.required_delta_paths, "required_delta_paths", allow_empty=True))
        object.__setattr__(self, "forbidden_delta_paths", _normalize_text_tuple(self.forbidden_delta_paths, "forbidden_delta_paths", allow_empty=True))
        object.__setattr__(self, "invariant_delta_paths", _normalize_text_tuple(self.invariant_delta_paths, "invariant_delta_paths", allow_empty=True))
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence))
        object.__setattr__(self, "obligations", tuple(self.obligations))


@dataclass(frozen=True, slots=True)
class PolicyTransition:
    """Exact proposed state transition submitted to VCPP v2."""

    transition_id: str
    actor_id: str
    action_id: str
    resource_id: str
    resource_type: str
    intent: str
    pre_state: dict[str, Any]
    post_state: dict[str, Any]
    context: dict[str, Any]
    proof_time: str
    actor_authenticated: bool = False
    authority_refs: tuple[str, ...] = ()
    activated_symbols: tuple[str, ...] = ()
    risk_level: str = "low"
    reversibility: str = "reversible"
    external_exposure: bool = False
    lease_seconds: int = 300
    lock_scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "transition_id",
            "actor_id",
            "action_id",
            "resource_id",
            "resource_type",
            "intent",
            "proof_time",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds_positive_required")
        _parse_iso_timestamp(self.proof_time, "proof_time")
        object.__setattr__(self, "transition_id", self.transition_id.strip())
        object.__setattr__(self, "actor_id", self.actor_id.strip())
        object.__setattr__(self, "action_id", self.action_id.strip())
        object.__setattr__(self, "resource_id", self.resource_id.strip())
        object.__setattr__(self, "resource_type", self.resource_type.strip())
        object.__setattr__(self, "intent", self.intent.strip())
        object.__setattr__(self, "pre_state", dict(self.pre_state))
        object.__setattr__(self, "post_state", dict(self.post_state))
        object.__setattr__(self, "context", dict(self.context))
        object.__setattr__(self, "proof_time", self.proof_time.strip())
        object.__setattr__(self, "authority_refs", _normalize_text_tuple(self.authority_refs, "authority_refs", allow_empty=True))
        object.__setattr__(self, "activated_symbols", _normalize_text_tuple(self.activated_symbols, "activated_symbols", allow_empty=True))
        object.__setattr__(self, "risk_level", self.risk_level.strip().lower())
        object.__setattr__(self, "reversibility", self.reversibility.strip().lower())
        lock_scope = self.lock_scope or (self.resource_id.strip(),)
        object.__setattr__(self, "lock_scope", _normalize_text_tuple(lock_scope, "lock_scope"))


@dataclass(frozen=True, slots=True)
class PolicyTransitionProofStep:
    """One causal proof step for a VCPP v2 judgment."""

    stage: str
    claim: str
    result: str
    reason: str
    policy_id: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("stage", "claim", "result", "reason"):
            _require_text(str(getattr(self, field_name)), field_name)
        if self.result not in {"pass", "fail", "unknown"}:
            raise ValueError("proof_step_result_invalid")
        object.__setattr__(self, "stage", self.stage.strip())
        object.__setattr__(self, "claim", self.claim.strip())
        object.__setattr__(self, "reason", self.reason.strip())
        object.__setattr__(self, "policy_id", self.policy_id.strip())
        object.__setattr__(self, "evidence_refs", _normalize_evidence_refs(self.evidence_refs, allow_empty=True))


@dataclass(frozen=True, slots=True)
class PolicyTransitionCounterexample:
    """Concrete surviving counterexample against an allow judgment."""

    counterexample_id: str
    reason: str
    policy_id: str = ""
    delta_path: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.counterexample_id, "counterexample_id")
        _require_text(self.reason, "reason")
        object.__setattr__(self, "counterexample_id", self.counterexample_id.strip())
        object.__setattr__(self, "reason", self.reason.strip())
        object.__setattr__(self, "policy_id", self.policy_id.strip())
        object.__setattr__(self, "delta_path", self.delta_path.strip())
        object.__setattr__(self, "evidence_refs", _normalize_evidence_refs(self.evidence_refs, allow_empty=True))


@dataclass(frozen=True, slots=True)
class PolicyMissingEvidence:
    """Missing or insufficient evidence for a selected policy."""

    requirement_id: str
    policy_id: str
    evidence_type: str
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("requirement_id", "policy_id", "evidence_type", "reason"):
            _require_text(str(getattr(self, field_name)), field_name)
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())


@dataclass(frozen=True, slots=True)
class PolicyProofLease:
    """Lease-bound proof authority for executing one transition."""

    lease_id: str
    event_hash: str
    pre_state_hash: str
    policy_set_hash: str
    evidence_hash: str
    obligation_plan_hash: str
    issued_at: str
    expires_at: str
    lock_scope: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "lease_id",
            "event_hash",
            "pre_state_hash",
            "policy_set_hash",
            "evidence_hash",
            "obligation_plan_hash",
            "issued_at",
            "expires_at",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        _parse_iso_timestamp(self.issued_at, "issued_at")
        _parse_iso_timestamp(self.expires_at, "expires_at")
        object.__setattr__(self, "lock_scope", _normalize_text_tuple(self.lock_scope, "lock_scope"))


@dataclass(frozen=True, slots=True)
class PolicyLeaseVerification:
    """Result of checking an execution lease against current state."""

    status: PolicyLeaseStatus
    reason: str
    lease_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", PolicyLeaseStatus(str(self.status)))
        _require_text(self.reason, "reason")
        _require_text(self.lease_id, "lease_id")


@dataclass(frozen=True, slots=True)
class PolicyTransitionProofReport:
    """Hash-bound VCPP v2 transition proof report."""

    report_id: str
    transition_id: str
    verdict: PolicyTransitionVerdict
    reason: str
    delta_paths: tuple[str, ...]
    activated_symbols: tuple[str, ...]
    selected_policy_ids: tuple[str, ...]
    missing_policy_symbols: tuple[str, ...]
    violated_policy_ids: tuple[str, ...]
    missing_evidence: tuple[PolicyMissingEvidence, ...]
    obligations: tuple[PolicyObligation, ...]
    obligation_gaps: tuple[str, ...]
    proof_trace: tuple[PolicyTransitionProofStep, ...]
    counterexamples: tuple[PolicyTransitionCounterexample, ...]
    lease: PolicyProofLease | None = None
    receipt_id: str = ""
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.report_id, "report_id")
        _require_text(self.transition_id, "transition_id")
        _require_text(self.reason, "reason")
        object.__setattr__(self, "verdict", PolicyTransitionVerdict(str(self.verdict)))
        object.__setattr__(self, "delta_paths", tuple(self.delta_paths))
        object.__setattr__(self, "activated_symbols", tuple(self.activated_symbols))
        object.__setattr__(self, "selected_policy_ids", tuple(self.selected_policy_ids))
        object.__setattr__(self, "missing_policy_symbols", tuple(self.missing_policy_symbols))
        object.__setattr__(self, "violated_policy_ids", tuple(self.violated_policy_ids))
        object.__setattr__(self, "missing_evidence", tuple(self.missing_evidence))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "obligation_gaps", tuple(self.obligation_gaps))
        object.__setattr__(self, "proof_trace", tuple(self.proof_trace))
        object.__setattr__(self, "counterexamples", tuple(self.counterexamples))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.verdict in _ALLOWING_VERDICTS and self.lease is None:
            raise ValueError("allow_verdict_requires_lease")
        if self.verdict in _ALLOWING_VERDICTS and self.counterexamples:
            raise ValueError("allow_verdict_cannot_have_counterexamples")


class PolicyProver:
    """Search bounded cases for policy invariant counterexamples."""

    def prove(
        self,
        *,
        policy_id: str,
        invariants: tuple[PolicyProofInvariant, ...],
        cases: tuple[PolicyProofCase, ...],
        evidence_refs: tuple[str, ...] = (),
    ) -> PolicyProofReport:
        """Return a deterministic proof report for explicit invariants and cases."""
        if not policy_id.strip():
            raise ValueError("policy_id_required")
        if not invariants:
            raise ValueError("policy_invariants_required")
        if not cases:
            raise ValueError("policy_cases_required")
        counterexamples = tuple(
            counterexample
            for invariant in invariants
            for case in cases
            for counterexample in _counterexamples_for_case(invariant, case)
        )
        violated = {counterexample.invariant_id for counterexample in counterexamples}
        proven_invariants = tuple(
            invariant.invariant_id for invariant in invariants if invariant.invariant_id not in violated
        )
        status = "proved" if not counterexamples else "counterexample_found"
        report = PolicyProofReport(
            report_id="pending",
            policy_id=policy_id.strip(),
            status=status,
            invariant_count=len(invariants),
            case_count=len(cases),
            counterexample_count=len(counterexamples),
            proven_invariants=proven_invariants,
            counterexamples=counterexamples,
            evidence_refs=evidence_refs,
            metadata={"proof_is_bounded": True, "policy_weakening_allowed": False},
        )
        report_hash = canonical_hash(asdict(report))
        return replace(report, report_id=f"policy-proof-{report_hash[:16]}", report_hash=report_hash)


class VeriCausalPolicyProver:
    """Prove exact state transitions under VCPP v2 constraints."""

    def prove_transition(
        self,
        *,
        transition: PolicyTransition,
        policies: tuple[PolicyTransitionPolicy, ...],
        evidence: tuple[PolicyEvidence, ...] = (),
    ) -> PolicyTransitionProofReport:
        """Return a deterministic VCPP v2 judgment for one proposed transition."""
        if not policies:
            raise ValueError("transition_policies_required")
        policy_ids = [policy.policy_id for policy in policies]
        if len(policy_ids) != len(set(policy_ids)):
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.CONFLICT_BLOCKED,
                reason="Policy universe contains duplicate policy ids.",
                policies=policies,
                selected_policies=(),
                evidence=evidence,
                proof_trace=(
                    _proof_step("policy_compile", "policy ids are unique", "fail", "duplicate_policy_id"),
                ),
            )

        delta_paths = _state_delta_paths(transition.pre_state, transition.post_state)
        activated_symbols = _activated_symbols(transition, delta_paths)
        transition_hash = _transition_hash(transition, delta_paths, activated_symbols)
        proof_trace: list[PolicyTransitionProofStep] = [
            _proof_step("canonicalize", "transition is exact", "pass", "event and delta were canonicalized"),
        ]

        if not transition.actor_authenticated:
            proof_trace.append(_proof_step("identity", "actor identity is proven", "fail", "actor_not_authenticated"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.DENY_AUTHORITY,
                reason="Actor identity could not be proven.",
                policies=policies,
                selected_policies=(),
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("identity", "actor identity is proven", "pass", "actor_authenticated"))

        if not transition.authority_refs:
            proof_trace.append(_proof_step("authority", "authority chain is present", "fail", "authority_refs_missing"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.DENY_AUTHORITY,
                reason="Authority chain could not be proven.",
                policies=policies,
                selected_policies=(),
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("authority", "authority chain is present", "pass", "authority_refs_present"))

        if _context_is_stale(transition):
            proof_trace.append(_proof_step("context", "context is fresh", "fail", "context_expired"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.STALE_CONTEXT_BLOCKED,
                reason="Context freshness expired before proof settlement.",
                policies=policies,
                selected_policies=(),
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("context", "context is fresh", "pass", "context_fresh"))

        selected_policies = _select_transition_policies(activated_symbols, policies)
        missing_policy_symbols = _missing_policy_symbols(activated_symbols, selected_policies)
        if missing_policy_symbols:
            proof_trace.append(
                _proof_step(
                    "policy_coverage",
                    "selected policies cover activated symbols",
                    "fail",
                    "missing_policy_symbols",
                )
            )
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.UNKNOWN_BLOCKED,
                reason="Policy selection completeness could not be proven.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                missing_policy_symbols=missing_policy_symbols,
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(
            _proof_step(
                "policy_coverage",
                "selected policies cover activated symbols",
                "pass",
                "coverage_complete",
            )
        )

        invariant_policies = tuple(
            policy for policy in selected_policies if _policy_invariant_violated(policy, delta_paths)
        )
        if invariant_policies:
            proof_trace.append(_proof_step("invariant", "immutable deltas are preserved", "fail", "invariant_delta_changed"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.DENY_INVARIANT,
                reason="Transition changes a protected invariant delta path.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                violated_policy_ids=tuple(policy.policy_id for policy in invariant_policies),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("invariant", "immutable deltas are preserved", "pass", "invariants_preserved"))

        missing_evidence = _missing_evidence(
            selected_policies,
            evidence,
            proof_time=transition.proof_time,
            transition_hash=transition_hash,
        )
        if missing_evidence:
            proof_trace.append(_proof_step("evidence", "required evidence is trusted", "fail", "evidence_missing_or_insufficient"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.DENY_EVIDENCE,
                reason="Required evidence is missing, stale, unbound, or below required trust.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                missing_evidence=missing_evidence,
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("evidence", "required evidence is trusted", "pass", "evidence_sufficient"))

        permit_policies = tuple(
            policy for policy in selected_policies
            if policy.effect is PolicyTransitionEffect.PERMIT and _policy_applies_to_delta(policy, delta_paths)
        )
        deny_policies = tuple(
            policy for policy in selected_policies
            if policy.effect is PolicyTransitionEffect.DENY and _policy_applies_to_delta(policy, delta_paths)
        )
        conflict_verdict = _settle_policy_conflict(permit_policies, deny_policies)
        if conflict_verdict is PolicyTransitionVerdict.CONFLICT_BLOCKED:
            proof_trace.append(_proof_step("conflict", "policy effects are resolvable", "fail", "equal_precedence_conflict"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.CONFLICT_BLOCKED,
                reason="Permit and deny policies conflict at the same precedence layer.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                violated_policy_ids=tuple(policy.policy_id for policy in deny_policies),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        if conflict_verdict is PolicyTransitionVerdict.DENY_HARD:
            proof_trace.append(_proof_step("prohibition", "hard prohibition is absent", "fail", "deny_policy_precedes_permit"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.DENY_HARD,
                reason="A denial policy has equal or stronger precedence than permission.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                violated_policy_ids=tuple(policy.policy_id for policy in deny_policies),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("prohibition", "hard prohibition is absent", "pass", "no_preceding_deny"))

        if not permit_policies:
            proof_trace.append(_proof_step("permission", "positive permission is proven", "unknown", "permit_policy_missing"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.UNKNOWN_BLOCKED,
                reason="No positive permission proof was found.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("permission", "positive permission is proven", "pass", "permit_policy_applies"))

        obligations = tuple(
            obligation
            for policy in selected_policies
            for obligation in policy.obligations
        )
        obligation_gaps = _obligation_gaps(obligations)
        if obligation_gaps:
            proof_trace.append(_proof_step("obligation", "obligations are enforceable", "fail", "obligation_gap"))
            verdict = (
                PolicyTransitionVerdict.DENY_EVIDENCE
                if any(gap.startswith("pre_obligation_unsatisfied:") for gap in obligation_gaps)
                else PolicyTransitionVerdict.ESCALATE_HUMAN
            )
            return self._report(
                transition=transition,
                verdict=verdict,
                reason="Transition obligations are not satisfied or enforceable.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                obligations=obligations,
                obligation_gaps=obligation_gaps,
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("obligation", "obligations are enforceable", "pass", "obligations_enforceable"))

        counterexamples = _search_transition_counterexamples(transition, evidence)
        if counterexamples:
            proof_trace.append(_proof_step("counterexample", "no counterexample survives", "fail", "counterexample_survived"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.ESCALATE_HUMAN,
                reason="Counterexample search found unresolved transition risk.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                obligations=obligations,
                counterexamples=counterexamples,
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )
        proof_trace.append(_proof_step("counterexample", "no counterexample survives", "pass", "counterexamples_absent"))

        if _simulation_required(transition, selected_policies) and not _has_evidence_type(evidence, "simulation_receipt"):
            proof_trace.append(_proof_step("simulation", "required simulation receipt is present", "unknown", "simulation_receipt_missing"))
            return self._report(
                transition=transition,
                verdict=PolicyTransitionVerdict.SIMULATE_FIRST,
                reason="High-risk transition requires simulation before execution.",
                policies=policies,
                selected_policies=selected_policies,
                evidence=evidence,
                proof_trace=tuple(proof_trace),
                obligations=obligations,
                delta_paths=delta_paths,
                activated_symbols=activated_symbols,
            )

        lease = _create_policy_lease(
            transition=transition,
            policies=selected_policies,
            evidence=evidence,
            obligations=obligations,
            transition_hash=transition_hash,
        )
        verdict = (
            PolicyTransitionVerdict.ALLOW_WITH_ENFORCED_OBLIGATIONS
            if obligations
            else PolicyTransitionVerdict.ALLOW
        )
        return self._report(
            transition=transition,
            verdict=verdict,
            reason="Transition proof settled with lease-bound execution authority.",
            policies=policies,
            selected_policies=selected_policies,
            evidence=evidence,
            proof_trace=tuple(proof_trace),
            obligations=obligations,
            lease=lease,
            delta_paths=delta_paths,
            activated_symbols=activated_symbols,
        )

    def verify_lease(
        self,
        lease: PolicyProofLease,
        *,
        observed_pre_state: Mapping[str, Any],
        policies: tuple[PolicyTransitionPolicy, ...],
        observed_at: str,
    ) -> PolicyLeaseVerification:
        """Verify that execution may still use a transition proof lease."""
        observed_dt = _parse_iso_timestamp(observed_at, "observed_at")
        expires_dt = _parse_iso_timestamp(lease.expires_at, "expires_at")
        if observed_dt >= expires_dt:
            return PolicyLeaseVerification(
                status=PolicyLeaseStatus.LEASE_EXPIRED_REPROVE,
                reason="lease_expired",
                lease_id=lease.lease_id,
            )
        if canonical_hash(dict(observed_pre_state)) != lease.pre_state_hash:
            return PolicyLeaseVerification(
                status=PolicyLeaseStatus.STATE_HASH_MISMATCH,
                reason="pre_state_hash_changed",
                lease_id=lease.lease_id,
            )
        if _policy_set_hash(policies) != lease.policy_set_hash:
            return PolicyLeaseVerification(
                status=PolicyLeaseStatus.POLICY_HASH_MISMATCH,
                reason="policy_set_hash_changed",
                lease_id=lease.lease_id,
            )
        return PolicyLeaseVerification(
            status=PolicyLeaseStatus.ACTIVE,
            reason="lease_active",
            lease_id=lease.lease_id,
        )

    def _report(
        self,
        *,
        transition: PolicyTransition,
        verdict: PolicyTransitionVerdict,
        reason: str,
        policies: tuple[PolicyTransitionPolicy, ...],
        selected_policies: tuple[PolicyTransitionPolicy, ...],
        evidence: tuple[PolicyEvidence, ...],
        proof_trace: tuple[PolicyTransitionProofStep, ...],
        delta_paths: tuple[str, ...] | None = None,
        activated_symbols: tuple[str, ...] | None = None,
        missing_policy_symbols: tuple[str, ...] = (),
        violated_policy_ids: tuple[str, ...] = (),
        missing_evidence: tuple[PolicyMissingEvidence, ...] = (),
        obligations: tuple[PolicyObligation, ...] = (),
        obligation_gaps: tuple[str, ...] = (),
        counterexamples: tuple[PolicyTransitionCounterexample, ...] = (),
        lease: PolicyProofLease | None = None,
    ) -> PolicyTransitionProofReport:
        report = PolicyTransitionProofReport(
            report_id="pending",
            transition_id=transition.transition_id,
            verdict=verdict,
            reason=reason,
            delta_paths=delta_paths if delta_paths is not None else _state_delta_paths(transition.pre_state, transition.post_state),
            activated_symbols=activated_symbols if activated_symbols is not None else transition.activated_symbols,
            selected_policy_ids=tuple(policy.policy_id for policy in selected_policies),
            missing_policy_symbols=missing_policy_symbols,
            violated_policy_ids=violated_policy_ids,
            missing_evidence=missing_evidence,
            obligations=obligations,
            obligation_gaps=obligation_gaps,
            proof_trace=proof_trace,
            counterexamples=counterexamples,
            lease=lease,
            receipt_id="pending",
            metadata={
                "prover_version": "vcpp-kernel-v2",
                "transition_proof": True,
                "default_deny": True,
                "proof_is_bounded": True,
                "policy_weakening_allowed": False,
                "policy_coverage_complete": not missing_policy_symbols,
                "lease_bound": lease is not None,
                "policy_universe_hash": _policy_set_hash(policies),
                "selected_policy_hash": _policy_set_hash(selected_policies),
                "evidence_hash": _evidence_hash(evidence),
            },
        )
        payload = policy_transition_proof_report_to_json_dict(report)
        payload["report_id"] = ""
        payload["receipt_id"] = ""
        payload["report_hash"] = ""
        report_hash = canonical_hash(payload)
        return replace(
            report,
            report_id=f"vcpp-transition-{report_hash[:16]}",
            receipt_id=f"vcpp-receipt-{report_hash[:16]}",
            report_hash=report_hash,
        )


PolicyTransitionProver = VeriCausalPolicyProver


def _counterexamples_for_case(
    invariant: PolicyProofInvariant,
    case: PolicyProofCase,
) -> tuple[PolicyCounterexample, ...]:
    counterexamples: list[PolicyCounterexample] = []
    for field_name in invariant.required_fields:
        if field_name not in case.attributes:
            counterexamples.append(
                PolicyCounterexample(
                    invariant_id=invariant.invariant_id,
                    case_id=case.case_id,
                    subject_id=case.subject_id,
                    reason=f"missing_required_field:{field_name}",
                    evidence_refs=case.evidence_refs,
                )
            )
    for field_name, expected_value in invariant.expected_values.items():
        if field_name not in case.attributes:
            continue
        observed_value = case.attributes.get(field_name)
        if observed_value != expected_value:
            counterexamples.append(
                PolicyCounterexample(
                    invariant_id=invariant.invariant_id,
                    case_id=case.case_id,
                    subject_id=case.subject_id,
                    reason=f"expected_value_mismatch:{field_name}",
                    evidence_refs=case.evidence_refs,
                )
            )
    return tuple(counterexamples)


def _normalize_evidence_refs(values: tuple[str, ...] | list[str], *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(values, tuple | list) or not all(isinstance(ref, str) for ref in values):
        raise ValueError("evidence_refs_invalid")
    return tuple(dict.fromkeys(ref.strip() for ref in values if ref.strip()))


def policy_transition_proof_report_to_json_dict(report: PolicyTransitionProofReport) -> dict[str, Any]:
    """Return the public JSON-contract representation of a VCPP v2 report."""
    return _json_ready(asdict(report))


def _proof_step(
    stage: str,
    claim: str,
    result: str,
    reason: str,
    *,
    policy_id: str = "",
    evidence_refs: tuple[str, ...] = (),
) -> PolicyTransitionProofStep:
    return PolicyTransitionProofStep(
        stage=stage,
        claim=claim,
        result=result,
        reason=reason,
        policy_id=policy_id,
        evidence_refs=evidence_refs,
    )


def _state_delta_paths(pre_state: Mapping[str, Any], post_state: Mapping[str, Any], prefix: str = "") -> tuple[str, ...]:
    delta_paths: list[str] = []
    missing = object()
    for key in sorted(set(pre_state) | set(post_state)):
        pre_value = pre_state.get(key, missing)
        post_value = post_state.get(key, missing)
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(pre_value, Mapping) and isinstance(post_value, Mapping):
            delta_paths.extend(_state_delta_paths(pre_value, post_value, path))
        elif pre_value != post_value:
            delta_paths.append(path)
    return tuple(delta_paths)


def _activated_symbols(transition: PolicyTransition, delta_paths: tuple[str, ...]) -> tuple[str, ...]:
    symbols = [
        *transition.activated_symbols,
        f"action:{transition.action_id}",
        f"resource:{transition.resource_type}",
        f"risk:{transition.risk_level}",
    ]
    if transition.external_exposure:
        symbols.append("exposure:external")
    if transition.reversibility == "irreversible":
        symbols.append("reversibility:irreversible")
    symbols.extend(f"delta:{path}" for path in delta_paths)
    return tuple(dict.fromkeys(symbol for symbol in symbols if symbol))


def _transition_hash(
    transition: PolicyTransition,
    delta_paths: tuple[str, ...],
    activated_symbols: tuple[str, ...],
) -> str:
    payload = _json_ready(asdict(transition))
    payload["delta_paths"] = list(delta_paths)
    payload["activated_symbols"] = list(activated_symbols)
    return canonical_hash(payload)


def _context_is_stale(transition: PolicyTransition) -> bool:
    expires_at = str(transition.context.get("fresh_until", "")).strip()
    if not expires_at:
        return False
    return _parse_iso_timestamp(transition.proof_time, "proof_time") >= _parse_iso_timestamp(expires_at, "fresh_until")


def _select_transition_policies(
    activated_symbols: tuple[str, ...],
    policies: tuple[PolicyTransitionPolicy, ...],
) -> tuple[PolicyTransitionPolicy, ...]:
    return tuple(
        policy for policy in policies
        if any(_symbol_is_covered(symbol, policy.coverage_symbols) for symbol in activated_symbols)
    )


def _missing_policy_symbols(
    activated_symbols: tuple[str, ...],
    policies: tuple[PolicyTransitionPolicy, ...],
) -> tuple[str, ...]:
    return tuple(
        symbol for symbol in activated_symbols
        if not any(_symbol_is_covered(symbol, policy.coverage_symbols) for policy in policies)
    )


def _symbol_is_covered(symbol: str, coverage_symbols: tuple[str, ...]) -> bool:
    for coverage_symbol in coverage_symbols:
        if coverage_symbol == "*" or coverage_symbol == symbol:
            return True
        if coverage_symbol.endswith(":*") and symbol.startswith(coverage_symbol[:-1]):
            return True
    return False


def _policy_invariant_violated(policy: PolicyTransitionPolicy, delta_paths: tuple[str, ...]) -> bool:
    if policy.effect is not PolicyTransitionEffect.INVARIANT and not policy.invariant_delta_paths:
        return False
    return _delta_matches(delta_paths, policy.invariant_delta_paths)


def _policy_applies_to_delta(policy: PolicyTransitionPolicy, delta_paths: tuple[str, ...]) -> bool:
    if policy.required_delta_paths and not all(_delta_matches(delta_paths, (path,)) for path in policy.required_delta_paths):
        return False
    if policy.forbidden_delta_paths:
        return _delta_matches(delta_paths, policy.forbidden_delta_paths)
    return True


def _delta_matches(delta_paths: tuple[str, ...], policy_paths: tuple[str, ...]) -> bool:
    return any(_path_matches(delta_path, policy_path) for delta_path in delta_paths for policy_path in policy_paths)


def _path_matches(delta_path: str, policy_path: str) -> bool:
    if policy_path == "*" or delta_path == policy_path:
        return True
    if policy_path.endswith(".*") and delta_path.startswith(policy_path[:-1]):
        return True
    return delta_path.startswith(f"{policy_path}.")


def _missing_evidence(
    policies: tuple[PolicyTransitionPolicy, ...],
    evidence: tuple[PolicyEvidence, ...],
    *,
    proof_time: str,
    transition_hash: str,
) -> tuple[PolicyMissingEvidence, ...]:
    missing: list[PolicyMissingEvidence] = []
    for policy in policies:
        for requirement in policy.required_evidence:
            if not _evidence_requirement_satisfied(
                requirement,
                evidence,
                proof_time=proof_time,
                transition_hash=transition_hash,
            ):
                missing.append(
                    PolicyMissingEvidence(
                        requirement_id=requirement.requirement_id,
                        policy_id=policy.policy_id,
                        evidence_type=requirement.evidence_type,
                        reason="missing_or_insufficient_trusted_evidence",
                    )
                )
    return tuple(missing)


def _evidence_requirement_satisfied(
    requirement: PolicyEvidenceRequirement,
    evidence: tuple[PolicyEvidence, ...],
    *,
    proof_time: str,
    transition_hash: str,
) -> bool:
    return any(
        item.evidence_type == requirement.evidence_type
        and _trust_meets(item.trust_level, requirement.minimum_trust)
        and _evidence_scope_matches(item, requirement)
        and _evidence_time_valid(item, proof_time)
        and (not requirement.binds_transition or item.event_hash_binding == transition_hash)
        for item in evidence
    )


def _trust_meets(observed: PolicyEvidenceTrust, required: PolicyEvidenceTrust) -> bool:
    return _EVIDENCE_TRUST_RANK[observed] >= _EVIDENCE_TRUST_RANK[required]


def _evidence_scope_matches(evidence: PolicyEvidence, requirement: PolicyEvidenceRequirement) -> bool:
    if not requirement.scope_symbol:
        return True
    return _symbol_is_covered(requirement.scope_symbol, evidence.scope_symbols)


def _evidence_time_valid(evidence: PolicyEvidence, proof_time: str) -> bool:
    proof_dt = _parse_iso_timestamp(proof_time, "proof_time")
    if evidence.issued_at and _parse_iso_timestamp(evidence.issued_at, "issued_at") > proof_dt:
        return False
    if evidence.expires_at and _parse_iso_timestamp(evidence.expires_at, "expires_at") <= proof_dt:
        return False
    return True


def _settle_policy_conflict(
    permit_policies: tuple[PolicyTransitionPolicy, ...],
    deny_policies: tuple[PolicyTransitionPolicy, ...],
) -> PolicyTransitionVerdict | None:
    if not deny_policies:
        return None
    if not permit_policies:
        return PolicyTransitionVerdict.DENY_HARD
    permit_rank = max(_PRECEDENCE_RANK[policy.precedence_layer] for policy in permit_policies)
    deny_rank = max(_PRECEDENCE_RANK[policy.precedence_layer] for policy in deny_policies)
    if deny_rank > permit_rank:
        return PolicyTransitionVerdict.DENY_HARD
    if deny_rank == permit_rank:
        return PolicyTransitionVerdict.CONFLICT_BLOCKED
    return None


def _obligation_gaps(obligations: tuple[PolicyObligation, ...]) -> tuple[str, ...]:
    gaps: list[str] = []
    for obligation in obligations:
        if obligation.phase is PolicyObligationPhase.PRE and not obligation.satisfied:
            gaps.append(f"pre_obligation_unsatisfied:{obligation.obligation_id}")
        elif obligation.phase is not PolicyObligationPhase.PRE and not obligation.enforceable:
            gaps.append(f"obligation_not_enforceable:{obligation.obligation_id}")
        elif (
            obligation.phase in {PolicyObligationPhase.POST, PolicyObligationPhase.CONTINUING}
            and not obligation.satisfied
            and not obligation.compensation_ref
        ):
            gaps.append(f"obligation_compensation_missing:{obligation.obligation_id}")
    return tuple(gaps)


def _search_transition_counterexamples(
    transition: PolicyTransition,
    evidence: tuple[PolicyEvidence, ...],
) -> tuple[PolicyTransitionCounterexample, ...]:
    counterexamples: list[PolicyTransitionCounterexample] = []
    if transition.external_exposure and transition.context.get("resource_sensitivity") == "secret":
        counterexamples.append(
            PolicyTransitionCounterexample(
                counterexample_id="secret_external_exposure",
                reason="secret_resource_would_be_externally_exposed",
            )
        )
    if transition.reversibility == "irreversible" and not _has_evidence_type(evidence, "explicit_confirmation"):
        counterexamples.append(
            PolicyTransitionCounterexample(
                counterexample_id="irreversible_without_confirmation",
                reason="irreversible_transition_lacks_explicit_confirmation",
            )
        )
    return tuple(counterexamples)


def _simulation_required(
    transition: PolicyTransition,
    policies: tuple[PolicyTransitionPolicy, ...],
) -> bool:
    return transition.risk_level in {"high", "critical"} and any(policy.requires_simulation for policy in policies)


def _has_evidence_type(evidence: tuple[PolicyEvidence, ...], evidence_type: str) -> bool:
    return any(item.evidence_type == evidence_type for item in evidence)


def _create_policy_lease(
    *,
    transition: PolicyTransition,
    policies: tuple[PolicyTransitionPolicy, ...],
    evidence: tuple[PolicyEvidence, ...],
    obligations: tuple[PolicyObligation, ...],
    transition_hash: str,
) -> PolicyProofLease:
    issued_dt = _parse_iso_timestamp(transition.proof_time, "proof_time")
    issued_at = issued_dt.isoformat()
    expires_at = (issued_dt + timedelta(seconds=transition.lease_seconds)).isoformat()
    pre_state_hash = canonical_hash(transition.pre_state)
    policy_set_hash = _policy_set_hash(policies)
    evidence_hash = _evidence_hash(evidence)
    obligation_plan_hash = canonical_hash(tuple(_json_ready(asdict(obligation)) for obligation in obligations))
    lease_seed = {
        "event_hash": transition_hash,
        "pre_state_hash": pre_state_hash,
        "policy_set_hash": policy_set_hash,
        "evidence_hash": evidence_hash,
        "obligation_plan_hash": obligation_plan_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "lock_scope": transition.lock_scope,
    }
    lease_hash = canonical_hash(lease_seed)
    return PolicyProofLease(
        lease_id=f"vcpp-lease-{lease_hash[:16]}",
        event_hash=transition_hash,
        pre_state_hash=pre_state_hash,
        policy_set_hash=policy_set_hash,
        evidence_hash=evidence_hash,
        obligation_plan_hash=obligation_plan_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        lock_scope=transition.lock_scope,
    )


def _policy_set_hash(policies: tuple[PolicyTransitionPolicy, ...]) -> str:
    return canonical_hash(tuple(_json_ready(asdict(policy)) for policy in policies))


def _evidence_hash(evidence: tuple[PolicyEvidence, ...]) -> str:
    return canonical_hash(tuple(_json_ready(asdict(item)) for item in evidence))


def _normalize_text_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(values, tuple | list):
        raise ValueError(f"{field_name}_invalid")
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _parse_iso_timestamp(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name}_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
