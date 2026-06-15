"""Purpose: GitHub/Codex review planning facade for personal assistant.
Governance scope: operator-supplied repository evidence, no-effect review
summaries, Codex instruction drafting, receipt emission, and connector/write
denial.
Dependencies: personal-assistant registry contracts and intake proof refs.
Invariants:
  - This module does not call GitHub, push branches, open or merge PRs, write
    issues, trigger deployments, or mutate repository state.
  - Review guidance is based only on bounded operator-supplied evidence.
  - Raw diffs, raw private payloads, secrets, tokens, and credentials are
    rejected before projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import ConnectorProofRef, GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


GITHUB_CODEX_REVIEW_SKILL_ID = "github.pr.summarize"

_GITHUB_CODEX_ACTIONS_NOT_TAKEN = (
    "github_not_called",
    "pull_request_not_opened",
    "pull_request_not_merged",
    "branch_not_pushed",
    "issue_not_created",
    "review_not_submitted",
    "deployment_not_started",
    "repository_not_mutated",
    "secret_values_not_serialized",
    "raw_diff_not_serialized",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gho_[A-Za-z0-9]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_diff",
        "diff",
        "patch",
        "raw_patch",
        "raw_private_connector_payload",
        "raw_connector_payload",
        "connector_response",
        "authorization",
        "cookie",
        "token",
        "secret",
        "private_key",
        "credential",
        "credentials",
    }
)


@dataclass(frozen=True, slots=True)
class GitHubCodexReviewProjection:
    """GitHub/Codex review plan plus governed receipt."""

    request_id: str
    skill_id: str
    plan: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "skill_id", _require_text(self.skill_id, "skill_id"))
        if not isinstance(self.plan, Mapping):
            raise PersonalAssistantInvariantError("plan must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "plan", MappingProxyType(dict(self.plan)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready GitHub/Codex projection."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "plan": dict(self.plan),
            "receipt": dict(self.receipt),
        }


def plan_github_codex_review(
    intent: GovernedIntent,
    *,
    generated_at: str,
    repository_ref: str,
    change_summary: str,
    pull_request_ref: str = "",
    changed_files: Sequence[str] = (),
    risk_notes: Sequence[str] = (),
    blocking_questions: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    requested_instruction_goal: str = "prepare the next safe Codex instruction",
    registry: PersonalAssistantSkillRegistry | None = None,
) -> GitHubCodexReviewProjection:
    """Prepare a GitHub/Codex review plan without GitHub or repository writes."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(GITHUB_CODEX_REVIEW_SKILL_ID)
    _assert_intent_admits_github_codex_review(intent)
    timestamp = _require_text(generated_at, "generated_at")
    repository = _require_text(repository_ref, "repository_ref")
    summary = _require_text(change_summary, "change_summary")
    pr_ref = _optional_text(pull_request_ref, "pull_request_ref")
    files = _bounded_text_tuple(changed_files, "changed_files", allow_empty=True, max_items=25)
    risks = _bounded_text_tuple(risk_notes, "risk_notes", allow_empty=True, max_items=12)
    questions = _bounded_text_tuple(blocking_questions, "blocking_questions", allow_empty=True, max_items=12)
    refs = _bounded_text_tuple(evidence_refs, "evidence_refs", allow_empty=True, max_items=20)
    instruction_goal = _require_text(requested_instruction_goal, "requested_instruction_goal")
    supplied_evidence_complete = bool(summary and files and refs)
    blockers = _blocking_reasons(files=files, evidence_refs=refs, blocking_questions=questions)
    codex_instruction = _codex_instruction(
        repository_ref=repository,
        pull_request_ref=pr_ref,
        change_summary=summary,
        changed_files=files,
        risk_notes=risks,
        blocking_questions=questions,
        instruction_goal=instruction_goal,
    )
    plan = {
        "plan_type": "github_codex_review_foundation",
        "repository_ref": repository,
        "pull_request_ref": pr_ref,
        "change_summary": summary,
        "changed_files": list(files),
        "risk_notes": list(risks),
        "blocking_questions": list(questions),
        "review_decision": "review_only",
        "merge_recommendation": "do_not_merge_from_projection",
        "codex_instruction": codex_instruction,
        "evidence_gate": {
            "operator_supplied_evidence_complete": supplied_evidence_complete,
            "evidence_refs": list(refs),
            "blocking_reasons": blockers,
            "github_call_performed": False,
            "repository_write_performed": False,
            "review_submission_performed": False,
            "deployment_performed": False,
        },
        "next_actions": blockers or ["operator may send the drafted Codex instruction in a separate tool context"],
        "effect_boundary": "github_codex_review_no_repository_effect",
        "execution_allowed": False,
        "github_call_allowed": False,
        "repository_mutation_allowed": False,
        "pull_request_mutation_allowed": False,
        "deployment_allowed": False,
    }
    receipt = _github_codex_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        generated_at=timestamp,
        plan=plan,
        evidence_refs=refs,
    )
    return GitHubCodexReviewProjection(intent.request_id, skill.skill_id, plan, receipt)


