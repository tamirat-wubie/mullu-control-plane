"""Gateway Phone Connector Adapters - bounded provider HTTP clients.

Purpose: perform Twilio and Vonage voice HTTP operations for the signed phone
    worker without exposing raw tools upstream.
Governance scope: connector credential binding, explicit action allowlists,
    approval defense for outbound calls, transfers, and terminations, response
    digest evidence, and provider error containment.
Dependencies: stdlib urllib/json/hashlib and gateway.phone_worker request/
    observation contracts.
Invariants:
  - Connector credentials are never returned in observations or errors.
  - Unsupported actions fail closed before an HTTP request is issued.
  - Outbound place, transfer, and terminate require an approval witness.
  - Provider responses are represented by call SIDs and SHA-256 digests.
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

from gateway.phone_worker import (
    PhoneActionObservation,
    PhoneActionRequest,
)
from gateway.proxy_policy import assert_proxy_environment_allowed


READ_ACTIONS = frozenset({"phone.call.receive", "phone.call.transcript_record"})
WRITE_ACTIONS = frozenset(
    {
        "phone.call.place.with_approval",
        "phone.call.transfer.with_approval",
        "phone.call.terminate",
    }
)
SUPPORTED_ACTIONS = READ_ACTIONS | WRITE_ACTIONS
APPROVAL_REQUIRED_ACTIONS = frozenset(
    {
        "phone.call.place.with_approval",
        "phone.call.transfer.with_approval",
        "phone.call.terminate",
    }
)


@dataclass(frozen=True, slots=True)
class PhoneConnectorCredential:
    """Credential binding for one external phone connector."""

    connector_id: str
    access_token: str
    base_url: str
    scope_id: str
    extra: Mapping[str, str] = ()

    def __post_init__(self) -> None:
        _require_text(self.connector_id, "connector_id")
        _require_text(self.access_token, "access_token")
        _require_text(self.scope_id, "scope_id")
        object.__setattr__(self, "base_url", _normalize_connector_base_url(self.base_url))
        object.__setattr__(self, "extra", dict(self.extra))


@dataclass(frozen=True, slots=True)
class PhoneHttpOperation:
    """Normalized HTTP operation produced from a governed worker request."""

    method: str
    url: str
    body: bytes | None
    content_type: str
    extra_headers: Mapping[str, str]
    provider_operation: str
    external_call: bool

    def __post_init__(self) -> None:
        _require_text(self.method, "method")
        _require_text(self.url, "url")
        _require_text(self.provider_operation, "provider_operation")
        if self.method not in {"GET", "POST"}:
            raise ValueError("HTTP method is unsupported")
        object.__setattr__(self, "extra_headers", dict(self.extra_headers))


class HttpPhoneAdapter:
    """Concrete HTTP adapter for bounded phone connector requests."""

    def __init__(
        self,
        *,
        credentials: Mapping[str, PhoneConnectorCredential],
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

    def perform(self, request: PhoneActionRequest) -> PhoneActionObservation:
        """Perform one connector request and return receipt-compatible evidence."""
        credential = self._credentials.get(request.connector_id)
        if credential is None:
            return _failed_observation(request, "phone connector credential unavailable")
        if request.action not in SUPPORTED_ACTIONS:
            return _failed_observation(request, "phone connector action unsupported")
        if request.action in APPROVAL_REQUIRED_ACTIONS and not request.approval_id:
            return _failed_observation(request, "approval witness required for connector call")
        try:
            operation = _operation_for(request, credential)
            http_request = _http_request(operation, credential)
            assert_proxy_environment_allowed()
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
            return PhoneActionObservation(
                succeeded=200 <= status_code < 300,
                connector_id=request.connector_id,
                provider_operation=operation.provider_operation,
                resource_id=resource_id,
                response_digest=response_digest,
                external_call=operation.external_call,
                error="" if 200 <= status_code < 300 else f"provider status {status_code}",
            )
        except (TimeoutError, OSError, ValueError, urllib.error.URLError) as exc:
            return _failed_observation(
                request,
                f"phone connector transport failed: {type(exc).__name__}",
            )


def build_phone_adapter_from_env() -> HttpPhoneAdapter | None:
    """Build the HTTP phone adapter from worker environment variables."""
    adapter_name = os.environ.get("MULLU_PHONE_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name not in {"http", "production", "twilio", "vonage"}:
        raise ValueError(f"unsupported phone worker adapter: {adapter_name}")

    credentials: dict[str, PhoneConnectorCredential] = {}
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    twilio_caller = os.environ.get("TWILIO_VOICE_CALLER_ID", "").strip()
    twilio_callback = os.environ.get("TWILIO_VOICE_CALLBACK_URL", "").strip()
    if twilio_token and twilio_sid:
        credentials["twilio"] = PhoneConnectorCredential(
            connector_id="twilio",
            access_token=twilio_token,
            base_url=os.environ.get("TWILIO_API_BASE_URL", "https://api.twilio.com").rstrip("/"),
            scope_id=os.environ.get("TWILIO_VOICE_SCOPE_ID", "carrier:twilio.voice"),
            extra={
                "account_sid": twilio_sid,
                "caller_id": twilio_caller,
                "callback_url": twilio_callback,
            },
        )
    vonage_key = os.environ.get("VONAGE_API_KEY", "").strip()
    vonage_secret = os.environ.get("VONAGE_API_SECRET", "").strip()
    vonage_application_id = os.environ.get("VONAGE_APPLICATION_ID", "").strip()
    vonage_caller = os.environ.get("VONAGE_VOICE_CALLER_ID", "").strip()
    if vonage_key and vonage_secret:
        credentials["vonage"] = PhoneConnectorCredential(
            connector_id="vonage",
            access_token=vonage_secret,
            base_url=os.environ.get("VONAGE_API_BASE_URL", "https://api.vonage.com").rstrip("/"),
            scope_id=os.environ.get("VONAGE_VOICE_SCOPE_ID", "carrier:vonage.voice"),
            extra={
                "api_key": vonage_key,
                "application_id": vonage_application_id,
                "caller_id": vonage_caller,
            },
        )
    return HttpPhoneAdapter(credentials=credentials)


def _operation_for(
    request: PhoneActionRequest,
    credential: PhoneConnectorCredential,
) -> PhoneHttpOperation:
    if request.connector_id == "twilio":
        return _twilio_operation(request, credential)
    if request.connector_id == "vonage":
        return _vonage_operation(request, credential)
    raise ValueError("phone connector is unsupported")


def _twilio_operation(
    request: PhoneActionRequest,
    credential: PhoneConnectorCredential,
) -> PhoneHttpOperation:
    account_sid = credential.extra.get("account_sid", "")
    if not account_sid:
        raise ValueError("twilio credential missing account_sid")
    encoded_sid = urllib.parse.quote(account_sid)
    base = credential.base_url
    auth_header = _basic_auth(account_sid, credential.access_token)

    if request.action == "phone.call.place.with_approval":
        caller = credential.extra.get("caller_id", "")
        callback = credential.extra.get("callback_url", "")
        if not caller:
            raise ValueError("twilio credential missing caller_id")
        if not callback:
            raise ValueError("twilio credential missing callback_url")
        form = urllib.parse.urlencode({
            "From": caller,
            "To": request.callees[0],
            "Url": callback,
        }).encode("utf-8")
        return PhoneHttpOperation(
            method="POST",
            url=f"{base}/2010-04-01/Accounts/{encoded_sid}/Calls.json",
            body=form,
            content_type="application/x-www-form-urlencoded",
            extra_headers={"Authorization": auth_header},
            provider_operation="twilio.calls.create",
            external_call=True,
        )
    if request.action == "phone.call.transfer.with_approval":
        # Update an in-progress call with new TwiML pointing at the transferee.
        callback = credential.extra.get("callback_url", "")
        if not callback:
            raise ValueError("twilio credential missing callback_url")
        form = urllib.parse.urlencode({
            "Url": f"{callback}?transfer_to={urllib.parse.quote(request.callees[0])}",
            "Method": "POST",
        }).encode("utf-8")
        call_id = urllib.parse.quote(request.call_id)
        return PhoneHttpOperation(
            method="POST",
            url=f"{base}/2010-04-01/Accounts/{encoded_sid}/Calls/{call_id}.json",
            body=form,
            content_type="application/x-www-form-urlencoded",
            extra_headers={"Authorization": auth_header},
            provider_operation="twilio.calls.update.transfer",
            external_call=True,
        )
    if request.action == "phone.call.terminate":
        form = urllib.parse.urlencode({"Status": "completed"}).encode("utf-8")
        call_id = urllib.parse.quote(request.call_id)
        return PhoneHttpOperation(
            method="POST",
            url=f"{base}/2010-04-01/Accounts/{encoded_sid}/Calls/{call_id}.json",
            body=form,
            content_type="application/x-www-form-urlencoded",
            extra_headers={"Authorization": auth_header},
            provider_operation="twilio.calls.update.terminate",
            external_call=False,
        )
    if request.action == "phone.call.receive":
        # Record-only probe of inbound call metadata; no external effect.
        call_id = urllib.parse.quote(request.call_id) if request.call_id else ""
        url = (
            f"{base}/2010-04-01/Accounts/{encoded_sid}/Calls/{call_id}.json"
            if call_id
            else f"{base}/2010-04-01/Accounts/{encoded_sid}/Calls.json"
        )
        return PhoneHttpOperation(
            method="GET",
            url=url,
            body=None,
            content_type="",
            extra_headers={"Authorization": auth_header},
            provider_operation="twilio.calls.read",
            external_call=False,
        )
    if request.action == "phone.call.transcript_record":
        return _local_probe_operation(
            request,
            credential,
            provider_operation="twilio.transcript.record",
        )
    raise ValueError("twilio phone action is unsupported")


def _vonage_operation(
    request: PhoneActionRequest,
    credential: PhoneConnectorCredential,
) -> PhoneHttpOperation:
    if request.action == "phone.call.place.with_approval":
        caller = credential.extra.get("caller_id", "")
        application_id = credential.extra.get("application_id", "")
        if not caller:
            raise ValueError("vonage credential missing caller_id")
        if not application_id:
            raise ValueError("vonage credential missing application_id")
        body = json.dumps(
            {
                "to": [{"type": "phone", "number": request.callees[0]}],
                "from": {"type": "phone", "number": caller},
                "ncco": [{"action": "talk", "text": "governed call connecting"}],
                "application_id": application_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return PhoneHttpOperation(
            method="POST",
            url=f"{credential.base_url}/v1/calls",
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="vonage.calls.create",
            external_call=True,
        )
    if request.action == "phone.call.transfer.with_approval":
        body = json.dumps(
            {
                "action": "transfer",
                "destination": {
                    "type": "ncco",
                    "ncco": [
                        {
                            "action": "connect",
                            "endpoint": [{"type": "phone", "number": request.callees[0]}],
                        }
                    ],
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        call_id = urllib.parse.quote(request.call_id)
        return PhoneHttpOperation(
            method="POST",
            url=f"{credential.base_url}/v1/calls/{call_id}",
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="vonage.calls.update.transfer",
            external_call=True,
        )
    if request.action == "phone.call.terminate":
        body = json.dumps(
            {"action": "hangup"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        call_id = urllib.parse.quote(request.call_id)
        return PhoneHttpOperation(
            method="POST",
            url=f"{credential.base_url}/v1/calls/{call_id}",
            body=body,
            content_type="application/json",
            extra_headers={},
            provider_operation="vonage.calls.update.terminate",
            external_call=False,
        )
    if request.action == "phone.call.receive":
        call_id = urllib.parse.quote(request.call_id) if request.call_id else ""
        url = f"{credential.base_url}/v1/calls/{call_id}" if call_id else f"{credential.base_url}/v1/calls"
        return PhoneHttpOperation(
            method="GET",
            url=url,
            body=None,
            content_type="",
            extra_headers={},
            provider_operation="vonage.calls.read",
            external_call=False,
        )
    if request.action == "phone.call.transcript_record":
        return _local_probe_operation(
            request,
            credential,
            provider_operation="vonage.transcript.record",
        )
    raise ValueError("vonage phone action is unsupported")


def _local_probe_operation(
    request: PhoneActionRequest,
    credential: PhoneConnectorCredential,
    *,
    provider_operation: str,
) -> PhoneHttpOperation:
    """Local-only probe — no external effect, returns evidence anchor only."""
    return PhoneHttpOperation(
        method="GET",
        url=f"{credential.base_url}/governed/probe",
        body=None,
        content_type="",
        extra_headers={"X-Mullu-Probe": "true"},
        provider_operation=provider_operation,
        external_call=False,
    )


def _http_request(
    operation: PhoneHttpOperation,
    credential: PhoneConnectorCredential,
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
    if operation.body is not None and operation.content_type:
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
    for key in ("sid", "id", "uuid", "call_uuid"):
        value = payload.get(key)
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


def _failed_observation(request: PhoneActionRequest, error: str) -> PhoneActionObservation:
    return PhoneActionObservation(
        succeeded=False,
        connector_id=request.connector_id,
        provider_operation=request.action,
        error=error,
    )


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_connector_base_url(base_url: str) -> str:
    """Return a credential-safe connector base URL."""

    value = _require_text(base_url, "base_url").rstrip("/")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("base_url must not contain control characters")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not include credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not include query or fragment")
    hostname = parsed.hostname.lower()
    if parsed.scheme.lower() == "http" and hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("base_url must use HTTPS unless targeting loopback")
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )
