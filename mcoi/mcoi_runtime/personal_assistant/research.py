"""Purpose: research source-compare planning facade for personal assistant.
Governance scope: operator-supplied public source metadata, citation pack
projection, no-effect synthesis planning, receipt emission, and public/private
payload denial.
Dependencies: personal-assistant registry contracts and governed intake.
Invariants:
  - This module does not perform web search, contact sources, post publicly,
    start paid subscriptions, write memory, or mutate system-of-record state.
  - Source comparison is based only on bounded operator-supplied metadata.
  - Raw source bodies, raw private payloads, secrets, tokens, and credentials
    are rejected before projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


RESEARCH_SOURCE_COMPARE_SKILL_ID = "research.web_search"

_RESEARCH_ACTIONS_NOT_TAKEN = (
    "web_search_not_performed",
    "source_not_contacted",
    "external_submission_not_performed",
    "public_post_not_created",
    "paid_subscription_not_started",
    "raw_source_body_not_serialized",
    "secret_values_not_serialized",
    "system_of_record_not_mutated",
    "memory_not_written",
    "nested_mind_not_activated",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_body",
        "body",
        "raw_source_body",
        "raw_page",
        "html",
        "raw_html",
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
_ALLOWED_SOURCE_FIELDS = frozenset(
    {
        "source_ref",
        "title",
        "publisher",
        "published_at",
        "summary",
        "trust_tier",
        "citation_ref",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchSourceCompareProjection:
    """Research source-compare plan plus governed receipt."""

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
        """Return a deterministic JSON-ready research projection."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "plan": dict(self.plan),
            "receipt": dict(self.receipt),
        }


