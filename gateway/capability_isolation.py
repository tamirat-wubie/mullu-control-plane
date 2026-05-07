"""Gateway Capability Isolation - execution boundary contracts.

Purpose: Classifies dangerous gateway capabilities and routes them through an
    explicit execution plane before effects can be claimed.
Governance scope: gateway capability dispatch for world-mutating capabilities.
Dependencies: gateway command spine capability passports, capability dispatcher.
Invariants:
  - Dangerous capabilities carry an execution-boundary witness.
  - Pilot and production runtimes fail closed without an isolated executor.
  - Local development may use the local worker only as an explicit test plane.
  - Isolation receipts are preserved in command evidence metadata.
"""

from __future__ import annotations

import hmac
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from gateway.capability_dispatch import CapabilityDispatcher, CapabilityIntent
from gateway.command_spine import CapabilityPassport, canonical_hash


@dataclass(frozen=True, slots=True)
class CapabilityExecutionBoundary:
    """Policy boundary for dispatching one capability."""

    capability_id: str
    execution_plane: str
    isolation_required: bool
    network_policy: tuple[str, ...]
    filesystem_policy: str
    max_runtime_seconds: int
    max_memory_mb: int
    service_account: str
    evidence_required: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.capability_id, "capability_id")
        _require_non_empty_text(self.execution_plane, "execution_plane")
        if not isinstance(self.isolation_required, bool):
            raise ValueError("isolation_required must be a boolean")
        object.__setattr__(self, "network_policy", tuple(self.network_policy))
        object.__setattr__(self, "filesystem_policy", _require_non_empty_text(self.filesystem_policy, "filesystem_policy"))
        if self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be > 0")
        if self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be > 0")
        _require_non_empty_text(self.service_account, "service_account")
        object.__setattr__(self, "evidence_required", tuple(self.evidence_required))
        for index, evidence in enumerate(self.evidence_required):
            _require_non_empty_text(evidence, f"evidence_required[{index}]")


@dataclass(frozen=True, slots=True)
class CapabilityExecutionReceipt:
    """Receipt proving which execution plane ran a capability."""

    receipt_id: str
    capability_id: str
    execution_plane: str
    isolation_required: bool
    worker_id: str
    input_hash: str
    output_hash: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.receipt_id, "receipt_id")
        _require_non_empty_text(self.capability_id, "capability_id")
        _require_non_empty_text(self.execution_plane, "execution_plane")
        if not isinstance(self.isolation_required, bool):
            raise ValueError("isolation_required must be a boolean")
        _require_non_empty_text(self.worker_id, "worker_id")
        _require_non_empty_text(self.input_hash, "input_hash")
        _require_non_empty_text(self.output_hash, "output_hash")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        if not self.evidence_refs:
            raise ValueError("evidence_refs must contain at least one item")
        for index, evidence_ref in enumerate(self.evidence_refs):
            _require_non_empty_text(evidence_ref, f"evidence_refs[{index}]")


@dataclass(frozen=True, slots=True)
class CapabilityExecutionRequest:
    """Signed request sent from the control plane to a restricted worker."""

    request_id: str
    tenant_id: str
    identity_id: str
    intent: dict[str, Any]
    boundary: CapabilityExecutionBoundary
    input_hash: str
    command_id: str = ""
    conversation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.request_id, "request_id")
        _require_non_empty_text(self.tenant_id, "tenant_id")
        _require_non_empty_text(self.identity_id, "identity_id")
        if not isinstance(self.boundary, CapabilityExecutionBoundary):
            raise ValueError("boundary must be a CapabilityExecutionBoundary")
        if not isinstance(self.intent, dict):
            raise ValueError("intent must be an object")
        skill = _require_non_empty_text(str(self.intent.get("skill", "")), "intent.skill")
        action = _require_non_empty_text(str(self.intent.get("action", "")), "intent.action")
        if self.boundary.capability_id != f"{skill}.{action}":
            raise ValueError("capability boundary does not match intent")
        _require_non_empty_text(self.input_hash, "input_hash")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class CapabilityExecutionResponse:
    """Worker response containing capability output and receipt evidence."""

    request_id: str
    status: str
    result: dict[str, Any] | None
    receipt: CapabilityExecutionReceipt
    error: str = ""

    def __post_init__(self) -> None:
        _require_non_empty_text(self.request_id, "request_id")
        _require_non_empty_text(self.status, "status")
        if self.result is not None and not isinstance(self.result, dict):
            raise ValueError("result must be an object")
        if not isinstance(self.receipt, CapabilityExecutionReceipt):
            raise ValueError("receipt must be a CapabilityExecutionReceipt")


class IsolatedCapabilityExecutor(Protocol):
    """Protocol implemented by restricted capability workers."""

    def execute(
        self,
        *,
        intent: CapabilityIntent,
        tenant_id: str,
        identity_id: str,
        boundary: CapabilityExecutionBoundary,
        command_id: str = "",
        conversation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, CapabilityExecutionReceipt]: ...


class CapabilityWorkerTransport(Protocol):
    """Transport used by the gateway to reach a restricted worker."""

    def submit(self, request: CapabilityExecutionRequest) -> CapabilityExecutionResponse:
        """Submit one execution request and return a bounded worker response."""
        ...


class CapabilityIsolationPolicy:
    """Classifies capability passports into execution boundaries."""

    _DANGEROUS_EXTERNAL_SYSTEMS = {
        "browser_worker",
        "computer_worker",
        "payment_provider",
        "deployment",
        "filesystem",
        "database",
        "secret_store",
        "external_webhook",
        "shell_worker",
    }
    _WORKER_REQUIRED_DOMAINS = {"browser", "computer", "shell"}

    def __init__(self, *, environment: str = "local_dev") -> None:
        self._environment = environment.strip().lower() or "local_dev"

    @property
    def fail_closed_without_worker(self) -> bool:
        """Return whether this environment requires a real isolated worker."""
        return self._environment in {"pilot", "prod", "production"}

    def boundary_for(self, passport: CapabilityPassport) -> CapabilityExecutionBoundary:
        """Build the execution boundary for a capability passport."""
        capability_domain = passport.capability.split(".", 1)[0]
        worker_required = capability_domain in self._WORKER_REQUIRED_DOMAINS
        isolation_required = bool(
            worker_required
            or
            passport.mutates_world
            or passport.risk_tier == "high"
            or passport.external_system in self._DANGEROUS_EXTERNAL_SYSTEMS
        )
        execution_plane = "isolated_worker" if isolation_required else "gateway_process"
        service_account = f"capability-{passport.capability.replace('.', '-')}"
        network_policy = (passport.external_system,) if passport.external_system else ()
        if worker_required and capability_domain == "browser":
            network_policy = ("browser_egress_allowlist",)
        if worker_required and capability_domain in {"computer", "shell"}:
            network_policy = ("deny_all",)
        return CapabilityExecutionBoundary(
            capability_id=passport.capability,
            execution_plane=execution_plane,
            isolation_required=isolation_required,
            network_policy=network_policy,
            filesystem_policy="read_only",
            max_runtime_seconds=30 if isolation_required else 10,
            max_memory_mb=256 if isolation_required else 128,
            service_account=service_account,
            evidence_required=passport.evidence_required or passport.proof_required_fields,
        )


