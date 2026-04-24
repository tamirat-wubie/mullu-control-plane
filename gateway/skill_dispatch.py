"""Gateway Skill Dispatcher — Routes financial and other skill intents.

Purpose: Detects skill intents from user messages and dispatches to the
    appropriate governed skill executor instead of raw LLM completion.
    Falls back to LLM for conversational messages.

Invariants:
  - Financial intents always route through GovernedPaymentExecutor.
  - Read-only financial queries route through provider skills.
  - Unknown intents fall through to LLM.
  - Every dispatch is audited.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any


class SkillIntent:
    """Detected skill intent from user message."""

    def __init__(self, skill: str, action: str, params: dict[str, Any]) -> None:
        self.skill = skill
        self.action = action
        self.params = params


# Financial intent patterns (re.IGNORECASE used at compile level for Python 3.13 compat)
_BALANCE_PATTERNS = re.compile(
    r"\b(?:balance|how much|account|bank)\b.*\b(?:have|left|remaining|balance|account)\b|"
    r"\b(?:what'?s|show|check)\b.*\b(?:balance|account)\b",
    re.IGNORECASE,
)

_HISTORY_PATTERNS = re.compile(
    r"\b(?:transaction|spending|history|recent|last)\b.*\b(?:transaction|purchase|payment|days?|month)\b|"
    r"\b(?:show|list|get)\b.*\b(?:transaction|spending|history)\b",
    re.IGNORECASE,
)

_INSIGHTS_PATTERNS = re.compile(
    r"\b(?:why|increase|decrease|spending|insight|analyze|analysis|breakdown|category)\b.*"
    r"\b(?:spending|cost|expense|increase|category|breakdown)\b",
    re.IGNORECASE,
)

_PAYMENT_PATTERNS = re.compile(
    r"\b(?:pay|send|transfer|invoice|payment)\b.*\b(?:\$[\d,.]+|\d+\s*(?:dollar|usd|eur|gbp|etb))\b|"
    r"\b(?:create|make|send)\b.*\b(?:payment|invoice|transfer)\b",
    re.IGNORECASE,
)

_REFUND_PATTERNS = re.compile(
    r"\b(?:refund|reverse|cancel)\b.*\b(?:transaction|payment|charge)\b",
    re.IGNORECASE,
)


def detect_intent(message: str) -> SkillIntent | None:
    """Detect skill intent from a user message.

    Returns None for conversational messages (routed to LLM).
    """
    if _PAYMENT_PATTERNS.search(message):
        amount = _extract_amount(message)
        # Only dispatch payment if a valid positive amount was found
        try:
            from decimal import Decimal, InvalidOperation
            parsed = Decimal(amount)
            if parsed > 0:
                return SkillIntent("financial", "send_payment", {"amount": amount})
        except (InvalidOperation, ValueError):
            pass
        # No valid amount — fall through to LLM for clarification

    if _REFUND_PATTERNS.search(message):
        return SkillIntent("financial", "refund", {})

    if _BALANCE_PATTERNS.search(message):
        return SkillIntent("financial", "balance_check", {})

    if _INSIGHTS_PATTERNS.search(message):
        return SkillIntent("financial", "spending_insights", {})

    if _HISTORY_PATTERNS.search(message):
        return SkillIntent("financial", "transaction_history", {})

    return None  # Conversational — route to LLM


def _extract_amount(message: str) -> str:
    """Extract dollar amount from message text."""
    match = re.search(r"\$?([\d,]+\.?\d*)", message)
    if match:
        return match.group(1).replace(",", "")
    return "0"


class SkillDispatcher:
    """Dispatches skill intents to governed executors.

    Integrates with gateway router to intercept skill-able messages
    before they reach the LLM.
    """

    def __init__(
        self,
        *,
        financial_provider: Any | None = None,
        payment_executor: Any | None = None,
        capability_registry: Any | None = None,
    ) -> None:
        self._financial_provider = financial_provider
        self._payment_executor = payment_executor
        self._capability_registry = capability_registry

    def dispatch(self, intent: SkillIntent, tenant_id: str, identity_id: str) -> dict[str, Any] | None:
        """Dispatch a skill intent. Returns response dict or None if no handler.

        If a capability_registry is configured, checks that an agent with
        the required capability exists for the tenant before dispatching.
        """
        # Capability gate: check an agent can handle this skill
        if self._capability_registry is not None:
            agents = self._capability_registry.find_agents_with_capability(
                intent.skill, tenant_id,
            )
            if not agents:
                return {
                    "skill": intent.skill,
                    "action": intent.action,
                    "response": f"No agent with '{intent.skill}' capability is available.",
                    "routed": False,
                }

        if intent.skill == "financial":
            return self._dispatch_financial(intent, tenant_id, identity_id)
        return None

    def _dispatch_financial(self, intent: SkillIntent, tenant_id: str, identity_id: str) -> dict[str, Any] | None:
        if intent.action == "balance_check" and self._financial_provider:
            from skills.financial.skills.balance_check import check_balance
            result = check_balance(self._financial_provider, tenant_id)
            if result.success:
                accounts = "\n".join(
                    f"  {a['name']} ({a['type']}): {a['currency']} {a['balance']}"
                    for a in result.accounts
                )
                return {"response": f"Your accounts:\n{accounts}", "governed": True, "skill": "balance_check"}
            return {"response": f"Could not check balance: {result.error}", "governed": True}

        if intent.action == "transaction_history" and self._financial_provider:
            from skills.financial.skills.transaction_history import get_transaction_history
            result = get_transaction_history(self._financial_provider, tenant_id, "default")
            if result.success:
                txs = "\n".join(
                    f"  {t['date']} | {t['currency']} {t['amount']} | {t['description']}"
                    for t in result.transactions[:10]
                )
                return {"response": f"Recent transactions:\n{txs}", "governed": True, "skill": "transaction_history"}
            return {"response": f"Could not fetch history: {result.error}", "governed": True}

        if intent.action == "spending_insights" and self._financial_provider:
            from skills.financial.skills.spending_insights import analyze_spending
            result = analyze_spending(self._financial_provider, tenant_id, "default")
            if result.success:
                cats = "\n".join(
                    f"  {c.category}: {c.total} ({c.percentage:.1f}%)"
                    for c in result.categories[:5]
                )
                return {
                    "response": f"Spending analysis ({result.transaction_count} transactions, total: {result.total_spent}):\n{cats}",
                    "governed": True, "skill": "spending_insights",
                }
            return {"response": "Could not analyze spending.", "governed": True}

        if intent.action == "send_payment" and self._payment_executor:
            amount_str = intent.params.get("amount", "0")
            try:
                amount = Decimal(amount_str)
            except InvalidOperation:
                return {"response": "I couldn't understand the amount. Please specify clearly.", "governed": True}
            if amount <= 0:
                return {"response": "Amount must be positive.", "governed": True}

            result = self._payment_executor.initiate_payment(
                tenant_id=tenant_id, amount=amount, currency="USD",
                destination="pending", actor_id=identity_id,
            )
            if result.requires_approval:
                return {
                    "response": f"Payment of ${amount} requires approval. Request ID: {result.tx_id}",
                    "governed": True, "skill": "send_payment", "approval_required": True,
                    "tx_id": result.tx_id,
                }
            if result.success:
                return {"response": f"Payment processed: {result.tx_id}", "governed": True, "skill": "send_payment"}
            return {"response": f"Payment failed: {result.error}", "governed": True}

        if intent.action == "refund":
            return {"response": "To process a refund, please provide the transaction ID.", "governed": True, "skill": "refund"}

        return None


def _first_platform_attribute(platform: Any, names: tuple[str, ...]) -> Any | None:
    """Return the first non-empty runtime attribute exposed by a platform."""
    for name in names:
        if hasattr(platform, name):
            value = getattr(platform, name)
            if value is not None:
                return value
    return None


def _nested_platform_attribute(platform: Any, container_names: tuple[str, ...], names: tuple[str, ...]) -> Any | None:
    """Return the first non-empty attribute from a known platform sub-runtime."""
    for container_name in container_names:
        container = _first_platform_attribute(platform, (container_name,))
        if container is None:
            continue
        value = _first_platform_attribute(container, names)
        if value is not None:
            return value
    return None


def build_skill_dispatcher_from_platform(platform: Any | None) -> SkillDispatcher:
    """Build a dispatcher from explicit platform-backed capability providers.

    The gateway uses this as its default runtime binding so detected skill
    intent is connected to governed providers when the platform exposes them.
    """
    if platform is None:
        return SkillDispatcher()

    factory = _first_platform_attribute(platform, ("build_skill_dispatcher", "skill_dispatcher"))
    if callable(factory):
        dispatcher = factory()
        if isinstance(dispatcher, SkillDispatcher):
            return dispatcher

    financial_provider = _first_platform_attribute(
        platform,
        (
            "financial_provider",
            "_financial_provider",
            "read_only_financial_provider",
            "_read_only_financial_provider",
        ),
    ) or _nested_platform_attribute(
        platform,
        ("capability_runtime", "_capability_runtime", "financial_runtime", "_financial_runtime"),
        (
            "financial_provider",
            "_financial_provider",
            "read_only_financial_provider",
            "_read_only_financial_provider",
        ),
    )
    payment_executor = _first_platform_attribute(
        platform,
        ("payment_executor", "_payment_executor", "governed_payment_executor", "_governed_payment_executor"),
    ) or _nested_platform_attribute(
        platform,
        ("capability_runtime", "_capability_runtime", "financial_runtime", "_financial_runtime"),
        ("payment_executor", "_payment_executor", "governed_payment_executor", "_governed_payment_executor"),
    )
    capability_registry = _first_platform_attribute(
        platform,
        ("capability_registry", "_capability_registry", "agent_capability_registry", "_agent_capability_registry"),
    ) or _nested_platform_attribute(
        platform,
        ("capability_runtime", "_capability_runtime", "capability_bootstrap", "_capability_bootstrap"),
        ("capability_registry", "_capability_registry", "agent_capability_registry", "_agent_capability_registry"),
    )
    return SkillDispatcher(
        financial_provider=financial_provider,
        payment_executor=payment_executor,
        capability_registry=capability_registry,
    )
