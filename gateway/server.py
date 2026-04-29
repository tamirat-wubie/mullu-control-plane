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
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from gateway.channels.discord import DiscordAdapter
from gateway.channels.slack import SlackAdapter
from gateway.channels.telegram import TelegramAdapter
from gateway.channels.web import WebChatAdapter
from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.authority_obligation_mesh import (
    AuthorityObligationMesh,
    build_authority_obligation_mesh_store_from_env,
)
from gateway.capability_fabric import build_capability_admission_gate_from_env
from gateway.capability_isolation import build_isolated_capability_executor_from_env
from gateway.command_spine import build_command_ledger_from_env
from gateway.conformance import issue_conformance_certificate
from gateway.event_log import WebhookEventLog
from gateway.plan_ledger import build_capability_plan_ledger_from_env
from gateway.router import GatewayRouter
from gateway.session import SessionManager
from gateway.skill_dispatch import build_skill_dispatcher_from_platform
from gateway.signature_verification import (
    ChannelVerifierConfig, VerificationMethod, WebhookVerifier,
)
from gateway.tenant_identity import build_tenant_identity_store_from_env

_log = logging.getLogger(__name__)


def create_gateway_app(platform: Any = None) -> FastAPI:
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
    authority_operator_audit_events: list[dict[str, Any]] = []
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
    capability_admission_gate = build_capability_admission_gate_from_env(clock=_clock)
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
    skill_dispatcher = build_skill_dispatcher_from_platform(platform)
    isolated_capability_executor = build_isolated_capability_executor_from_env()
    router = GatewayRouter(
        platform=platform,
        command_ledger=command_ledger,
        tenant_identity_store=tenant_identity_store,
        authority_obligation_mesh=authority_obligation_mesh,
        plan_ledger=plan_ledger,
        skill_dispatcher=skill_dispatcher,
        defer_approved_execution=defer_approved_execution,
        environment=gateway_env,
        isolated_capability_executor=isolated_capability_executor,
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
            environment=gateway_env,
            signing_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", "local-runtime-conformance-secret"),
            signature_key_id=os.environ.get("MULLU_RUNTIME_CONFORMANCE_KEY_ID", "runtime-conformance-local"),
            runtime_witness_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            runtime_witness_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )
        return certificate.to_json_dict()

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

    @app.get("/commands/{command_id}/capability-admission")
    def command_capability_admission(command_id: str, request: Request):
        _require_authority_operator(request)
        audit = command_ledger.capability_admission_audit_for(command_id)
        if audit is None:
            raise HTTPException(404, detail="command capability admission audit not found")
        return audit

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

    # Store references for testing
    app.state.router = router
    app.state.command_ledger = command_ledger
    app.state.tenant_identity_store = tenant_identity_store
    app.state.authority_mesh_store = authority_mesh_store
    app.state.authority_obligation_mesh = authority_obligation_mesh
    app.state.authority_operator_audit_events = authority_operator_audit_events
    app.state.session_mgr = session_mgr
    app.state.event_log = event_log
    app.state.capability_admission_gate = capability_admission_gate
    app.state.plan_ledger = plan_ledger
    app.state.verifier = verifier

    return app


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


# Default app instance
app = create_gateway_app()
