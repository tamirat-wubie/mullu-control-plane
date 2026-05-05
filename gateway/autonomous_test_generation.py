"""Gateway autonomous test-generation engine.

Purpose: convert certified failure traces into permanent governed test-case
    proposals for replay, policy, approval, tenant, prompt-injection, budget,
    temporal, and sandbox coverage.
Governance scope: failure evidence admission, deterministic test expansion,
    activation blocking, replay-library projection, and operator review.
Dependencies: standard-library dataclasses, hashlib, and JSON serialization.
Invariants:
  - Test plans are proposals, not executed tests or automatic promotions.
  - Every generated case is causally anchored to one failure trace.
  - Every failure trace must carry evidence references.
  - High-risk failures generate governance, replay, and operator-review cases.
  - Generated plans remain activation-blocked until reviewed and certified.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable


FAILURE_TYPES = (
    "approval_bypass",
    "expired_approval",
    "tenant_boundary",
    "prompt_injection",
    "budget_bypass",
    "budget_exhaustion",
    "provider_failure",
    "sandbox_escape",
    "shell_bypass",
    "verification_gap",
    "generic_failure",
)
RISK_TIERS = ("low", "medium", "high", "critical")
TEST_TYPES = (
    "unit",
    "governance",
    "prompt_injection",
    "tenant_boundary",
    "budget",
    "approval",
    "temporal",
    "replay_fixture",
    "sandbox_scenario",
    "channel_variant",
)
HIGH_RISK_FAILURES = frozenset({
    "approval_bypass",
    "expired_approval",
    "tenant_boundary",
    "prompt_injection",
    "budget_bypass",
    "sandbox_escape",
    "shell_bypass",
    "verification_gap",
})


@dataclass(frozen=True, slots=True)
class FailureTrace:
    """Certified trace describing one observed governance or execution failure."""

    trace_id: str
    tenant_id: str
    command_id: str
    capability_id: str
    channel: str
    action: str
    failure_type: str
    failure_reason: str
    observed_at: str
    risk_tier: str
    evidence_refs: tuple[str, ...]
    actor_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "trace_id",
            "tenant_id",
            "command_id",
            "capability_id",
            "channel",
            "action",
            "failure_type",
            "failure_reason",
            "observed_at",
            "risk_tier",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        if self.failure_type not in FAILURE_TYPES:
            raise ValueError("failure_type_invalid")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class GeneratedTestCase:
    """One deterministic test proposal derived from a failure trace."""

    case_id: str
    trace_id: str
    tenant_id: str
    test_type: str
    title: str
    target: str
    scenario: str
    input_mutations: tuple[str, ...]
    expected_outcome: str
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    replay_required: bool
    sandbox_required: bool
    operator_review_required: bool
    case_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.test_type not in TEST_TYPES:
            raise ValueError("test_type_invalid")
        for field_name in ("case_id", "trace_id", "tenant_id", "title", "target", "scenario", "expected_outcome"):
            _require_text(str(getattr(self, field_name)), field_name)
        object.__setattr__(self, "input_mutations", _normalize_text_tuple(self.input_mutations, "input_mutations"))
        object.__setattr__(self, "required_controls", _normalize_text_tuple(self.required_controls, "required_controls"))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TestGenerationPlan:
    """Activation-blocked test-generation plan for one tenant."""

    plan_id: str
    tenant_id: str
    source_trace_ids: tuple[str, ...]
    cases: tuple[GeneratedTestCase, ...]
    coverage_requirements: tuple[str, ...]
    replay_library_refs: tuple[str, ...]
    operator_review_required: bool
    activation_blocked: bool
    plan_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        _require_text(self.tenant_id, "tenant_id")
        object.__setattr__(self, "source_trace_ids", _normalize_text_tuple(self.source_trace_ids, "source_trace_ids", allow_empty=True))
        object.__setattr__(self, "cases", tuple(self.cases))
        object.__setattr__(self, "coverage_requirements", _normalize_text_tuple(self.coverage_requirements, "coverage_requirements"))
        object.__setattr__(self, "replay_library_refs", _normalize_text_tuple(self.replay_library_refs, "replay_library_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.operator_review_required:
            raise ValueError("operator_review_required")
        if not self.activation_blocked:
            raise ValueError("activation_must_be_blocked")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-schema compatible projection."""
        return _json_ready(asdict(self))


