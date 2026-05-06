"""Gateway Webhook Server — FastAPI endpoints for channel webhooks.

Purpose: HTTP entry points that receive webhooks from WhatsApp, Telegram,
    Slack, Discord, and serve the web chat WebSocket. Routes all messages
    through the GatewayRouter → GovernedSession governance pipeline.

Run: uvicorn gateway.server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from mcoi_runtime.governance.audit.decision_log import (
    GovernanceDecisionLog,
    GuardDecisionDetail,
)
from mcoi_runtime.contracts.change_assurance import ChangeCertificate
from mcoi_runtime.contracts.reflex import (
    ReflexCanaryHandoff,
    ReflexDeploymentWitness,
    ReflexEvidenceRef,
    ReflexPromotionDisposition,
    ReflexReplayResult,
    ReflexSandboxBundle,
    ReflexSandboxResult,
    RuntimeHealthSnapshot,
)
from mcoi_runtime.core.reflex import (
    build_canary_handoff,
    build_certification_handoff,
    build_sandbox_bundle,
    detect_anomalies,
    diagnose_anomaly,
    generate_eval_cases,
    propose_upgrade,
    verify_reflex_deployment_witness,
)

from gateway.channels.discord import DiscordAdapter
from gateway.channels.slack import SlackAdapter
from gateway.channels.telegram import TelegramAdapter
from gateway.channels.web import WebChatAdapter
from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.authority_obligation_mesh import (
    AuthorityObligationMesh,
    build_authority_obligation_mesh_store_from_env,
)
from gateway.capability_capsule_installer import install_certified_capsule_with_handoff_evidence
from gateway.capability_fabric import build_capability_admission_gate_from_env
from gateway.capability_isolation import build_isolated_capability_executor_from_env
from gateway.capability_forge import CapabilityCertificationHandoff
from gateway.capability_maturity import CapabilityCertificationEvidenceBundle
from gateway.case_management import build_operational_case_read_model
from gateway.command_spine import build_command_ledger_from_env
from gateway.conformance import issue_conformance_certificate
from gateway.evidence_bundle import build_command_trust_bundle
from gateway.event_log import WebhookEventLog
from gateway.mcp_capabilities import register_mcp_capabilities
from gateway.mcp_capability_fabric import MCPAuthorityRecords, build_mcp_gateway_import_from_env
from gateway.observability import GatewayObservabilityRecorder
from gateway.mcp_operator_read_model import build_mcp_operator_read_model
from gateway.operator_capability_console import (
    build_operator_capability_read_model,
    render_operator_capability_console,
)
from gateway.plan_ledger import build_capability_plan_ledger_from_env
from gateway.router import GatewayRouter
from gateway.session import SessionManager
from gateway.capability_dispatch import build_capability_dispatcher_from_platform
from gateway.signature_verification import (
    ChannelVerifierConfig, VerificationMethod, WebhookVerifier,
)
from gateway.tenant_identity import build_tenant_identity_store_from_env
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule

_log = logging.getLogger(__name__)


def create_gateway_app(
    platform: Any = None,
    *,
    capability_admission_gate_override: Any | None = None,
    mcp_capability_entries: tuple[Any, ...] = (),
    mcp_executor: Any | None = None,
    mcp_authority_records: MCPAuthorityRecords | None = None,
) -> FastAPI:
    """Create the gateway FastAPI app.

    If platform is None, attempts to import from MCOI server.
    """
    if platform is None:
        try:
            from mcoi_runtime.core.governed_session import Platform
            platform = Platform.from_env()
        except Exception:
            platform = None

    from datetime import datetime, timezone
    import hmac

    def _clock() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _int_env(name: str, default: int = 0) -> int:
        try:
            return int(os.environ.get(name, str(default)))
        except ValueError:
            return default

    gateway_env = (os.environ.get("MULLU_ENV", "local_dev") or "local_dev").strip().lower()
    approval_secret = os.environ.get("MULLU_GATEWAY_APPROVAL_SECRET", "")
    authority_operator_secret = os.environ.get("MULLU_AUTHORITY_OPERATOR_SECRET", "")
    authority_operator_roles = tuple(
        role.strip()
        for role in os.environ.get(
            "MULLU_AUTHORITY_OPERATOR_ROLES",
            "authority_operator,tenant_owner,platform_operator",
        ).split(",")
        if role.strip()
    )
    deployment_authority_secret = os.environ.get("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "")
    deployment_authority_roles = tuple(
        role.strip()
        for role in os.environ.get(
            "MULLU_DEPLOYMENT_AUTHORITY_ROLES",
            "deployment_authority,platform_operator",
        ).split(",")
        if role.strip()
    )
    authority_operator_audit_events: list[dict[str, Any]] = []
    capability_capsule_admission_receipts: list[dict[str, Any]] = []
    platform_decision_log = getattr(platform, "_decision_log", None)
    reflex_deployment_witness_log_backed = platform_decision_log is not None
    reflex_deployment_witness_log = platform_decision_log or GovernanceDecisionLog(clock=_clock)
    reflex_ephemeral_witness_log_allowed = gateway_env in {"local_dev", "test"} or (
        os.environ.get("MULLU_ALLOW_EPHEMERAL_REFLEX_WITNESS_LOG", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    defer_approved_execution = (
        os.environ.get("MULLU_GATEWAY_DEFER_APPROVED_EXECUTION", "0").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    def _approval_webhook_authorized(request: Request) -> bool:
        """Fail closed outside local and test unless an explicit approval secret matches."""
        if gateway_env in {"local_dev", "test"}:
            return True
        provided = request.headers.get("X-Mullu-Approval-Secret", "")
        if not approval_secret:
            return False
        return hmac.compare_digest(provided, approval_secret)

    def _authority_operator_authorized(request: Request) -> bool:
        """Fail closed outside local and test unless operator identity or secret matches."""
        if gateway_env in {"local_dev", "test"}:
            return True
        provided = request.headers.get("X-Mullu-Authority-Secret", "")
        if authority_operator_secret and hmac.compare_digest(provided, authority_operator_secret):
            return True
        channel = request.headers.get("X-Mullu-Authority-Channel", "").strip()
        sender_id = request.headers.get("X-Mullu-Authority-Sender-Id", "").strip()
        if not channel or not sender_id:
            return False
        mapping = tenant_identity_store.resolve(channel, sender_id)
        if mapping is None:
            return False
        tenant_id = request.headers.get("X-Mullu-Authority-Tenant-Id", "").strip()
        if tenant_id and mapping.tenant_id != tenant_id:
            return False
        roles = set(mapping.roles)
        return bool(roles.intersection(authority_operator_roles))

    def _require_authority_operator(request: Request) -> None:
        authorized = _authority_operator_authorized(request)
        _record_authority_operator_audit(request, authorized=authorized)
        if not authorized:
            raise HTTPException(403, detail="Authority operator access not authorized")

    def _deployment_authority_authorized(request: Request) -> bool:
        """Fail closed outside local and test unless deployment authority is explicit."""
        if gateway_env in {"local_dev", "test"}:
            return True
        provided = request.headers.get("X-Mullu-Deployment-Secret", "")
        if deployment_authority_secret and hmac.compare_digest(provided, deployment_authority_secret):
            return True
        channel = request.headers.get("X-Mullu-Authority-Channel", "").strip()
        sender_id = request.headers.get("X-Mullu-Authority-Sender-Id", "").strip()
        if not channel or not sender_id:
            return False
        mapping = tenant_identity_store.resolve(channel, sender_id)
        if mapping is None:
            return False
        tenant_id = request.headers.get("X-Mullu-Authority-Tenant-Id", "").strip()
        if tenant_id and mapping.tenant_id != tenant_id:
            return False
        roles = set(mapping.roles)
        return bool(roles.intersection(deployment_authority_roles))

    def _require_deployment_authority(request: Request) -> None:
        authorized = _deployment_authority_authorized(request)
        if not authorized:
            raise HTTPException(403, detail="Deployment authority access not authorized")

    def _require_reflex_deployment_witness_log_backed() -> None:
        if reflex_deployment_witness_log_backed or reflex_ephemeral_witness_log_allowed:
            return
        raise HTTPException(
            503,
            detail="Persistent Reflex deployment witness log required",
        )

    def _stable_payload_hash(payload: dict[str, Any]) -> str:
        """Return a deterministic hash for a JSON-compatible witness payload."""
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    def _signed_claim(payload: dict[str, Any], *, signing_secret: str, signature_key_id: str) -> dict[str, Any]:
        """Return a payload with a bounded HMAC claim signature."""
        claim = {**payload, "signature_key_id": signature_key_id}
        unsigned_hash = _stable_payload_hash(claim)
        signature = hmac.new(signing_secret.encode("utf-8"), unsigned_hash.encode("utf-8"), sha256).hexdigest()
        return {
            **claim,
            "claim_hash": unsigned_hash,
            "signature": f"hmac-sha256:{signature}",
        }

    def _signed_claim_valid(payload: dict[str, Any], *, signing_secret: str) -> bool:
        """Verify a signed claim emitted by this gateway."""
        signature = str(payload.get("signature", ""))
        if not signature.startswith("hmac-sha256:") or not signing_secret:
            return False
        unsigned = dict(payload)
        unsigned.pop("signature", None)
        observed_hash = str(unsigned.pop("claim_hash", ""))
        expected_hash = _stable_payload_hash(unsigned)
        if not hmac.compare_digest(observed_hash, expected_hash):
            return False
        expected_signature = hmac.new(
            signing_secret.encode("utf-8"),
            expected_hash.encode("utf-8"),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(signature.removeprefix("hmac-sha256:"), expected_signature)

    def _hmac_certificate_signature_valid(payload: dict[str, Any], *, signing_secret: str) -> bool:
        """Verify conformance-style HMAC signatures without leaking certificate details."""
        signature = str(payload.get("signature", ""))
        if not signature.startswith("hmac-sha256:") or not signing_secret:
            return False
        unsigned = dict(payload)
        unsigned.pop("signature", None)
        expected_hash = _stable_payload_hash(unsigned)
        expected_signature = hmac.new(
            signing_secret.encode("utf-8"),
            expected_hash.encode("utf-8"),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(signature.removeprefix("hmac-sha256:"), expected_signature)

    def _status_from_bool(passed: bool) -> str:
        """Map a witnessed boolean to public health status text."""
        return "pass" if passed else "missing"

    def _deployment_id() -> str:
        """Return configured deployment id or a bounded local placeholder."""
        return os.environ.get("MULLU_DEPLOYMENT_ID", "").strip() or f"dep_{gateway_env}_unpublished"

    def _commit_sha() -> str:
        """Return configured commit sha without reading deployment host state."""
        for name in ("MULLU_DEPLOYED_COMMIT_SHA", "GITHUB_SHA", "COMMIT_SHA", "SOURCE_VERSION"):
            value = os.environ.get(name, "").strip()
            if value:
                return value
        return "unknown"

    def _capability_evidence_projection() -> dict[str, Any]:
        """Return maturity-oriented capability evidence from the active fabric."""
        if capability_admission_gate is None:
            return {
                "enabled": False,
                "capability_count": 0,
                "capability_evidence": {},
                "live_capabilities": [],
                "sandbox_only_capabilities": [],
                "checks": [{
                    "check_id": "capability_registry_configured",
                    "passed": False,
                    "detail": "capability fabric admission is not configured",
                }],
            }
        read_model = capability_admission_gate.read_model()
        capabilities = tuple(read_model.get("capabilities", ()))
        evidence_by_capability: dict[str, str] = {}
        live_capabilities: list[str] = []
        sandbox_only_capabilities: list[str] = []
        for item in capabilities:
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("capability_id", "")).strip()
            if not capability_id:
                continue
            assessment = item.get("maturity_assessment", {})
            maturity_level = str(assessment.get("maturity_level", "C0")) if isinstance(assessment, dict) else "C0"
            production_ready = bool(assessment.get("production_ready")) if isinstance(assessment, dict) else False
            if production_ready:
                status = "production"
                live_capabilities.append(capability_id)
            elif maturity_level in {"C4", "C5"}:
                status = "pilot"
            elif maturity_level == "C3":
                status = "sandbox"
                sandbox_only_capabilities.append(capability_id)
            elif maturity_level in {"C1", "C2"}:
                status = "tested"
            else:
                status = "described_only"
            evidence_by_capability[capability_id] = status
        return {
            "enabled": True,
            "capability_count": int(read_model.get("capability_count", len(evidence_by_capability))),
            "capsule_count": int(read_model.get("capsule_count", 0)),
            "require_certified": read_model.get("require_certified"),
            "capability_evidence": evidence_by_capability,
            "live_capabilities": live_capabilities,
            "sandbox_only_capabilities": sandbox_only_capabilities,
            "checks": [{
                "check_id": "capability_registry_configured",
                "passed": True,
                "detail": f"capability_count={len(evidence_by_capability)}",
            }],
        }

    def _build_deployment_witness() -> dict[str, Any]:
        """Build the public production evidence witness for this gateway."""
        health_payload = health()
        conformance = runtime_conformance()
        capability_projection = _capability_evidence_projection()
        command_summary = command_ledger.summary()
        checks = [
            {
                "check_id": "gateway_health",
                "passed": health_payload.get("status") == "healthy",
                "detail": str(health_payload.get("status", "unknown")),
            },
            {
                "check_id": "runtime_conformance",
                "passed": str(conformance.get("terminal_status", "")) in {
                    "conformant",
                    "conformant_with_gaps",
                },
                "detail": str(conformance.get("terminal_status", "missing")),
            },
            {
                "check_id": "capability_registry",
                "passed": capability_projection["enabled"],
                "detail": f"capability_count={capability_projection['capability_count']}",
            },
            {
                "check_id": "audit_anchor",
                "passed": bool(command_summary.get("latest_anchor_id")),
                "detail": str(command_summary.get("latest_anchor_id") or "anchor_missing"),
            },
            {
                "check_id": "proof_store",
                "passed": int(command_summary.get("terminal_certificates", 0)) > 0,
                "detail": f"terminal_certificates={command_summary.get('terminal_certificates', 0)}",
            },
        ]
        passed_checks = [check["check_id"] for check in checks if check["passed"]]
        missing_checks = [check["check_id"] for check in checks if not check["passed"]]
        payload = {
            "deployment_id": _deployment_id(),
            "commit_sha": _commit_sha(),
            "runtime_env": gateway_env,
            "version": app.version,
            "gateway_health": _status_from_bool(health_payload.get("status") == "healthy"),
            "api_health": "pass",
            "db_health": _status_from_bool(command_summary.get("store", {}).get("available", True)),
            "policy_engine": "pass",
            "audit_store": _status_from_bool(bool(command_summary.get("latest_event_hash"))),
            "proof_store": _status_from_bool(int(command_summary.get("terminal_certificates", 0)) > 0),
            "capability_evidence": capability_projection["capability_evidence"],
            "live_capabilities": capability_projection["live_capabilities"],
            "sandbox_only_capabilities": capability_projection["sandbox_only_capabilities"],
            "checks": checks,
            "checks_passed": passed_checks,
            "checks_missing": missing_checks,
            "runtime_conformance_certificate_id": conformance.get("certificate_id", ""),
            "signed_at": _clock(),
            "witness": "mullu_gateway_production_evidence_v1",
        }
        return _signed_claim(
            payload,
            signing_secret=os.environ.get("MULLU_DEPLOYMENT_WITNESS_SECRET", "local-deployment-witness-secret"),
            signature_key_id=os.environ.get("MULLU_DEPLOYMENT_WITNESS_KEY_ID", "deployment-witness-local"),
        )

    def _unanchored_event_count() -> int:
        """Return unanchored command-event count when the ledger store exposes it."""
        store = getattr(command_ledger, "_store", None)
        if store is None or not hasattr(store, "unanchored_events"):
            return 0
        try:
            return len(store.unanchored_events())
        except Exception:
            return 0

    def _record_authority_operator_audit(request: Request, *, authorized: bool) -> None:
        """Record bounded authority operator access without storing bearer secrets."""
        channel = request.headers.get("X-Mullu-Authority-Channel", "").strip()
        sender_id = request.headers.get("X-Mullu-Authority-Sender-Id", "").strip()
        tenant_id = request.headers.get("X-Mullu-Authority-Tenant-Id", "").strip()
        provided_secret = request.headers.get("X-Mullu-Authority-Secret", "")
        credential_type = "none"
        if gateway_env in {"local_dev", "test"}:
            credential_type = "local_dev"
        elif provided_secret:
            credential_type = "operator_secret"
        elif channel or sender_id:
            credential_type = "tenant_identity"
        event_payload = {
            "event_type": "authority_operator_access_v1",
            "observed_at": _clock(),
            "method": request.method,
            "path": request.url.path,
            "authorized": authorized,
            "reason": "authorized" if authorized else "not_authorized",
            "credential_type": credential_type,
            "tenant_id": tenant_id,
            "channel": channel,
            "sender_id_hash": sha256(sender_id.encode()).hexdigest() if sender_id else "",
        }
        event_hash = sha256(
            json.dumps(event_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        authority_operator_audit_events.append({
            "event_id": f"authority-operator-access-{event_hash[:16]}",
            "event_hash": event_hash,
            **event_payload,
        })
        del authority_operator_audit_events[:-500]

    app = FastAPI(title="Mullu Gateway", version="1.0.0")

    # G10.1 — install entry-point receipt middleware. Closes the
    # gap documented in docs/MAF_RECEIPT_COVERAGE.md §"Routes NOT
    # covered". Every webhook/authority POST now produces a
    # TransitionReceipt regardless of which handler runs.
    from gateway.receipt_middleware import install_gateway_receipt_middleware
    install_gateway_receipt_middleware(app, platform)

    event_log = WebhookEventLog(clock=_clock)
    verifier = WebhookVerifier()
    capability_admission_gate = (
        capability_admission_gate_override
        if capability_admission_gate_override is not None
        else build_capability_admission_gate_from_env(clock=_clock)
    )
    mcp_gateway_import = build_mcp_gateway_import_from_env(clock=_clock)
    if mcp_gateway_import is not None:
        if capability_admission_gate is not None:
            raise ValueError("MCP capability manifest cannot be combined with configured capability admission")
        if mcp_capability_entries or mcp_authority_records is not None:
            raise ValueError("MCP capability manifest cannot be combined with explicit MCP overrides")
        capability_admission_gate = mcp_gateway_import.admission_gate
        mcp_capability_entries = mcp_gateway_import.entries
        mcp_authority_records = mcp_gateway_import.authority_records
    command_ledger = build_command_ledger_from_env(
        clock=_clock,
        capability_admission_gate=capability_admission_gate,
    )
    tenant_identity_store = build_tenant_identity_store_from_env(clock=_clock)
    authority_mesh_store = build_authority_obligation_mesh_store_from_env()
    authority_obligation_mesh = AuthorityObligationMesh(
        commands=command_ledger,
        clock=_clock,
        store=authority_mesh_store,
    )
    plan_ledger = build_capability_plan_ledger_from_env(clock=_clock)
    capability_dispatcher = build_capability_dispatcher_from_platform(platform)
    if mcp_capability_entries and mcp_executor is not None:
        register_mcp_capabilities(
            capability_dispatcher,
            capabilities=mcp_capability_entries,
            executor=mcp_executor,
        )
    isolated_capability_executor = build_isolated_capability_executor_from_env()
    observability_recorder = GatewayObservabilityRecorder()
    router = GatewayRouter(
        platform=platform,
        command_ledger=command_ledger,
        tenant_identity_store=tenant_identity_store,
        authority_obligation_mesh=authority_obligation_mesh,
        plan_ledger=plan_ledger,
        capability_dispatcher=capability_dispatcher,
        defer_approved_execution=defer_approved_execution,
        environment=gateway_env,
        isolated_capability_executor=isolated_capability_executor,
        mcp_authority_records=mcp_authority_records,
        observability_recorder=observability_recorder,
    )
    session_mgr = SessionManager()

    # ── Channel Adapters (configured from env vars) ──

    whatsapp = None
    if os.environ.get("WHATSAPP_PHONE_NUMBER_ID"):
        if not os.environ.get("WHATSAPP_APP_SECRET"):
            _log.warning("WHATSAPP_APP_SECRET not set — signature verification will reject all requests")
        whatsapp = WhatsAppAdapter(
            phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
            access_token=os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
            verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN", ""),
            app_secret=os.environ.get("WHATSAPP_APP_SECRET", ""),
        )
        router.register_channel(whatsapp)

    telegram = None
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        telegram = TelegramAdapter(
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        )
        router.register_channel(telegram)

    slack = None
    if os.environ.get("SLACK_BOT_TOKEN"):
        if not os.environ.get("SLACK_SIGNING_SECRET"):
            _log.warning("SLACK_SIGNING_SECRET not set — signature verification will reject all requests")
        slack = SlackAdapter(
            bot_token=os.environ["SLACK_BOT_TOKEN"],
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
        )
        router.register_channel(slack)

    discord = None
    if os.environ.get("DISCORD_BOT_TOKEN"):
        if not os.environ.get("DISCORD_PUBLIC_KEY"):
            _log.warning("DISCORD_PUBLIC_KEY not set — signature verification will reject all requests")
        discord = DiscordAdapter(
            bot_token=os.environ["DISCORD_BOT_TOKEN"],
            public_key=os.environ.get("DISCORD_PUBLIC_KEY", ""),
        )
        router.register_channel(discord)

    web = WebChatAdapter()
    router.register_channel(web)

    # ── Register signature verifiers from env ──
    if os.environ.get("WHATSAPP_APP_SECRET"):
        verifier.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp", method=VerificationMethod.HMAC_SHA256,
            secret=os.environ["WHATSAPP_APP_SECRET"], signature_prefix="sha256=",
        ))
    if os.environ.get("SLACK_SIGNING_SECRET"):
        verifier.register("slack", ChannelVerifierConfig(
            channel="slack", method=VerificationMethod.HMAC_SHA256,
            secret=os.environ["SLACK_SIGNING_SECRET"], signature_prefix="v0=",
            replay_window_seconds=300.0,
        ))
    if os.environ.get("DISCORD_PUBLIC_KEY"):
        verifier.register("discord", ChannelVerifierConfig(
            channel="discord", method=VerificationMethod.ED25519,
            secret=os.environ["DISCORD_PUBLIC_KEY"],
        ))

    # ── Health ──

    @app.get("/health")
    def health():
        # Check dependency health
        deps = {}
        overall = "healthy"
        if platform is not None:
            try:
                components = getattr(platform, "bootstrap_components", {})
                if callable(getattr(components, "__call__", None)):
                    components = components()
                deps["platform_components"] = components
                if isinstance(components, dict):
                    for name, ok in components.items():
                        if not ok:
                            overall = "degraded"
            except Exception:
                overall = "degraded"

        # Check channel adapters
        channels_configured = []
        for ch_name in ["whatsapp", "telegram", "slack", "discord", "web"]:
            if ch_name in [a for a in router._channels]:
                channels_configured.append(ch_name)

        return {
            "status": overall,
            "gateway": router.summary(),
            "sessions": session_mgr.summary(),
            "event_log": event_log.summary(),
            "verifier": verifier.status(),
            "dependencies": deps,
            "channels_configured": channels_configured,
        }

    # ── WhatsApp Webhook ──

    @app.get("/webhook/whatsapp")
    def whatsapp_verify(request: Request):
        """WhatsApp webhook verification (GET)."""
        if whatsapp is None:
            raise HTTPException(503, detail="WhatsApp not configured")
        mode = request.query_params.get("hub.mode", "")
        token = request.query_params.get("hub.verify_token", "")
        challenge = request.query_params.get("hub.challenge", "")
        result = whatsapp.verify_webhook(mode, token, challenge)
        if result is None:
            raise HTTPException(403, detail="Verification failed")
        return PlainTextResponse(result)

    @app.post("/webhook/whatsapp")
    async def whatsapp_receive(request: Request):
        """WhatsApp webhook message receive (POST)."""
        if whatsapp is None:
            raise HTTPException(503, detail="WhatsApp not configured")
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not whatsapp.verify_signature(body, signature):
            raise HTTPException(403, detail="Invalid signature")
        import time as _time
        _t0 = _time.monotonic()
        payload = json.loads(body)
        msg = whatsapp.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="whatsapp",
            request=request,
            body=body,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="whatsapp", sender_id="", status="ignored",
                             body=body.decode("utf-8", errors="replace")[:200],
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="whatsapp", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Telegram Webhook ──

    @app.post("/webhook/telegram")
    async def telegram_receive(request: Request):
        """Telegram Bot API webhook (POST)."""
        if telegram is None:
            raise HTTPException(503, detail="Telegram not configured")
        import time as _time
        _t0 = _time.monotonic()
        body_bytes = await request.body()
        # Verify Telegram secret token if configured (X-Telegram-Bot-Api-Secret-Token)
        if hasattr(telegram, "verify_signature"):
            secret_header = request.headers.get("x-telegram-bot-api-secret-token", "")
            if not telegram.verify_signature(body_bytes, secret_header):
                raise HTTPException(403, detail="Invalid Telegram signature")
        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        msg = telegram.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="telegram",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="telegram", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="telegram", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Slack Events API ──

    @app.post("/webhook/slack")
    async def slack_receive(request: Request):
        """Slack Events API webhook (POST)."""
        if slack is None:
            raise HTTPException(503, detail="Slack not configured")
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        payload = json.loads(body_str)

        # URL verification challenge
        challenge = slack.handle_url_verification(payload)
        if challenge is not None:
            return JSONResponse({"challenge": challenge})

        # Verify signature
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        if not slack.verify_request(timestamp, body_str, signature):
            raise HTTPException(403, detail="Invalid signature")

        msg = slack.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="slack",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="slack", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        import time as _time
        _t0 = _time.monotonic()
        response = router.handle_message(msg)
        event_log.record(channel="slack", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Discord Interactions ──

    @app.post("/webhook/discord")
    async def discord_receive(request: Request):
        """Discord interaction webhook (POST)."""
        if discord is None:
            raise HTTPException(503, detail="Discord not configured")
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        payload = json.loads(body_str)

        # Verify interaction
        signature = request.headers.get("X-Signature-Ed25519", "")
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        if not discord.verify_interaction(signature, timestamp, body_str):
            raise HTTPException(401, detail="Invalid interaction")

        # PING response (type 1)
        if payload.get("type") == 1:
            return JSONResponse({"type": 1})

        msg = discord.parse_interaction(payload)
        request_receipt = _gateway_request_receipt(
            channel="discord",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="discord", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        import time as _time
        _t0 = _time.monotonic()
        response = router.handle_message(msg)
        # Discord interaction response format
        event_log.record(channel="discord", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({
            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
            "data": {"content": response.body},
            "request_receipt": request_receipt,
        })

    # ── Web Chat ──

    @app.post("/webhook/web")
    async def web_receive(request: Request):
        """Web chat message endpoint (POST)."""
        body = await request.body()
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        session_token = request.headers.get("X-Session-Token", "")
        if not session_token or len(session_token) > 512:
            raise HTTPException(401, detail="Missing or invalid session token")
        msg = web.parse_message(payload, session_token=session_token)
        if msg is None:
            raise HTTPException(400, detail="Invalid message")
        request_receipt = _gateway_request_receipt(
            channel="web",
            request=request,
            body=body,
            message=msg,
        )
        response = router.handle_message(msg)
        return JSONResponse({
            "status": "ok",
            "message_id": response.message_id,
            "body": response.body,
            "governed": response.governed,
            "request_receipt": request_receipt,
            "metadata": response.metadata,
        })

    # ── Approval Callback ──

    @app.post("/webhook/approve/{request_id}")
    async def approve_request(request_id: str, request: Request):
        """Approve a pending governance request."""
        import json
        if not _approval_webhook_authorized(request):
            raise HTTPException(403, detail="Approval callback not authorized")
        try:
            payload = json.loads(await request.body())
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        approved = payload.get("approved", False)
        resolver_channel = str(payload.get("resolver_channel", "")).strip()
        resolver_sender_id = str(payload.get("resolver_sender_id", "")).strip()
        if not resolver_channel or not resolver_sender_id:
            raise HTTPException(400, detail="resolver_channel and resolver_sender_id are required")
        result = router.handle_external_approval_callback(
            request_id,
            approved=approved,
            resolver_channel=resolver_channel,
            resolver_sender_id=resolver_sender_id,
        )
        if result is None:
            raise HTTPException(404, detail="Request not found or already resolved")
        if result.metadata.get("error") == "approval_context_denied":
            raise HTTPException(403, detail={
                "error": "approval_context_denied",
                "authority_reason": result.metadata.get("authority_reason", ""),
                "required_roles": list(result.metadata.get("required_roles", ())),
                "resolver_roles": list(result.metadata.get("resolver_roles", ())),
            })
        return JSONResponse({
            "status": "resolved",
            "body": result.body,
            "governed": result.governed,
            "metadata": result.metadata,
        })

    # ── Gateway Status ──

    @app.get("/gateway/status")
    def gateway_status():
        return {
            "router": router.summary(),
            "sessions": session_mgr.summary(),
            "governed": True,
        }

    @app.get("/gateway/witness")
    def gateway_witness():
        return router.runtime_witness(
            environment=gateway_env,
            signature_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            signing_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )

    @app.get("/runtime/witness")
    def runtime_witness():
        return router.runtime_witness(
            environment=gateway_env,
            signature_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            signing_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )

    @app.get("/runtime/conformance")
    def runtime_conformance():
        certificate = issue_conformance_certificate(
            router=router,
            command_ledger=command_ledger,
            authority_obligation_mesh=authority_obligation_mesh,
            capability_admission_gate=capability_admission_gate,
            plan_ledger=plan_ledger,
            environment=gateway_env,
            signing_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", "local-runtime-conformance-secret"),
            signature_key_id=os.environ.get("MULLU_RUNTIME_CONFORMANCE_KEY_ID", "runtime-conformance-local"),
            runtime_witness_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            runtime_witness_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )
        return certificate.to_json_dict()

    @app.get("/deployment/witness")
    def deployment_witness():
        return _build_deployment_witness()

    @app.get("/capabilities/evidence")
    def capabilities_evidence():
        projection = _capability_evidence_projection()
        return {
            "runtime_env": gateway_env,
            "commit_sha": _commit_sha(),
            "deployment_id": _deployment_id(),
            **projection,
        }

    @app.get("/audit/verify")
    def audit_verify():
        anchors = command_ledger.list_anchors(limit=1)
        if not anchors:
            return {
                "valid": False,
                "reason": "anchor_not_found",
                "entries_checked": 0,
                "latest_anchor_id": "",
                "unanchored_event_count": _unanchored_event_count(),
                "governed": True,
            }
        anchor = anchors[0]
        proof = command_ledger.export_anchor_proof(anchor.anchor_id)
        if proof is None:
            return {
                "valid": False,
                "reason": "anchor_proof_not_found",
                "entries_checked": 0,
                "latest_anchor_id": anchor.anchor_id,
                "unanchored_event_count": _unanchored_event_count(),
                "governed": True,
            }
        verification = command_ledger.verify_anchor_proof(
            proof,
            signing_secret=os.environ.get("MULLU_COMMAND_ANCHOR_SECRET", "local-command-anchor-secret"),
        )
        return {
            "valid": verification.valid,
            "reason": verification.reason,
            "entries_checked": len(proof.event_hashes),
            "latest_anchor_id": verification.anchor_id,
            "last_hash": anchor.to_event_hash[:16],
            "unanchored_event_count": _unanchored_event_count(),
            "governed": True,
        }

    @app.get("/proof/verify")
    def proof_verify():
        conformance = runtime_conformance()
        deployment = _build_deployment_witness()
        audit = audit_verify()
        conformance_valid = _hmac_certificate_signature_valid(
            conformance,
            signing_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", "local-runtime-conformance-secret"),
        )
        deployment_valid = _signed_claim_valid(
            deployment,
            signing_secret=os.environ.get("MULLU_DEPLOYMENT_WITNESS_SECRET", "local-deployment-witness-secret"),
        )
        checks = [
            {
                "check_id": "runtime_conformance_signature",
                "passed": conformance_valid,
                "detail": str(conformance.get("certificate_id", "")),
            },
            {
                "check_id": "deployment_witness_signature",
                "passed": deployment_valid,
                "detail": str(deployment.get("deployment_id", "")),
            },
            {
                "check_id": "audit_anchor_verification",
                "passed": bool(audit.get("valid")),
                "detail": str(audit.get("reason", "")),
            },
        ]
        return {
            "valid": all(check["passed"] for check in checks),
            "runtime_env": gateway_env,
            "deployment_id": deployment.get("deployment_id", ""),
            "commit_sha": deployment.get("commit_sha", ""),
            "checks": checks,
            "checks_passed": [check["check_id"] for check in checks if check["passed"]],
            "checks_missing": [check["check_id"] for check in checks if not check["passed"]],
            "terminal_status": "verified" if all(check["passed"] for check in checks) else "verification_gaps",
            "governed": True,
        }

    def _reflex_snapshot() -> RuntimeHealthSnapshot:
        router_summary = router.summary()
        command_summary = router_summary.get("command_ledger", {})
        state_counts = command_summary.get("states", {}) if isinstance(command_summary, dict) else {}
        runtime_witness_payload = router.runtime_witness(
            environment=gateway_env,
            signature_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            signing_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )
        missing_deployment_witnesses = 0 if runtime_witness_payload.get("latest_anchor_id") else 1
        terminal_certificates = (
            int(command_summary.get("terminal_certificates", 0))
            if isinstance(command_summary, dict)
            else 0
        )
        pending_approval_count = int(router.pending_approvals)
        metrics = {
            "requests": int(router_summary.get("message_count", 0)),
            "failures": int(router_summary.get("error_count", 0)),
            "duplicate_messages": int(router_summary.get("duplicate_count", 0)),
            "missing_approvals": pending_approval_count,
            "approval_escalations": pending_approval_count,
            "unverified_executions": int(state_counts.get("requires_review", 0)),
            "deployment_witness_missing": missing_deployment_witnesses,
            "missing_deployment_witnesses": missing_deployment_witnesses,
            "premium_model_low_risk_requests": _int_env(
                "MULLU_REFLEX_PREMIUM_MODEL_LOW_RISK_REQUESTS"
            ),
            "terminal_certificates": terminal_certificates,
        }
        return RuntimeHealthSnapshot(
            snapshot_id=f"reflex-snapshot-{sha256(json.dumps(metrics, sort_keys=True).encode()).hexdigest()[:16]}",
            runtime=gateway_env,
            time_window="current_process",
            metrics=metrics,
            evidence_refs=(
                ReflexEvidenceRef(
                    kind="gateway_summary",
                    ref_id="gateway:router.summary",
                    evidence_hash=sha256(json.dumps(router_summary, sort_keys=True, default=str).encode()).hexdigest(),
                ),
                ReflexEvidenceRef(
                    kind="runtime_witness",
                    ref_id=str(runtime_witness_payload.get("witness_id", "runtime-witness:missing")),
                    evidence_hash=sha256(
                        json.dumps(runtime_witness_payload, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
            ),
            captured_at=_clock(),
        )

    def _reflex_pipeline() -> dict[str, Any]:
        snapshot = _reflex_snapshot()
        anomalies = detect_anomalies(snapshot)
        diagnoses = tuple(diagnose_anomaly(anomaly, snapshot) for anomaly in anomalies)
        eval_cases = tuple(eval_case for diagnosis in diagnoses for eval_case in generate_eval_cases(diagnosis))
        evals_by_diagnosis = {
            diagnosis.diagnosis_id: tuple(
                eval_case for eval_case in eval_cases
                if eval_case.diagnosis_id == diagnosis.diagnosis_id
            )
            for diagnosis in diagnoses
        }
        candidates = tuple(
            propose_upgrade(diagnosis, evals_by_diagnosis[diagnosis.diagnosis_id])
            for diagnosis in diagnoses
        )
        return {
            "snapshot": snapshot,
            "anomalies": anomalies,
            "diagnoses": diagnoses,
            "eval_cases": eval_cases,
            "candidates": candidates,
        }

    def _reflex_evidence_from_payload(payload: dict[str, Any]) -> ReflexEvidenceRef:
        return ReflexEvidenceRef(
            kind=str(payload.get("kind", "")).strip(),
            ref_id=str(payload.get("ref_id", "")).strip(),
            evidence_hash=payload.get("evidence_hash"),
        )

    def _reflex_sandbox_result_from_payload(payload: dict[str, Any]) -> ReflexSandboxResult:
        report_refs = tuple(
            _reflex_evidence_from_payload(report_ref)
            for report_ref in payload.get("report_refs", ())
            if isinstance(report_ref, dict)
        )
        return ReflexSandboxResult(
            candidate_id=str(payload.get("candidate_id", "")).strip(),
            passed=bool(payload.get("passed", False)),
            failed_checks=tuple(str(check) for check in payload.get("failed_checks", ())),
            report_refs=report_refs,
        )

    def _reflex_replay_from_payload(payload: dict[str, Any]) -> ReflexReplayResult:
        evidence_payload = payload.get("evidence_ref")
        if not isinstance(evidence_payload, dict):
            raise ValueError("replay evidence_ref must be an object")
        return ReflexReplayResult(
            replay_id=str(payload.get("replay_id", "")).strip(),
            passed=bool(payload.get("passed", False)),
            evidence_ref=_reflex_evidence_from_payload(evidence_payload),
            detail=str(payload.get("detail", "")).strip(),
        )

    def _reflex_sandbox_bundle_from_payload(
        candidate_id: str,
        payload: dict[str, Any],
    ) -> ReflexSandboxBundle:
        bundle_payload = payload.get("sandbox_bundle")
        if isinstance(bundle_payload, dict):
            sandbox_payload = bundle_payload.get("sandbox_result")
            if not isinstance(sandbox_payload, dict):
                raise ValueError("sandbox_bundle.sandbox_result must be an object")
            return ReflexSandboxBundle(
                bundle_id=str(bundle_payload.get("bundle_id", "")).strip(),
                candidate_id=str(bundle_payload.get("candidate_id", "")).strip(),
                eval_ids=tuple(str(eval_id) for eval_id in bundle_payload.get("eval_ids", ())),
                replay_results=tuple(
                    _reflex_replay_from_payload(replay_payload)
                    for replay_payload in bundle_payload.get("replay_results", ())
                    if isinstance(replay_payload, dict)
                ),
                sandbox_result=_reflex_sandbox_result_from_payload(sandbox_payload),
                mutation_applied=bool(bundle_payload.get("mutation_applied", False)),
            )
        sandbox_payload = payload.get("sandbox_result")
        if not isinstance(sandbox_payload, dict):
            raise ValueError("sandbox_bundle or sandbox_result is required before promotion")
        return ReflexSandboxBundle(
            bundle_id=f"sandbox:{candidate_id}",
            candidate_id=candidate_id,
            eval_ids=(),
            replay_results=(),
            sandbox_result=_reflex_sandbox_result_from_payload(sandbox_payload),
            mutation_applied=False,
        )

    def _build_reflex_deployment_witness(
        handoff: ReflexCanaryHandoff,
        snapshot: RuntimeHealthSnapshot,
        *,
        target_environment: str,
    ) -> ReflexDeploymentWitness:
        witness_core = {
            "candidate_id": handoff.candidate_id,
            "certificate_id": handoff.certificate.certificate_id,
            "promotion_decision_id": handoff.promotion_decision.decision_id,
            "target_environment": target_environment,
            "canary_status": "planned",
            "rollback_plan_ref": handoff.rollback_plan_ref,
            "signed_at": _clock(),
            "signature_key_id": os.environ.get(
                "MULLU_REFLEX_DEPLOYMENT_WITNESS_KEY_ID",
                "reflex-deployment-witness-local",
            ),
            "production_mutation_applied": False,
        }
        witness_id_seed = json.dumps(
            {
                **witness_core,
                "health_refs": [ref.to_json_dict() for ref in snapshot.evidence_refs],
            },
            sort_keys=True,
        )
        signature = hmac.new(
            os.environ.get(
                "MULLU_REFLEX_DEPLOYMENT_WITNESS_SECRET",
                "local-reflex-deployment-witness-secret",
            ).encode("utf-8"),
            witness_id_seed.encode("utf-8"),
            sha256,
        ).hexdigest()
        return ReflexDeploymentWitness(
            witness_id=f"reflex-deployment-witness-{sha256(witness_id_seed.encode()).hexdigest()[:16]}",
            health_refs=snapshot.evidence_refs,
            signature=f"hmac-sha256:{signature}",
            **witness_core,
        )

    def _record_reflex_deployment_witness(
        witness: dict[str, Any],
        request: Request,
    ) -> None:
        _require_reflex_deployment_witness_log_backed()
        reflex_deployment_witness_log.record(
            tenant_id=request.headers.get("X-Mullu-Authority-Tenant-Id", "platform") or "platform",
            identity_id=request.headers.get("X-Mullu-Authority-Sender-Id", "reflex") or "reflex",
            endpoint="/runtime/self/promote",
            method="POST",
            allowed=True,
            guards=[
                GuardDecisionDetail(
                    guard_name="deployment_authority",
                    allowed=True,
                    reason="deployment authority authorized canary witness persistence",
                ),
                GuardDecisionDetail(
                    guard_name="reflex_auto_canary_decision",
                    allowed=True,
                    reason="promotion decision allowed canary witness persistence",
                ),
            ],
            detail={
                "event_type": "reflex_deployment_witness_persisted_v1",
                "witness": witness,
            },
        )

    def _reflex_deployment_witness_records(limit: int = 1000) -> list[dict[str, Any]]:
        decisions = reflex_deployment_witness_log.query(
            endpoint="/runtime/self/promote",
            allowed=True,
            limit=limit,
        )
        records: list[dict[str, Any]] = []
        for decision in decisions:
            if decision.detail.get("event_type") != "reflex_deployment_witness_persisted_v1":
                continue
            witness = decision.detail.get("witness")
            if isinstance(witness, dict):
                records.append(witness)
        return records

    def _replay_reflex_deployment_witness(witness: dict[str, Any]) -> bool:
        return verify_reflex_deployment_witness(
            witness,
            signing_secret=os.environ.get(
                "MULLU_REFLEX_DEPLOYMENT_WITNESS_SECRET",
                "local-reflex-deployment-witness-secret",
            ),
        )

    def _bounded_query_limit(request: Request, *, default: int = 50, maximum: int = 500) -> int:
        raw_limit = request.query_params.get("limit", str(default))
        try:
            requested_limit = int(raw_limit)
        except ValueError:
            requested_limit = default
        return max(1, min(requested_limit, maximum))

    def _reflex_witness_validator_envelope(witness: dict[str, Any]) -> dict[str, Any]:
        return {
            "witness": witness,
            "validator": "scripts/validate_reflex_deployment_witness.py",
            "format": "reflex_deployment_witness_validator_envelope_v1",
        }

    @app.get("/runtime/self/health")
    def runtime_self_health(request: Request):
        _require_authority_operator(request)
        return _reflex_snapshot().to_json_dict()

    @app.get("/runtime/self/inspect")
    def runtime_self_inspect(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        return {
            "snapshot": pipeline["snapshot"].to_json_dict(),
            "anomalies": [anomaly.to_json_dict() for anomaly in pipeline["anomalies"]],
            "anomaly_count": len(pipeline["anomalies"]),
        }

    @app.post("/runtime/self/diagnose")
    def runtime_self_diagnose(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        return {
            "diagnoses": [diagnosis.to_json_dict() for diagnosis in pipeline["diagnoses"]],
            "diagnosis_count": len(pipeline["diagnoses"]),
        }

    @app.post("/runtime/self/evaluate")
    def runtime_self_evaluate(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        evals_by_diagnosis = {
            diagnosis.diagnosis_id: tuple(
                eval_case for eval_case in pipeline["eval_cases"]
                if eval_case.diagnosis_id == diagnosis.diagnosis_id
            )
            for diagnosis in pipeline["diagnoses"]
        }
        sandbox_bundles = tuple(
            build_sandbox_bundle(candidate, evals_by_diagnosis.get(candidate.diagnosis_id, ()))
            for candidate in pipeline["candidates"]
        )
        return {
            "eval_cases": [eval_case.to_json_dict() for eval_case in pipeline["eval_cases"]],
            "sandbox_bundles": [bundle.to_json_dict() for bundle in sandbox_bundles],
            "eval_count": len(pipeline["eval_cases"]),
            "sandbox_bundle_count": len(sandbox_bundles),
            "side_effects": "none",
        }

    @app.post("/runtime/self/propose-upgrade")
    def runtime_self_propose_upgrade(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        return {
            "candidates": [candidate.to_json_dict() for candidate in pipeline["candidates"]],
            "candidate_count": len(pipeline["candidates"]),
            "mutation_applied": False,
        }

    @app.post("/runtime/self/certify")
    def runtime_self_certify(payload: dict[str, Any], request: Request):
        _require_authority_operator(request)
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            raise HTTPException(400, detail="candidate_id is required")
        pipeline = _reflex_pipeline()
        candidates = {candidate.candidate_id: candidate for candidate in pipeline["candidates"]}
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise HTTPException(404, detail="reflex candidate not found")
        handoff = build_certification_handoff(
            candidate,
            author_id=str(payload.get("author_id", "reflex@mullusi.com")).strip() or "reflex@mullusi.com",
            branch=str(payload.get("branch", "reflex/candidate")).strip() or "reflex/candidate",
            base_commit=str(payload.get("base_commit", "0" * 40)).strip() or "0" * 40,
            head_commit=str(payload.get("head_commit", "1" * 40)).strip() or "1" * 40,
            created_at=_clock(),
            base_ref=str(payload.get("base_ref", "HEAD^")).strip() or "HEAD^",
            head_ref=str(payload.get("head_ref", "HEAD")).strip() or "HEAD",
        )
        return {
            **handoff.to_json_dict(),
            "candidate_id": candidate_id,
            "status": "certification_required",
            "required_command": " ".join(handoff.command_args),
        }

    @app.post("/runtime/self/promote")
    def runtime_self_promote(payload: dict[str, Any], request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        candidates = {candidate.candidate_id: candidate for candidate in pipeline["candidates"]}
        candidate_id = str(payload.get("candidate_id", "")).strip()
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise HTTPException(404, detail="reflex candidate not found")
        certificate_payload = payload.get("certificate")
        if not isinstance(certificate_payload, dict) or (
            not isinstance(payload.get("sandbox_bundle"), dict)
            and not isinstance(payload.get("sandbox_result"), dict)
        ):
            return {
                "candidate_id": candidate_id,
                "disposition": "human_approval_required",
                "requires_human_approval": True,
                "mutation_applied": False,
                "reason": "sandbox bundle and certificate are required before promotion",
            }
        try:
            sandbox_bundle = _reflex_sandbox_bundle_from_payload(candidate_id, payload)
            certificate = ChangeCertificate(**certificate_payload)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                400,
                detail=f"invalid reflex promotion evidence: {exc}",
            ) from exc
        handoff = build_canary_handoff(candidate, sandbox_bundle, certificate)
        decision = handoff.promotion_decision
        deployment_witness = None
        witness_persisted = False
        if bool(payload.get("apply_canary", False)):
            _require_deployment_authority(request)
            if decision.disposition is not ReflexPromotionDisposition.AUTO_CANARY_ALLOWED:
                raise HTTPException(
                    409,
                    detail="reflex canary application requires auto-canary promotion decision",
                )
            target_environment = str(payload.get("target_environment", "canary")).strip() or "canary"
            deployment_witness = _build_reflex_deployment_witness(
                handoff,
                pipeline["snapshot"],
                target_environment=target_environment,
            ).to_json_dict()
            _record_reflex_deployment_witness(deployment_witness, request)
            witness_persisted = True
        return {
            **handoff.to_json_dict(),
            "mutation_applied": False,
            "disposition": decision.disposition.value,
            "requires_human_approval": decision.requires_human_approval,
            "deployment_witness": deployment_witness,
            "deployment_witness_persisted": witness_persisted,
        }

    @app.get("/runtime/self/deployment-witnesses")
    def runtime_self_deployment_witnesses(request: Request):
        _require_authority_operator(request)
        _require_reflex_deployment_witness_log_backed()
        limit = _bounded_query_limit(request)
        records = _reflex_deployment_witness_records(limit=limit)
        replayed_records = [
            {
                "witness": witness,
                "replay_passed": _replay_reflex_deployment_witness(witness),
                "validator_envelope": _reflex_witness_validator_envelope(witness),
            }
            for witness in records
        ]
        return {
            "records": replayed_records,
            "record_count": len(replayed_records),
            "limit": limit,
            "export_format": "reflex_deployment_witness_validator_envelope_v1",
            "validator": "scripts/validate_reflex_deployment_witness.py",
            "all_replay_passed": all(record["replay_passed"] for record in replayed_records),
            "mutation_applied": False,
        }

    @app.get("/runtime/self/witness")
    def runtime_self_witness(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        deployment_witness_records = _reflex_deployment_witness_records()
        payload = {
            "witness_id": f"reflex-witness-{sha256(pipeline['snapshot'].to_json().encode()).hexdigest()[:16]}",
            "snapshot_id": pipeline["snapshot"].snapshot_id,
            "anomaly_count": len(pipeline["anomalies"]),
            "diagnosis_count": len(pipeline["diagnoses"]),
            "eval_count": len(pipeline["eval_cases"]),
            "candidate_count": len(pipeline["candidates"]),
            "mutation_applied": False,
            "protected_surfaces_auto_promote": False,
            "deployment_witness_log_backed": reflex_deployment_witness_log_backed,
            "ephemeral_deployment_witness_log_allowed": reflex_ephemeral_witness_log_allowed,
            "deployment_witness_count": len(deployment_witness_records),
            "deployment_witness_replay_passed": all(
                _replay_reflex_deployment_witness(witness)
                for witness in deployment_witness_records
            ),
            "latest_deployment_witness_id": (
                deployment_witness_records[0]["witness_id"]
                if deployment_witness_records
                else None
            ),
            "signed_at": _clock(),
            "signature_key_id": os.environ.get("MULLU_REFLEX_WITNESS_KEY_ID", "reflex-witness-local"),
        }
        signature_payload = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        signature = hmac.new(
            os.environ.get("MULLU_REFLEX_WITNESS_SECRET", "local-reflex-witness-secret").encode("utf-8"),
            signature_payload.encode("utf-8"),
            sha256,
        ).hexdigest()
        return {
            **payload,
            "signature": f"hmac-sha256:{signature}",
        }

    @app.get("/authority/witness")
    def authority_witness(request: Request):
        _require_authority_operator(request)
        return asdict(authority_obligation_mesh.responsibility_witness())

    @app.get("/authority/ownership")
    def authority_ownership(
        request: Request,
        tenant_id: str = "",
        resource_ref: str = "",
        owner_team: str = "",
        primary_owner_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        ownership = authority_mesh_store.list_ownership()
        if tenant_id:
            ownership = tuple(item for item in ownership if item.tenant_id == tenant_id)
        if resource_ref:
            ownership = tuple(item for item in ownership if item.resource_ref == resource_ref)
        if owner_team:
            ownership = tuple(item for item in ownership if item.owner_team == owner_team)
        if primary_owner_id:
            ownership = tuple(item for item in ownership if item.primary_owner_id == primary_owner_id)
        page, page_meta = _read_model_page(
            ownership,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "ownership": [asdict(item) for item in page],
            "count": len(page),
            **page_meta,
        }

    @app.get("/authority/policies")
    def authority_policies(
        request: Request,
        tenant_id: str = "",
        policy_id: str = "",
        capability: str = "",
        risk_tier: str = "",
        required_role: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        approval_policies = authority_mesh_store.list_approval_policies()
        escalation_policies = authority_mesh_store.list_escalation_policies()
        if tenant_id:
            approval_policies = tuple(policy for policy in approval_policies if policy.tenant_id == tenant_id)
            escalation_policies = tuple(policy for policy in escalation_policies if policy.tenant_id == tenant_id)
        if policy_id:
            approval_policies = tuple(policy for policy in approval_policies if policy.policy_id == policy_id)
            escalation_policies = tuple(policy for policy in escalation_policies if policy.policy_id == policy_id)
        if capability:
            approval_policies = tuple(policy for policy in approval_policies if policy.capability == capability)
            escalation_policies = ()
        if risk_tier:
            approval_policies = tuple(policy for policy in approval_policies if policy.risk_tier == risk_tier)
            escalation_policies = ()
        if required_role:
            approval_policies = tuple(policy for policy in approval_policies if required_role in policy.required_roles)
            escalation_policies = ()
        approval_page, approval_meta = _read_model_page(
            approval_policies,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        escalation_page, escalation_meta = _read_model_page(
            escalation_policies,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "approval_policies": [asdict(policy) for policy in approval_page],
            "escalation_policies": [asdict(policy) for policy in escalation_page],
            "approval_count": len(approval_page),
            "escalation_count": len(escalation_page),
            "approval_page": approval_meta,
            "escalation_page": escalation_meta,
        }

    @app.get("/authority/approval-chains")
    def authority_approval_chains(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        command_id: str = "",
        policy_id: str = "",
        required_role: str = "",
        overdue: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        chains = authority_mesh_store.list_approval_chains()
        if tenant_id:
            chains = tuple(chain for chain in chains if chain.tenant_id == tenant_id)
        if status:
            chains = tuple(chain for chain in chains if chain.status.value == status)
        if command_id:
            chains = tuple(chain for chain in chains if chain.command_id == command_id)
        if policy_id:
            chains = tuple(chain for chain in chains if chain.policy_id == policy_id)
        if required_role:
            chains = tuple(chain for chain in chains if required_role in chain.required_roles)
        if overdue:
            requested_overdue = overdue.strip().lower()
            if requested_overdue not in {"true", "false"}:
                raise HTTPException(400, detail="overdue must be true or false")
            now = datetime.fromisoformat(_clock().replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            def _chain_overdue(chain: Any) -> bool:
                try:
                    due_at = datetime.fromisoformat(chain.due_at.replace("Z", "+00:00"))
                except ValueError:
                    return False
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
                return due_at <= now

            expected = requested_overdue == "true"
            chains = tuple(chain for chain in chains if _chain_overdue(chain) is expected)
        page, page_meta = _read_model_page(
            chains,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "approval_chains": [asdict(chain) for chain in page],
            "count": len(page),
            **page_meta,
        }

    @app.get("/commands/{command_id}/authority")
    def command_authority(command_id: str, request: Request):
        _require_authority_operator(request)
        chain = authority_obligation_mesh.approval_chain_for(command_id)
        obligations = authority_obligation_mesh.obligations_for(command_id)
        if chain is None and not obligations:
            raise HTTPException(404, detail="authority records not found")
        return {
            "command_id": command_id,
            "approval_chain": asdict(chain) if chain is not None else None,
            "obligations": [asdict(obligation) for obligation in obligations],
        }

    @app.post("/authority/approval-chains/expire-overdue")
    def expire_overdue_authority_approval_chains(request: Request):
        _require_authority_operator(request)
        chains = authority_obligation_mesh.expire_overdue_approval_chains()
        return {
            "status": "expired",
            "approval_chains": [asdict(chain) for chain in chains],
            "count": len(chains),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.get("/authority/obligations")
    def authority_obligations(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        command_id: str = "",
        owner_id: str = "",
        owner_team: str = "",
        obligation_type: str = "",
        overdue: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        obligations = authority_mesh_store.list_obligations(command_id)
        if tenant_id:
            obligations = tuple(obligation for obligation in obligations if obligation.tenant_id == tenant_id)
        if status:
            obligations = tuple(obligation for obligation in obligations if obligation.status.value == status)
        if owner_id:
            obligations = tuple(obligation for obligation in obligations if obligation.owner_id == owner_id)
        if owner_team:
            obligations = tuple(obligation for obligation in obligations if obligation.owner_team == owner_team)
        if obligation_type:
            obligations = tuple(
                obligation for obligation in obligations
                if obligation.obligation_type == obligation_type
            )
        if overdue:
            requested_overdue = overdue.strip().lower()
            if requested_overdue not in {"true", "false"}:
                raise HTTPException(400, detail="overdue must be true or false")
            now = datetime.fromisoformat(_clock().replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            def _obligation_overdue(obligation: Any) -> bool:
                try:
                    due_at = datetime.fromisoformat(obligation.due_at.replace("Z", "+00:00"))
                except ValueError:
                    return False
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
                return due_at <= now

            expected = requested_overdue == "true"
            obligations = tuple(
                obligation for obligation in obligations
                if _obligation_overdue(obligation) is expected
            )
        page, page_meta = _read_model_page(
            obligations,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "obligations": [asdict(obligation) for obligation in page],
            "count": len(page),
            **page_meta,
        }

    @app.post("/authority/obligations/{obligation_id}/satisfy")
    def satisfy_authority_obligation(obligation_id: str, payload: dict[str, Any], request: Request):
        _require_authority_operator(request)
        raw_evidence_refs = payload.get("evidence_refs", ())
        if isinstance(raw_evidence_refs, str):
            raw_evidence_refs = (raw_evidence_refs,)
        if not isinstance(raw_evidence_refs, (list, tuple)):
            raise HTTPException(400, detail="evidence_refs must be a list of strings")
        evidence_refs = tuple(str(ref).strip() for ref in raw_evidence_refs)
        evidence_refs = tuple(ref for ref in evidence_refs if ref)
        try:
            obligation = authority_obligation_mesh.satisfy_obligation(
                obligation_id,
                evidence_refs=evidence_refs,
            )
        except KeyError as exc:
            raise HTTPException(404, detail="obligation not found") from exc
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {
            "status": "satisfied",
            "obligation": asdict(obligation),
            "evidence_refs": list(evidence_refs),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.post("/authority/obligations/escalate-overdue")
    def escalate_overdue_authority_obligations(request: Request):
        _require_authority_operator(request)
        obligations = authority_obligation_mesh.escalate_overdue()
        return {
            "status": "escalated",
            "obligations": [asdict(obligation) for obligation in obligations],
            "count": len(obligations),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.get("/authority/escalations")
    def authority_escalations(
        request: Request,
        tenant_id: str = "",
        command_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        events = authority_mesh_store.list_escalation_events()
        if tenant_id:
            events = tuple(event for event in events if event.get("tenant_id") == tenant_id)
        if command_id:
            events = tuple(event for event in events if event.get("command_id") == command_id)
        page, page_meta = _read_model_page(
            events,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "escalation_events": list(page),
            "count": len(page),
            **page_meta,
        }

    @app.get("/authority/responsibility")
    def authority_responsibility(
        request: Request,
        tenant_id: str = "",
        limit: int = 25,
    ):
        _require_authority_operator(request)
        bounded_limit = _bounded_read_model_limit(limit, maximum=100)
        witness = asdict(authority_obligation_mesh.responsibility_witness())
        chains = authority_mesh_store.list_approval_chains()
        obligations = authority_mesh_store.list_obligations()
        escalation_events = authority_mesh_store.list_escalation_events()
        ownership = authority_mesh_store.list_ownership()
        approval_policies = authority_mesh_store.list_approval_policies()
        escalation_policies = authority_mesh_store.list_escalation_policies()
        if tenant_id:
            chains = tuple(chain for chain in chains if chain.tenant_id == tenant_id)
            obligations = tuple(obligation for obligation in obligations if obligation.tenant_id == tenant_id)
            escalation_events = tuple(event for event in escalation_events if event.get("tenant_id") == tenant_id)
            ownership = tuple(item for item in ownership if item.tenant_id == tenant_id)
            approval_policies = tuple(policy for policy in approval_policies if policy.tenant_id == tenant_id)
            escalation_policies = tuple(policy for policy in escalation_policies if policy.tenant_id == tenant_id)
        pending_chains = tuple(
            chain for chain in chains
            if chain.status.value == "pending"
        )
        unresolved_obligations = tuple(
            obligation for obligation in obligations
            if obligation.status.value in {"open", "escalated"}
        )
        priority_chains = tuple(sorted(
            pending_chains,
            key=lambda chain: (_due_sort_key(chain.due_at), chain.chain_id),
        ))[:bounded_limit]
        priority_obligations = tuple(sorted(
            unresolved_obligations,
            key=lambda obligation: (_due_sort_key(obligation.due_at), obligation.obligation_id),
        ))[:bounded_limit]
        priority_escalations = tuple(reversed(escalation_events))[:bounded_limit]
        debt_clear = (
            int(witness.get("overdue_approval_chain_count", 0)) == 0
            and int(witness.get("expired_approval_chain_count", 0)) == 0
            and int(witness.get("overdue_obligation_count", 0)) == 0
            and int(witness.get("escalated_obligation_count", 0)) == 0
            and int(witness.get("unowned_high_risk_capability_count", 0)) == 0
        )
        return {
            "tenant_id": tenant_id,
            "responsibility_debt_clear": debt_clear,
            "authority_witness": witness,
            "ownership_count": len(ownership),
            "approval_policy_count": len(approval_policies),
            "escalation_policy_count": len(escalation_policies),
            "pending_approval_chain_count": len(pending_chains),
            "unresolved_obligation_count": len(unresolved_obligations),
            "escalation_event_count": len(escalation_events),
            "priority_approval_chains": [asdict(chain) for chain in priority_chains],
            "priority_obligations": [asdict(obligation) for obligation in priority_obligations],
            "priority_escalation_events": list(priority_escalations),
            "limit": bounded_limit,
            "evidence_refs": [
                "authority:witness",
                "authority:approval_chains_read_model",
                "authority:obligations_read_model",
                "authority:escalations_read_model",
                "authority:ownership_read_model",
                "authority:policy_read_model",
            ],
        }

    @app.get("/cases/read-model")
    def operational_cases_read_model(
        request: Request,
        tenant_id: str = "",
        case_type: str = "",
        status: str = "",
        owner: str = "",
        severity: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        read_model = build_operational_case_read_model(
            approval_chains=authority_mesh_store.list_approval_chains(),
            obligations=authority_mesh_store.list_obligations(),
            escalation_events=authority_mesh_store.list_escalation_events(),
        )
        cases = tuple(read_model["cases"])
        if tenant_id:
            cases = tuple(case for case in cases if case["tenant_id"] == tenant_id)
        if case_type:
            cases = tuple(case for case in cases if case["case_type"] == case_type)
        if status:
            cases = tuple(case for case in cases if case["status"] == status)
        if owner:
            cases = tuple(case for case in cases if case["owner"] == owner)
        if severity:
            cases = tuple(case for case in cases if case["severity"] == severity)
        page, page_meta = _read_model_page(
            cases,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            **read_model,
            "cases": list(page),
            "case_count": len(page),
            "total_case_count": len(cases),
            **page_meta,
        }

    @app.get("/authority/operator-audit")
    def authority_operator_audit(
        request: Request,
        path: str = "",
        authorized: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        audit_events = tuple(authority_operator_audit_events)
        if path:
            audit_events = tuple(event for event in audit_events if event.get("path") == path)
        if authorized:
            requested_authorized = authorized.strip().lower()
            if requested_authorized not in {"true", "false"}:
                raise HTTPException(400, detail="authorized must be true or false")
            expected = requested_authorized == "true"
            audit_events = tuple(event for event in audit_events if event.get("authorized") is expected)
        page, page_meta = _read_model_page(
            audit_events,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "operator_audit_events": list(page),
            "count": len(page),
            **page_meta,
        }

    @app.get("/authority/operator", response_class=HTMLResponse)
    def authority_operator_console(request: Request):
        _require_authority_operator(request)
        witness = authority_obligation_mesh.responsibility_witness()
        chains = authority_mesh_store.list_approval_chains()
        obligations = authority_mesh_store.list_obligations()
        escalations = authority_mesh_store.list_escalation_events()
        return HTMLResponse(
            _authority_operator_console_html(
                witness=asdict(witness),
                approval_chains=[asdict(chain) for chain in chains],
                obligations=[asdict(obligation) for obligation in obligations],
                escalation_events=list(escalations),
                operator_audit_events=list(authority_operator_audit_events[-100:]),
            )
        )

    @app.get("/capability-fabric/read-model")
    def capability_fabric_read_model(request: Request):
        _require_authority_operator(request)
        if capability_admission_gate is None:
            return {
                "enabled": False,
                "require_certified": None,
                "capsule_count": 0,
                "capability_count": 0,
                "artifact_count": 0,
                "installations": (),
                "capabilities": (),
                "domains": (),
            }
        return {
            "enabled": True,
            **capability_admission_gate.read_model(),
        }

    @app.post("/capability-fabric/capsule-admissions")
    async def capability_fabric_capsule_admission(request: Request):
        _require_authority_operator(request)
        if capability_admission_gate is None:
            raise HTTPException(503, detail="Capability fabric admission is not enabled")
        try:
            payload = await request.json()
            capsule, registry_entries, handoffs, require_production_ready = _capsule_admission_request(payload)
            outcome = install_certified_capsule_with_handoff_evidence(
                capsule=capsule,
                registry_entries=registry_entries,
                handoffs=handoffs,
                registry=capability_admission_gate.registry,
                clock=_clock,
                require_production_ready=require_production_ready,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, detail=str(exc)) from exc

        receipt = asdict(outcome.receipt)
        capability_capsule_admission_receipts.append(receipt)
        del capability_capsule_admission_receipts[:-500]
        return {
            "admission_receipt": receipt,
            "installation_record": outcome.installation_record.to_json_dict(),
            "compilation_result": outcome.compilation_result.to_json_dict(),
            "evidence_batch": _handoff_evidence_batch_payload(outcome.evidence_batch),
        }

    @app.get("/commands/{command_id}/closure")
    def command_closure(command_id: str):
        certificate = command_ledger.terminal_certificate_for(command_id)
        if certificate is None:
            raise HTTPException(404, detail="terminal closure certificate not found")
        events = [
            {
                "event_id": event.event_id,
                "previous_state": event.previous_state.value,
                "next_state": event.next_state.value,
                "event_hash": event.event_hash,
                "timestamp": event.timestamp,
            }
            for event in command_ledger.events_for(command_id)
        ]
        certificate_payload = asdict(certificate)
        return {
            "command_id": command_id,
            "terminal_certificate": certificate,
            "proof_coverage_witnesses": _closure_proof_coverage_witnesses(
                terminal_certificate=certificate_payload,
                events=events,
            ),
            "events": events,
        }

    @app.get("/capability-fabric/admission-audits")
    def capability_fabric_admission_audits(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        limit: int = 100,
    ):
        _require_authority_operator(request)
        audits = command_ledger.capability_admission_audits(
            tenant_id=tenant_id,
            status=status,
            limit=limit,
        )
        return {
            "admission_audits": audits,
            "count": len(audits),
        }

    @app.get("/capability-fabric/capsule-admission-receipts")
    def capability_fabric_capsule_admission_receipts(
        request: Request,
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        receipts = tuple(reversed(capability_capsule_admission_receipts))
        if status:
            receipts = tuple(
                receipt for receipt in receipts
                if receipt.get("admission_status") == status
            )
        bounded_limit = max(1, min(int(limit), 500))
        bounded_offset = max(0, int(offset))
        page_items = list(receipts)[bounded_offset:bounded_offset + bounded_limit]
        return {
            "capsule_admission_receipts": page_items,
            "count": len(page_items),
            "total": len(receipts),
            "status_filter": status,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }

    @app.get("/operator/capabilities/read-model")
    def operator_capabilities_read_model(
        request: Request,
        domain: str = "",
        risk_level: str = "",
        admission_status: str = "",
        audit_limit: int = 100,
        audit_offset: int = 0,
    ):
        _require_authority_operator(request)
        return build_operator_capability_read_model(
            capability_admission_gate=capability_admission_gate,
            command_ledger=command_ledger,
            plan_ledger=plan_ledger,
            domain=domain,
            risk_level=risk_level,
            admission_status=admission_status,
            audit_limit=audit_limit,
            audit_offset=audit_offset,
        )

    @app.get("/operator/capabilities", response_class=HTMLResponse)
    def operator_capabilities_console(
        request: Request,
        domain: str = "",
        risk_level: str = "",
        admission_status: str = "",
        audit_limit: int = 100,
        audit_offset: int = 0,
    ):
        _require_authority_operator(request)
        read_model = build_operator_capability_read_model(
            capability_admission_gate=capability_admission_gate,
            command_ledger=command_ledger,
            plan_ledger=plan_ledger,
            domain=domain,
            risk_level=risk_level,
            admission_status=admission_status,
            audit_limit=audit_limit,
            audit_offset=audit_offset,
        )
        return HTMLResponse(render_operator_capability_console(read_model))

    @app.get("/commands/{command_id}/capability-admission")
    def command_capability_admission(command_id: str, request: Request):
        _require_authority_operator(request)
        audit = command_ledger.capability_admission_audit_for(command_id)
        if audit is None:
            raise HTTPException(404, detail="command capability admission audit not found")
        return audit

    @app.get("/mcp/operator/read-model")
    def mcp_operator_read_model(
        request: Request,
        capability_id: str = "",
        audit_status: str = "",
        audit_limit: int = 100,
        audit_offset: int = 0,
    ):
        _require_authority_operator(request)
        return build_mcp_operator_read_model(
            capability_admission_gate=capability_admission_gate,
            authority_mesh_store=authority_mesh_store,
            mcp_executor=mcp_executor,
            mcp_gateway_import=mcp_gateway_import,
            capability_id=capability_id,
            audit_status=audit_status,
            audit_limit=audit_limit,
            audit_offset=audit_offset,
        )

    @app.get("/mcp/operator/evidence-bundles/{command_id}")
    def mcp_operator_evidence_bundle(command_id: str, request: Request):
        _require_authority_operator(request)
        if mcp_executor is None or not hasattr(mcp_executor, "export_evidence_bundle"):
            raise HTTPException(404, detail="MCP executor evidence export is not available")
        try:
            bundle = mcp_executor.export_evidence_bundle(command_id=command_id)
        except KeyError as exc:
            raise HTTPException(404, detail="MCP execution evidence bundle not found") from exc
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return asdict(bundle)

    @app.get("/capability-plans/read-model")
    def capability_plans_read_model(
        request: Request,
        recovery_action: str = "",
        failed_witness_limit: int = 100,
        failed_witness_offset: int = 0,
        recovery_attempt_status: str = "",
        recovery_attempt_limit: int = 100,
        recovery_attempt_offset: int = 0,
    ):
        _require_authority_operator(request)
        return {
            "enabled": True,
            **plan_ledger.read_model(
                recovery_action=recovery_action,
                failed_witness_limit=_bounded_read_model_limit(failed_witness_limit),
                failed_witness_offset=_bounded_read_model_offset(failed_witness_offset),
                recovery_attempt_status=recovery_attempt_status,
                recovery_attempt_limit=_bounded_read_model_limit(recovery_attempt_limit),
                recovery_attempt_offset=_bounded_read_model_offset(recovery_attempt_offset),
            ),
        }

    @app.get("/capability-plans/{plan_id}/closure")
    def capability_plan_closure(plan_id: str, request: Request):
        _require_authority_operator(request)
        certificate = plan_ledger.certificate_for(plan_id)
        if certificate is None:
            raise HTTPException(404, detail="plan terminal certificate not found")
        witnesses = plan_ledger.witnesses_for(plan_id)
        recovery_attempts = plan_ledger.recovery_attempts_for(plan_id)
        return {
            "plan_id": plan_id,
            "plan_terminal_certificate": asdict(certificate),
            "plan_evidence_bundle": asdict(plan_ledger.export_evidence_bundle(plan_id=plan_id)),
            "plan_witnesses": [asdict(witness) for witness in witnesses],
            "plan_recovery_attempts": [asdict(attempt) for attempt in recovery_attempts],
            "witness_count": len(witnesses),
            "recovery_attempt_count": len(recovery_attempts),
        }

    @app.post("/capability-plans/{plan_id}/recover")
    def recover_capability_plan(plan_id: str, request: Request):
        _require_authority_operator(request)
        try:
            response = router.recover_waiting_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(404, detail="failed plan witness not found") from exc
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        return {
            "status": "recovered" if response.metadata.get("plan_terminal_certificate_id") else "not_recovered",
            "response": asdict(response),
            "plan_id": plan_id,
            "plan_terminal_certificate_id": response.metadata.get("plan_terminal_certificate_id"),
            "plan_error": response.metadata.get("plan_error", ""),
        }

    @app.get("/observability/summary")
    def observability_summary(request: Request):
        _require_authority_operator(request)
        return router.observability_snapshot()

    @app.get("/observability/traces/{trace_id}")
    def observability_trace(trace_id: str, request: Request):
        _require_authority_operator(request)
        trace = router.observability_trace(trace_id)
        if trace is None:
            raise HTTPException(404, detail="trace not found")
        return trace

    @app.get("/anchors/latest")
    def latest_anchor():
        anchors = command_ledger.list_anchors(limit=1)
        if not anchors:
            raise HTTPException(404, detail="anchor not found")
        anchor = anchors[0]
        return {
            "anchor_id": anchor.anchor_id,
            "from_event_hash": anchor.from_event_hash,
            "to_event_hash": anchor.to_event_hash,
            "event_count": anchor.event_count,
            "merkle_root": anchor.merkle_root,
            "signature": f"hmac-sha256:{anchor.signature}",
            "signature_key_id": anchor.signature_key_id,
            "anchored_at": anchor.anchored_at,
        }

    @app.get("/evidence/bundles/{command_id}")
    def command_evidence_bundle(command_id: str, request: Request):
        _require_authority_operator(request)
        try:
            bundle = build_command_trust_bundle(
                command_ledger=command_ledger,
                command_id=command_id,
                deployment_id=_deployment_id(),
                commit_sha=_commit_sha(),
                signing_secret=os.environ.get("MULLU_TRUST_LEDGER_SECRET", "local-trust-ledger-secret"),
                signature_key_id=os.environ.get("MULLU_TRUST_LEDGER_KEY_ID", "trust-ledger-local"),
                clock=_clock,
            )
        except KeyError as exc:
            raise HTTPException(404, detail="command not found") from exc
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        return bundle.to_json_dict()

    # Store references for testing
    app.state.router = router
    app.state.command_ledger = command_ledger
    app.state.tenant_identity_store = tenant_identity_store
    app.state.authority_mesh_store = authority_mesh_store
    app.state.authority_obligation_mesh = authority_obligation_mesh
    app.state.authority_operator_audit_events = authority_operator_audit_events
    app.state.capability_capsule_admission_receipts = capability_capsule_admission_receipts
    app.state.session_mgr = session_mgr
    app.state.event_log = event_log
    app.state.capability_admission_gate = capability_admission_gate
    app.state.mcp_capability_entries = mcp_capability_entries
    app.state.mcp_executor = mcp_executor
    app.state.mcp_authority_records = mcp_authority_records
    app.state.mcp_gateway_import = mcp_gateway_import
    app.state.plan_ledger = plan_ledger
    app.state.observability_recorder = observability_recorder
    app.state.verifier = verifier

    return app


def _capsule_admission_request(
    payload: Any,
) -> tuple[DomainCapsule, tuple[CapabilityRegistryEntry, ...], tuple[CapabilityCertificationHandoff, ...], bool]:
    if not isinstance(payload, Mapping):
        raise ValueError("capsule_admission_request_must_be_object")
    capsule_payload = _required_mapping(payload, "capsule")
    raw_entries = payload.get("registry_entries")
    raw_handoffs = payload.get("handoffs")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("capsule_admission_registry_entries_required")
    if not isinstance(raw_handoffs, list) or not raw_handoffs:
        raise ValueError("capsule_admission_handoffs_required")
    return (
        DomainCapsule.from_mapping(capsule_payload),
        tuple(CapabilityRegistryEntry.from_mapping(_mapping_item(raw_entry, "registry_entries")) for raw_entry in raw_entries),
        tuple(_certification_handoff_from_mapping(_mapping_item(raw_handoff, "handoffs")) for raw_handoff in raw_handoffs),
        _payload_bool(payload, "require_production_ready", default=True),
    )


def _certification_handoff_from_mapping(payload: Mapping[str, Any]) -> CapabilityCertificationHandoff:
    bundle_payload = _required_mapping(payload, "maturity_evidence_bundle")
    raw_evidence_refs = payload.get("required_evidence_refs", ())
    if not isinstance(raw_evidence_refs, (list, tuple)):
        raise ValueError("capsule_admission_handoff_required_evidence_refs_must_be_array")
    return CapabilityCertificationHandoff(
        package_id=_required_text(payload, "package_id"),
        capability_id=_required_text(payload, "capability_id"),
        package_hash=_required_text(payload, "package_hash"),
        maturity_evidence_bundle=CapabilityCertificationEvidenceBundle.from_mapping(bundle_payload),
        required_evidence_refs=tuple(str(value) for value in raw_evidence_refs),
        handoff_hash=_required_text(payload, "handoff_hash"),
    )


def _handoff_evidence_batch_payload(batch: Any) -> dict[str, Any]:
    return {
        "registry_entries": tuple(entry.to_json_dict() for entry in batch.registry_entries),
        "installed_capability_ids": tuple(batch.installed_capability_ids),
        "handoff_hashes": tuple(batch.handoff_hashes),
        "batch_hash": batch.batch_hash,
    }


def _required_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_must_be_object")
    return value


def _mapping_item(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_items_must_be_objects")
    return value


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    if not value:
        raise ValueError(f"{field_name}_required")
    return value


def _payload_bool(payload: Mapping[str, Any], field_name: str, *, default: bool) -> bool:
    value = payload.get(field_name, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}_must_be_boolean")
    return value


def _authority_operator_console_html(
    *,
    witness: dict[str, Any],
    approval_chains: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
    escalation_events: list[dict[str, Any]],
    operator_audit_events: list[dict[str, Any]],
) -> str:
    """Render authority responsibility state as a small governed read model."""
    from html import escape

    def _cell(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        return escape(rendered)

    def _rows(records: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
        if not records:
            return f'<tr><td colspan="{len(columns)}">No records</td></tr>'
        return "\n".join(
            "<tr>" + "".join(f"<td>{_cell(record.get(column, ''))}</td>" for column in columns) + "</tr>"
            for record in records
        )

    chain_columns = ("chain_id", "command_id", "tenant_id", "status", "required_roles", "approvals_received")
    obligation_columns = (
        "obligation_id",
        "command_id",
        "tenant_id",
        "owner_team",
        "obligation_type",
        "status",
        "due_at",
    )
    escalation_columns = ("event_id", "obligation_id", "command_id", "tenant_id", "owner_team", "escalated_at")
    operator_audit_columns = (
        "event_id",
        "observed_at",
        "method",
        "path",
        "authorized",
        "credential_type",
        "tenant_id",
    )
    metric_items = "\n".join(
        f"<li><span>{escape(key.replace('_', ' ').title())}</span><strong>{_cell(value)}</strong></li>"
        for key, value in witness.items()
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Authority Operator Console</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f6f7f9; color: #1b1f24; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 32px 0 12px; font-size: 18px; }}
    p {{ margin: 0 0 20px; color: #57606a; }}
    ul {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; padding: 0; }}
    li {{ display: flex; justify-content: space-between; gap: 16px; list-style: none; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #eef1f4; font-weight: 700; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 20px; }}
    a {{ color: #0969da; }}
  </style>
</head>
<body>
<main>
  <h1>Mullu Authority Operator Console</h1>
  <p>Organizational responsibility witness for approval chains, obligations, and escalation debt.</p>
  <nav>
    <a href="/authority/responsibility">responsibility json</a>
    <a href="/authority/witness">witness json</a>
    <a href="/authority/approval-chains">approval chains json</a>
    <a href="/authority/obligations">obligations json</a>
    <a href="/authority/escalations">escalations json</a>
    <a href="/authority/operator-audit">operator audit json</a>
  </nav>
  <h2>Responsibility Witness</h2>
  <ul>{metric_items}</ul>
  <h2>Approval Chains</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in chain_columns)}</tr></thead>
    <tbody>{_rows(approval_chains, chain_columns)}</tbody>
  </table>
  <h2>Obligations</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in obligation_columns)}</tr></thead>
    <tbody>{_rows(obligations, obligation_columns)}</tbody>
  </table>
  <h2>Escalations</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in escalation_columns)}</tr></thead>
    <tbody>{_rows(escalation_events, escalation_columns)}</tbody>
  </table>
  <h2>Operator Audit</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in operator_audit_columns)}</tr></thead>
    <tbody>{_rows(operator_audit_events, operator_audit_columns)}</tbody>
  </table>
</main>
</body>
</html>"""


