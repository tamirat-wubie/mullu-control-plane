"""Simple user-facing facade for governed platform actions.

Purpose: expose a small task vocabulary over the MVK governance SDK so product
surfaces do not require users to understand intent frames, proof stamps, or
constraint identifiers.
Governance scope: usability projection only; all action authority remains
owned by the Runtime ABI and MVK gate.
Dependencies: dataclasses, typing literals, and governance SDK builders.
Invariants: every action check creates a bounded intent, declares side effects,
requires scope proof, and preserves raw proof references for audit readback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from .governance_sdk import (
    ActionSentenceBuilder,
    GovernanceClient,
    GovernanceClientConfig,
    IntentFrameBuilder,
)
from .invariants import RuntimeCoreInvariantError

SimpleActionKind = Literal["view", "change", "send", "verify"]
SimpleOutcome = Literal["ready", "needs_review", "blocked"]
SimpleTaskKind = Literal["review_docs", "update_docs", "notify_support", "verify_artifact"]
SimpleWorkflowKind = Literal["docs_update", "support_notice", "artifact_review"]


@dataclass(frozen=True)
class SimpleTaskTemplate:
    """Plain task template that hides action and scope details from users."""

    task: SimpleTaskKind
    label: str
    default_goal: str
    action: SimpleActionKind
    allowed_area: str
    default_target: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible template."""

        return {
            "task": self.task,
            "label": self.label,
            "default_goal": self.default_goal,
            "action": self.action,
            "allowed_area": self.allowed_area,
            "default_target": self.default_target,
        }