class AutonomousTestGenerationEngine:
    """Generate permanent test proposals from failure traces."""

    def generate(self, *, tenant_id: str, traces: Iterable[FailureTrace]) -> TestGenerationPlan:
        """Expand failure traces into a deterministic activation-blocked plan."""
        _require_text(tenant_id, "tenant_id")
        tenant_traces = tuple(sorted(
            (trace for trace in traces if trace.tenant_id == tenant_id),
            key=lambda trace: trace.trace_id,
        ))
        cases: list[GeneratedTestCase] = []
        for trace in tenant_traces:
            cases.extend(_cases_for_trace(trace))
        cases = list(_dedupe_cases(cases))
        coverage = _coverage_requirements(tenant_traces, cases)
        replay_refs = tuple(
            f"replay_fixture:{case.case_id}"
            for case in cases
            if case.replay_required
        )
        plan = TestGenerationPlan(
            plan_id=f"test-generation-plan-{_hash_payload({'tenant_id': tenant_id, 'trace_ids': [trace.trace_id for trace in tenant_traces]})[:16]}",
            tenant_id=tenant_id,
            source_trace_ids=tuple(trace.trace_id for trace in tenant_traces),
            cases=tuple(cases),
            coverage_requirements=coverage,
            replay_library_refs=replay_refs,
            operator_review_required=True,
            activation_blocked=True,
            metadata={
                "plan_is_not_execution": True,
                "trace_count": len(tenant_traces),
                "case_count": len(cases),
            },
        )
        return _stamp_plan(plan)


def _cases_for_trace(trace: FailureTrace) -> tuple[GeneratedTestCase, ...]:
    templates = _templates_for_failure(trace)
    return tuple(_stamp_case(_case_from_template(trace, template)) for template in templates)


def _templates_for_failure(trace: FailureTrace) -> tuple[dict[str, Any], ...]:
    templates = [
        _template("unit", "regression_unit", ("original_request",), "failure_is_bounded", ("failure_reproduction",)),
        _template("replay_fixture", "certified_replay_fixture", ("recorded_trace_replay",), "same_failure_path_blocked", ("replay_determinism", "terminal_closure")),
    ]
    if trace.failure_type in {"approval_bypass", "expired_approval"}:
        templates.extend((
            _template("approval", "approval_required_direct", ("direct_request",), "approval_required", ("approval_gate", "self_approval_denied")),
            _template("approval", "approval_required_paraphrase", ("paraphrased_request",), "approval_required", ("approval_gate",)),
            _template("temporal", "expired_approval_rejected", ("expired_approval",), "approval_rejected", ("validity_window", "fresh_approval")),
            _template("tenant_boundary", "wrong_tenant_approval_rejected", ("wrong_tenant",), "tenant_boundary_denied", ("tenant_boundary",)),
        ))
    if trace.failure_type == "tenant_boundary":
        templates.extend((
            _template("tenant_boundary", "cross_tenant_read_denied", ("wrong_tenant",), "tenant_boundary_denied", ("tenant_boundary", "rbac")),
            _template("tenant_boundary", "cross_tenant_write_denied", ("wrong_tenant_write",), "tenant_boundary_denied", ("tenant_boundary", "policy_gate")),
        ))
    if trace.failure_type in {"budget_bypass", "budget_exhaustion"}:
        templates.extend((
            _template("budget", "budget_exhaustion_blocks_spend", ("zero_remaining_budget",), "budget_denied", ("budget_gate",)),
            _template("budget", "budget_evasion_paraphrase_denied", ("paraphrased_budget_bypass",), "budget_denied", ("budget_gate", "cost_receipt")),
        ))
    if trace.failure_type == "prompt_injection":
        templates.extend((
            _template("prompt_injection", "direct_injection_denied", ("override_instruction",), "content_safety_denied", ("prompt_injection",)),
            _template("prompt_injection", "nested_document_injection_denied", ("embedded_instruction",), "content_safety_denied", ("prompt_injection", "source_reference")),
        ))
    if trace.failure_type in {"sandbox_escape", "shell_bypass"}:
        templates.extend((
            _template("sandbox_scenario", "sandbox_escape_denied", ("host_path_access",), "sandbox_denied", ("sandbox", "no_host_root")),
            _template("governance", "legacy_shell_requires_sandbox", ("legacy_shell_path",), "policy_denied", ("sandbox", "policy_gate")),
        ))
    if trace.failure_type == "provider_failure":
        templates.extend((
            _template("governance", "provider_failure_emits_receipt", ("provider_timeout",), "requires_review", ("worker_receipt", "recovery_ref")),
            _template("replay_fixture", "provider_failure_replay", ("provider_error_replay",), "same_failure_path_blocked", ("replay_determinism",)),
        ))
    if trace.failure_type == "verification_gap":
        templates.extend((
            _template("governance", "verification_gap_blocks_closure", ("missing_verification",), "terminal_closure_denied", ("verification", "terminal_closure")),
            _template("replay_fixture", "verification_replay_fixture", ("missing_verification_replay",), "terminal_closure_denied", ("replay_determinism", "verification")),
        ))
    if trace.risk_tier in {"high", "critical"} or trace.failure_type in HIGH_RISK_FAILURES:
        templates.extend((
            _template("prompt_injection", "hidden_injection_variant_denied", ("hidden_instruction",), "content_safety_denied", ("prompt_injection",)),
            _template("channel_variant", "slack_channel_variant", ("channel:slack",), "same_policy_outcome", ("channel_gateway", "policy_gate")),
            _template("channel_variant", "whatsapp_channel_variant", ("channel:whatsapp",), "same_policy_outcome", ("channel_gateway", "policy_gate")),
        ))
    return tuple(templates)