class LocalCapabilityExecutionWorker:
    """Local development execution plane that emits isolation receipts."""

    def __init__(self, dispatcher: CapabilityDispatcher, *, worker_id: str = "local-capability-worker") -> None:
        self._dispatcher = dispatcher
        self._worker_id = worker_id

    def execute(
        self,
        *,
        intent: CapabilityIntent,
        tenant_id: str,
        identity_id: str,
        boundary: CapabilityExecutionBoundary,
        command_id: str = "",
        conversation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, CapabilityExecutionReceipt]:
        """Execute through the local worker and return an execution receipt."""
        _validate_boundary_matches_intent(boundary, intent)
        dispatch_metadata = dict(metadata or {})
        input_hash = canonical_hash({
            "intent": {"skill": intent.skill, "action": intent.action, "params": dict(intent.params)},
            "tenant_id": tenant_id,
            "identity_id": identity_id,
            "command_id": command_id,
            "conversation_id": conversation_id,
            "boundary": asdict(boundary),
            "metadata": dispatch_metadata,
        })
        result = self._dispatcher.dispatch(
            intent,
            tenant_id,
            identity_id,
            command_id=command_id,
            conversation_id=conversation_id,
            metadata=dispatch_metadata,
        )
        output_hash = canonical_hash(result or {})
        receipt_hash = canonical_hash({
            "capability_id": boundary.capability_id,
            "execution_plane": boundary.execution_plane,
            "worker_id": self._worker_id,
            "input_hash": input_hash,
            "output_hash": output_hash,
        })
        receipt = CapabilityExecutionReceipt(
            receipt_id=f"capability-receipt-{receipt_hash[:16]}",
            capability_id=boundary.capability_id,
            execution_plane=boundary.execution_plane,
            isolation_required=boundary.isolation_required,
            worker_id=self._worker_id,
            input_hash=input_hash,
            output_hash=output_hash,
            evidence_refs=(f"capability_execution:{receipt_hash[:16]}",),
        )
        if isinstance(result, dict):
            result = {
                **result,
                "capability_execution_boundary": asdict(boundary),
                "capability_execution_receipt": asdict(receipt),
            }
        return result, receipt


