"""Gateway solver-forge capsule probes.

Purpose: Candidate-specific adversarial review for the Solver Forge. Where
    `RedTeamPlatformReviewer` tests *platform* invariants (every candidate in a
    session inherits the same verdict), this reviewer derives deterministic
    probes from each capsule's DECLARED contract (inputs, assumptions,
    failure_modes, risk, explainability) so that two different candidates can
    receive different findings. It red-teams the contract for unguarded
    adversarial surfaces — it does not run the method.
Governance scope: a second-gate reviewer only. It produces findings; it never
    promotes, never scores, never mutates a ledger. It plugs into the composer
    through the existing `AdversarialReviewCallback` seam and obeys every
    existing invariant: it is applied symmetrically to the baseline, a
    compromised baseline still zeroes winners, and findings are recorded on the
    ledger record by the composer.
Dependencies: gateway.candidate_composer (MethodCapsule, CandidatePipeline,
    CandidateEvaluation, AdversarialReviewResult), gateway.problem_signature
    (ProblemSignature), canonical command-spine hashing for evidence refs.
Invariants:
  - Deterministic: identical capsule contracts -> identical findings.
  - Honest: findings are derived from DECLARED metadata, not fabricated runtime
    results. A finding means "the declared contract leaves an adversarial
    surface unguarded", never "the method was attacked and failed".
  - Candidate-specific: findings name the offending capsule; different capsules
    in a session can produce different findings.
  - No promotion surface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from itertools import chain

from gateway.candidate_composer import (
    AdversarialReviewResult,
    CandidateEvaluation,
    CandidatePipeline,
    MethodCapsule,
)
from gateway.command_spine import canonical_hash
from gateway.problem_signature import ProblemSignature


# A probe inspects one capsule (with the full pipeline for context) and returns
# a finding string when the declared contract leaves a surface unguarded.
CapsuleProbe = Callable[[MethodCapsule, tuple[MethodCapsule, ...]], "str | None"]


# --- token vocabularies (kept deliberately tight to avoid false positives) --- #

_LLM_FAMILIES = {"llm_planner", "llm_reviewer", "multi_agent_debate"}
_UNTRUSTED_INPUT_TOKENS = (
    "text",
    "prompt",
    "message",
    "document",
    "email",
    "content",
    "artifact",
)
_INJECTION_MITIGATION_TOKENS = ("inject", "adversar", "untrusted", "sanitiz", "prompt")

_EXTERNAL_STATE_TOKENS = ("exists", "available", "fresh", "reachable", "online", "up-to-date")
_STATE_GUARD_TOKENS = (
    "missing",
    "stale",
    "unavailable",
    "absent",
    "unreachable",
    "drift",
    "outdated",
    "expired",
)


def _any_token(text_values: tuple[str, ...], tokens: tuple[str, ...]) -> bool:
    lowered = [value.lower() for value in text_values]
    return any(token in value for value in lowered for token in tokens)


def probe_injection_surface(
    capsule: MethodCapsule, pipeline_capsules: tuple[MethodCapsule, ...]
) -> str | None:
    """A capsule that consumes untrusted free-text (LLM-backed, or an input
    that names text/prompt/document/...) must declare an injection-class
    failure mode. If it does not, the injection surface is unguarded."""
    consumes_untrusted = capsule.method_family in _LLM_FAMILIES or _any_token(
        capsule.declared_inputs, _UNTRUSTED_INPUT_TOKENS
    )
    if not consumes_untrusted:
        return None
    if _any_token(capsule.declared_failure_modes, _INJECTION_MITIGATION_TOKENS):
        return None
    return f"unmitigated_injection_surface:{capsule.capsule_id}"


def probe_unguarded_external_state(
    capsule: MethodCapsule, pipeline_capsules: tuple[MethodCapsule, ...]
) -> str | None:
    """A capsule whose assumptions depend on external mutable state (a graph
    'exists', data is 'fresh', a service is 'reachable') must declare a failure
    mode for that state being missing/stale/unavailable."""
    if not _any_token(capsule.declared_assumptions, _EXTERNAL_STATE_TOKENS):
        return None
    if _any_token(capsule.declared_failure_modes, _STATE_GUARD_TOKENS):
        return None
    return f"unguarded_external_state_assumption:{capsule.capsule_id}"


def probe_high_risk_low_oversight(
    capsule: MethodCapsule, pipeline_capsules: tuple[MethodCapsule, ...]
) -> str | None:
    """A high/physical-risk capsule with low explainability must be paired with
    a human_review_gate in the pipeline; alone it is an oversight gap."""
    if capsule.risk_ceiling not in ("high", "physical"):
        return None
    if capsule.explainability != "low":
        return None
    if any(c.method_family == "human_review_gate" for c in pipeline_capsules):
        return None
    return f"high_risk_low_oversight:{capsule.capsule_id}"


DEFAULT_PROBES: tuple[CapsuleProbe, ...] = (
    probe_injection_surface,
    probe_unguarded_external_state,
    probe_high_risk_low_oversight,
)


class CapsuleProbeReviewer:
    """An AdversarialReviewCallback that runs contract-level probes per capsule."""

    def __init__(
        self,
        capsules: Mapping[str, MethodCapsule],
        *,
        probes: tuple[CapsuleProbe, ...] = DEFAULT_PROBES,
    ) -> None:
        self._capsules = dict(capsules)
        self._probes = tuple(probes)

    @classmethod
    def from_registry(cls, registry, *, probes: tuple[CapsuleProbe, ...] = DEFAULT_PROBES):
        """Build from anything exposing `all_capsules()` (e.g. MethodRegistry)."""
        lookup = {c.capsule_id: c for c in registry.all_capsules()}
        return cls(lookup, probes=probes)

    def __call__(
        self,
        signature: ProblemSignature,
        pipeline: CandidatePipeline,
        evaluation: CandidateEvaluation,
        seed: str,
    ) -> AdversarialReviewResult:
        resolved = tuple(
            self._capsules[cid] for cid in pipeline.capsule_ids if cid in self._capsules
        )
        unresolved = tuple(
            cid for cid in pipeline.capsule_ids if cid not in self._capsules
        )

        findings: list[str] = []
        for capsule in resolved:
            for probe in self._probes:
                finding = probe(capsule, resolved)
                if finding:
                    findings.append(finding)
        findings = sorted(set(findings))

        evidence = canonical_hash(
            {
                "pipeline_id": pipeline.pipeline_id,
                "capsules": [c.capsule_id for c in resolved],
                "findings": findings,
            }
        )
        notes_parts = [f"probed={len(resolved)} capsule(s)"]
        if unresolved:
            notes_parts.append(f"unresolved={list(unresolved)}")
        return AdversarialReviewResult(
            passed=not findings,
            findings=tuple(findings),
            evidence_refs=(f"capsule_probe:{evidence}",),
            notes="; ".join(notes_parts),
        )


class CompositeAdversarialReviewer:
    """Runs several AdversarialReviewCallbacks and unions their findings.

    Passes only when every reviewer passes. Useful for combining platform
    invariants (RedTeamPlatformReviewer) with per-capsule contract probes."""

    def __init__(self, reviewers: tuple[Callable, ...]) -> None:
        if not reviewers:
            raise ValueError("composite_reviewer_requires_at_least_one_reviewer")
        self._reviewers = tuple(reviewers)

    def __call__(
        self,
        signature: ProblemSignature,
        pipeline: CandidatePipeline,
        evaluation: CandidateEvaluation,
        seed: str,
    ) -> AdversarialReviewResult:
        results = [r(signature, pipeline, evaluation, seed) for r in self._reviewers]
        findings = tuple(sorted(set(chain.from_iterable(r.findings for r in results))))
        evidence = tuple(
            sorted(set(chain.from_iterable(r.evidence_refs for r in results)))
        ) or ("composite_no_evidence",)
        return AdversarialReviewResult(
            passed=not findings,
            findings=findings,
            evidence_refs=evidence,
            notes=f"composite of {len(results)} reviewer(s)",
        )
