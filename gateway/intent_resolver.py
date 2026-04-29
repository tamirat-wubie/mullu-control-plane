"""Gateway Capability Intent Resolver - typed goal admission front door.

Purpose: Convert user text into typed capability intents without binding the
    dispatcher to domain-specific branches.
Governance scope: explicit command parsing and deterministic capability
    pattern matching before registry admission.
Dependencies: gateway capability dispatch contracts.
Invariants:
  - Explicit commands must name a domain.action capability.
  - JSON params must be objects.
  - Pattern matches propose intents only; dispatch still requires admission.
  - Conversational messages return None.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from gateway.capability_dispatch import CapabilityIntent


@dataclass(frozen=True, slots=True)
class CapabilityPattern:
    """Deterministic natural-language pattern for one capability."""

    capability_id: str
    patterns: tuple[str, ...]
    required_params: tuple[str, ...] = ()
    default_params: dict[str, Any] = field(default_factory=dict)


class CapabilityIntentResolver:
    """Resolve user text into typed capability intent proposals."""

    def __init__(self, patterns: tuple[CapabilityPattern, ...] = ()) -> None:
        self._patterns = patterns or DEFAULT_CAPABILITY_PATTERNS

    def resolve(self, message: str) -> CapabilityIntent | None:
        explicit = self._parse_explicit(message)
        if explicit is not None:
            return explicit

        normalized = message.strip().lower()
        for item in self._patterns:
            if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in item.patterns):
                domain, action = item.capability_id.split(".", 1)
                params = dict(item.default_params)
                params.update(self._extract_params(item.capability_id, message))
                if item.required_params and any(not params.get(name) for name in item.required_params):
                    return None
                return CapabilityIntent(domain=domain, action=action, params=params)
        return None

    def _parse_explicit(self, message: str) -> CapabilityIntent | None:
        normalized = message.strip()
        if not normalized.startswith("/run "):
            return None
        rest = normalized[len("/run "):].strip()
        capability_id, _, raw_json = rest.partition(" ")
        if "." not in capability_id:
            return None
        params: dict[str, Any] = {}
        if raw_json.strip():
            parsed = json.loads(raw_json)
            if not isinstance(parsed, dict):
                raise ValueError("explicit capability params must be a JSON object")
            params = parsed
        domain, action = capability_id.split(".", 1)
        return CapabilityIntent(domain=domain, action=action, params=params)

    def _extract_params(self, capability_id: str, message: str) -> dict[str, Any]:
        if capability_id == "financial.send_payment":
            amount = _extract_amount(message)
            try:
                parsed = Decimal(amount)
            except (InvalidOperation, ValueError):
                return {}
            if parsed <= 0:
                return {}
            return {"amount": amount}
        if capability_id == "financial.refund":
            return {"transaction_id": _extract_transaction_id(message)}
        if capability_id == "creative.document_generate":
            return {"brief": message, "title": "Generated document", "format": "report"}
        if capability_id == "creative.data_analyze":
            return {"csv": message} if "," in message and "\n" in message else {}
        if capability_id == "creative.translate":
            return {"text": message, "target_lang": "en"}
        if capability_id == "enterprise.knowledge_search":
            return {"query": message}
        if capability_id == "enterprise.notification_send":
            return {"body": message, "title": "Mullu notification"}
        if capability_id == "enterprise.task_schedule":
            return {"title": message}
        return {}


DEFAULT_CAPABILITY_PATTERNS = (
    CapabilityPattern(
        capability_id="financial.send_payment",
        patterns=(
            r"\b(?:pay|send|transfer|invoice|payment)\b.*\b(?:\$[\d,.]+|\d+\s*(?:dollar|usd|eur|gbp|etb))\b",
            r"\b(?:create|make|send)\b.*\b(?:payment|invoice|transfer)\b",
        ),
        required_params=("amount",),
    ),
    CapabilityPattern(
        capability_id="financial.refund",
        patterns=(r"\b(?:refund|reverse|cancel)\b.*\b(?:transaction|payment|charge)\b",),
    ),
    CapabilityPattern(
        capability_id="financial.balance_check",
        patterns=(
            r"\b(?:balance|how much|account|bank)\b.*\b(?:have|left|remaining|balance|account)\b",
            r"\b(?:what'?s|show|check)\b.*\b(?:balance|account)\b",
        ),
    ),
    CapabilityPattern(
        capability_id="financial.spending_insights",
        patterns=(r"\b(?:why|increase|decrease|spending|insight|analyze|analysis|breakdown|category)\b.*"
                  r"\b(?:spending|cost|expense|increase|category|breakdown)\b",),
    ),
    CapabilityPattern(
        capability_id="financial.transaction_history",
        patterns=(
            r"\b(?:transaction|spending|history|recent|last)\b.*\b(?:transaction|purchase|payment|days?|month)\b",
            r"\b(?:show|list|get)\b.*\b(?:transaction|spending|history)\b",
        ),
    ),
    CapabilityPattern(
        capability_id="creative.document_generate",
        patterns=(r"\b(?:write|draft|generate)\b.*\b(?:document|memo|proposal|report)\b",),
    ),
    CapabilityPattern(
        capability_id="creative.data_analyze",
        patterns=(r"\b(?:analyze|summarize|break down)\b.*\b(?:data|csv|table|spreadsheet)\b",),
    ),
    CapabilityPattern(
        capability_id="creative.translate",
        patterns=(r"\btranslate\b",),
    ),
    CapabilityPattern(
        capability_id="enterprise.knowledge_search",
        patterns=(r"\b(?:search|find|lookup)\b.*\b(?:knowledge|docs|policy|document)\b",),
    ),
    CapabilityPattern(
        capability_id="enterprise.notification_send",
        patterns=(r"\b(?:send|notify|message)\b.*\b(?:team|user|channel)\b",),
    ),
    CapabilityPattern(
        capability_id="enterprise.task_schedule",
        patterns=(r"\b(?:schedule|remind|create task|todo)\b",),
    ),
)


def detect_intent(message: str) -> CapabilityIntent | None:
    """Compatibility function for legacy imports."""
    return CapabilityIntentResolver().resolve(message)


def _extract_amount(message: str) -> str:
    match = re.search(r"\$?([\d,]+\.?\d*)", message)
    if match:
        return match.group(1).replace(",", "")
    return "0"


def _extract_transaction_id(message: str) -> str:
    matches = re.finditer(
        r"\b((?:tx|txn|transaction|ch|pi|pl|re)[-_]?[A-Za-z0-9][A-Za-z0-9_-]*)\b",
        message,
        re.IGNORECASE,
    )
    for match in matches:
        if any(char.isdigit() for char in match.group(1)):
            return match.group(1)
    match = re.search(r"\b([A-Za-z]+[-_][A-Za-z0-9][A-Za-z0-9_-]*\d[A-Za-z0-9_-]*)\b", message)
    if match:
        return match.group(1)
    return ""
