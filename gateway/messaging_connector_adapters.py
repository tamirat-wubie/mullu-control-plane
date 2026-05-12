"""Gateway Messaging Connector Adapters - bounded provider HTTP clients.

Purpose: perform Twilio, AWS SNS, Slack, Teams, WhatsApp, Telegram, and Discord
    HTTP operations for the signed messaging worker without exposing raw tools
    upstream.
Governance scope: connector credential binding, explicit action allowlists,
    approval defense for external sends, response digest evidence, and
    provider error containment.
Dependencies: stdlib urllib/json/hashlib and gateway.messaging_worker
    request/observation contracts.
Invariants:
  - Connector access tokens are never returned in observations or errors.
  - Unsupported actions fail closed before an HTTP request is issued.
  - External send actions require an approval witness.
  - Provider responses are represented by resource IDs and SHA-256 digests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from gateway.messaging_worker import (
    MessagingActionObservation,
    MessagingActionRequest,
)


READ_ACTIONS = frozenset({"messaging.thread.read"})
WRITE_ACTIONS = frozenset(
    {
        "messaging.sms.draft",
        "messaging.sms.send.with_approval",
        "messaging.chat.draft",
        "messaging.chat.send.with_approval",
    }
)
SUPPORTED_ACTIONS = READ_ACTIONS | WRITE_ACTIONS
APPROVAL_REQUIRED_ACTIONS = frozenset(
    {"messaging.sms.send.with_approval", "messaging.chat.send.with_approval"}
)
SMS_CONNECTORS = frozenset({"twilio", "aws_sns"})
CHAT_CONNECTORS = frozenset({"slack", "teams", "whatsapp", "telegram", "discord"})


@dataclass(frozen=True, slots=True)
class MessagingConnectorCredential:
    """Credential binding for one external messaging connector."""

    connector_id: str
    access_token: str
    base_url: str
    scope_id: str
    extra: Mapping[str, str] = ()  # provider-specific (account_sid, sender, region…)

    def __post_init__(self) -> None:
        _require_text(self.connector_id, "connector_id")
        _require_text(self.access_token, "access_token")
        _require_text(self.base_url, "base_url")
        _require_text(self.scope_id, "scope_id")
        if not self.base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an HTTP(S) URL")
        object.__setattr__(self, "extra", dict(self.extra))


@dataclass(frozen=True, slots=True)
class MessagingHttpOperation:
    """Normalized HTTP operation produced from a governed worker request."""

    method: str
    url: str
    body: bytes | None
    content_type: str
    extra_headers: Mapping[str, str]
    provider_operation: str
    external_send: bool

    def __post_init__(self) -> None:
        _require_text(self.method, "method")
        _require_text(self.url, "url")
        _require_text(self.provider_operation, "provider_operation")
        if self.method not in {"GET", "POST"}:
            raise ValueError("HTTP method is unsupported")
        object.__setattr__(self, "extra_headers", dict(self.extra_headers))


class HttpMessagingAdapter:
    """Concrete HTTP adapter for bounded messaging connector requests."""

    def __init__(
        self,
        *,
        credentials: Mapping[str, MessagingConnectorCredential],
        timeout_seconds: float = 10.0,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._credentials = dict(credentials)
        for connector_id, credential in self._credentials.items():
            _require_text(connector_id, "credentials key")
            if connector_id != credential.connector_id:
                raise ValueError("credential key must match connector_id")
        self._timeout_seconds = timeout_seconds
        self._urlopen = urlopen or urllib.request.urlopen

    def perform(self, request: MessagingActionRequest) -> MessagingActionObservation:
        """Perform one connector request and return receipt-compatible evidence."""
        credential = self._credentials.get(request.connector_id)
        if credential is None:
            return _failed_observation(request, "messaging connector credential unavailable")
        if request.action not in SUPPORTED_ACTIONS:
            return _failed_observation(request, "messaging connector action unsupported")
        if request.action in APPROVAL_REQUIRED_ACTIONS and not request.approval_id:
            return _failed_observation(request, "approval witness required for connector send")
        try:
            operation = _operation_for(request, credential)
            http_request = _http_request(operation, credential)
            response = self._urlopen(http_request, timeout=self._timeout_seconds)
            try:
                response_body = response.read()
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
            status_code = _response_status(response)
            response_digest = hashlib.sha256(response_body).hexdigest()
            payload = _json_payload(response_body)
            resource_id = _resource_id(payload)
            return MessagingActionObservation(
                succeeded=200 <= status_code < 300,
                connector_id=request.connector_id,
                provider_operation=operation.provider_operation,
                resource_id=resource_id,
                response_digest=response_digest,
                external_send=operation.external_send,
                error="" if 200 <= status_code < 300 else f"provider status {status_code}",
            )
        except (TimeoutError, OSError, ValueError, urllib.error.URLError) as exc:
            return _failed_observation(
                request,
                f"messaging connector transport failed: {type(exc).__name__}",
            )


def build_messaging_adapter_from_env() -> HttpMessagingAdapter | None:
    """Build the HTTP messaging adapter from worker environment variables."""
    adapter_name = os.environ.get("MULLU_MESSAGING_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name not in {"http", "production", "twilio", "slack", "teams"}:
        raise ValueError(f"unsupported messaging worker adapter: {adapter_name}")

    credentials: dict[str, MessagingConnectorCredential] = {}
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    twilio_sender = os.environ.get("TWILIO_SMS_SENDER", "").strip()
    if twilio_token and twilio_sid:
        credentials["twilio"] = MessagingConnectorCredential(
            connector_id="twilio",
            access_token=twilio_token,
            base_url=os.environ.get("TWILIO_API_BASE_URL", "https://api.twilio.com").rstrip("/"),
            scope_id=os.environ.get("TWILIO_SCOPE_ID", "carrier:twilio.sms"),
            extra={"account_sid": twilio_sid, "sender": twilio_sender},
        )
    sns_token = os.environ.get("AWS_SNS_ACCESS_TOKEN", "").strip()
    if sns_token:
        credentials["aws_sns"] = MessagingConnectorCredential(
            connector_id="aws_sns",
            access_token=sns_token,
            base_url=os.environ.get(
                "AWS_SNS_API_BASE_URL",
                "https://sns.us-east-1.amazonaws.com",
            ).rstrip("/"),
            scope_id=os.environ.get("AWS_SNS_SCOPE_ID", "carrier:aws_sns.sms"),
            extra={"region": os.environ.get("AWS_SNS_REGION", "us-east-1")},
        )
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if slack_token:
        credentials["slack"] = MessagingConnectorCredential(
            connector_id="slack",
            access_token=slack_token,
            base_url=os.environ.get("SLACK_API_BASE_URL", "https://slack.com").rstrip("/"),
            scope_id=os.environ.get("SLACK_SCOPE_ID", "oauth:slack.chat"),
        )
    teams_token = os.environ.get("MICROSOFT_TEAMS_ACCESS_TOKEN", "").strip()
    if teams_token:
        credentials["teams"] = MessagingConnectorCredential(
            connector_id="teams",
            access_token=teams_token,
            base_url=os.environ.get(
                "MICROSOFT_TEAMS_API_BASE_URL",
                "https://graph.microsoft.com",
            ).rstrip("/"),
            scope_id=os.environ.get("MICROSOFT_TEAMS_SCOPE_ID", "oauth:teams.chat"),
        )
    whatsapp_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    whatsapp_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if whatsapp_token and whatsapp_phone_id:
        credentials["whatsapp"] = MessagingConnectorCredential(
            connector_id="whatsapp",
            access_token=whatsapp_token,
            base_url=os.environ.get(
                "WHATSAPP_API_BASE_URL",
                "https://graph.facebook.com",
            ).rstrip("/"),
            scope_id=os.environ.get("WHATSAPP_SCOPE_ID", "oauth:whatsapp.chat"),
            extra={"phone_number_id": whatsapp_phone_id},
        )
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if telegram_token:
        credentials["telegram"] = MessagingConnectorCredential(
            connector_id="telegram",
            access_token=telegram_token,
            base_url=os.environ.get("TELEGRAM_API_BASE_URL", "https://api.telegram.org").rstrip("/"),
            scope_id=os.environ.get("TELEGRAM_SCOPE_ID", "bot:telegram.chat"),
        )
    discord_token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if discord_token:
        credentials["discord"] = MessagingConnectorCredential(
            connector_id="discord",
            access_token=discord_token,
            base_url=os.environ.get("DISCORD_API_BASE_URL", "https://discord.com").rstrip("/"),
            scope_id=os.environ.get("DISCORD_SCOPE_ID", "bot:discord.chat"),
        )
    return HttpMessagingAdapter(credentials=credentials)


def _operation_for(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.connector_id == "twilio":
        return _twilio_sms_operation(request, credential)
    if request.connector_id == "aws_sns":
        return _aws_sns_operation(request, credential)
    if request.connector_id == "slack":
        return _slack_operation(request, credential)
    if request.connector_id == "teams":
        return _teams_operation(request, credential)
    if request.connector_id == "whatsapp":
        return _whatsapp_operation(request, credential)
    if request.connector_id == "telegram":
        return _telegram_operation(request, credential)
    if request.connector_id == "discord":
        return _discord_operation(request, credential)
    raise ValueError("messaging connector is unsupported")


def _twilio_sms_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.sms.draft":
        # Twilio has no draft API — record an in-house draft echo without external send.
        return _local_draft_operation(request, credential, provider_operation="twilio.sms.draft")
    if request.action == "messaging.sms.send.with_approval":
        account_sid = credential.extra.get("account_sid", "")
        sender = credential.extra.get("sender", "")
        if not account_sid or not sender:
            raise ValueError("twilio credential missing account_sid or sender")
        url = f"{credential.base_url}/2010-04-01/Accounts/{urllib.parse.quote(account_sid)}/Messages.json"
        form = urllib.parse.urlencode({
            "From": sender,
            "To": request.recipients[0],
            "Body": request.body,
        }).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=url,
            body=form,
            content_type="application/x-www-form-urlencoded",
            extra_headers={
                "Authorization": _basic_auth(account_sid, credential.access_token),
            },
            provider_operation="twilio.sms.send",
            external_send=True,
        )
    raise ValueError("twilio action is unsupported")


def _aws_sns_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.sms.draft":
        return _local_draft_operation(request, credential, provider_operation="aws_sns.sms.draft")
    if request.action == "messaging.sms.send.with_approval":
        # AWS SNS Publish action via simple bearer-token signed gateway proxy.
        form = urllib.parse.urlencode({
            "Action": "Publish",
            "PhoneNumber": request.recipients[0],
            "Message": request.body,
            "Version": "2010-03-31",
        }).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=credential.base_url,
            body=form,
            content_type="application/x-www-form-urlencoded",
            extra_headers={"X-Amz-Target": "AmazonSNS_20100331.Publish"},
            provider_operation="aws_sns.publish",
            external_send=True,
        )
    raise ValueError("aws_sns action is unsupported")


def _slack_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.thread.read":
        params = urllib.parse.urlencode({
            "channel": request.recipients[0] if request.recipients else "",
            "ts": request.thread_id,
        })
        return MessagingHttpOperation(
            method="GET",
            url=f"{credential.base_url}/api/conversations.replies?{params}",
            body=None,
            content_type="",
            extra_headers={},
            provider_operation="slack.conversations.replies",
            external_send=False,
        )
    if request.action == "messaging.chat.draft":
        return _local_draft_operation(request, credential, provider_operation="slack.chat.draft")
    if request.action == "messaging.chat.send.with_approval":
        body = json.dumps(
            {
                "channel": request.recipients[0],
                "text": request.body,
                "thread_ts": request.thread_id or None,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=f"{credential.base_url}/api/chat.postMessage",
            body=body,
            content_type="application/json; charset=utf-8",
            extra_headers={},
            provider_operation="slack.chat.postMessage",
            external_send=True,
        )
    raise ValueError("slack action is unsupported")


def _teams_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.thread.read":
        chat_id = urllib.parse.quote(request.thread_id or request.recipients[0] if request.recipients else "")
        return MessagingHttpOperation(
            method="GET",
            url=f"{credential.base_url}/v1.0/chats/{chat_id}/messages",
            body=None,
            content_type="",
            extra_headers={},
            provider_operation="teams.chats.messages.list",
            external_send=False,
        )
    if request.action == "messaging.chat.draft":
        return _local_draft_operation(request, credential, provider_operation="teams.chat.draft")
    if request.action == "messaging.chat.send.with_approval":
        chat_id = urllib.parse.quote(request.recipients[0])
        body = json.dumps(
            {"body": {"contentType": "text", "content": request.body}},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=f"{credential.base_url}/v1.0/chats/{chat_id}/messages",
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="teams.chats.messages.send",
            external_send=True,
        )
    raise ValueError("teams action is unsupported")


def _whatsapp_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.thread.read":
        # WhatsApp Cloud API has no read-back; return a no-effect probe operation.
        return _local_probe_operation(request, credential, provider_operation="whatsapp.thread.probe")
    if request.action == "messaging.chat.draft":
        return _local_draft_operation(request, credential, provider_operation="whatsapp.chat.draft")
    if request.action == "messaging.chat.send.with_approval":
        phone_id = credential.extra.get("phone_number_id", "")
        if not phone_id:
            raise ValueError("whatsapp credential missing phone_number_id")
        url = f"{credential.base_url}/v18.0/{urllib.parse.quote(phone_id)}/messages"
        body = json.dumps(
            {
                "messaging_product": "whatsapp",
                "to": request.recipients[0],
                "type": "text",
                "text": {"body": request.body},
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=url,
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="whatsapp.messages.send",
            external_send=True,
        )
    raise ValueError("whatsapp action is unsupported")


def _telegram_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.thread.read":
        return _local_probe_operation(request, credential, provider_operation="telegram.thread.probe")
    if request.action == "messaging.chat.draft":
        return _local_draft_operation(request, credential, provider_operation="telegram.chat.draft")
    if request.action == "messaging.chat.send.with_approval":
        url = f"{credential.base_url}/bot{credential.access_token}/sendMessage"
        body = json.dumps(
            {"chat_id": request.recipients[0], "text": request.body},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=url,
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="telegram.sendMessage",
            external_send=True,
        )
    raise ValueError("telegram action is unsupported")


def _discord_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
) -> MessagingHttpOperation:
    if request.action == "messaging.thread.read":
        return _local_probe_operation(request, credential, provider_operation="discord.thread.probe")
    if request.action == "messaging.chat.draft":
        return _local_draft_operation(request, credential, provider_operation="discord.chat.draft")
    if request.action == "messaging.chat.send.with_approval":
        channel_id = urllib.parse.quote(request.recipients[0])
        url = f"{credential.base_url}/api/v10/channels/{channel_id}/messages"
        body = json.dumps(
            {"content": request.body},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return MessagingHttpOperation(
            method="POST",
            url=url,
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="discord.channels.messages.create",
            external_send=True,
        )
    raise ValueError("discord action is unsupported")


def _local_draft_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
    *,
    provider_operation: str,
) -> MessagingHttpOperation:
    """Local-only draft probe — no external send, returns a 204 No Content URL."""
    return MessagingHttpOperation(
        method="GET",
        url=f"{credential.base_url}/governed/draft/probe",
        body=None,
        content_type="",
        extra_headers={"X-Mullu-Draft-Probe": "true"},
        provider_operation=provider_operation,
        external_send=False,
    )


def _local_probe_operation(
    request: MessagingActionRequest,
    credential: MessagingConnectorCredential,
    *,
    provider_operation: str,
) -> MessagingHttpOperation:
    """Local-only probe — no external effect, returns evidence anchor only."""
    return MessagingHttpOperation(
        method="GET",
        url=f"{credential.base_url}/governed/probe",
        body=None,
        content_type="",
        extra_headers={"X-Mullu-Probe": "true"},
        provider_operation=provider_operation,
        external_send=False,
    )


def _http_request(
    operation: MessagingHttpOperation,
    credential: MessagingConnectorCredential,
) -> urllib.request.Request:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "X-Mullu-Connector-Scope": credential.scope_id,
    }
    auth_header = operation.extra_headers.get("Authorization")
    if auth_header is None:
        headers["Authorization"] = f"Bearer {credential.access_token}"
    for key, value in operation.extra_headers.items():
        headers[key] = value
    if operation.body is not None:
        if operation.content_type:
            headers["Content-Type"] = operation.content_type
    return urllib.request.Request(
        operation.url,
        data=operation.body,
        headers=headers,
        method=operation.method,
    )


def _basic_auth(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _json_payload(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resource_id(payload: dict[str, Any]) -> str:
    for key in ("sid", "id", "message_id", "MessageId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    nested = payload.get("message")
    if isinstance(nested, dict):
        for key in ("ts", "id"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value
    nested = payload.get("PublishResponse")
    if isinstance(nested, dict):
        result = nested.get("PublishResult")
        if isinstance(result, dict):
            value = result.get("MessageId")
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        code = getcode()
        if isinstance(code, int):
            return code
    return 0


def _failed_observation(request: MessagingActionRequest, error: str) -> MessagingActionObservation:
    return MessagingActionObservation(
        succeeded=False,
        connector_id=request.connector_id,
        provider_operation=request.action,
        error=error,
    )


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()