def _template(
    test_type: str,
    name: str,
    input_mutations: tuple[str, ...],
    expected_outcome: str,
    required_controls: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "test_type": test_type,
        "name": name,
        "input_mutations": input_mutations,
        "expected_outcome": expected_outcome,
        "required_controls": required_controls,
    }


def _case_from_template(trace: FailureTrace, template: dict[str, Any]) -> GeneratedTestCase:
    test_type = str(template["test_type"])
    name = str(template["name"])
    return GeneratedTestCase(
        case_id="pending",
        trace_id=trace.trace_id,
        tenant_id=trace.tenant_id,
        test_type=test_type,
        title=f"{trace.failure_type}:{name}",
        target=trace.capability_id,
        scenario=f"{trace.action}:{trace.failure_reason}",
        input_mutations=tuple(str(item) for item in template["input_mutations"]),
        expected_outcome=str(template["expected_outcome"]),
        required_controls=tuple(str(item) for item in template["required_controls"]),
        evidence_refs=trace.evidence_refs,
        replay_required=test_type in {"replay_fixture", "governance", "approval", "tenant_boundary", "budget", "temporal", "prompt_injection"},
        sandbox_required=test_type == "sandbox_scenario" or trace.failure_type in {"sandbox_escape", "shell_bypass"},
        operator_review_required=True,
        metadata={
            "source_failure_type": trace.failure_type,
            "source_channel": trace.channel,
            "risk_tier": trace.risk_tier,
            "created_from_failure": True,
        },
    )


def _stamp_case(test_case: GeneratedTestCase) -> GeneratedTestCase:
    payload = asdict(replace(test_case, case_id="pending", case_hash=""))
    case_hash = _hash_payload(payload)
    return replace(test_case, case_id=f"generated-test-{case_hash[:16]}", case_hash=case_hash)


def _stamp_plan(plan: TestGenerationPlan) -> TestGenerationPlan:
    payload = asdict(replace(plan, plan_hash=""))
    return replace(plan, plan_hash=_hash_payload(payload))


def _dedupe_cases(cases: Iterable[GeneratedTestCase]) -> tuple[GeneratedTestCase, ...]:
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    unique: list[GeneratedTestCase] = []
    for case in cases:
        key = (case.trace_id, case.test_type, case.expected_outcome, case.input_mutations)
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    return tuple(sorted(unique, key=lambda case: case.case_id))


def _coverage_requirements(
    traces: tuple[FailureTrace, ...],
    cases: list[GeneratedTestCase],
) -> tuple[str, ...]:
    requirements = {"unit", "replay_fixture"}
    if any(trace.failure_type in HIGH_RISK_FAILURES or trace.risk_tier in {"high", "critical"} for trace in traces):
        requirements.update({"governance", "prompt_injection", "operator_review"})
    for case in cases:
        if case.test_type in {"approval", "tenant_boundary", "budget", "temporal", "sandbox_scenario", "channel_variant"}:
            requirements.add(case.test_type)
    return tuple(sorted(requirements))


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
    return value.strip()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple | list):
        raise ValueError(f"{field_name}_must_be_array")
    normalized = tuple(str(value).strip() for value in values)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name}_required")
    if any(not value for value in normalized):
        raise ValueError(f"{field_name}_item_required")
    return normalized


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value
