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
        metadata: dict[str, Any] | None = None,
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
            metadata=dict(metadata or {}),
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


def register_computer_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    code_adapter: Any | None = None,
    sandbox_runner: Any | None = None,
) -> None:
    """Register workspace-bound computer handlers."""
    dispatcher.register(FunctionCapabilityHandler(
        "computer.filesystem.observe",
        lambda context, params: _filesystem_observe(code_adapter, context, params),
    ))
    dispatcher.register(FunctionCapabilityHandler(
        "computer.code.patch",
        lambda context, params: _code_patch(code_adapter, context, params),
    ))
    dispatcher.register(FunctionCapabilityHandler(
        "computer.command.run",
        lambda context, params: _command_run(sandbox_runner, context, params),
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


def register_browser_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    browser_worker_client: Any | None = None,
) -> None:
    """Register browser handlers that dispatch only through a signed worker."""
    for capability_id in (
        "browser.open",
        "browser.screenshot",
        "browser.extract_text",
        "browser.click",
        "browser.type",
        "browser.submit",
    ):
        dispatcher.register(FunctionCapabilityHandler(
            capability_id,
            lambda context, params, capability_id=capability_id: _adapter_worker_dispatch(
                plane="browser",
                capability_id=capability_id,
                worker_client=browser_worker_client,
                context=context,
                params=params,
                payload_builder=_browser_payload,
            ),
        ))


def register_document_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    document_worker_client: Any | None = None,
) -> None:
    """Register document/data handlers that dispatch only through a signed worker."""
    for capability_id in (
        "document.extract_text",
        "document.extract_tables",
        "document.summarize",
        "document.generate_docx",
        "document.generate_pdf",
        "spreadsheet.analyze",
        "spreadsheet.generate",
    ):
        dispatcher.register(FunctionCapabilityHandler(
            capability_id,
            lambda context, params, capability_id=capability_id: _adapter_worker_dispatch(
                plane="document",
                capability_id=capability_id,
                worker_client=document_worker_client,
                context=context,
                params=params,
                payload_builder=_document_payload,
            ),
        ))


def register_voice_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    voice_worker_client: Any | None = None,
) -> None:
    """Register voice handlers that create text intent through a signed worker."""
    for capability_id in (
        "voice.speech_to_text",
        "voice.text_to_speech",
        "voice.intent_classification",
        "voice.intent_confirm",
        "voice.meeting_summarize",
        "voice.action_items_extract",
    ):
        dispatcher.register(FunctionCapabilityHandler(
            capability_id,
            lambda context, params, capability_id=capability_id: _adapter_worker_dispatch(
                plane="voice",
                capability_id=capability_id,
                worker_client=voice_worker_client,
                context=context,
                params=params,
                payload_builder=_voice_payload,
            ),
        ))


def register_email_calendar_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    email_calendar_worker_client: Any | None = None,
) -> None:
    """Register email and calendar handlers through a signed communication worker."""
    for capability_id in (
        "email.read",
        "email.search",
        "email.draft",
        "email.send.with_approval",
        "email.classify",
        "email.reply_suggest",
        "calendar.read",
        "calendar.conflict_check",
        "calendar.schedule",
        "calendar.reschedule",
        "calendar.invite",
    ):
        dispatcher.register(FunctionCapabilityHandler(
            capability_id,
            lambda context, params, capability_id=capability_id: _adapter_worker_dispatch(
                plane="email/calendar",
                capability_id=capability_id,
                worker_client=email_calendar_worker_client,
                context=context,
                params=params,
                payload_builder=_email_calendar_payload,
            ),
        ))


