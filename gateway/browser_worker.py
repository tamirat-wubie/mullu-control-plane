"""Gateway Browser Worker - restricted browser automation contract.

Purpose: Hosts the signed browser-worker boundary used by the control plane
    for browser/web capability execution.
Governance scope: action allowlisting, domain allowlisting, approval
    enforcement for submit-class effects, adapter isolation, and receipt
    emission.
Dependencies: FastAPI, gateway canonical hashing, and an injected browser
    automation adapter.
Invariants:
  - Unsigned requests are rejected before adapter invocation.
  - The worker never accepts file URLs or unrestricted domains.
  - Submit-class effects require an approval witness.
  - Adapter observations are reconciled against the domain policy.
  - Successful adapter observations require before/after screenshot evidence.
  - Responses are signed and carry audit receipts.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import Response

    _FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature
from gateway.command_spine import canonical_hash


@dataclass(frozen=True, slots=True)
class BrowserWorkerPolicy:
    """Policy envelope for one restricted browser worker."""

    worker_id: str = "browser-worker"
    allowed_actions: tuple[str, ...] = (
        "browser.open",
        "browser.screenshot",
        "browser.extract_text",
        "browser.click",
        "browser.type",
        "browser.submit",
    )
    allowed_domains: tuple[str, ...] = ("docs.mullusi.com", "learn.mullusi.com", "api.mullusi.com")
    approval_required_actions: tuple[str, ...] = ("browser.submit",)
    max_network_requests: int = 100
    store_audio: bool = False

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _validate_text_tuple(self.allowed_actions, "allowed_actions")
        _validate_text_tuple(self.allowed_domains, "allowed_domains")
        object.__setattr__(self, "approval_required_actions", tuple(self.approval_required_actions))
        for action in self.approval_required_actions:
            _require_text(action, "approval_required_actions")
        if self.max_network_requests <= 0:
            raise ValueError("max_network_requests must be > 0")
        if self.store_audio is not False:
            raise ValueError("browser worker must not store audio")


@dataclass(frozen=True, slots=True)
class BrowserActionRequest:
    """Signed request for one browser action."""

    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    url: str = ""
    selector: str = ""
    text: str = ""
    approval_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.action, "action")
        if self.action != self.capability_id:
            raise ValueError("browser action must match capability_id")
        if self.action in {"browser.open", "browser.screenshot", "browser.extract_text"}:
            _require_text(self.url, "url")
        if self.action in {"browser.click", "browser.type", "browser.submit"}:
            _require_text(self.selector, "selector")
        if self.action == "browser.type":
            _require_text(self.text, "text")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class BrowserActionObservation:
    """Observation returned by a concrete browser adapter."""

    succeeded: bool
    url_before: str
    url_after: str
    screenshot_before_ref: str = ""
    screenshot_after_ref: str = ""
    extracted_text: str = ""
    network_requests: tuple[str, ...] = ()
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        object.__setattr__(self, "network_requests", tuple(self.network_requests))


@dataclass(frozen=True, slots=True)
class BrowserActionReceipt:
    """Receipt proving browser action policy and observation."""

    receipt_id: str
    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    worker_id: str
    url_before: str
    url_after: str
    element_selector_hash: str
    screenshot_before_ref: str
    screenshot_after_ref: str
    network_requests: tuple[str, ...]
    forbidden_effects_observed: bool
    verification_status: str
    evidence_refs: tuple[str, ...]
    approval_id: str = ""
    text_hash: str = ""


@dataclass(frozen=True, slots=True)
class BrowserActionResponse:
    """Signed browser-worker response."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: BrowserActionReceipt
    error: str = ""


class BrowserAutomationAdapter(Protocol):
    """Protocol implemented by concrete Playwright/CDP adapters."""

    def perform(self, request: BrowserActionRequest) -> BrowserActionObservation:
        """Perform a browser action and return observed effects."""
        ...


class UnavailableBrowserAdapter:
    """Fail-closed adapter used until a real Playwright worker is installed."""

    def perform(self, request: BrowserActionRequest) -> BrowserActionObservation:
        return BrowserActionObservation(
            succeeded=False,
            url_before=request.url,
            url_after=request.url,
            error="browser adapter unavailable",
        )