@dataclass(frozen=True)
class SimpleWorkflowTemplate:
    """Plain workflow template that groups common tasks for users."""

    workflow: SimpleWorkflowKind
    label: str
    default_goal: str
    tasks: tuple[SimpleTaskKind, ...]
    target_required: bool
    default_target: str = ""

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible workflow template."""

        return {
            "workflow": self.workflow,
            "label": self.label,
            "default_goal": self.default_goal,
            "tasks": list(self.tasks),
            "target_required": self.target_required,
            "default_target": self.default_target,
        }


@dataclass(frozen=True)
class DocumentManipulationComponent:
    """One governed component in the document manipulation path."""

    component_ref: str
    label: str
    boundary: str
    contract_ref: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("document manipulation component cannot allow execution")
        for field_name, field_value in {
            "component_ref": self.component_ref,
            "label": self.label,
            "boundary": self.boundary,
            "contract_ref": self.contract_ref,
        }.items():
            _require_trimmed_text(field_value, f"document manipulation {field_name}")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible wiring component."""

        return {
            "component_ref": self.component_ref,
            "label": self.label,
            "boundary": self.boundary,
            "contract_ref": self.contract_ref,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DocumentManipulationWiring:
    """Read-only proof that document manipulation checks are fully wired."""

    title: str
    manipulation_ref: str
    components: tuple[DocumentManipulationComponent, ...]
    invariants: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("document manipulation wiring cannot allow execution")
        _require_trimmed_text(self.title, "document manipulation title")
        _require_trimmed_text(self.manipulation_ref, "document manipulation ref")
        if self.manipulation_ref != "docs_update":
            raise RuntimeCoreInvariantError("document manipulation ref must be docs_update")
        expected_refs = {
            "task.update_docs",
            "workflow.docs_update",
            "cli.workflow_docs_update",
            "api.check_workflow",
            "http.workflows_check",
            "app.mount_gate",
            "memory.update_documentation",
            "dashboard.simple_workflow_summaries",
        }
        actual_refs = {component.component_ref for component in self.components}
        if actual_refs != expected_refs:
            raise RuntimeCoreInvariantError("document manipulation components must match wiring contract")
        if len(actual_refs) != len(self.components):
            raise RuntimeCoreInvariantError("document manipulation components must be unique")
        if len(self.invariants) < 3:
            raise RuntimeCoreInvariantError("document manipulation wiring requires invariant coverage")
        for invariant in self.invariants:
            _require_trimmed_text(invariant, "document manipulation invariant")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible document manipulation wiring contract."""

        return {
            "title": self.title,
            "manipulation_ref": self.manipulation_ref,
            "components": [component.to_dict() for component in self.components],
            "invariants": list(self.invariants),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class SimpleTaskRequest:
    """Plain task request that can be converted into a governed action check."""

    task: SimpleTaskKind
    target: str = ""
    goal: str = ""
    actor_id: str = "local-user"

    def validate(self) -> None:
        """Reject incomplete task requests before governance execution."""

        _require_text(self.task, "task")
        _require_text(self.actor_id, "actor_id")


@dataclass(frozen=True)
class SimpleWorkflowRequest:
    """Plain workflow request that expands into governed task checks."""

    workflow: SimpleWorkflowKind
    target: str = ""
    goal: str = ""
    actor_id: str = "local-user"

    def validate(self) -> None:
        """Reject incomplete workflow requests before governance execution."""

        _require_text(self.workflow, "workflow")
        _require_text(self.actor_id, "actor_id")


@dataclass(frozen=True)
class SimpleActionRequest:
    """Plain task request from a user-facing surface."""

    goal: str
    action: SimpleActionKind
    target: str
    allowed_area: str
    actor_id: str = "local-user"

    def validate(self) -> None:
        """Reject incomplete requests before governance execution."""

        _require_text(self.goal, "goal")
        _require_text(self.target, "target")
        _require_text(self.allowed_area, "allowed_area")
        _require_text(self.actor_id, "actor_id")


@dataclass(frozen=True)
class SimpleActionCheck:
    """Plain outcome plus audit references for one action check."""

    outcome: SimpleOutcome
    title: str
    message: str
    next_step: str
    decision_ref: str
    proof_stamp_ref: str
    boundary_witness_ref: str
    raw_decision: str
    raw_reason: str
    blocked_reasons: tuple[str, ...]
    review_reasons: tuple[str, ...]

    @property
    def ok_to_continue(self) -> bool:
        """Return whether the action can proceed without extra review."""

        return self.outcome == "ready"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible projection."""

        return {
            "outcome": self.outcome,
            "title": self.title,
            "message": self.message,
            "next_step": self.next_step,
            "ok_to_continue": self.ok_to_continue,
            "decision_ref": self.decision_ref,
            "proof_stamp_ref": self.proof_stamp_ref,
            "boundary_witness_ref": self.boundary_witness_ref,
            "raw_decision": self.raw_decision,
            "raw_reason": self.raw_reason,
            "blocked_reasons": list(self.blocked_reasons),
            "review_reasons": list(self.review_reasons),
        }


@dataclass(frozen=True)
class SimpleWorkflowPlan:
    """Plain outcome for a workflow composed from governed task checks."""

    workflow: SimpleWorkflowKind
    label: str
    outcome: SimpleOutcome
    title: str
    message: str
    next_step: str
    checks: tuple[SimpleActionCheck, ...]

    @property
    def ok_to_continue(self) -> bool:
        """Return whether every workflow step can continue without review."""

        return self.outcome == "ready"

    @property
    def ready_count(self) -> int:
        """Return how many workflow steps are ready."""

        return sum(1 for check in self.checks if check.outcome == "ready")

    @property
    def review_count(self) -> int:
        """Return how many workflow steps need review."""

        return sum(1 for check in self.checks if check.outcome == "needs_review")

    @property
    def blocked_count(self) -> int:
        """Return how many workflow steps are blocked."""

        return sum(1 for check in self.checks if check.outcome == "blocked")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible workflow projection."""

        return {
            "workflow": self.workflow,
            "label": self.label,
            "outcome": self.outcome,
            "title": self.title,
            "message": self.message,
            "next_step": self.next_step,
            "ok_to_continue": self.ok_to_continue,
            "ready_count": self.ready_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class SimpleOnboardingStep:
    """Plain onboarding step that points to a governed simple command."""

    step: str
    title: str
    command: str
    purpose: str

    def __post_init__(self) -> None:
        for field_name, field_value in {
            "step": self.step,
            "title": self.title,
            "command": self.command,
            "purpose": self.purpose,
        }.items():
            _require_trimmed_text(field_value, field_name)

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible onboarding step."""

        return {
            "step": self.step,
            "title": self.title,
            "command": self.command,
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class SimpleOnboardingGuide:
    """Plain start guide for non-technical users."""

    title: str
    message: str
    recommended_path: tuple[SimpleOnboardingStep, ...]
    outcomes: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("simple onboarding guide cannot allow execution")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible onboarding guide."""

        return {
            "title": self.title,
            "message": self.message,
            "recommended_path": [step.to_dict() for step in self.recommended_path],
            "outcomes": list(self.outcomes),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class SimpleHomeChoice:
    """One plain choice for the simple platform home surface."""

    choice_ref: str
    label: str
    command: str
    purpose: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("simple home choice cannot allow execution")
        for field_name, field_value in {
            "choice_ref": self.choice_ref,
            "label": self.label,
            "command": self.command,
            "purpose": self.purpose,
        }.items():
            _require_text(field_value, f"simple home choice {field_name}")
            if field_value.strip() != field_value:
                raise RuntimeCoreInvariantError(f"simple home choice {field_name} must be trimmed")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible home choice."""

        return {
            "choice_ref": self.choice_ref,
            "label": self.label,
            "command": self.command,
            "purpose": self.purpose,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class SimpleHomeSummary:
    """Compact first-screen summary for non-technical users."""

    title: str
    message: str
    primary_command: str
    next_action: str
    choices: tuple[SimpleHomeChoice, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("simple home summary cannot allow execution")
        if len(self.choices) > 3:
            raise RuntimeCoreInvariantError("simple home choices must be three or fewer")
        if any(choice.execution_allowed for choice in self.choices):
            raise RuntimeCoreInvariantError("simple home choices cannot allow execution")
        for field_name, field_value in {
            "title": self.title,
            "message": self.message,
            "primary_command": self.primary_command,
            "next_action": self.next_action,
        }.items():
            _require_text(field_value, f"simple home {field_name}")
            if field_value.strip() != field_value:
                raise RuntimeCoreInvariantError(f"simple home {field_name} must be trimmed")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple home summary."""

        return {
            "title": self.title,
            "message": self.message,
            "primary_command": self.primary_command,
            "next_action": self.next_action,
            "choices": [choice.to_dict() for choice in self.choices],
            "execution_allowed": self.execution_allowed,
        }


class SimplePlatform:
    """Small governed facade for user-oriented action checks."""

    def __init__(self, client: GovernanceClient | None = None) -> None:
        self._client = client

    def check_action(self, request: SimpleActionRequest | Mapping[str, object]) -> SimpleActionCheck:
        """Check whether a plain action is ready, blocked, or needs review."""

        action_request = _request_from_mapping(request) if isinstance(request, Mapping) else request
        action_request.validate()
        client = self._client or GovernanceClient(GovernanceClientConfig(caller_id=action_request.actor_id))
        intent = (
            IntentFrameBuilder()
            .goal(action_request.goal)
            .within_scope(action_request.allowed_area)
            .succeeds_when("plain_user_outcome_emitted")
            .build()
        )
        action = _build_action(action_request).build()
        result = client.gate_action(intent=intent, action=action)
        decision = result.raw_call.output["result"]["decision"]
        blocked_reasons = tuple(_plain_reason(item) for item in decision["violated_constraints"])
        review_reasons = tuple(_plain_reason(item) for item in decision["required_escalations"])
        return _project_check(
            raw_decision=result.decision,
            raw_reason=result.explanation,
            blocked_reasons=blocked_reasons,
            review_reasons=review_reasons,
            decision_ref=result.decision_ref,
            proof_stamp_ref=result.proof_stamp_ref,
            boundary_witness_ref=result.boundary_witness_ref,
        )

    def check_task(self, request: SimpleTaskRequest | Mapping[str, object]) -> SimpleActionCheck:
        """Check one template-backed task without requiring users to pick scope."""

        task_request = _task_request_from_mapping(request) if isinstance(request, Mapping) else request
        task_request.validate()
        return self.check_action(_action_request_from_task(task_request))

    def check_workflow(self, request: SimpleWorkflowRequest | Mapping[str, object]) -> SimpleWorkflowPlan:
        """Check a common user workflow as one plain outcome."""

        workflow_request = _workflow_request_from_mapping(request) if isinstance(request, Mapping) else request
        workflow_request.validate()
        template = _workflow_template_for(workflow_request.workflow)
        target = workflow_request.target.strip() or template.default_target
        if template.target_required and not target:
            raise RuntimeCoreInvariantError(f"target is required for workflow: {workflow_request.workflow}")
        checks = tuple(
            self.check_task(
                SimpleTaskRequest(
                    task=task,
                    target=target,
                    goal=workflow_request.goal.strip() or template.default_goal,
                    actor_id=workflow_request.actor_id,
                )
            )
            for task in template.tasks
        )
        return _project_workflow_plan(template=template, checks=checks)

    @staticmethod
    def task_templates() -> tuple[SimpleTaskTemplate, ...]:
        """Return supported simple task templates."""

        return _TASK_TEMPLATES

    @staticmethod
    def workflow_templates() -> tuple[SimpleWorkflowTemplate, ...]:
        """Return supported simple workflow templates."""

        return _WORKFLOW_TEMPLATES

    @staticmethod
    def onboarding_guide() -> SimpleOnboardingGuide:
        """Return the plain start guide for simple platform users."""

        return SimpleOnboardingGuide(
            title="Mullu simple mode",
            message="Choose a workflow, check it, then continue only when it is ready.",
            recommended_path=(
                SimpleOnboardingStep(
                    step="choose",
                    title="Choose a workflow",
                    command="mullu workflows",
                    purpose="Show the common work users can start with.",
                ),
                SimpleOnboardingStep(
                    step="check",
                    title="Check before continuing",
                    command="mullu workflow docs-update --target docs/README.md",
                    purpose="Confirm whether the workflow is ready, needs review, or is blocked.",
                ),
                SimpleOnboardingStep(
                    step="act",
                    title="Continue only when ready",
                    command="mullu workflow docs-update --target docs/README.md --json",
                    purpose="Use the proof-backed outcome in an app, dashboard, or support flow.",
                ),
            ),
            outcomes=("Ready", "Needs review", "Blocked"),
        )

    @staticmethod
    def simple_home() -> SimpleHomeSummary:
        """Return the compact first-screen summary for simple platform users."""

        guide = SimplePlatform.onboarding_guide()
        choices = tuple(
            SimpleHomeChoice(
                choice_ref=step.step,
                label=step.title,
                command=step.command,
                purpose=step.purpose,
            )
            for step in guide.recommended_path[:3]
        )
        return SimpleHomeSummary(
            title="Start simple",
            message="Choose one guided workflow and check it before continuing.",
            primary_command=choices[0].command if choices else "mullu workflows",
            next_action="Open the workflow list and choose the work you want to do.",
            choices=choices,
        )

    @staticmethod
    def document_manipulation_wiring() -> DocumentManipulationWiring:
        """Return the read-only document manipulation wiring proof."""

        return DocumentManipulationWiring(
            title="Document manipulation wiring",
            manipulation_ref="docs_update",
            components=(
                DocumentManipulationComponent(
                    component_ref="task.update_docs",
                    label="Update docs task",
                    boundary="docs/**",
                    contract_ref="SimplePlatform.check_task",
                ),
                DocumentManipulationComponent(
                    component_ref="workflow.docs_update",
                    label="Docs update workflow",
                    boundary="docs/**",
                    contract_ref="SimplePlatform.check_workflow",
                ),
                DocumentManipulationComponent(
                    component_ref="cli.workflow_docs_update",
                    label="CLI workflow command",
                    boundary="mullu workflow docs-update --item docs/README.md",
                    contract_ref="mcoi_runtime.core.simple_cli.guarded_main",
                ),
                DocumentManipulationComponent(
                    component_ref="api.check_workflow",
                    label="Runtime workflow envelope",
                    boundary="SimplePlatformRuntime.check_workflow",
                    contract_ref="simple_platform.menu.v1",
                ),
                DocumentManipulationComponent(
                    component_ref="http.workflows_check",
                    label="HTTP workflow check route",
                    boundary="POST /api/v1/simple/workflows/check",
                    contract_ref="SimplePlatformFastAPIAdapter.route_specs",
                ),
                DocumentManipulationComponent(
                    component_ref="app.mount_gate",
                    label="App mount gate",
                    boundary="MULLU_SIMPLE_PLATFORM_ENABLED",
                    contract_ref="mount_simple_platform_router_from_env",
                ),
                DocumentManipulationComponent(
                    component_ref="memory.update_documentation",
                    label="Memory candidate action",
                    boundary="CompiledActionType.UPDATE_DOCUMENTATION",
                    contract_ref="compile_memory_actions",
                ),
                DocumentManipulationComponent(
                    component_ref="dashboard.simple_workflow_summaries",
                    label="Dashboard readback",
                    boundary="simple_workflow_summaries",
                    contract_ref="build_operational_dashboard_state",
                ),
            ),
            invariants=(
                "docs_update targets remain bounded to docs/**",
                "workflow checks preserve review and blocked outcomes",
                "route and dashboard readbacks do not grant execution authority",
                "memory candidates require a Mullu control-plane verdict before side effects",
            ),
        )


_TASK_TEMPLATES: tuple[SimpleTaskTemplate, ...] = (
    SimpleTaskTemplate(
        task="review_docs",
        label="Review docs",
        default_goal="Review documentation",
        action="view",
        allowed_area="docs/**",
    ),
    SimpleTaskTemplate(
        task="update_docs",
        label="Update docs",
        default_goal="Update documentation",
        action="change",
        allowed_area="docs/**",
    ),
    SimpleTaskTemplate(
        task="notify_support",
        label="Notify support",
        default_goal="Notify support",
        action="send",
        allowed_area="support@mullusi.com",
        default_target="support@mullusi.com",
    ),
    SimpleTaskTemplate(
        task="verify_artifact",
        label="Verify artifact",
        default_goal="Verify an artifact",
        action="verify",
        allowed_area="**",
    ),
)


_WORKFLOW_TEMPLATES: tuple[SimpleWorkflowTemplate, ...] = (
    SimpleWorkflowTemplate(
        workflow="docs_update",
        label="Update docs",
        default_goal="Review, update, and verify documentation",
        tasks=("review_docs", "update_docs", "verify_artifact"),
        target_required=True,
    ),
    SimpleWorkflowTemplate(
        workflow="support_notice",
        label="Notify support",
        default_goal="Notify support",
        tasks=("notify_support",),
        target_required=False,
        default_target="support@mullusi.com",
    ),
    SimpleWorkflowTemplate(
        workflow="artifact_review",
        label="Verify artifact",
        default_goal="Verify an artifact",
        tasks=("verify_artifact",),
        target_required=True,
    ),
)

_ACTION_REQUEST_FIELDS = frozenset({"goal", "action", "target", "allowed_area", "actor_id"})
_TASK_REQUEST_FIELDS = frozenset({"task", "target", "goal", "actor_id"})
_WORKFLOW_REQUEST_FIELDS = frozenset({"workflow", "target", "goal", "actor_id"})


def _build_action(request: SimpleActionRequest) -> ActionSentenceBuilder:
    """Map a plain action onto a governed action sentence builder."""

    if request.action == "view":
        return ActionSentenceBuilder.read_file(request.target).within_scope(request.target).requires_proof("scope_checked")
    if request.action == "change":
        return ActionSentenceBuilder.write_file(request.target).within_scope(request.target).requires_proof("scope_checked")
    if request.action == "send":
        return (
            ActionSentenceBuilder("notify", "message", request.target)
            .within_scope(request.target)
            .with_side_effects("external_write")
            .requires_proof("scope_checked")
        )
    if request.action == "verify":
        return (
            ActionSentenceBuilder("verify", "artifact", request.target)
            .within_scope(request.target)
            .requires_proof("scope_checked")
        )
    raise RuntimeCoreInvariantError(f"unsupported simple action: {request.action}")


def _project_check(
    *,
    raw_decision: str,
    raw_reason: str,
    blocked_reasons: tuple[str, ...],
    review_reasons: tuple[str, ...],
    decision_ref: str,
    proof_stamp_ref: str,
    boundary_witness_ref: str,
) -> SimpleActionCheck:
    """Translate governed decision details into a user-facing outcome."""

    if raw_decision == "allow":
        return SimpleActionCheck(
            outcome="ready",
            title="Ready",
            message="This action stays inside the allowed area and has the required proof.",
            next_step="Continue with the action.",
            decision_ref=decision_ref,
            proof_stamp_ref=proof_stamp_ref,
            boundary_witness_ref=boundary_witness_ref,
            raw_decision=raw_decision,
            raw_reason=raw_reason,
            blocked_reasons=(),
            review_reasons=(),
        )
    if raw_decision == "escalate":
        reasons = review_reasons or ("This action changes something outside the local workspace.",)
        return SimpleActionCheck(
            outcome="needs_review",
            title="Needs review",
            message="This action needs approval before it can continue.",
            next_step="Send it to an approver with the proof reference.",
            decision_ref=decision_ref,
            proof_stamp_ref=proof_stamp_ref,
            boundary_witness_ref=boundary_witness_ref,
            raw_decision=raw_decision,
            raw_reason=raw_reason,
            blocked_reasons=(),
            review_reasons=reasons,
        )
    if raw_decision == "block":
        reasons = blocked_reasons or ("The action does not satisfy the required constraints.",)
        return SimpleActionCheck(
            outcome="blocked",
            title="Blocked",
            message="This action cannot continue as requested.",
            next_step="Narrow the request or change the allowed area, then check again.",
            decision_ref=decision_ref,
            proof_stamp_ref=proof_stamp_ref,
            boundary_witness_ref=boundary_witness_ref,
            raw_decision=raw_decision,
            raw_reason=raw_reason,
            blocked_reasons=reasons,
            review_reasons=(),
        )
    raise RuntimeCoreInvariantError(f"unsupported governance decision: {raw_decision}")


def _project_workflow_plan(
    *,
    template: SimpleWorkflowTemplate,
    checks: tuple[SimpleActionCheck, ...],
) -> SimpleWorkflowPlan:
    """Translate task checks into one user-facing workflow plan."""

    blocked = tuple(check for check in checks if check.outcome == "blocked")
    review = tuple(check for check in checks if check.outcome == "needs_review")
    if blocked:
        return SimpleWorkflowPlan(
            workflow=template.workflow,
            label=template.label,
            outcome="blocked",
            title="Blocked",
            message="One or more steps cannot continue as requested.",
            next_step=blocked[0].next_step,
            checks=checks,
        )
    if review:
        return SimpleWorkflowPlan(
            workflow=template.workflow,
            label=template.label,
            outcome="needs_review",
            title="Needs review",
            message="One or more steps need approval before the workflow can continue.",
            next_step=review[0].next_step,
            checks=checks,
        )
    return SimpleWorkflowPlan(
        workflow=template.workflow,
        label=template.label,
        outcome="ready",
        title="Ready",
        message="All workflow steps are ready.",
        next_step="Continue with the workflow.",
        checks=checks,
    )


def _request_from_mapping(value: Mapping[str, object]) -> SimpleActionRequest:
    """Load a simple request from a JSON-like mapping."""

    _reject_unsupported_fields(value, _ACTION_REQUEST_FIELDS)
    return SimpleActionRequest(
        goal=_required_text(value, "goal"),
        action=_action_kind(_required_text(value, "action")),
        target=_required_text(value, "target"),
        allowed_area=_required_text(value, "allowed_area"),
        actor_id=_optional_text(value, "actor_id", default="local-user"),
    )


def _task_request_from_mapping(value: Mapping[str, object]) -> SimpleTaskRequest:
    """Load a simple task request from a JSON-like mapping."""

    _reject_unsupported_fields(value, _TASK_REQUEST_FIELDS)
    return SimpleTaskRequest(
        task=_task_kind(_required_text(value, "task")),
        target=_optional_text(value, "target", default=""),
        goal=_optional_text(value, "goal", default=""),
        actor_id=_optional_text(value, "actor_id", default="local-user"),
    )


def _workflow_request_from_mapping(value: Mapping[str, object]) -> SimpleWorkflowRequest:
    """Load a simple workflow request from a JSON-like mapping."""

    _reject_unsupported_fields(value, _WORKFLOW_REQUEST_FIELDS)
    return SimpleWorkflowRequest(
        workflow=_workflow_kind(_required_text(value, "workflow")),
        target=_optional_text(value, "target", default=""),
        goal=_optional_text(value, "goal", default=""),
        actor_id=_optional_text(value, "actor_id", default="local-user"),
    )


def _action_request_from_task(request: SimpleTaskRequest) -> SimpleActionRequest:
    """Convert a template-backed task into a governed action request."""

    template = _template_for(request.task)
    target = request.target.strip() or template.default_target
    if not target:
        raise RuntimeCoreInvariantError(f"target is required for task: {request.task}")
    return SimpleActionRequest(
        goal=request.goal.strip() or template.default_goal,
        action=template.action,
        target=target,
        allowed_area=template.allowed_area,
        actor_id=request.actor_id,
    )


def _template_for(task: SimpleTaskKind) -> SimpleTaskTemplate:
    for template in _TASK_TEMPLATES:
        if template.task == task:
            return template
    raise RuntimeCoreInvariantError(f"unsupported task: {task}")


def _workflow_template_for(workflow: SimpleWorkflowKind) -> SimpleWorkflowTemplate:
    for template in _WORKFLOW_TEMPLATES:
        if template.workflow == workflow:
            return template
    raise RuntimeCoreInvariantError(f"unsupported workflow: {workflow}")


def _plain_reason(reason: object) -> str:
    """Translate internal constraint ids into stable plain language."""

    text = str(reason)
    translations = {
        "This item is outside the right place for this task.": "The target is outside the allowed area.",
        "scope_within_intent": "The target is outside the allowed area.",
        "kernel.side_effect.declared": "The action includes an undeclared side effect.",
        "kernel.proof.scope_checked:scope_checked": "The action is missing required scope proof.",
        "kernel.side_effect.external_requires_approval:external_write": "External changes require approval.",
        "mfidel_atomicity_violation": "Mfidel atomicity would be violated.",
    }
    return translations.get(text, text.replace("_", " "))


def _action_kind(value: str) -> SimpleActionKind:
    if value in {"view", "change", "send", "verify"}:
        return value  # type: ignore[return-value]
    raise RuntimeCoreInvariantError("action must be one of: view, change, send, verify")


def _task_kind(value: str) -> SimpleTaskKind:
    normalized = value.strip().replace("-", "_")
    if normalized == "verify_item":
        return "verify_artifact"
    if normalized in {"review_docs", "update_docs", "notify_support", "verify_artifact"}:
        return normalized  # type: ignore[return-value]
    raise RuntimeCoreInvariantError("task must be one of: review_docs, update_docs, notify_support, verify_artifact")


def _workflow_kind(value: str) -> SimpleWorkflowKind:
    normalized = value.strip().replace("-", "_")
    if normalized == "item_review":
        return "artifact_review"
    if normalized in {"docs_update", "support_notice", "artifact_review"}:
        return normalized  # type: ignore[return-value]
    raise RuntimeCoreInvariantError("workflow must be one of: docs_update, support_notice, artifact_review")


def _required_text(value: Mapping[str, object], field_name: str) -> str:
    if field_name not in value:
        raise RuntimeCoreInvariantError(f"{field_name} is required")
    raw_value = value[field_name]
    if not isinstance(raw_value, str):
        raise RuntimeCoreInvariantError(f"{field_name} must be text")
    text = raw_value.strip()
    _require_text(text, field_name)
    return text


def _optional_text(value: Mapping[str, object], field_name: str, *, default: str) -> str:
    if field_name not in value:
        return default
    raw_value = value[field_name]
    if not isinstance(raw_value, str):
        raise RuntimeCoreInvariantError(f"{field_name} must be text")
    text = raw_value.strip()
    if not text:
        return default
    return text



def _public_field_name(field_name: str) -> str:
    return {
        "target": "item",
        "actor_id": "person or app",
    }.get(field_name, field_name)


def _reject_unsupported_fields(value: Mapping[str, object], allowed_fields: frozenset[str]) -> None:
    if any(field_name not in allowed_fields for field_name in value):
        raise RuntimeCoreInvariantError("request contains unsupported fields")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty text")


def _require_trimmed_text(value: str, field_name: str) -> None:
    _require_text(value, field_name)
    if value.strip() != value:
        raise RuntimeCoreInvariantError(f"{field_name} must be trimmed text")
