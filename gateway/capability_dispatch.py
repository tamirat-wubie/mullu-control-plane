"""Gateway Capability Dispatcher - domain-neutral governed execution.

Purpose: Resolve typed capability intents to registered handlers while keeping
    dispatch authority tied to exact capability identifiers.
Governance scope: gateway capability admission, handler dispatch, and
    compatibility with legacy skill payloads.
Dependencies: financial, creative, and enterprise skill implementations.
Invariants:
  - Capability registry admission uses the exact capability_id.
  - Unknown capabilities fall through to conversational execution.
  - Handlers return explicit governed results with evidence fields where needed.
  - Legacy SkillIntent payloads remain loadable during migration.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Protocol


@dataclass(frozen=True, slots=True)
class CapabilityIntent:
    """Typed capability intent emitted by the intent resolver."""

    domain: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def capability_id(self) -> str:
        return f"{self.domain}.{self.action}"

    @property
    def skill(self) -> str:
        """Compatibility alias for legacy command payloads."""
        return self.domain


SkillIntent = CapabilityIntent


@dataclass(frozen=True, slots=True)
class CapabilityExecutionContext:
    """Tenant-bound execution context supplied to capability handlers."""

    tenant_id: str
    identity_id: str
    command_id: str = ""
    conversation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityHandler(Protocol):
    """Executable handler bound to one capability id."""

    capability_id: str

    def execute(
        self,
        context: CapabilityExecutionContext,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a capability with tenant-bound params."""
        ...


class FunctionCapabilityHandler:
    """Function-backed capability handler."""

    def __init__(
        self,
        capability_id: str,
        fn: Callable[[CapabilityExecutionContext, dict[str, Any]], dict[str, Any]],
    ) -> None:
        if not capability_id or "." not in capability_id:
            raise ValueError("capability_id must be domain.action")
        self.capability_id = capability_id
        self._fn = fn

    def execute(
        self,
        context: CapabilityExecutionContext,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        return self._fn(context, params)


class CapabilityDispatcher:
    """Dispatch capability intents through a registry of exact handlers."""

    def __init__(
        self,
        *,
        handlers: dict[str, CapabilityHandler] | None = None,
        capability_registry: Any | None = None,
        financial_provider: Any | None = None,
        payment_executor: Any | None = None,
    ) -> None:
        self._handlers: dict[str, CapabilityHandler] = dict(handlers or {})
        self._capability_registry = capability_registry
        if financial_provider is not None or payment_executor is not None:
            register_financial_capabilities(
                self,
                financial_provider=financial_provider,
                payment_executor=payment_executor,
            )

    def register(self, handler: CapabilityHandler) -> None:
        if not handler.capability_id or "." not in handler.capability_id:
            raise ValueError("handler capability_id must be domain.action")
        self._handlers[handler.capability_id] = handler

    def dispatch(
        self,
        intent: CapabilityIntent,
        tenant_id: str,
        identity_id: str,
        *,
        command_id: str = "",
        conversation_id: str = "",
    ) -> dict[str, Any] | None:
        """Dispatch a typed intent or return None for no registered handler."""
        capability_id = intent.capability_id
        if self._capability_registry is not None:
            agents = self._capability_registry.find_agents_with_capability(
                capability_id,
                tenant_id,
            )
            if not agents:
                return {
                    "governed": True,
                    "capability_id": capability_id,
                    "skill": intent.action,
                    "action": intent.action,
                    "response": f"No agent with capability '{capability_id}' is available.",
                    "routed": False,
                }

        handler = self._handlers.get(capability_id)
        if handler is None:
            return None

        context = CapabilityExecutionContext(
            tenant_id=tenant_id,
            identity_id=identity_id,
            command_id=command_id,
            conversation_id=conversation_id,
        )
        result = handler.execute(context, dict(intent.params))
        return {
            "governed": True,
            "capability_id": capability_id,
            "skill": intent.action,
            "action": intent.action,
            **result,
        }


SkillDispatcher = CapabilityDispatcher


def register_financial_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    financial_provider: Any | None = None,
    payment_executor: Any | None = None,
) -> None:
    """Register financial handlers as one domain in the capability fabric."""
    if financial_provider is not None:
        dispatcher.register(FunctionCapabilityHandler(
            "financial.balance_check",
            lambda context, params: _balance_check(financial_provider, context),
        ))
        dispatcher.register(FunctionCapabilityHandler(
            "financial.transaction_history",
            lambda context, params: _transaction_history(financial_provider, context),
        ))
        dispatcher.register(FunctionCapabilityHandler(
            "financial.spending_insights",
            lambda context, params: _spending_insights(financial_provider, context),
        ))
    if payment_executor is not None:
        dispatcher.register(FunctionCapabilityHandler(
            "financial.send_payment",
            lambda context, params: _send_payment(payment_executor, context, params),
        ))
        dispatcher.register(FunctionCapabilityHandler(
            "financial.refund",
            lambda context, params: _refund(payment_executor, context, params),
        ))