def _closure_proof_coverage_witnesses(
    *,
    terminal_certificate: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bind closure proof matrix claims to runtime witness references."""
    event_hashes = tuple(
        str(event["event_hash"])
        for event in events
        if event.get("event_hash")
    )
    witnesses: list[dict[str, Any]] = [
        {
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "command_lifecycle_events_are_hash_linked",
            "witness_type": "command_event_hash_chain",
            "witness_refs": event_hashes,
        },
        {
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "terminal_closure_requires_evidence_refs",
            "witness_type": "terminal_closure_certificate",
            "witness_ref": terminal_certificate["certificate_id"],
            "evidence_refs": tuple(terminal_certificate["evidence_refs"]),
        },
    ]
    response_evidence_closure_id = terminal_certificate.get("response_evidence_closure_id")
    if response_evidence_closure_id:
        witnesses.append({
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "successful_response_is_bound_to_response_evidence_closure",
            "witness_type": "response_evidence_closure",
            "witness_ref": response_evidence_closure_id,
        })
    return witnesses


def _gateway_request_receipt(
    *,
    channel: str,
    request: Request,
    body: bytes,
    message: Any | None,
) -> dict[str, Any]:
    """Normalize a request-bound proof envelope for gateway ingress."""
    safe_header_names = tuple(sorted(
        name.lower()
        for name in request.headers
        if not _sensitive_header_name(name)
    ))
    message_id = str(getattr(message, "message_id", "") or "")
    sender_id = str(getattr(message, "sender_id", "") or "")
    body_hash = sha256(body).hexdigest()
    receipt_payload = {
        "channel": channel,
        "method": request.method,
        "path": request.url.path,
        "message_id": message_id,
        "sender_id_hash": sha256(sender_id.encode()).hexdigest() if sender_id else "",
        "body_hash": body_hash,
        "safe_header_names": safe_header_names,
        "receipt_type": "gateway_request_receipt_v1",
    }
    receipt_hash = sha256(
        json.dumps(receipt_payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "receipt_id": f"gateway-request-{receipt_hash[:16]}",
        "receipt_hash": receipt_hash,
        **receipt_payload,
    }


def _sensitive_header_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("authorization", "secret", "signature", "token", "cookie"))


def _bounded_read_model_limit(limit: int, *, maximum: int = 500) -> int:
    """Return a positive bounded read-model page size."""
    return max(1, min(int(limit), maximum))


def _bounded_read_model_offset(offset: int) -> int:
    """Return a non-negative read-model offset."""
    return max(0, int(offset))


def _read_model_page(items: tuple[Any, ...], *, limit: int, offset: int) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Return a bounded read-model page and pagination metadata."""
    total = len(items)
    page = items[offset:offset + limit]
    next_offset = offset + len(page)
    return page, {
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset if next_offset < total else None,
    }


def _due_sort_key(timestamp: str) -> str:
    """Return a stable sortable timestamp key for responsibility read models."""
    from datetime import datetime, timezone

    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.max.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


# Default app instance
app = create_gateway_app()
