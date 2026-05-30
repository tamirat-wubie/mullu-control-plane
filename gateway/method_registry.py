"""Gateway method registry.

Purpose: A catalog of method capsules the Solver Forge can draw on when
    composing candidate pipelines for a problem signature. The registry is the
    "Method Registry" box of the governed solver laboratory: it holds *typed
    declarations* of what each method family can do, what it costs, and the
    maximum risk it may be composed under. It owns no implementation — the
    evaluator owns that — and it owns no promotion path.
Governance scope: declaration-only. The registry selects capsules for a
    signature; it NEVER runs a method, NEVER scores a candidate, NEVER promotes
    a capability, and NEVER mutates the capability registry or the maturity
    ladder. Its only effect is producing a CandidateComposer seeded with the
    capsules a signature admits.
Dependencies: gateway.candidate_composer (MethodCapsule, CandidateComposer),
    gateway.problem_signature (ProblemSignature, family/risk admissibility),
    gateway.candidate_ledger (CandidateLedger, only as a composer argument).
Invariants:
  - capsule_id is unique within a registry; duplicate registration is rejected.
  - A capsule is admissible for a signature only when its method family is
    admitted by the signature AND its risk_ceiling covers the signature risk.
  - The registry adds no surface a capsule does not already declare. It cannot
    raise a capsule's risk_ceiling or relabel its family.
  - STARTER_CAPSULES are conservative starter DEFAULTS. Capsule/adapter owners
    SHOULD review and replace the risk_ceiling, cost_class, and explainability
    claims with measured values before those claims inform a promotion decision.
"""

from __future__ import annotations

from gateway.candidate_composer import CandidateComposer, MethodCapsule
from gateway.candidate_ledger import CandidateLedger
from gateway.problem_signature import ProblemSignature


# Mirror of candidate_composer._RISK_RANK. The four classes are fixed by
# ProblemSignature.RISK_CLASSES; keep these two ranks identical.
_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "physical": 3}


def _capsule_covers_risk(capsule: MethodCapsule, signature_risk: str) -> bool:
    return _RISK_RANK.get(signature_risk, 0) <= _RISK_RANK.get(capsule.risk_ceiling, 0)


class MethodRegistry:
    """An ordered, de-duplicated catalog of method capsules."""

    def __init__(self, capsules: tuple[MethodCapsule, ...] = ()) -> None:
        self._capsules: dict[str, MethodCapsule] = {}
        self.register_all(capsules)

    def register(self, capsule: MethodCapsule) -> None:
        if capsule.capsule_id in self._capsules:
            raise ValueError(f"duplicate_capsule_id:{capsule.capsule_id}")
        self._capsules[capsule.capsule_id] = capsule

    def register_all(self, capsules: tuple[MethodCapsule, ...]) -> None:
        for capsule in capsules:
            self.register(capsule)

    def has(self, capsule_id: str) -> bool:
        return capsule_id in self._capsules

    def get(self, capsule_id: str) -> MethodCapsule:
        if capsule_id not in self._capsules:
            raise ValueError(f"unknown_capsule_id:{capsule_id}")
        return self._capsules[capsule_id]

    def all_capsules(self) -> tuple[MethodCapsule, ...]:
        return tuple(self._capsules.values())

    def families(self) -> tuple[str, ...]:
        return tuple(sorted({c.method_family for c in self._capsules.values()}))

    def by_family(self, method_family: str) -> tuple[MethodCapsule, ...]:
        return tuple(
            c for c in self._capsules.values() if c.method_family == method_family
        )

    def for_domain(self, domain: str) -> tuple[MethodCapsule, ...]:
        """Capsules tagged for `domain` plus untagged (general-purpose) capsules.

        The `domains` tag is a metadata hint only; final admissibility is still
        decided per-signature by `admissible_for` / the composer.
        """
        out: list[MethodCapsule] = []
        for capsule in self._capsules.values():
            domains = capsule.metadata.get("domains")
            if not domains or domain in domains:
                out.append(capsule)
        return tuple(out)

    def admissible_for(self, signature: ProblemSignature) -> tuple[MethodCapsule, ...]:
        """Capsules whose family the signature admits and whose risk_ceiling
        covers the signature risk. This mirrors the composer's own
        admissibility test so callers can inspect it without a run.
        """
        out: list[MethodCapsule] = []
        for capsule in self._capsules.values():
            if not signature.admits_method_family(capsule.method_family):
                continue
            if not _capsule_covers_risk(capsule, signature.risk):
                continue
            out.append(capsule)
        return tuple(out)

    def composer_for(
        self,
        signature: ProblemSignature,
        ledger: CandidateLedger,
        *,
        adversarial_reviewer=None,
    ) -> CandidateComposer:
        """Build a CandidateComposer seeded with the capsules whose family the
        signature admits. Risk-ceiling skips are left to the composer so they
        are reported transparently in the comparison report (a capsule eligible
        by family but too risky for the signature is informative evidence).

        The composer is the only thing this method produces. It does not run,
        score, or promote anything — the caller drives the run with an
        evaluator, exactly as if it had constructed the composer by hand.
        """
        capsules = tuple(
            c
            for c in self._capsules.values()
            if signature.admits_method_family(c.method_family)
        )
        return CandidateComposer(
            ledger, capsules=capsules, adversarial_reviewer=adversarial_reviewer
        )