def register_creative_capabilities(dispatcher: CapabilityDispatcher) -> None:
    """Register deterministic creative handlers."""
    dispatcher.register(FunctionCapabilityHandler("creative.document_generate", _document_generate))
    dispatcher.register(FunctionCapabilityHandler("creative.data_analyze", _data_analyze))
    dispatcher.register(FunctionCapabilityHandler("creative.translate", _translate))


def register_enterprise_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    knowledge_base: Any | None = None,
    notification_engine: Any | None = None,
    task_scheduler: Any | None = None,
) -> None:
    """Register tenant-scoped enterprise handlers."""
    dispatcher.register(FunctionCapabilityHandler(
        "enterprise.knowledge_search",
        lambda context, params: _knowledge_search(knowledge_base, context, params),
    ))
    dispatcher.register(FunctionCapabilityHandler(
        "enterprise.notification_send",
        lambda context, params: _notification_send(notification_engine, context, params),
    ))
    dispatcher.register(FunctionCapabilityHandler(
        "enterprise.task_schedule",
        lambda context, params: _task_schedule(task_scheduler, context, params),
    ))


def _balance_check(financial_provider: Any, context: CapabilityExecutionContext) -> dict[str, Any]:
    from skills.financial.skills.balance_check import check_balance

    result = check_balance(financial_provider, context.tenant_id)
    if not result.success:
        return {"response": f"Could not check balance: {result.error}", "receipt_status": "failed"}
    accounts = "\n".join(
        f"  {account['name']} ({account['type']}): {account['currency']} {account['balance']}"
        for account in result.accounts
    )
    return {"response": f"Your accounts:\n{accounts}", "receipt_status": "read_only"}


def _transaction_history(financial_provider: Any, context: CapabilityExecutionContext) -> dict[str, Any]:
    from skills.financial.skills.transaction_history import get_transaction_history

    result = get_transaction_history(financial_provider, context.tenant_id, "default")
    if not result.success:
        return {"response": f"Could not fetch history: {result.error}", "receipt_status": "failed"}
    transactions = "\n".join(
        f"  {tx['date']} | {tx['currency']} {tx['amount']} | {tx['description']}"
        for tx in result.transactions[:10]
    )
    return {"response": f"Recent transactions:\n{transactions}", "receipt_status": "read_only"}


def _spending_insights(financial_provider: Any, context: CapabilityExecutionContext) -> dict[str, Any]:
    from skills.financial.skills.spending_insights import analyze_spending

    result = analyze_spending(financial_provider, context.tenant_id, "default")
    if not result.success:
        return {"response": "Could not analyze spending.", "receipt_status": "failed"}
    categories = "\n".join(
        f"  {category.category}: {category.total} ({category.percentage:.1f}%)"
        for category in result.categories[:5]
    )
    return {
        "response": (
            f"Spending analysis ({result.transaction_count} transactions, "
            f"total: {result.total_spent}):\n{categories}"
        ),
        "receipt_status": "read_only",
    }