class HttpCapabilityWorkerTransport:
    """HTTP transport for restricted capability workers."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        signing_secret: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not endpoint_url:
            raise ValueError("capability worker endpoint is required")
        if not signing_secret:
            raise ValueError("capability worker signing secret is required")
        if timeout_seconds <= 0:
            raise ValueError("capability worker timeout must be > 0")
        self._endpoint_url = endpoint_url
        self._signing_secret = signing_secret
        self._timeout_seconds = timeout_seconds

    def submit(self, request: CapabilityExecutionRequest) -> CapabilityExecutionResponse:
        """Submit a request to a restricted worker over HTTP."""
        payload = _request_payload(request)
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = _sign_payload(body, self._signing_secret)
        http_request = urllib.request.Request(
            self._endpoint_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Mullu-Capability-Signature": signature,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                response_body = response.read()
                response_signature = response.headers.get("X-Mullu-Capability-Response-Signature", "")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"capability worker transport failed: {type(exc).__name__}") from exc
        if not verify_capability_signature(response_body, response_signature, self._signing_secret):
            raise RuntimeError("capability worker response signature invalid")
        try:
            raw_response = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("capability worker returned invalid JSON") from exc
        return _response_from_mapping(raw_response)


class RemoteCapabilityExecutionExecutor:
    """Executor that requires a restricted worker transport receipt."""

    def __init__(self, transport: CapabilityWorkerTransport) -> None:
        self._transport = transport

    def execute(
        self,
        *,
        intent: CapabilityIntent,
        tenant_id: str,
        identity_id: str,
        boundary: CapabilityExecutionBoundary,
        command_id: str = "",
        conversation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, CapabilityExecutionReceipt]:
        """Submit execution to a restricted worker and validate its receipt."""
        request = _build_execution_request(
            intent=intent,
            tenant_id=tenant_id,
            identity_id=identity_id,
            boundary=boundary,
            command_id=command_id,
            conversation_id=conversation_id,
            metadata=metadata,
        )
        response = self._transport.submit(request)
        _validate_worker_response(request, response)
        result = response.result
        if isinstance(result, dict):
            result = {
                **result,
                "capability_execution_boundary": asdict(boundary),
                "capability_execution_receipt": asdict(response.receipt),
                "capability_execution_request_id": request.request_id,
            }
        return result, response.receipt


def build_isolated_capability_executor_from_env() -> IsolatedCapabilityExecutor | None:
    """Build a restricted capability executor from environment configuration."""
    endpoint_url = os.environ.get("MULLU_CAPABILITY_WORKER_URL", "").strip()
    signing_secret = os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", "").strip()
    if not endpoint_url and not signing_secret:
        return None
    timeout_seconds = float(os.environ.get("MULLU_CAPABILITY_WORKER_TIMEOUT_SECONDS", "10.0"))
    transport = HttpCapabilityWorkerTransport(
        endpoint_url=endpoint_url,
        signing_secret=signing_secret,
        timeout_seconds=timeout_seconds,
    )
    return RemoteCapabilityExecutionExecutor(transport)


def build_capability_execution_request(
    *,
    intent: CapabilityIntent,
    tenant_id: str,
    identity_id: str,
    boundary: CapabilityExecutionBoundary,
    command_id: str = "",
    conversation_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> CapabilityExecutionRequest:
    """Build a signed-transport-ready capability execution request."""
    return _build_execution_request(
        intent=intent,
        tenant_id=tenant_id,
        identity_id=identity_id,
        boundary=boundary,
        command_id=command_id,
        conversation_id=conversation_id,
        metadata=metadata,
    )


def _build_execution_request(
    *,
    intent: CapabilityIntent,
    tenant_id: str,
    identity_id: str,
    boundary: CapabilityExecutionBoundary,
    command_id: str = "",
    conversation_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> CapabilityExecutionRequest:
    intent_payload = {"skill": intent.skill, "action": intent.action, "params": dict(intent.params)}
    request_metadata = dict(metadata or {})
    input_hash = canonical_hash({
        "intent": intent_payload,
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "command_id": command_id,
        "conversation_id": conversation_id,
        "boundary": asdict(boundary),
        "metadata": request_metadata,
    })
    request_hash = canonical_hash({
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "command_id": command_id,
        "conversation_id": conversation_id,
        "intent": intent_payload,
        "boundary": asdict(boundary),
        "input_hash": input_hash,
        "metadata": request_metadata,
    })
    return CapabilityExecutionRequest(
        request_id=f"capability-request-{request_hash[:16]}",
        tenant_id=tenant_id,
        identity_id=identity_id,
        intent=intent_payload,
        boundary=boundary,
        input_hash=input_hash,
        command_id=command_id,
        conversation_id=conversation_id,
        metadata=request_metadata,
    )


def _request_payload(request: CapabilityExecutionRequest) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "tenant_id": request.tenant_id,
        "identity_id": request.identity_id,
        "command_id": request.command_id,
        "conversation_id": request.conversation_id,
        "intent": dict(request.intent),
        "boundary": asdict(request.boundary),
        "input_hash": request.input_hash,
        "metadata": dict(request.metadata),
    }


def capability_execution_request_from_mapping(raw: dict[str, Any]) -> CapabilityExecutionRequest:
    """Parse a worker request payload into a typed execution request."""
    boundary = raw.get("boundary")
    intent = raw.get("intent")
    if not isinstance(boundary, dict):
        raise RuntimeError("capability request requires boundary")
    if not isinstance(intent, dict):
        raise RuntimeError("capability request requires intent")
    try:
        parsed_boundary = CapabilityExecutionBoundary(
            capability_id=str(boundary["capability_id"]),
            execution_plane=str(boundary["execution_plane"]),
            isolation_required=bool(boundary["isolation_required"]),
            network_policy=tuple(boundary["network_policy"]),
            filesystem_policy=str(boundary["filesystem_policy"]),
            max_runtime_seconds=int(boundary["max_runtime_seconds"]),
            max_memory_mb=int(boundary["max_memory_mb"]),
            service_account=str(boundary["service_account"]),
            evidence_required=tuple(boundary["evidence_required"]),
        )
        request = CapabilityExecutionRequest(
            request_id=str(raw["request_id"]),
            tenant_id=str(raw["tenant_id"]),
            identity_id=str(raw["identity_id"]),
            intent=dict(intent),
            boundary=parsed_boundary,
            input_hash=str(raw["input_hash"]),
            command_id=str(raw.get("command_id", "")),
            conversation_id=str(raw.get("conversation_id", "")),
            metadata=dict(raw.get("metadata", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("capability request is malformed") from exc
    expected = canonical_hash({
        "intent": request.intent,
        "tenant_id": request.tenant_id,
        "identity_id": request.identity_id,
        "command_id": request.command_id,
        "conversation_id": request.conversation_id,
        "boundary": asdict(request.boundary),
        "metadata": dict(request.metadata),
    })
    if request.input_hash != expected:
        raise RuntimeError("capability request input hash mismatch")
    return request


def capability_execution_response_payload(response: CapabilityExecutionResponse) -> dict[str, Any]:
    """Serialize a worker execution response for transport."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": response.result,
        "receipt": asdict(response.receipt),
        "error": response.error,
    }