def _adapter_worker_dispatch(
    *,
    plane: str,
    capability_id: str,
    worker_client: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
    payload_builder: Callable[[str, CapabilityExecutionContext, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    if worker_client is None or not callable(getattr(worker_client, "execute", None)):
        return {
            "response": f"{plane.capitalize()} worker is not available.",
            "worker_plane": plane,
            "worker_status": "unavailable",
            "receipt_status": "worker_unavailable",
        }
    try:
        payload = payload_builder(capability_id, context, params)
        response = worker_client.execute(payload)
        return _adapter_worker_result(plane=plane, response=response)
    except (RuntimeError, ValueError) as exc:
        return {
            "response": f"{plane.capitalize()} worker dispatch failed.",
            "worker_plane": plane,
            "worker_status": "failed",
            "worker_error": str(exc),
            "receipt_status": "worker_dispatch_failed",
        }


def _adapter_worker_result(*, plane: str, response: Any) -> dict[str, Any]:
    status = str(getattr(response, "status", ""))
    result = getattr(response, "result", {})
    receipt = getattr(response, "receipt", {})
    error = str(getattr(response, "error", ""))
    if isinstance(response, dict):
        status = str(response.get("status", status))
        result = response.get("result", result)
        receipt = response.get("receipt", receipt)
        error = str(response.get("error", error))
    if not isinstance(result, dict):
        result = {}
    if not isinstance(receipt, dict):
        receipt = {}
    return {
        "response": f"{plane.capitalize()} action {status or 'completed'}.",
        "worker_plane": plane,
        "worker_status": status,
        "worker_result": dict(result),
        "worker_receipt": dict(receipt),
        "worker_error": error,
        "verification_status": str(receipt.get("verification_status", "")),
        "evidence_refs": list(receipt.get("evidence_refs", ())),
        "receipt_status": status or "unknown",
    }


def _browser_payload(
    capability_id: str,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    url = str(params.get("url") or params.get("target_url") or "").strip()
    selector = str(params.get("selector") or "").strip()
    text = str(params.get("text") or "").strip()
    if capability_id in {"browser.open", "browser.screenshot", "browser.extract_text"} and not url:
        raise ValueError("browser action requires url")
    if capability_id in {"browser.click", "browser.type", "browser.submit"} and not selector:
        raise ValueError("browser action requires selector")
    if capability_id == "browser.type" and not text:
        raise ValueError("browser type action requires text")
    metadata = _merged_worker_metadata(context, params)
    if url and "url_before" not in metadata:
        metadata["url_before"] = url
    return {
        "request_id": _request_id_for("browser", capability_id, context, params),
        "tenant_id": context.tenant_id,
        "capability_id": capability_id,
        "action": capability_id,
        "url": url,
        "selector": selector,
        "text": text,
        "approval_id": str(params.get("approval_id") or context.metadata.get("approval_id") or ""),
        "metadata": metadata,
    }


def _document_payload(
    capability_id: str,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    rows = params.get("rows", ())
    if rows is None:
        rows = ()
    if not isinstance(rows, list | tuple):
        raise ValueError("document rows must be an array")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("document rows entries must be objects")
    return {
        "request_id": _request_id_for("document", capability_id, context, params),
        "tenant_id": context.tenant_id,
        "capability_id": capability_id,
        "action": capability_id,
        "filename": str(params.get("filename") or ""),
        "content_base64": str(params.get("content_base64") or ""),
        "text": str(params.get("text") or params.get("body") or ""),
        "rows": [dict(row) for row in rows],
        "title": str(params.get("title") or ""),
        "metadata": _merged_worker_metadata(context, params),
    }


def _voice_payload(
    capability_id: str,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    session_id = str(
        params.get("session_id")
        or context.conversation_id
        or f"voice-session-{_hash_text(context.tenant_id + context.identity_id)[:16]}"
    )
    return {
        "request_id": _request_id_for("voice", capability_id, context, params),
        "tenant_id": context.tenant_id,
        "capability_id": capability_id,
        "action": capability_id,
        "session_id": session_id,
        "audio_base64": str(params.get("audio_base64") or ""),
        "transcript_text": str(params.get("transcript_text") or params.get("transcript") or ""),
        "response_text": str(params.get("response_text") or params.get("text") or ""),
        "approval_id": str(params.get("approval_id") or context.metadata.get("approval_id") or ""),
        "metadata": _merged_worker_metadata(context, params),
    }


def _email_calendar_payload(
    capability_id: str,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    recipients = params.get("recipients", ())
    attendees = params.get("attendees", ())
    if recipients is None:
        recipients = ()
    if attendees is None:
        attendees = ()
    if isinstance(recipients, str):
        recipients = (recipients,)
    if isinstance(attendees, str):
        attendees = (attendees,)
    if not isinstance(recipients, list | tuple):
        raise ValueError("email/calendar recipients must be an array")
    if not isinstance(attendees, list | tuple):
        raise ValueError("email/calendar attendees must be an array")
    return {
        "request_id": _request_id_for("email-calendar", capability_id, context, params),
        "tenant_id": context.tenant_id,
        "capability_id": capability_id,
        "action": capability_id,
        "connector_id": str(params.get("connector_id") or _default_connector_id_for(capability_id)),
        "subject": str(params.get("subject") or ""),
        "body": str(params.get("body") or params.get("message") or ""),
        "query": str(params.get("query") or ""),
        "event_id": str(params.get("event_id") or ""),
        "start_time": str(params.get("start_time") or params.get("start") or ""),
        "end_time": str(params.get("end_time") or params.get("end") or ""),
        "recipients": [str(item) for item in recipients],
        "attendees": [str(item) for item in attendees],
        "approval_id": str(params.get("approval_id") or context.metadata.get("approval_id") or ""),
        "metadata": _merged_worker_metadata(context, params),
    }


def _default_connector_id_for(capability_id: str) -> str:
    if capability_id.startswith("calendar."):
        return "google_calendar"
    return "gmail"


def _merged_worker_metadata(
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    metadata = dict(context.metadata)
    param_metadata = params.get("metadata", {})
    if isinstance(param_metadata, dict):
        metadata.update(param_metadata)
    metadata.setdefault("identity_id", context.identity_id)
    if context.command_id:
        metadata.setdefault("command_id", context.command_id)
    if context.conversation_id:
        metadata.setdefault("conversation_id", context.conversation_id)
    return metadata


def _request_id_for(
    plane: str,
    capability_id: str,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> str:
    explicit = str(params.get("request_id") or "").strip()
    if explicit:
        return explicit
    material = ":".join((
        plane,
        capability_id,
        context.tenant_id,
        context.identity_id,
        context.command_id,
        context.conversation_id,
    ))
    return f"{plane}-request-{_hash_text(material)[:16]}"


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


def _filesystem_observe(
    code_adapter: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    if code_adapter is None:
        return {"response": "Workspace observation is not available.", "receipt_status": "executor_unavailable"}
    repo_id = str(params.get("repo_id") or "workspace")
    extensions = tuple(params.get("extensions", ()))
    workspace = code_adapter.list_files(repo_id, extensions=extensions)
    root_hash = _hash_text(str(getattr(workspace, "root_path", "")))
    files = [
        {
            "relative_path": getattr(item, "relative_path", ""),
            "content_hash": getattr(item, "content_hash", ""),
            "size_bytes": getattr(item, "size_bytes", 0),
            "line_count": getattr(item, "line_count", 0),
        }
        for item in getattr(workspace, "files", ())
    ]
    return {
        "response": f"Observed {getattr(workspace, 'total_files', 0)} workspace file(s).",
        "workspace_root_hash": root_hash,
        "file_count": getattr(workspace, "total_files", 0),
        "total_bytes": getattr(workspace, "total_bytes", 0),
        "files": files,
        "receipt_status": "observed",
    }


def _code_patch(
    code_adapter: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    if code_adapter is None:
        return {"response": "Workspace patching is not available.", "receipt_status": "executor_unavailable"}
    target_file = str(params.get("target_file") or "").strip()
    unified_diff = str(params.get("unified_diff") or "").strip()
    if not target_file or not unified_diff:
        return {"response": "Code patch requires target_file and unified_diff.", "receipt_status": "invalid"}
    patch_id = str(params.get("patch_id") or f"patch-{_hash_text(target_file + unified_diff)[:16]}")
    result = code_adapter.apply_patch(patch_id, target_file, unified_diff)
    status = getattr(result, "status", "")
    status_value = getattr(status, "value", str(status))
    error_message = getattr(result, "error_message", "")
    return {
        "response": f"Patch {status_value}: {target_file}",
        "patch_id": getattr(result, "patch_id", patch_id),
        "patch_status": status_value,
        "target_file": getattr(result, "target_file", target_file),
        "error_message": error_message,
        "receipt_status": "patched" if status_value == "applied" else "failed",
    }


def _command_run(
    sandbox_runner: Any | None,
    context: CapabilityExecutionContext,
    params: dict[str, Any],
) -> dict[str, Any]:
    if sandbox_runner is None:
        return {"response": "Sandbox runner is not available.", "receipt_status": "sandbox_unavailable"}
    command = params.get("argv") or params.get("command")
    if not isinstance(command, (list, tuple)) or not command:
        return {"response": "Sandbox command requires argv.", "receipt_status": "invalid"}
    from gateway.sandbox_runner import SandboxCommandRequest

    request = SandboxCommandRequest(
        request_id=str(params.get("request_id") or f"sandbox-request-{_hash_text(context.command_id or context.tenant_id)[:16]}"),
        tenant_id=context.tenant_id,
        capability_id="computer.command.run",
        argv=tuple(str(item) for item in command),
        cwd=str(params.get("cwd") or "/workspace"),
        environment=dict(params.get("environment", {})),
    )
    result = sandbox_runner.execute(request)
    receipt = result.receipt
    receipt_payload = {
        "receipt_id": receipt.receipt_id,
        "request_id": receipt.request_id,
        "tenant_id": receipt.tenant_id,
        "capability_id": receipt.capability_id,
        "sandbox_id": receipt.sandbox_id,
        "image": receipt.image,
        "command_hash": receipt.command_hash,
        "docker_args_hash": receipt.docker_args_hash,
        "stdout_hash": receipt.stdout_hash,
        "stderr_hash": receipt.stderr_hash,
        "returncode": receipt.returncode,
        "network_disabled": receipt.network_disabled,
        "read_only_rootfs": receipt.read_only_rootfs,
        "workspace_mount": receipt.workspace_mount,
        "forbidden_effects_observed": receipt.forbidden_effects_observed,
        "verification_status": receipt.verification_status,
        "evidence_refs": list(receipt.evidence_refs),
    }
    return {
        "response": f"Sandbox command {result.status}.",
        "sandbox_status": result.status,
        "sandbox_stdout": result.stdout,
        "sandbox_stderr": result.stderr,
        "sandbox_receipt_id": receipt.receipt_id,
        "verification_status": receipt.verification_status,
        "sandbox_execution_receipt": receipt_payload,
        "receipt_status": result.status,
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


def _adapter_worker_clients_for_platform(platform: Any | None) -> tuple[Any | None, Any | None, Any | None, Any | None]:
    """Resolve adapter worker clients from platform state or environment."""
    if platform is not None:
        bundle = _first_platform_attribute(platform, ("adapter_worker_clients", "_adapter_worker_clients"))
        if bundle is not None:
            return (
                getattr(bundle, "browser", None),
                getattr(bundle, "document", None),
                getattr(bundle, "voice", None),
                getattr(bundle, "email_calendar", None),
            )
        browser_client = _first_platform_attribute(platform, ("browser_worker_client", "_browser_worker_client")) or _nested_platform_attribute(
            platform,
            ("capability_runtime", "_capability_runtime", "adapter_runtime", "_adapter_runtime"),
            ("browser_worker_client", "_browser_worker_client"),
        )
        document_client = _first_platform_attribute(platform, ("document_worker_client", "_document_worker_client")) or _nested_platform_attribute(
            platform,
            ("capability_runtime", "_capability_runtime", "adapter_runtime", "_adapter_runtime"),
            ("document_worker_client", "_document_worker_client"),
        )
        voice_client = _first_platform_attribute(platform, ("voice_worker_client", "_voice_worker_client")) or _nested_platform_attribute(
            platform,
            ("capability_runtime", "_capability_runtime", "adapter_runtime", "_adapter_runtime"),
            ("voice_worker_client", "_voice_worker_client"),
        )
        email_calendar_client = _first_platform_attribute(
            platform,
            ("email_calendar_worker_client", "_email_calendar_worker_client"),
        ) or _nested_platform_attribute(
            platform,
            ("capability_runtime", "_capability_runtime", "adapter_runtime", "_adapter_runtime"),
            ("email_calendar_worker_client", "_email_calendar_worker_client"),
        )
        if any(client is not None for client in (browser_client, document_client, voice_client, email_calendar_client)):
            return browser_client, document_client, voice_client, email_calendar_client

    from gateway.adapter_worker_clients import build_adapter_worker_clients_from_env

    clients = build_adapter_worker_clients_from_env()
    return clients.browser, clients.document, clients.voice, clients.email_calendar


def build_capability_dispatcher_from_platform(platform: Any | None) -> CapabilityDispatcher:
    """Build a dispatcher from platform-backed providers and default handlers."""
    if platform is None:
        dispatcher = CapabilityDispatcher()
        browser_client, document_client, voice_client, email_calendar_client = _adapter_worker_clients_for_platform(None)
        register_computer_capabilities(dispatcher)
        register_browser_capabilities(dispatcher, browser_worker_client=browser_client)
        register_document_capabilities(dispatcher, document_worker_client=document_client)
        register_voice_capabilities(dispatcher, voice_worker_client=voice_client)
        register_email_calendar_capabilities(dispatcher, email_calendar_worker_client=email_calendar_client)
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
    register_computer_capabilities(
        dispatcher,
        code_adapter=_first_platform_attribute(platform, ("code_adapter", "_code_adapter", "workspace_adapter", "_workspace_adapter")),
        sandbox_runner=_first_platform_attribute(platform, ("sandbox_runner", "_sandbox_runner")),
    )
    browser_client, document_client, voice_client, email_calendar_client = _adapter_worker_clients_for_platform(platform)
    register_browser_capabilities(dispatcher, browser_worker_client=browser_client)
    register_document_capabilities(dispatcher, document_worker_client=document_client)
    register_voice_capabilities(dispatcher, voice_worker_client=voice_client)
    register_email_calendar_capabilities(dispatcher, email_calendar_worker_client=email_calendar_client)
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