def create_browser_worker_app(
    *,
    adapter: BrowserAutomationAdapter | None = None,
    policy: BrowserWorkerPolicy | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Create the restricted browser worker FastAPI app."""
    _require_fastapi()
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_BROWSER_WORKER_SECRET", "")
    if not secret:
        raise ValueError("browser worker signing secret is required")
    resolved_policy = policy or BrowserWorkerPolicy()
    resolved_adapter = adapter or UnavailableBrowserAdapter()
    app = FastAPI(title="Mullu Browser Worker", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": resolved_policy.worker_id,
            "governed": True,
        }

    @app.post("/browser/execute")
    async def execute_browser_action(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Browser-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid browser request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("browser request body must be an object")
            browser_request = browser_action_request_from_mapping(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
            raise HTTPException(422, detail=str(exc)) from exc

        response = execute_browser_request(browser_request, adapter=resolved_adapter, policy=resolved_policy)
        response_body = json.dumps(
            browser_action_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Browser-Response-Signature": response_signature},
        )

    app.state.browser_policy = resolved_policy
    app.state.browser_adapter = resolved_adapter
    return app


def execute_browser_request(
    request: BrowserActionRequest,
    *,
    adapter: BrowserAutomationAdapter,
    policy: BrowserWorkerPolicy,
) -> BrowserActionResponse:
    """Execute one browser request under worker policy."""
    denial = _policy_denial(request, policy)
    if denial:
        observation = BrowserActionObservation(
            succeeded=False,
            url_before=request.url,
            url_after=request.url,
            error=denial,
        )
        receipt = _receipt_for(
            request=request,
            policy=policy,
            observation=observation,
            forbidden_effects_observed=False,
            verification_status="blocked",
        )
        return BrowserActionResponse(
            request_id=request.request_id,
            status="blocked",
            result={"error": denial},
            receipt=receipt,
            error=denial,
        )

    observation = adapter.perform(request)
    forbidden_observation = _observation_forbidden(observation, policy)
    missing_evidence = _missing_observation_evidence(observation)
    succeeded = observation.succeeded and not forbidden_observation and not missing_evidence
    verification_status = "passed" if succeeded else "failed"
    forbidden_effects_observed = forbidden_observation
    receipt = _receipt_for(
        request=request,
        policy=policy,
        observation=observation,
        forbidden_effects_observed=forbidden_effects_observed,
        verification_status=verification_status,
    )
    return BrowserActionResponse(
        request_id=request.request_id,
        status="succeeded" if succeeded else "failed",
        result={
            "url_before": observation.url_before,
            "url_after": observation.url_after,
            "screenshot_before_ref": observation.screenshot_before_ref,
            "screenshot_after_ref": observation.screenshot_after_ref,
            "extracted_text": observation.extracted_text,
            "text_hash": _sha256(observation.extracted_text),
            "network_requests": list(observation.network_requests),
        },
        receipt=receipt,
        error="" if succeeded else observation.error or missing_evidence or "browser verification failed",
    )


def browser_action_request_from_mapping(raw: dict[str, Any]) -> BrowserActionRequest:
    """Parse a browser request payload into a typed request."""
    return BrowserActionRequest(
        request_id=str(raw["request_id"]),
        tenant_id=str(raw["tenant_id"]),
        capability_id=str(raw["capability_id"]),
        action=str(raw["action"]),
        url=str(raw.get("url", "")),
        selector=str(raw.get("selector", "")),
        text=str(raw.get("text", "")),
        approval_id=str(raw.get("approval_id", "")),
        metadata=dict(raw.get("metadata", {})),
    )


def browser_action_response_payload(response: BrowserActionResponse) -> dict[str, Any]:
    """Serialize a browser worker response."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": dict(response.result),
        "receipt": {
            **asdict(response.receipt),
            "network_requests": list(response.receipt.network_requests),
            "evidence_refs": list(response.receipt.evidence_refs),
        },
        "error": response.error,
    }


def _policy_denial(request: BrowserActionRequest, policy: BrowserWorkerPolicy) -> str:
    if request.action not in policy.allowed_actions:
        return "browser action is not allowlisted"
    if request.action in policy.approval_required_actions and not request.approval_id:
        return "browser action requires approval"
    candidate_urls = [request.url] if request.url else []
    if request.metadata.get("url_before"):
        candidate_urls.append(str(request.metadata["url_before"]))
    for url in candidate_urls:
        if not _url_allowed(url, policy.allowed_domains):
            return "browser URL is outside allowed domains"
    return ""


def _receipt_for(
    *,
    request: BrowserActionRequest,
    policy: BrowserWorkerPolicy,
    observation: BrowserActionObservation,
    forbidden_effects_observed: bool,
    verification_status: str,
) -> BrowserActionReceipt:
    selector_hash = _sha256(request.selector) if request.selector else ""
    text_hash = _sha256(observation.extracted_text)
    receipt_material = {
        "request_id": request.request_id,
        "capability_id": request.capability_id,
        "action": request.action,
        "url_before": observation.url_before,
        "url_after": observation.url_after,
        "selector_hash": selector_hash,
        "network_requests": tuple(observation.network_requests),
        "forbidden_effects_observed": forbidden_effects_observed,
        "verification_status": verification_status,
    }
    receipt_hash = canonical_hash(receipt_material)
    return BrowserActionReceipt(
        receipt_id=f"browser-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        capability_id=request.capability_id,
        action=request.action,
        worker_id=policy.worker_id,
        url_before=observation.url_before,
        url_after=observation.url_after,
        element_selector_hash=selector_hash,
        screenshot_before_ref=observation.screenshot_before_ref,
        screenshot_after_ref=observation.screenshot_after_ref,
        network_requests=tuple(observation.network_requests),
        forbidden_effects_observed=forbidden_effects_observed,
        verification_status=verification_status,
        evidence_refs=(f"browser_action:{receipt_hash[:16]}",),
        approval_id=request.approval_id,
        text_hash=text_hash,
    )


def _observation_forbidden(observation: BrowserActionObservation, policy: BrowserWorkerPolicy) -> bool:
    observed_urls = tuple(url for url in (observation.url_before, observation.url_after) if url)
    if any(not _url_allowed(url, policy.allowed_domains) for url in observed_urls):
        return True
    return _network_forbidden(observation.network_requests, policy)


def _network_forbidden(network_requests: tuple[str, ...], policy: BrowserWorkerPolicy) -> bool:
    if len(network_requests) > policy.max_network_requests:
        return True
    return any(not _url_allowed(url, policy.allowed_domains) for url in network_requests)


def _missing_observation_evidence(observation: BrowserActionObservation) -> str:
    if not observation.succeeded:
        return ""
    if not observation.screenshot_before_ref or not observation.screenshot_after_ref:
        return "browser observation missing screenshot evidence"
    return ""


def _url_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validate_text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field_name} must contain at least one item")
    for value in values:
        _require_text(value, field_name)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _require_fastapi() -> None:
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("fastapi is required to create the browser worker HTTP app")


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_BROWSER_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-browser-worker-secret"
    return create_browser_worker_app(signing_secret=secret)


app = _default_app() if _FASTAPI_AVAILABLE else None
