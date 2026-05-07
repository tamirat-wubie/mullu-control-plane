"""
Software Development Domain Adapter.

First concrete domain adapter for MUSIA. Translates software engineering
work (bug fixes, features, refactors, deployments) into the universal
25-construct framework, and back.

Pattern: every domain adapter implements two functions:
  - translate_to_universal(request) -> UniversalRequest
  - translate_from_universal(result) -> DomainResult

Domain adapters are the ONLY place that holds domain vocabulary.
The core MUSIA runtime knows nothing about "code", "PRs", or "tests".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class SoftwareWorkKind(Enum):
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    DEPLOY = "deploy"
    REVIEW = "review"
    INVESTIGATE = "investigate"
    TEST_GENERATION = "test_generation"
    SECURITY_FIX = "security_fix"
    DOCS = "docs"
    MIGRATION = "migration"
    DEPENDENCY_UPDATE = "dependency_update"
    ROLLBACK = "rollback"


class SoftwareWorkMode(Enum):
    """How far the autonomy loop is allowed to take an accepted request."""

    PLAN_ONLY = "plan_only"
    DRY_RUN = "dry_run"
    PATCH_ONLY = "patch_only"
    PATCH_AND_TEST = "patch_and_test"
    PATCH_TEST_REVIEW = "patch_test_review"
    COMMIT_CANDIDATE = "commit_candidate"


class SoftwareQualityGate(Enum):
    """Named quality gates a software request can require evidence for."""

    UNIT_TESTS = "unit_tests"
    INTEGRATION_TESTS = "integration_tests"
    LINT = "lint"
    TYPECHECK = "typecheck"
    SECURITY_SCAN = "security_scan"
    BUILD = "build"
    REVIEW = "review"


@dataclass(frozen=True)
class SoftwareCommandPolicySpec:
    """Declarative description of the runtime CommandPolicy a request expects.

    The autonomy loop converts this spec into a runtime CommandPolicy when
    instantiating the LocalCodeAdapter. Defaults are deliberately empty
    tuples so that the adapter's own strict defaults apply unless the
    request widens or narrows them.
    """

    allowed_executables: tuple[str, ...] = ()
    denied_executables: tuple[str, ...] = ()
    denied_git_subcommands: tuple[str, ...] = ()
    max_timeout_seconds: int = 300
    max_output_bytes: int = 1_048_576
    network_allowed: bool = False
    sandbox_profile: str = "none"


@dataclass
class SoftwareRequest:
    """Domain-shaped input from a developer.

    Beyond the original kind/summary/repository contract, a request can
    declare:
      - mode                       — how far the autonomy loop runs
      - quality_gates              — which named gates produce evidence
      - max_self_debug_iterations  — retry budget for plan→patch→test loop
      - rollback_required          — must the loop be able to undo the change
      - command_policy             — declarative CommandPolicy for run_command
      - sandbox_profile            — sandbox name (e.g. "docker_network_none")
      - evidence_required          — names of evidence artifacts the terminal
                                     certificate must carry
    """

    kind: SoftwareWorkKind
    summary: str
    repository: str
    target_branch: str = "main"
    affected_files: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    blast_radius: str = "module"  # function | module | service | system
    reviewer_required: bool = True

    # F6 enrichments — autonomy loop contract
    mode: SoftwareWorkMode = SoftwareWorkMode.PATCH_TEST_REVIEW
    quality_gates: tuple[SoftwareQualityGate, ...] = (
        SoftwareQualityGate.UNIT_TESTS,
        SoftwareQualityGate.LINT,
    )
    max_self_debug_iterations: int = 3
    rollback_required: bool = True
    command_policy: SoftwareCommandPolicySpec = field(
        default_factory=SoftwareCommandPolicySpec
    )
    sandbox_profile: str = "none"
    evidence_required: tuple[str, ...] = (
        "workspace_snapshot",
        "patch_result",
        "test_result",
        "review_record",
    )


# UniversalRequest and UniversalResult moved to domain_adapters/_types.py
# in v4.14.1 to break the _cycle_helpers ↔ software_dev import cycle.
# Re-exported here so existing imports of these names from software_dev
# keep working unchanged.
from mcoi_runtime.domain_adapters._types import (
    UniversalRequest,
    UniversalResult,
)


@dataclass
class SoftwareResult:
    """Domain-shaped output for the developer."""

    work_plan: tuple[str, ...]
    risk_flags: tuple[str, ...]
    required_reviewers: tuple[str, ...]
    estimated_blast_radius: str
    completion_criteria: tuple[str, ...]
    governance_status: str
    audit_trail_id: UUID


# ---- TRANSLATION FUNCTIONS ----


def translate_to_universal(req: SoftwareRequest) -> UniversalRequest:
    """
    Project software request into universal causal shape.

    Mapping:
      - kind                  -> purpose_statement (verb + object)
      - repository + branch   -> boundary
      - affected_files        -> boundary.interface_points
      - acceptance_criteria   -> constraint_set
      - reviewer_required     -> authority + observer
      - blast_radius          -> boundary.permeability hint
    """
    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "code_state",
        "repo": req.repository,
        "branch": req.target_branch,
        "files": list(req.affected_files),
        "phase": "pre_change",
    }

    target_state = {
        "kind": "code_state",
        "repo": req.repository,
        "branch": req.target_branch,
        "files": list(req.affected_files),
        "phase": "post_change",
        "must_satisfy": list(req.acceptance_criteria),
    }

    boundary = {
        "inside_predicate": (
            f"file ∈ {{{', '.join(req.affected_files)}}} ∧ "
            f"repo = {req.repository} ∧ branch = {req.target_branch}"
        ),
        "interface_points": list(req.affected_files),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints = tuple(
        {
            "domain": "software_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    )

    authority = ("repo_write_access", "branch_push_access")
    observer = ("code_reviewer",) if req.reviewer_required else ("ci_pipeline",)

    return UniversalRequest(
        purpose_statement=purpose,
        initial_state_descriptor=initial_state,
        target_state_descriptor=target_state,
        boundary_specification=boundary,
        constraint_set=constraints,
        authority_required=authority,
        observer_required=observer,
    )


def translate_from_universal(
    universal_result: UniversalResult,
    original_request: SoftwareRequest,
) -> SoftwareResult:
    """
    Project universal result back into software-shaped output.

    The construct graph summary tells us what kinds of work were defined.
    We translate back to a developer-readable plan.
    """
    work_plan = _work_plan_from_constructs(
        universal_result.construct_graph_summary,
        original_request,
    )

    risk_flags = _risk_flags_from_result(universal_result)

    reviewers = ("code_reviewer",) if original_request.reviewer_required else ()

    governance_status = (
        "approved"
        if universal_result.proof_state == "Pass"
        else f"blocked: {universal_result.proof_state}"
    )

    return SoftwareResult(
        work_plan=work_plan,
        risk_flags=risk_flags,
        required_reviewers=reviewers,
        estimated_blast_radius=original_request.blast_radius,
        completion_criteria=original_request.acceptance_criteria,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- HELPERS ----


def _purpose_from_kind(kind: SoftwareWorkKind, summary: str) -> str:
    verb_map = {
        SoftwareWorkKind.BUG_FIX:           "eliminate_defect",
        SoftwareWorkKind.FEATURE:           "introduce_capability",
        SoftwareWorkKind.REFACTOR:          "preserve_behavior_change_structure",
        SoftwareWorkKind.DEPLOY:            "transition_to_production_state",
        SoftwareWorkKind.REVIEW:            "validate_proposed_change",
        SoftwareWorkKind.INVESTIGATE:       "produce_diagnostic_artifact",
        SoftwareWorkKind.TEST_GENERATION:   "increase_test_coverage",
        SoftwareWorkKind.SECURITY_FIX:      "remediate_security_finding",
        SoftwareWorkKind.DOCS:              "update_documentation",
        SoftwareWorkKind.MIGRATION:         "evolve_data_or_schema_state",
        SoftwareWorkKind.DEPENDENCY_UPDATE: "advance_dependency_versions",
        SoftwareWorkKind.ROLLBACK:          "revert_to_prior_known_good_state",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "function": "closed",
        "module":   "selective",
        "service":  "selective",
        "system":   "open",
    }.get(blast, "selective")


def _work_plan_from_constructs(
    summary: dict[str, int],
    req: SoftwareRequest,
) -> tuple[str, ...]:
    """Generate human-readable steps from construct graph composition."""
    steps: list[str] = []

    if summary.get("observation", 0) > 0:
        steps.append(f"Read current state of {len(req.affected_files)} affected file(s)")

    if summary.get("inference", 0) > 0:
        steps.append(
            f"Infer required changes to satisfy {len(req.acceptance_criteria)} criteria"
        )

    if summary.get("decision", 0) > 0:
        steps.append("Select implementation approach")

    if summary.get("transformation", 0) > 0:
        steps.append(
            f"Apply transformations within boundary [{req.repository}:{req.target_branch}]"
        )

    if summary.get("validation", 0) > 0:
        steps.append("Run validation suite (tests, lint, type-check)")

    if req.reviewer_required:
        steps.append("Submit for code review")

    if req.kind == SoftwareWorkKind.DEPLOY:
        steps.append("Execute deployment with rollback armed")

    return tuple(steps)


def _risk_flags_from_result(result: UniversalResult) -> tuple[str, ...]:
    flags: list[str] = []

    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")

    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge — manual review recommended")

    if result.proof_state == "Unknown":
        flags.append("evidence_insufficient — sense-then-retry recommended")

    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted — escalate to Φ_gov")

    if len(result.cascade_chain) > 5:
        flags.append(
            f"large_cascade ({len(result.cascade_chain)} dependents) — review impact"
        )

    return tuple(flags)


# ---- End-to-end cognitive cycle integration ----


def _request_to_ucja_payload(req: SoftwareRequest) -> dict[str, Any]:
    """Translate a SoftwareRequest into the dict UCJA L0 expects."""
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "developer_action",
        # F6 enrichments — autonomy loop contract
        "mode": req.mode.value,
        "quality_gates": [gate.value for gate in req.quality_gates],
        "max_self_debug_iterations": req.max_self_debug_iterations,
        "rollback_required": req.rollback_required,
        "sandbox_profile": req.sandbox_profile,
        "command_policy": {
            "allowed_executables": list(req.command_policy.allowed_executables),
            "denied_executables": list(req.command_policy.denied_executables),
            "denied_git_subcommands": list(req.command_policy.denied_git_subcommands),
            "max_timeout_seconds": req.command_policy.max_timeout_seconds,
            "max_output_bytes": req.command_policy.max_output_bytes,
            "network_allowed": req.command_policy.network_allowed,
            "sandbox_profile": req.command_policy.sandbox_profile,
        },
        "evidence_required": list(req.evidence_required),
    }


def materialize_runtime_command_policy(spec: SoftwareCommandPolicySpec):
    """Convert a SoftwareCommandPolicySpec into the runtime CommandPolicy.

    Preserves the adapter's strict defaults whenever the spec has empty
    allow/deny tuples: empty allowlist means "use the adapter's defaults",
    not "allow nothing". This keeps spec-less requests safely strict while
    letting callers narrow or widen explicitly.
    """
    from mcoi_runtime.adapters.code_adapter import CommandPolicy

    defaults = CommandPolicy()
    return CommandPolicy(
        allowed_executables=(
            spec.allowed_executables or defaults.allowed_executables
        ),
        denied_executables=(
            spec.denied_executables or defaults.denied_executables
        ),
        denied_git_subcommands=(
            spec.denied_git_subcommands or defaults.denied_git_subcommands
        ),
        max_timeout_seconds=spec.max_timeout_seconds,
        max_output_bytes=spec.max_output_bytes,
    )


def run_with_ucja(
    req: SoftwareRequest,
    *,
    capture: list | None = None,
) -> SoftwareResult:
    """Full pipeline: request → UCJA L0–L9 → SCCCE cycle → result.

    UCJA gates whether the request even merits a cognitive cycle. If L0
    rejects (no purpose, no boundary), or any layer reclassifies (missing
    authority, no acceptance criteria), the cycle never runs and the
    result reflects the gate verdict.

    If UCJA passes all 10 layers, the cycle runs as before.
    """
    from mcoi_runtime.ucja import UCJAPipeline, LayerVerdict
    from uuid import uuid4

    payload = _request_to_ucja_payload(req)
    outcome = UCJAPipeline().run(payload)

    if not outcome.accepted:
        # UCJA gate failed — do not run the cycle
        proof_state = (
            "Fail" if outcome.rejected else "Unknown"
        )
        rejected_deltas = (
            {"layer": outcome.halted_at_layer, "reason": outcome.reason},
        )
        universal_result = UniversalResult(
            job_definition_id=outcome.draft.job_id,
            construct_graph_summary={},
            cognitive_cycles_run=0,
            converged=False,
            proof_state=proof_state,
            rejected_deltas=rejected_deltas,
        )
        return translate_from_universal(universal_result, req)

    # UCJA passed → run the cycle
    return run_with_cognitive_cycle(req, capture=capture)


def run_with_cognitive_cycle(
    req: SoftwareRequest,
    *,
    capture: list | None = None,
) -> SoftwareResult:
    """Full round trip: domain request → universal → SCCCE cycle → domain result.

    Migrated to use the shared `_cycle_helpers.run_default_cycle` in v4.8.0.
    Per-step values that distinguish software-dev work from other domains
    (CI as observation source, implementation_plan as inference rule, etc.)
    flow through `StepOverrides`.
    """
    from mcoi_runtime.domain_adapters._cycle_helpers import (
        StepOverrides,
        run_default_cycle,
    )

    universal_req = translate_to_universal(req)
    overrides = StepOverrides(
        causation_mechanism="developer_action",
        causation_strength=0.9,
        transformation_energy=1.0,
        transformation_reversibility="reversible",
        validation_evidence_refs=("test_suite_passing",),
        validation_confidence=0.95,
        observation_sensor="ci_status",
        observation_signal="green",
        observation_confidence=0.99,
        inference_rule="implementation_plan",
        inference_certainty=0.9,
        inference_kind="deductive",
        decision_criteria=("meets_acceptance_criteria",),
        decision_justification="acceptance criteria are satisfied by target_state",
        execution_plan_prefix=f"apply {req.kind.value}",
        execution_resources=tuple(req.affected_files),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)