def plan_research_source_compare(
    intent: GovernedIntent,
    *,
    generated_at: str,
    research_question: str,
    source_summaries: Sequence[Mapping[str, Any]] = (),
    citation_refs: Sequence[str] = (),
    freshness_notes: Sequence[str] = (),
    conflict_notes: Sequence[str] = (),
    blocking_questions: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    requested_synthesis_goal: str = "prepare a source comparison with citations",
    registry: PersonalAssistantSkillRegistry | None = None,
) -> ResearchSourceCompareProjection:
    """Prepare a research source-comparison plan without live retrieval."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(RESEARCH_SOURCE_COMPARE_SKILL_ID)
    _assert_intent_admits_research_source_compare(intent)
    timestamp = _require_text(generated_at, "generated_at")
    question = _require_text(research_question, "research_question")
    sources = _bounded_source_tuple(source_summaries, "source_summaries", max_items=12)
    citations = _bounded_text_tuple(citation_refs, "citation_refs", allow_empty=True, max_items=20)
    freshness = _bounded_text_tuple(freshness_notes, "freshness_notes", allow_empty=True, max_items=12)
    conflicts = _bounded_text_tuple(conflict_notes, "conflict_notes", allow_empty=True, max_items=12)
    questions = _bounded_text_tuple(blocking_questions, "blocking_questions", allow_empty=True, max_items=12)
    refs = _bounded_text_tuple(evidence_refs, "evidence_refs", allow_empty=True, max_items=20)
    synthesis_goal = _require_text(requested_synthesis_goal, "requested_synthesis_goal")
    blockers = _blocking_reasons(sources=sources, citation_refs=citations, evidence_refs=refs, blocking_questions=questions)
    evidence_complete = not blockers
    source_compare = _source_compare_summary(
        question=question,
        sources=sources,
        freshness_notes=freshness,
        conflict_notes=conflicts,
    )
    plan = {
        "plan_type": "research_source_compare_foundation",
        "research_question": question,
        "requested_synthesis_goal": synthesis_goal,
        "source_summaries": [dict(source) for source in sources],
        "citation_refs": list(citations),
        "freshness_notes": list(freshness),
        "conflict_notes": list(conflicts),
        "blocking_questions": list(questions),
        "research_decision": "compare_only",
        "answer_claim_authority": "citation_backed_summary_only" if evidence_complete else "awaiting_citations",
        "source_compare": source_compare,
        "evidence_gate": {
            "operator_supplied_evidence_complete": evidence_complete,
            "evidence_refs": list(refs),
            "blocking_reasons": blockers,
            "web_search_performed": False,
            "source_contact_performed": False,
            "external_submission_performed": False,
            "public_post_performed": False,
            "paid_subscription_performed": False,
        },
        "next_actions": blockers or ["operator may review the citation-backed comparison before using it"],
        "effect_boundary": "research_source_compare_no_external_effect",
        "execution_allowed": False,
        "web_search_allowed": False,
        "source_contact_allowed": False,
        "external_submission_allowed": False,
        "public_post_allowed": False,
        "paid_subscription_allowed": False,
        "memory_write_allowed": False,
    }
    receipt = _research_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        generated_at=timestamp,
        plan=plan,
        evidence_refs=refs,
    )
    return ResearchSourceCompareProjection(intent.request_id, skill.skill_id, plan, receipt)


def _assert_intent_admits_research_source_compare(intent: GovernedIntent) -> None:
    if RESEARCH_SOURCE_COMPARE_SKILL_ID not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(
            f"{RESEARCH_SOURCE_COMPARE_SKILL_ID} is not requested by intent {intent.request_id}"
        )
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block research comparison")


def _blocking_reasons(
    *,
    sources: tuple[Mapping[str, Any], ...],
    citation_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    blocking_questions: tuple[str, ...],
) -> list[str]:
    blockers: list[str] = []
    if not sources:
        blockers.append("source_summaries_missing")
    if not citation_refs:
        blockers.append("citation_refs_missing")
    if not evidence_refs:
        blockers.append("evidence_refs_missing")
    blockers.extend(blocking_questions)
    return blockers


def _source_compare_summary(
    *,
    question: str,
    sources: tuple[Mapping[str, Any], ...],
    freshness_notes: tuple[str, ...],
    conflict_notes: tuple[str, ...],
) -> str:
    if not sources:
        return f"Research question '{question}' is awaiting operator-supplied public source metadata."
    titles = ", ".join(str(source["title"]) for source in sources)
    freshness = "; ".join(freshness_notes) if freshness_notes else "freshness not independently verified"
    conflicts = "; ".join(conflict_notes) if conflict_notes else "no conflicts supplied"
    return (
        f"Compare {len(sources)} operator-supplied public source summaries for '{question}': {titles}. "
        f"Freshness notes: {freshness}. Conflict notes: {conflicts}. Use only citation-backed summaries."
    )


def _research_receipt(
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
        "inputs_used": ["operator_supplied_source_summaries", "citation_refs", "evidence_refs"],
        "connectors_used": [],
        "decision": "blocked" if blocked else "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": ["research_source_compare_plan_prepared", "citation_pack_projected", "receipt_created"],
        "actions_not_taken": list(_RESEARCH_ACTIONS_NOT_TAKEN),
        "redactions": ["raw_source_body_not_serialized", "secret_values_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "no_connector_payload",
            "body_projection": "redacted_summary",
        },
        "timestamp": generated_at,
        "evidence_refs": all_refs,
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/research/{suffix}"],
        "outcome": "AwaitingEvidence" if blocked else "SolvedVerified",
        "metadata": {
            "research_decision": plan["research_decision"],
            "answer_claim_authority": plan["answer_claim_authority"],
            "blocking_reasons": list(plan["evidence_gate"]["blocking_reasons"]),
            "live_connector_execution_allowed": False,
            "web_search_performed": False,
            "external_write_allowed": False,
            "public_post_allowed": False,
            "paid_subscription_allowed": False,
            "memory_write_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _evidence_refs(intent: GovernedIntent, evidence_refs: tuple[str, ...], suffix: str) -> list[str]:
    refs: list[str] = []
    for evidence_ref in (*intent.evidence_refs, *evidence_refs):
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    refs.append(f"proof://personal-assistant/research/{suffix}")
    return refs


def _bounded_source_tuple(
    values: Sequence[Mapping[str, Any]],
    field_name: str,
    *,
    max_items: int,
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a mapping")
        normalized.append(MappingProxyType(_bounded_source_summary(value, f"{field_name}[{index}]")))
    if len(normalized) > max_items:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max_items={max_items}")
    return tuple(normalized)


def _bounded_source_summary(source: Mapping[str, Any], field_name: str) -> dict[str, str]:
    unexpected = sorted(set(source) - _ALLOWED_SOURCE_FIELDS)
    if unexpected:
        raise PersonalAssistantInvariantError(f"{field_name}: unsupported source fields {unexpected}")
    return {
        "source_ref": _require_text(source.get("source_ref"), f"{field_name}.source_ref"),
        "title": _require_text(source.get("title"), f"{field_name}.title"),
        "publisher": _require_text(source.get("publisher"), f"{field_name}.publisher"),
        "published_at": _optional_text(str(source.get("published_at", "")), f"{field_name}.published_at"),
        "summary": _require_text(source.get("summary"), f"{field_name}.summary"),
        "trust_tier": _require_text(source.get("trust_tier"), f"{field_name}.trust_tier"),
        "citation_ref": _require_text(source.get("citation_ref"), f"{field_name}.citation_ref"),
    }


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
    normalized_name = field_name.lower().rsplit(".", 1)[-1].split("[", 1)[0]
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
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "research"