def _starter(
    capsule_id: str,
    method_family: str,
    *,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    assumptions: tuple[str, ...],
    failure_modes: tuple[str, ...],
    cost_class: str,
    explainability: str,
    risk_ceiling: str,
    domains: tuple[str, ...],
    summary: str,
) -> MethodCapsule:
    return MethodCapsule(
        capsule_id=capsule_id,
        method_family=method_family,
        declared_inputs=inputs,
        declared_outputs=outputs,
        declared_assumptions=assumptions,
        declared_failure_modes=failure_modes,
        cost_class=cost_class,
        explainability=explainability,
        risk_ceiling=risk_ceiling,
        metadata={
            "provenance": "starter_default",
            "domains": domains,
            "summary": summary,
        },
    )


# Conservative starter catalog. See module docstring: these are defaults to
# seed the registry and exercise the loop, not measured production claims.
STARTER_CAPSULES: tuple[MethodCapsule, ...] = (
    # --- document_verification: the worked duplicate-detection benchmark ---
    _starter(
        "capsule:rule_based.exact_field_match.v1",
        "rule_based",
        inputs=("records",),
        outputs=("duplicate_pairs", "matched_fields"),
        assumptions=("fields are parsed and normalized identically",),
        failure_modes=("misses near-duplicates with formatting variation",),
        cost_class="low",
        explainability="high",
        risk_ceiling="high",
        domains=("document_verification",),
        summary="Exact match on (vendor, document_number, amount). High precision, low recall.",
    ),
    _starter(
        "capsule:graph_match.vendor_amount_proximity.v1",
        "graph_match",
        inputs=("records",),
        outputs=("duplicate_pairs", "matched_edges"),
        assumptions=("a vendor-identity normalization exists",),
        failure_modes=("over-merges when normalization is too aggressive", "stale ledger"),
        cost_class="medium",
        explainability="high",
        risk_ceiling="high",
        domains=("document_verification",),
        summary="Normalized vendor + amount proximity + number/date match. Catches variations.",
    ),
    _starter(
        "capsule:statistical.same_vendor_overflag.v1",
        "statistical_anomaly",
        inputs=("records",),
        outputs=("duplicate_pairs",),
        assumptions=("same-vendor invoices are suspicious",),
        failure_modes=("over-flags distinct invoices from the same vendor (low precision)",),
        cost_class="low",
        explainability="medium",
        risk_ceiling="medium",
        domains=("document_verification",),
        summary="Flags any same-vendor pair. High recall, low precision — a recall-only trap.",
    ),
    # --- workflow_automation / engineering_puzzle catalog (no evaluator yet) ---
    _starter(
        "capsule:constraint_solver.scheduling.v1",
        "constraint_solver",
        inputs=("tasks", "constraints", "resources"),
        outputs=("schedule", "infeasibility_certificate"),
        assumptions=("constraints are expressible as a finite-domain CSP",),
        failure_modes=("times out on large domains", "no solution reported as infeasible"),
        cost_class="medium",
        explainability="high",
        risk_ceiling="medium",
        domains=("workflow_automation", "engineering_puzzle"),
        summary="Finite-domain constraint satisfaction for scheduling/allocation.",
    ),
    _starter(
        "capsule:search_planner.bfs_deadline.v1",
        "search_planner",
        inputs=("initial_state", "goal", "operators"),
        outputs=("plan", "frontier_stats"),
        assumptions=("state space is enumerable", "operators are deterministic"),
        failure_modes=("combinatorial blow-up", "no plan within budget"),
        cost_class="medium",
        explainability="medium",
        risk_ceiling="medium",
        domains=("workflow_automation",),
        summary="Breadth-first / deadline-bounded search planning over discrete states.",
    ),
    _starter(
        "capsule:optimization_solver.lp_relax.v1",
        "optimization_solver",
        inputs=("objective", "constraints"),
        outputs=("assignment", "objective_value", "bound"),
        assumptions=("objective and constraints are (mixed-)linear",),
        failure_modes=("fractional relaxation needs rounding", "unbounded objective"),
        cost_class="medium",
        explainability="medium",
        risk_ceiling="medium",
        domains=("engineering_puzzle",),
        summary="Linear/MILP relaxation for resource allocation and routing.",
    ),
    _starter(
        "capsule:formal_verification.invariant_proof.v1",
        "formal_verification",
        inputs=("model", "invariants"),
        outputs=("proof", "counterexample"),
        assumptions=("the model is faithfully encoded",),
        failure_modes=("undecidable fragment", "spurious counterexample from abstraction"),
        cost_class="high",
        explainability="high",
        risk_ceiling="physical",
        domains=("engineering_puzzle",),
        summary="Proves declared invariants or returns a counterexample. Safe for high risk.",
    ),
    _starter(
        "capsule:simulation_check.deploy_dryrun.v1",
        "simulation_check",
        inputs=("plan", "environment_model"),
        outputs=("simulated_outcome", "violations"),
        assumptions=("the environment model is representative",),
        failure_modes=("model drift from reality", "unmodeled side effects"),
        cost_class="medium",
        explainability="medium",
        risk_ceiling="high",
        domains=("workflow_automation", "engineering_puzzle"),
        summary="Dry-runs a plan against a model before any real-world effect.",
    ),
    # --- general-purpose method families (no domain tag) ---
    _starter(
        "capsule:llm_planner.decompose.v1",
        "llm_planner",
        inputs=("goal", "context"),
        outputs=("subtasks", "rationale"),
        assumptions=("the goal is expressible in natural language",),
        failure_modes=("hallucinated steps", "non-reproducible without fixed seed/model"),
        cost_class="medium",
        explainability="low",
        risk_ceiling="medium",
        domains=(),
        summary="LLM decomposition of a goal into ordered subtasks. Pair with a verifier.",
    ),
    _starter(
        "capsule:llm_reviewer.spec_check.v1",
        "llm_reviewer",
        inputs=("artifact", "spec"),
        outputs=("findings", "verdict"),
        assumptions=("the spec is explicit enough to check against",),
        failure_modes=("misses subtle violations", "over-flags style as defects"),
        cost_class="medium",
        explainability="medium",
        risk_ceiling="medium",
        domains=(),
        summary="LLM check of an artifact against a spec. A reviewer, not an author.",
    ),
    _starter(
        "capsule:multi_agent_debate.adversarial.v1",
        "multi_agent_debate",
        inputs=("claim", "evidence"),
        outputs=("verdict", "dissent"),
        assumptions=("independent agents reduce correlated error",),
        failure_modes=("agreement collusion", "cost grows with rounds"),
        cost_class="high",
        explainability="medium",
        risk_ceiling="medium",
        domains=(),
        summary="Independent agents argue a claim; surfaces dissent. Expensive.",
    ),
    _starter(
        "capsule:human_review_gate.approval.v1",
        "human_review_gate",
        inputs=("proposal", "evidence_bundle"),
        outputs=("decision", "reviewer_id"),
        assumptions=("a qualified human reviewer is available",),
        failure_modes=("review latency", "rubber-stamping"),
        cost_class="high",
        explainability="high",
        risk_ceiling="physical",
        domains=(),
        summary="Routes a proposal to a human approver. The universal high-risk fallback.",
    ),
)


def default_registry() -> MethodRegistry:
    """A fresh MethodRegistry seeded with the conservative starter catalog."""
    return MethodRegistry(STARTER_CAPSULES)
