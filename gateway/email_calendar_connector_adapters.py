"""Gateway Email/Calendar Connector Adapters - bounded provider HTTP clients.

Purpose: perform Gmail, Google Calendar, and Microsoft Graph HTTP operations
    for the signed email/calendar worker without exposing raw tools upstream.
Governance scope: connector credential binding, explicit action allowlists,
    approval defense for external writes, response digest evidence, and
    provider error containment.
Dependencies: stdlib urllib/json/hashlib and gateway.email_calendar_worker
    request/observation contracts.
Invariants:
  - Connector access tokens are never returned in observations or errors.
  - Unsupported actions fail closed before an HTTP request is issued.
  - External send/calendar-write actions require an approval witness.
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

from gateway.email_calendar_worker import (
    EmailCalendarActionObservation,
    EmailCalendarActionRequest,
)

READ_ACTIONS = frozenset(
    {
        "email.read",
        "email.search",
        "email.classify",
        "email.reply_suggest",
        "calendar.read",
        "calendar.conflict_check",
    }
)
WRITE_ACTIONS = frozenset(
    {
        "email.draft",
        "email.send.with_approval",
        "calendar.schedule",
        "calendar.reschedule",
        "calendar.invite",
    }
)
SUPPORTED_ACTIONS = READ_ACTIONS | WRITE_ACTIONS


@dataclass(frozen=True, slots=True)
class ConnectorCredential:
    """Credential binding for one external email/calendar connector."""

    connector_id: str
    access_token: str
    base_url: str
    scope_id: str

    def __post_init__(self) -> None:
        _require_text(self.connector_id, "connector_id")
        _require_text(self.access_token, "access_token")
        _require_text(self.base_url, "base_url")
        _require_text(self.scope_id, "scope_id")
        if not self.base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an HTTP(S) URL")


@dataclass(frozen=True, slots=True)
class ConnectorHttpOperation:
    """Normalized HTTP operation produced from a governed worker request."""

    method: str
    url: str
    body: dict[str, Any] | None
    provider_operation: str
    external_write: bool

    def __post_init__(self) -> None:
        _require_text(self.method, "method")
        _require_text(self.url, "url")
        _require_text(self.provider_operation, "provider_operation")
        if self.method not in {"GET", "POST", "PATCH"}:
            raise ValueError("HTTP method is unsupported")


class HttpEmailCalendarAdapter:
    """Concrete HTTP adapter for bounded email/calendar connector requests."""

    def __init__(
        self,
        *,
        credentials: Mapping[str, ConnectorCredential],
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

    def perform(self, request: EmailCalendarActionRequest) -> EmailCalendarActionObservation:
        """Perform one connector request and return receipt-compatible evidence."""
        credential = self._credentials.get(request.connector_id)
        if credential is None:
            return _failed_observation(request, "connector credential unavailable")
        if request.action not in SUPPORTED_ACTIONS:
            return _failed_observation(request, "email/calendar connector action unsupported")
        if request.action in _approval_required_write_actions() and not request.approval_id:
            return _failed_observation(request, "approval witness required for connector write")
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
            return EmailCalendarActionObservation(
                succeeded=200 <= status_code < 300,
                connector_id=request.connector_id,
                provider_operation=operation.provider_operation,
                resource_id=resource_id,
                response_digest=response_digest,
                external_write=operation.external_write,
                error="" if 200 <= status_code < 300 else f"provider status {status_code}",
            )
        except (TimeoutError, OSError, ValueError, urllib.error.URLError) as exc:
            return _failed_observation(
                request,
                f"email/calendar connector transport failed: {type(exc).__name__}",
            )


def build_email_calendar_adapter_from_env() -> HttpEmailCalendarAdapter | None:
    """Build the HTTP connector adapter from worker environment variables."""
    adapter_name = os.environ.get("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name not in {"http", "google", "google_graph", "production"}:
        raise ValueError(f"unsupported email/calendar worker adapter: {adapter_name}")

    credentials: dict[str, ConnectorCredential] = {}
    gmail_token = os.environ.get("GMAIL_ACCESS_TOKEN", "").strip()
    if gmail_token:
        credentials["gmail"] = ConnectorCredential(
            connector_id="gmail",
            access_token=gmail_token,
            base_url=os.environ.get("GMAIL_API_BASE_URL", "https://gmail.googleapis.com").rstrip("/"),
            scope_id=os.environ.get("GMAIL_SCOPE_ID", "oauth:gmail"),
        )
    calendar_token = os.environ.get("GOOGLE_CALENDAR_ACCESS_TOKEN", "").strip()
    if calendar_token:
        credentials["google_calendar"] = ConnectorCredential(
            connector_id="google_calendar",
            access_token=calendar_token,
            base_url=os.environ.get("GOOGLE_CALENDAR_API_BASE_URL", "https://www.googleapis.com").rstrip("/"),
            scope_id=os.environ.get("GOOGLE_CALENDAR_SCOPE_ID", "oauth:google_calendar"),
        )
    graph_token = os.environ.get("MICROSOFT_GRAPH_ACCESS_TOKEN", "").strip()
    if graph_token:
        credentials["microsoft_graph"] = ConnectorCredential(
            connector_id="microsoft_graph",
            access_token=graph_token,
            base_url=os.environ.get("MICROSOFT_GRAPH_API_BASE_URL", "https://graph.microsoft.com").rstrip("/"),
            scope_id=os.environ.get("MICROSOFT_GRAPH_SCOPE_ID", "oauth:microsoft_graph"),
        )
    return HttpEmailCalendarAdapter(credentials=credentials)


def _operation_for(
    request: EmailCalendarActionRequest,
    credential: ConnectorCredential,
) -> ConnectorHttpOperation:
    if request.connector_id == "gmail":
        return _gmail_operation(request, credential)
    if request.connector_id == "google_calendar":
        return _google_calendar_operation(request, credential)
    if request.connector_id == "microsoft_graph":
        return _graph_operation(request, credential)
    raise ValueError("connector is unsupported")


def _gmail_operation(
    request: EmailCalendarActionRequest,
    credential: ConnectorCredential,
) -> ConnectorHttpOperation:
    base_url = credential.base_url.rstrip("/")
    message_id = _metadata_text(request, "message_id")
    if request.action in {"email.search", "email.classify", "email.reply_suggest"}:
        query = urllib.parse.urlencode({"q": request.query or "newer_than:1d"})
        return ConnectorHttpOperation(
            method="GET",
            url=f"{base_url}/gmail/v1/users/me/messages?{query}",
            body=None,
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "email.read":
        if message_id:
            return ConnectorHttpOperation(
                method="GET",
                url=f"{base_url}/gmail/v1/users/me/messages/{urllib.parse.quote(message_id)}?format=full",
                body=None,
                provider_operation=request.action,
                external_write=False,
            )
        query = urllib.parse.urlencode({"q": request.query or "newer_than:1d"})
        return ConnectorHttpOperation(
            method="GET",
            url=f"{base_url}/gmail/v1/users/me/messages?{query}",
            body=None,
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "email.draft":
        return ConnectorHttpOperation(
            method="POST",
            url=f"{base_url}/gmail/v1/users/me/drafts",
            body={"message": {"raw": _gmail_raw_message(request)}},
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "email.send.with_approval":
        return ConnectorHttpOperation(
            method="POST",
            url=f"{base_url}/gmail/v1/users/me/messages/send",
            body={"raw": _gmail_raw_message(request)},
            provider_operation=request.action,
            external_write=True,
        )
    raise ValueError("Gmail action is unsupported for this connector")


def _google_calendar_operation(
    request: EmailCalendarActionRequest,
    credential: ConnectorCredential,
) -> ConnectorHttpOperation:
    base_url = credential.base_url.rstrip("/")
    calendar_id = urllib.parse.quote(_metadata_text(request, "calendar_id") or "primary")
    if request.action in {"calendar.read", "calendar.conflict_check"}:
        query = _calendar_query(request)
        return ConnectorHttpOperation(
            method="GET",
            url=f"{base_url}/calendar/v3/calendars/{calendar_id}/events?{query}",
            body=None,
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "calendar.schedule":
        return ConnectorHttpOperation(
            method="POST",
            url=f"{base_url}/calendar/v3/calendars/{calendar_id}/events",
            body=_calendar_event_body(request),
            provider_operation=request.action,
            external_write=True,
        )
    if request.action in {"calendar.reschedule", "calendar.invite"}:
        event_id = _require_event_id(request)
        return ConnectorHttpOperation(
            method="PATCH",
            url=f"{base_url}/calendar/v3/calendars/{calendar_id}/events/{urllib.parse.quote(event_id)}",
            body=_calendar_event_body(request),
            provider_operation=request.action,
            external_write=True,
        )
    raise ValueError("Google Calendar action is unsupported for this connector")


def _graph_operation(
    request: EmailCalendarActionRequest,
    credential: ConnectorCredential,
) -> ConnectorHttpOperation:
    base_url = credential.base_url.rstrip("/")
    if request.action in {"email.search", "email.classify", "email.reply_suggest"}:
        query = urllib.parse.urlencode({"$top": "10", "$search": f'"{request.query}"' if request.query else '"newer_than:1d"'})
        return ConnectorHttpOperation(
            method="GET",
            url=f"{base_url}/v1.0/me/messages?{query}",
            body=None,
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "email.read":
        message_id = _metadata_text(request, "message_id")
        url = f"{base_url}/v1.0/me/messages/{urllib.parse.quote(message_id)}" if message_id else f"{base_url}/v1.0/me/messages?$top=10"
        return ConnectorHttpOperation(
            method="GET",
            url=url,
            body=None,
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "email.draft":
        return ConnectorHttpOperation(
            method="POST",
            url=f"{base_url}/v1.0/me/messages",
            body=_graph_message_body(request),
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "email.send.with_approval":
        return ConnectorHttpOperation(
            method="POST",
            url=f"{base_url}/v1.0/me/sendMail",
            body={"message": _graph_message_body(request), "saveToSentItems": True},
            provider_operation=request.action,
            external_write=True,
        )
    if request.action in {"calendar.read", "calendar.conflict_check"}:
        query = urllib.parse.urlencode({"$top": "10"})
        return ConnectorHttpOperation(
            method="GET",
            url=f"{base_url}/v1.0/me/events?{query}",
            body=None,
            provider_operation=request.action,
            external_write=False,
        )
    if request.action == "calendar.schedule":
        return ConnectorHttpOperation(
            method="POST",
            url=f"{base_url}/v1.0/me/events",
            body=_graph_event_body(request),
            provider_operation=request.action,
            external_write=True,
        )
    if request.action in {"calendar.reschedule", "calendar.invite"}:
        event_id = _require_event_id(request)
        return ConnectorHttpOperation(
            method="PATCH",
            url=f"{base_url}/v1.0/me/events/{urllib.parse.quote(event_id)}",
            body=_graph_event_body(request),
            provider_operation=request.action,
            external_write=True,
        )
    raise ValueError("Microsoft Graph action is unsupported for this connector")


def _http_request(
    operation: ConnectorHttpOperation,
    credential: ConnectorCredential,
) -> urllib.request.Request:
    body_bytes = None
    headers = {
        "Authorization": f"Bearer {credential.access_token}",
        "Accept": "application/json",
        "X-Mullu-Connector-Scope": credential.scope_id,
    }
    if operation.body is not None:
        body_bytes = json.dumps(operation.body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(
        operation.url,
        data=body_bytes,
        headers=headers,
        method=operation.method,
    )


def _gmail_raw_message(request: EmailCalendarActionRequest) -> str:
    headers = [
        f"To: {', '.join(request.recipients)}",
        f"Subject: {request.subject}",
        "Content-Type: text/plain; charset=UTF-8",
        "",
        request.body,
    ]
    message_bytes = "\r\n".join(headers).encode("utf-8")
    return base64.urlsafe_b64encode(message_bytes).decode("ascii").rstrip("=")


def _graph_message_body(request: EmailCalendarActionRequest) -> dict[str, Any]:
    return {
        "subject": request.subject,
        "body": {"contentType": "Text", "content": request.body},
        "toRecipients": [
            {"emailAddress": {"address": recipient}}
            for recipient in request.recipients
        ],
    }


def _calendar_event_body(request: EmailCalendarActionRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": request.subject,
        "description": request.body,
        "attendees": [{"email": attendee} for attendee in request.attendees],
    }
    if request.start_time:
        body["start"] = {"dateTime": request.start_time}
    if request.end_time:
        body["end"] = {"dateTime": request.end_time}
    return body


def _graph_event_body(request: EmailCalendarActionRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "subject": request.subject,
        "body": {"contentType": "Text", "content": request.body},
        "attendees": [
            {
                "emailAddress": {"address": attendee},
                "type": "required",
            }
            for attendee in request.attendees
        ],
    }
    if request.start_time:
        body["start"] = {"dateTime": request.start_time, "timeZone": "UTC"}
    if request.end_time:
        body["end"] = {"dateTime": request.end_time, "timeZone": "UTC"}
    return body


def _calendar_query(request: EmailCalendarActionRequest) -> str:
    params: dict[str, str] = {"singleEvents": "true", "maxResults": "10"}
    if request.start_time:
        params["timeMin"] = request.start_time
    if request.end_time:
        params["timeMax"] = request.end_time
    if request.query:
        params["q"] = request.query
    return urllib.parse.urlencode(params)


def _json_payload(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resource_id(payload: dict[str, Any]) -> str:
    for key in ("id", "messageId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for collection_key in ("messages", "items", "value"):
        collection = payload.get(collection_key)
        if isinstance(collection, list) and collection:
            first = collection[0]
            if isinstance(first, dict):
                resource_id = first.get("id")
                if isinstance(resource_id, str) and resource_id.strip():
                    return resource_id
    nested_message = payload.get("message")
    if isinstance(nested_message, dict):
        resource_id = nested_message.get("id")
        if isinstance(resource_id, str) and resource_id.strip():
            return resource_id
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


def _metadata_text(request: EmailCalendarActionRequest, key: str) -> str:
    value = request.metadata.get(key, "")
    return str(value).strip()


def _require_event_id(request: EmailCalendarActionRequest) -> str:
    event_id = request.event_id or _metadata_text(request, "event_id")
    return _require_text(event_id, "event_id")


def _approval_required_write_actions() -> frozenset[str]:
    return frozenset(WRITE_ACTIONS - {"email.draft"})


def _failed_observation(request: EmailCalendarActionRequest, error: str) -> EmailCalendarActionObservation:
    return EmailCalendarActionObservation(
        succeeded=False,
        connector_id=request.connector_id,
        provider_operation=request.action,
        error=error,
    )


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()