def _assert_intent_admits_github_codex_review(intent: GovernedIntent) -> None:
    if GITHUB_CODEX_REVIEW_SKILL_ID not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(
            f"{GITHUB_CODEX_REVIEW_SKILL_ID} is not requested by intent {intent.request_id}"
        )
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block GitHub/Codex review")
    connector_ref = next(
        (connector for connector in intent.connector_refs if connector.connector_name == "github"),
        None,
    )
    if connector_ref is None:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing github connector proof")
    _assert_connector_proof(connector_ref)


def _assert_connector_proof(connector_ref: ConnectorProofRef) -> None:
    if connector_ref.proof_state != "Pass" or not connector_ref.private_data_allowed:
        raise PersonalAssistantInvariantError("GitHub/Codex review requires passing github proof")


def _blocking_reasons(
    *,
    files: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    blocking_questions: tuple[str, ...],
) -> list[str]:
    blockers: list[str] = []
    if not files:
        blockers.append("changed_files_missing")
    if not evidence_refs:
        blockers.append("evidence_refs_missing")
    blockers.extend(blocking_questions)
    return blockers


def _codex_instruction(
    *,
    repository_ref: str,
    pull_request_ref: str,
    change_summary: str,
    changed_files: tuple[str, ...],
    risk_notes: tuple[str, ...],
    blocking_questions: tuple[str, ...],
    instruction_goal: str,
) -> str:
    file_text = ", ".join(changed_files) if changed_files else "operator-supplied file list is missing"
    risk_text = "; ".join(risk_notes) if risk_notes else "no additional risks supplied"
    question_text = "; ".join(blocking_questions) if blocking_questions else "no blocking questions supplied"
    pr_text = pull_request_ref or "no pull-request ref supplied"
    return (
        f"Repository: {repository_ref}. Pull request: {pr_text}. Goal: {instruction_goal}. "
        f"Change summary: {change_summary}. Files: {file_text}. Risks: {risk_text}. "
        f"Open questions: {question_text}. Stay in preview/review mode; do not push, merge, "
        "open issues, submit reviews, deploy, serialize secrets, or claim customer readiness."
    )


def _github_codex_receipt(
    *,
    intent: GovernedIntent,
    skill_id: str,
    risk_level: str,
    generated_at: str,
    plan: Mapping[str, Any],
    evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    suffix = _request_suffix(intent.request_id)
    blocked = bool(plan["evidence_gate"]["blocking_reasons"])
    all_refs = _evidence_refs(intent, evidence_refs, suffix)
    return {
        "receipt_id": f"pa_receipt_{suffix}_{_safe_identifier(skill_id)}",
        "request_id": intent.request_id,
        "skill_id": skill_id,
        "mode": "preview",
        "risk_level": risk_level,
        "inputs_used": ["operator_supplied_change_summary", "changed_files", "evidence_refs"],
        "connectors_used": ["github"],
        "decision": "blocked" if blocked else "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": ["github_codex_review_plan_prepared", "codex_instruction_drafted", "receipt_created"],
        "actions_not_taken": list(_GITHUB_CODEX_ACTIONS_NOT_TAKEN),
        "redactions": ["secret_values_not_serialized", "raw_diff_not_serialized", "connector_payload_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "redacted_summary",
        },
        "timestamp": generated_at,
        "evidence_refs": all_refs,
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/github-codex/{suffix}"],
        "outcome": "AwaitingEvidence" if blocked else "SolvedVerified",
        "metadata": {
            "review_decision": plan["review_decision"],
            "merge_recommendation": plan["merge_recommendation"],
            "blocking_reasons": list(plan["evidence_gate"]["blocking_reasons"]),
            "live_connector_execution_allowed": False,
            "github_call_performed": False,
            "repository_mutation_allowed": False,
            "pull_request_mutation_allowed": False,
            "external_write_allowed": False,
            "deployment_mutation_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _evidence_refs(intent: GovernedIntent, evidence_refs: tuple[str, ...], suffix: str) -> list[str]:
    refs: list[str] = []
    for evidence_ref in (*intent.evidence_refs, *evidence_refs):
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    refs.append(f"proof://personal-assistant/github-codex/{suffix}")
    return refs


def _bounded_text_tuple(
    values: Sequence[str],
    field_name: str,
    *,
    allow_empty: bool,
    max_items: int,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        text = _require_text(value, f"{field_name}[{index}]")
        if text not in normalized:
            normalized.append(text)
    if len(normalized) > max_items:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max_items={max_items}")
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _optional_text(value: str, field_name: str) -> str:
    if value == "":
        return ""
    return _require_text(value, field_name)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if len(value) > 2000:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max length")
    normalized_name = field_name.lower().split("[", 1)[0]
    if normalized_name in _RAW_PRIVATE_FIELD_NAMES:
        raise PersonalAssistantInvariantError(f"{field_name}: raw private field is forbidden")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _request_suffix(request_id: str) -> str:
    return _safe_identifier(request_id.removeprefix("pa_request_"))


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "github_codex"