def _response_from_mapping(raw: dict[str, Any]) -> CapabilityExecutionResponse:
    receipt = raw.get("receipt")
    if not isinstance(receipt, dict):
        raise RuntimeError("capability worker response requires receipt")
    result = raw.get("result")
    if result is not None and not isinstance(result, dict):
        raise RuntimeError("capability worker result must be an object")
    try:
        parsed_receipt = CapabilityExecutionReceipt(
            receipt_id=str(receipt["receipt_id"]),
            capability_id=str(receipt["capability_id"]),
            execution_plane=str(receipt["execution_plane"]),
            isolation_required=bool(receipt["isolation_required"]),
            worker_id=str(receipt["worker_id"]),
            input_hash=str(receipt["input_hash"]),
            output_hash=str(receipt["output_hash"]),
            evidence_refs=tuple(receipt["evidence_refs"]),
        )
        return CapabilityExecutionResponse(
            request_id=str(raw["request_id"]),
            status=str(raw["status"]),
            result=result,
            receipt=parsed_receipt,
            error=str(raw.get("error", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("capability worker response is malformed") from exc


def _validate_worker_response(
    request: CapabilityExecutionRequest,
    response: CapabilityExecutionResponse,
) -> None:
    if response.request_id != request.request_id:
        raise RuntimeError("capability worker response request mismatch")
    if response.status != "succeeded":
        raise RuntimeError("capability worker did not succeed")
    receipt = response.receipt
    if receipt.capability_id != request.boundary.capability_id:
        raise RuntimeError("capability worker receipt capability mismatch")
    if receipt.execution_plane != request.boundary.execution_plane:
        raise RuntimeError("capability worker receipt plane mismatch")
    if receipt.input_hash != request.input_hash:
        raise RuntimeError("capability worker receipt input mismatch")
    if not receipt.evidence_refs:
        raise RuntimeError("capability worker receipt requires evidence refs")
    expected_output_hash = canonical_hash(response.result or {})
    if receipt.output_hash != expected_output_hash:
        raise RuntimeError("capability worker receipt output mismatch")


def _validate_boundary_matches_intent(boundary: CapabilityExecutionBoundary, intent: CapabilityIntent) -> None:
    expected_capability_id = f"{intent.skill}.{intent.action}"
    if boundary.capability_id != expected_capability_id:
        raise RuntimeError("capability boundary does not match intent")


def _require_non_empty_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _sign_payload(body: bytes, signing_secret: str) -> str:
    return "hmac-sha256:" + hmac.new(
        signing_secret.encode("utf-8"),
        body,
        "sha256",
    ).hexdigest()


def sign_capability_payload(body: bytes, signing_secret: str) -> str:
    """Sign a capability transport payload."""
    return _sign_payload(body, signing_secret)


def verify_capability_signature(body: bytes, signature: str, signing_secret: str) -> bool:
    """Verify a capability transport payload signature."""
    expected = _sign_payload(body, signing_secret)
    return hmac.compare_digest(signature, expected)
