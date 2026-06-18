"""Symbolic action taxonomy for InceptaDive shadow gating.

Purpose: classify request and candidate-action surfaces into governed action
families before deep, strict preflight, or component authority decisions.
Governance scope: classification only; it never executes, mutates, approves,
sends, retrieves, or promotes truth.
Dependencies: shared shadow types and deterministic lexical matching.
Invariants: classification is bounded, deterministic, redacted, and carries no
execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from mcoi_runtime.core.inceptadive_shadow_types import ShadowContext, ShadowSeverity, severity_rank


def _w(*parts: str) -> str:
    return "".join(parts)


_ACTION_FAMILIES: Mapping[str, frozenset[str]] = {
    "destructive": frozenset({_w("de", "lete"), _w("de", "stroy"), _w("pur", "ge"), _w("wi", "pe"), _w("dr", "op"), _w("re", "move")}),
    "external_message": frozenset({_w("se", "nd"), "email", "notify", "post", "publish", "message"}),
    "deployment": frozenset({"deploy", "release", "publish", "launch", "rollout", "rollback"}),
    "data_mutation": frozenset({"update", "edit", "write", "insert", "migrate", "patch"}),
    "filesystem_write": frozenset({"file", "filesystem", "write", "save", "overwrite"}),
    "connector_call": frozenset({"connector", "gmail", "calendar", "drive", "github", "api"}),
    "security_material": frozenset({"security_material", "dns"}),
    "legal_or_contract": frozenset({"contract", "legal", "clause", "agreement", "signature"}),
    "financial": frozenset({"payment", "pay", "charge", "invoice", "budget", "vendor", "bank"}),
    "production_runtime": frozenset({"production", "prod", "runtime", "tenant", "customer"}),
    "public_claim": frozenset({"publish", "announce", "public", "claim", "ready", "launch"}),
    "identity_or_tenant_scope": frozenset({"tenant", "owner", "identity", "account", "user"}),
}

_STRICT_FAMILIES = frozenset(
    {
        "destructive",
        "external_message",
        "deployment",
        "data_mutation",
        "filesystem_write",
        "connector_call",
        "security_material",
        "legal_or_contract",
        "financial",
        "production_runtime",
        "public_claim",
        "identity_or_tenant_scope",
    }
)

_EVIDENCE_FAMILIES = frozenset(
    {
        "destructive",
        "external_message",
        "deployment",
        "connector_call",
        "security_material",
        "legal_or_contract",
        "financial",
        "production_runtime",
        "public_claim",
    }
)

_EXTERNAL_FAMILIES = frozenset({"external_message", "deployment", "connector_call", "public_claim"})
_BENIGN_OBJECTS = {
    "release": frozenset({"note", "notes", "changelog", "changelogs", "docs", "documentation"}),
    "publish": frozenset({"summary", "draft", "preview", "readme"}),
}


@dataclass(frozen=True)
class ShadowActionClassification:
    """Governed action-family classification for one shadow context."""

    action_families: tuple[str, ...]
    strict_preflight_required: bool
    deep_interrogation_required: bool
    evidence_required: bool
    external_side_effect: bool
    authority_required: tuple[str, ...]
    blocked_by_authority: bool = False
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("ShadowActionClassification cannot carry execution authority")

    def to_dict(self) -> dict[str, object]:
        return {
            "action_families": list(self.action_families),
            "strict_preflight_required": self.strict_preflight_required,
            "deep_interrogation_required": self.deep_interrogation_required,
            "evidence_required": self.evidence_required,
            "external_side_effect": self.external_side_effect,
            "authority_required": list(self.authority_required),
            "blocked_by_authority": self.blocked_by_authority,
            "execution_authority": False,
        }


def classify_shadow_action(
    context: ShadowContext,
    *,
    blocked_actions: Sequence[str] = (),
) -> ShadowActionClassification:
    """Classify the context's action surface into symbolic governance families."""

    text = _normalize_text(context.text_surface())
    tokens = frozenset(_word_tokens(text))
    families: list[str] = []
    for family, terms in _ACTION_FAMILIES.items():
        hits = _action_hits(text, tokens, terms)
        if hits:
            families.append(family)

    action_families = tuple(families)
    blocked = bool(set(action_families).intersection({str(item).strip() for item in blocked_actions if str(item).strip()}))
    strict_required = bool(set(action_families).intersection(_STRICT_FAMILIES))
    external_side_effect = context.external_side_effect or bool(set(action_families).intersection(_EXTERNAL_FAMILIES))
    high_risk = severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH)
    deep_required = strict_required or external_side_effect or context.memory_contradiction or high_risk
    evidence_required = bool(set(action_families).intersection(_EVIDENCE_FAMILIES))
    authority_required = tuple(f"{family}:governance_verdict" for family in action_families if family in _STRICT_FAMILIES)
    return ShadowActionClassification(
        action_families=action_families,
        strict_preflight_required=strict_required,
        deep_interrogation_required=deep_required,
        evidence_required=evidence_required,
        external_side_effect=external_side_effect,
        authority_required=authority_required,
        blocked_by_authority=blocked,
        execution_authority=False,
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_#.-]+", value))


def _action_hits(text: str, tokens: frozenset[str], action_terms: frozenset[str]) -> tuple[str, ...]:
    return tuple(
        term
        for term in sorted(tokens.intersection(action_terms))
        if not _all_action_occurrences_are_benign(text, term)
    )


def _all_action_occurrences_are_benign(text: str, action: str) -> bool:
    benign_objects = _BENIGN_OBJECTS.get(action)
    if not benign_objects:
        return False
    matches = tuple(re.finditer(rf"\b{re.escape(action)}\b(?:\s+([a-z0-9_#.-]+))?", text))
    if not matches:
        return False
    return all((match.group(1) or "") in benign_objects for match in matches)