def _send_payment(
    payment_executor: Any,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    amount_text = str(params.get("amount", "0"))
    try:
        amount = Decimal(amount_text)
    except InvalidOperation:
        return {"response": "I couldn't understand the amount. Please specify clearly.", "receipt_status": "invalid"}
    if amount <= 0:
        return {"response": "Amount must be positive.", "receipt_status": "invalid"}

    result = payment_executor.initiate_payment(
        tenant_id=context.tenant_id,
        amount=amount,
        currency=str(params.get("currency", "USD")),
        destination=str(params.get("destination", "pending")),
        actor_id=context.identity_id,
    )
    if result.requires_approval:
        approve_and_execute = getattr(payment_executor, "approve_and_execute", None)
        if callable(approve_and_execute):
            result = approve_and_execute(result.tx_id, approver_id=context.identity_id)
        else:
            receipt = _pending_payment_receipt(
                result,
                tenant_id=context.tenant_id,
                amount=amount,
                currency=str(params.get("currency", "USD")),
            )
            return {
                "response": f"Payment of ${amount} requires approval. Request ID: {result.tx_id}",
                "approval_required": True,
                **receipt,
            }
    if getattr(result, "requires_approval", False):
        receipt = _pending_payment_receipt(
            result,
            tenant_id=context.tenant_id,
            amount=amount,
            currency=str(params.get("currency", "USD")),
        )
        return {
            "response": f"Payment of ${amount} requires approval. Request ID: {result.tx_id}",
            "approval_required": True,
            **receipt,
        }
    if result.success:
        receipt = _settled_payment_receipt(
            result,
            tenant_id=context.tenant_id,
            amount=amount,
            currency=str(params.get("currency", "USD")),
        )
        return {"response": f"Payment processed: {result.tx_id}", **receipt}
    return {"response": f"Payment failed: {result.error}", "receipt_status": "failed"}


def _refund(
    payment_executor: Any,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    transaction_id = str(params.get("transaction_id", "")).strip()
    if not transaction_id:
        return {
            "response": "To process a refund, please provide the transaction ID.",
            "transaction_id": transaction_id,
            "receipt_status": "missing_transaction_id",
        }
    refund = getattr(payment_executor, "refund", None)
    if not callable(refund):
        return {
            "response": "Refund processing is not available right now.",
            "transaction_id": transaction_id,
            "receipt_status": "executor_unavailable",
        }
    result = refund(transaction_id, actor_id=context.identity_id)
    if result.success:
        receipt = _refund_receipt(result, tenant_id=context.tenant_id, transaction_id=transaction_id)
        return {"response": f"Refund processed: {receipt['refund_id']}", **receipt}
    return {
        "response": f"Refund failed: {result.error}",
        "transaction_id": transaction_id,
        "receipt_status": "failed",
    }


def _document_generate(context: CapabilityExecutionContext, params: dict[str, Any]) -> dict[str, Any]:
    from skills.creative.document_gen import DocumentGenerator, DocumentType

    brief = str(params.get("brief") or params.get("body") or "").strip()
    if not brief:
        return {"response": "Document generation requires a brief.", "receipt_status": "missing_brief"}
    title = str(params.get("title") or "Generated document")
    doc_type = str(params.get("format") or params.get("doc_type") or DocumentType.REPORT)
    generator = DocumentGenerator()
    document = generator.generate_from_llm(
        doc_type,
        brief,
        brief,
        tenant_id=context.tenant_id,
        identity_id=context.identity_id,
        title=title,
    )
    return {
        "response": f"Document generated: {document.document_id}",
        "artifact": {
            "document_id": document.document_id,
            "title": document.title,
            "doc_type": document.doc_type,
            "body": document.body,
            "content_hash": document.content_hash,
        },
        "document_id": document.document_id,
        "content_hash": document.content_hash,
        "receipt_status": "generated",
    }


def _data_analyze(context: CapabilityExecutionContext, params: dict[str, Any]) -> dict[str, Any]:
    from skills.creative.data_analysis import analyze_csv, analyze_key_value

    if "csv" in params:
        result = analyze_csv(str(params["csv"]))
    elif "data" in params and isinstance(params["data"], dict):
        result = analyze_key_value(dict(params["data"]))
    else:
        return {"response": "Data analysis requires csv text or key-value data.", "receipt_status": "missing_input"}
    if not result.success:
        return {"response": f"Could not analyze data: {result.error}", "receipt_status": "failed"}
    return {
        "response": result.summary,
        "row_count": result.row_count,
        "column_count": result.column_count,
        "insights": list(result.insights),
        "receipt_status": "analyzed",
    }


def _translate(context: CapabilityExecutionContext, params: dict[str, Any]) -> dict[str, Any]:
    from skills.creative.translation import build_translation_prompt

    text = str(params.get("text") or "").strip()
    if not text:
        return {"response": "Translation requires text.", "receipt_status": "missing_text"}
    source_lang = str(params.get("source_lang") or "auto")
    target_lang = str(params.get("target_lang") or params.get("language") or "en")
    prompt = build_translation_prompt(text, source_lang, target_lang)
    return {
        "response": "Translation prompt prepared.",
        "translation_prompt": prompt,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "receipt_status": "prepared",
    }


def _knowledge_search(
    knowledge_base: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    query = str(params.get("query") or params.get("text") or "").strip()
    if not query:
        return {"response": "Knowledge search requires a query.", "receipt_status": "missing_query"}
    if knowledge_base is None:
        return {"response": "Knowledge search is not available right now.", "receipt_status": "executor_unavailable"}
    result = knowledge_base.query(context.tenant_id, query, top_k=int(params.get("top_k", 5)))
    return {
        "response": f"Found {len(result.chunks)} knowledge result(s).",
        "chunks": [chunk.content for chunk in result.chunks],
        "scores": list(result.scores),
        "total_chunks_searched": result.total_chunks_searched,
        "receipt_status": "searched",
    }


def _notification_send(
    notification_engine: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    title = str(params.get("title") or "Mullu notification")
    body = str(params.get("body") or params.get("message") or "").strip()
    if not body:
        return {"response": "Notification requires a message body.", "receipt_status": "missing_body"}
    if notification_engine is None:
        return {
            "response": "Notification prepared but no delivery engine is available.",
            "notification_title": title,
            "notification_body": body,
            "receipt_status": "prepared",
        }
    from skills.enterprise.notifications import NotificationPriority, NotificationType

    notifications = notification_engine.notify(
        tenant_id=context.tenant_id,
        notification_type=NotificationType.CUSTOM,
        priority=NotificationPriority.MEDIUM,
        title=title,
        body=body,
        metadata={"actor_id": context.identity_id},
    )
    return {
        "response": f"Notification sent to {len(notifications)} recipient(s).",
        "notification_ids": [item.notification_id for item in notifications],
        "receipt_status": "sent",
    }


def _task_schedule(
    task_scheduler: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    title = str(params.get("title") or params.get("name") or "").strip()
    if not title:
        return {"response": "Task scheduling requires a title.", "receipt_status": "missing_title"}
    if task_scheduler is None:
        from skills.enterprise.task_scheduler import TaskScheduler
        task_scheduler = TaskScheduler()
    from skills.enterprise.task_scheduler import ScheduleInterval

    task = task_scheduler.register_task(
        tenant_id=context.tenant_id,
        name=title,
        description=str(params.get("description") or params.get("due_at") or ""),
        interval=ScheduleInterval.CUSTOM if params.get("due_at") else ScheduleInterval.DAILY,
        action=str(params.get("action") or "follow_up"),
        action_params=dict(params),
    )
    return {
        "response": f"Task scheduled: {task.task_id}",
        "task_id": task.task_id,
        "receipt_status": "scheduled",
    }


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


def build_capability_dispatcher_from_platform(platform: Any | None) -> CapabilityDispatcher:
    """Build a dispatcher from platform-backed providers and default handlers."""
    if platform is None:
        dispatcher = CapabilityDispatcher()
        register_creative_capabilities(dispatcher)
        register_enterprise_capabilities(dispatcher)
        return dispatcher

    factory = _first_platform_attribute(platform, ("build_capability_dispatcher", "capability_dispatcher"))
    if callable(factory):
        dispatcher = factory()
        if isinstance(dispatcher, CapabilityDispatcher):
            return dispatcher

    legacy_factory = _first_platform_attribute(platform, ("build_skill_dispatcher", "skill_dispatcher"))
    if callable(legacy_factory):
        dispatcher = legacy_factory()
        if isinstance(dispatcher, CapabilityDispatcher):
            return dispatcher

    capability_registry = _first_platform_attribute(
        platform,
        ("capability_registry", "_capability_registry", "agent_capability_registry", "_agent_capability_registry"),
    ) or _nested_platform_attribute(
        platform,
        ("capability_runtime", "_capability_runtime", "capability_bootstrap", "_capability_bootstrap"),
        ("capability_registry", "_capability_registry", "agent_capability_registry", "_agent_capability_registry"),
    )
    dispatcher = CapabilityDispatcher(capability_registry=capability_registry)
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
    register_financial_capabilities(
        dispatcher,
        financial_provider=financial_provider,
        payment_executor=payment_executor,
    )
    register_creative_capabilities(dispatcher)
    register_enterprise_capabilities(
        dispatcher,
        knowledge_base=_first_platform_attribute(platform, ("knowledge_base", "_knowledge_base")),
        notification_engine=_first_platform_attribute(platform, ("notification_engine", "_notification_engine")),
        task_scheduler=_first_platform_attribute(platform, ("task_scheduler", "_task_scheduler")),
    )
    return dispatcher


build_skill_dispatcher_from_platform = build_capability_dispatcher_from_platform


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pending_payment_receipt(result: Any, *, tenant_id: str, amount: Decimal, currency: str) -> dict[str, Any]:
    tx_id = str(getattr(result, "tx_id", ""))
    metadata = getattr(result, "metadata", {}) if isinstance(getattr(result, "metadata", {}), dict) else {}
    return {
        "tx_id": tx_id,
        "transaction_id": tx_id,
        "amount": str(getattr(result, "amount", "") or amount),
        "currency": str(getattr(result, "currency", "") or currency),
        "tenant_hash": _hash_text(tenant_id),
        "payment_state": str(getattr(result, "state", "") or "pending_approval"),
        "provider_tx_id": str(getattr(result, "provider_tx_id", "")),
        "receipt_status": "pending_approval",
        "receipt_metadata": dict(metadata),
    }


def _settled_payment_receipt(result: Any, *, tenant_id: str, amount: Decimal, currency: str) -> dict[str, Any]:
    tx_id = str(getattr(result, "tx_id", ""))
    result_amount = str(getattr(result, "amount", "") or amount)
    result_currency = str(getattr(result, "currency", "") or currency)
    provider_tx_id = str(getattr(result, "provider_tx_id", ""))
    metadata = getattr(result, "metadata", {}) if isinstance(getattr(result, "metadata", {}), dict) else {}
    recipient_ref = str(metadata.get("recipient_ref") or metadata.get("credit_account") or "pending")
    ledger_hash = str(metadata.get("ledger_hash") or _hash_text(
        f"{tenant_id}:{tx_id}:{result_amount}:{result_currency}:{provider_tx_id}:{recipient_ref}"
    ))
    return {
        "tx_id": tx_id,
        "transaction_id": tx_id,
        "amount": result_amount,
        "currency": result_currency,
        "recipient_hash": str(metadata.get("recipient_hash") or _hash_text(recipient_ref)),
        "ledger_hash": ledger_hash,
        "provider_tx_id": provider_tx_id,
        "payment_state": str(getattr(result, "state", "") or "settled"),
        "receipt_status": "settled",
    }


def _refund_receipt(result: Any, *, tenant_id: str, transaction_id: str) -> dict[str, Any]:
    refund_id = str(getattr(result, "provider_tx_id", "") or getattr(result, "tx_id", ""))
    result_amount = str(getattr(result, "amount", ""))
    result_currency = str(getattr(result, "currency", ""))
    metadata = getattr(result, "metadata", {}) if isinstance(getattr(result, "metadata", {}), dict) else {}
    ledger_hash = str(metadata.get("ledger_hash") or _hash_text(
        f"{tenant_id}:{transaction_id}:{refund_id}:{result_amount}:{result_currency}:refund"
    ))
    return {
        "refund_id": refund_id,
        "transaction_id": transaction_id,
        "amount": result_amount,
        "currency": result_currency,
        "ledger_hash": ledger_hash,
        "payment_state": str(getattr(result, "state", "") or "refunded"),
        "receipt_status": "refunded",
    }
