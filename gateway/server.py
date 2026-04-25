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
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from gateway.channels.discord import DiscordAdapter
from gateway.channels.slack import SlackAdapter
from gateway.channels.telegram import TelegramAdapter
from gateway.channels.web import WebChatAdapter
from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.authority_obligation_mesh import (
    AuthorityObligationMesh,
    build_authority_obligation_mesh_store_from_env,
)
from gateway.capability_isolation import build_isolated_capability_executor_from_env
from gateway.command_spine import build_command_ledger_from_env
from gateway.event_log import WebhookEventLog
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

    app = FastAPI(title="Mullu Gateway", version="1.0.0")
    event_log = WebhookEventLog(clock=_clock)
    verifier = WebhookVerifier()
    command_ledger = build_command_ledger_from_env(clock=_clock)
    tenant_identity_store = build_tenant_identity_store_from_env(clock=_clock)
    authority_mesh_store = build_authority_obligation_mesh_store_from_env()
    authority_obligation_mesh = AuthorityObligationMesh(
        commands=command_ledger,
        clock=_clock,
        store=authority_mesh_store,
    )
    skill_dispatcher = build_skill_dispatcher_from_platform(platform)
    isolated_capability_executor = build_isolated_capability_executor_from_env()
    router = GatewayRouter(
        platform=platform,
        command_ledger=command_ledger,
        tenant_identity_store=tenant_identity_store,
        authority_obligation_mesh=authority_obligation_mesh,
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
        import json
        import time as _time
        _t0 = _time.monotonic()
        payload = json.loads(body)
        msg = whatsapp.parse_message(payload)
        if msg is None:
            event_log.record(channel="whatsapp", sender_id="", status="ignored",
                             body=body.decode("utf-8", errors="replace")[:200],
                             headers=dict(request.headers))
            return JSONResponse({"status": "ignored"})
        response = router.handle_message(msg)
        event_log.record(channel="whatsapp", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body})

    # ── Telegram Webhook ──

    @app.post("/webhook/telegram")
    async def telegram_receive(request: Request):
        """Telegram Bot API webhook (POST)."""
        if telegram is None:
            raise HTTPException(503, detail="Telegram not configured")
        import json
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
        if msg is None:
            event_log.record(channel="telegram", sender_id="", status="ignored",
                             headers=dict(request.headers))
            return JSONResponse({"status": "ignored"})
        response = router.handle_message(msg)
        event_log.record(channel="telegram", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body})

    # ── Slack Events API ──

    @app.post("/webhook/slack")
    async def slack_receive(request: Request):
        """Slack Events API webhook (POST)."""
        if slack is None:
            raise HTTPException(503, detail="Slack not configured")
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        import json
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
        if msg is None:
            event_log.record(channel="slack", sender_id="", status="ignored",
                             headers=dict(request.headers))
            return JSONResponse({"status": "ignored"})
        import time as _time
        _t0 = _time.monotonic()
        response = router.handle_message(msg)
        event_log.record(channel="slack", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body})

    # ── Discord Interactions ──

    @app.post("/webhook/discord")
    async def discord_receive(request: Request):
        """Discord interaction webhook (POST)."""
        if discord is None:
            raise HTTPException(503, detail="Discord not configured")
        import json
        body_str = (await request.body()).decode("utf-8")
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
        if msg is None:
            event_log.record(channel="discord", sender_id="", status="ignored",
                             headers=dict(request.headers))
            return JSONResponse({"status": "ignored"})
        import time as _time
        _t0 = _time.monotonic()
        response = router.handle_message(msg)
        # Discord interaction response format
        event_log.record(channel="discord", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({
            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
            "data": {"content": response.body},
        })

    # ── Web Chat ──

    @app.post("/webhook/web")
    async def web_receive(request: Request):
        """Web chat message endpoint (POST)."""
        import json
        try:
            payload = json.loads(await request.body())
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        session_token = request.headers.get("X-Session-Token", "")
        if not session_token or len(session_token) > 512:
            raise HTTPException(401, detail="Missing or invalid session token")
        msg = web.parse_message(payload, session_token=session_token)
        if msg is None:
            raise HTTPException(400, detail="Invalid message")
        response = router.handle_message(msg)
        return JSONResponse({
            "status": "ok",
            "message_id": response.message_id,
            "body": response.body,
            "governed": response.governed,
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

    @app.get("/authority/witness")
    def authority_witness():
        return asdict(authority_obligation_mesh.responsibility_witness())

    @app.get("/authority/approval-chains")
    def authority_approval_chains(
        tenant_id: str = "",
        status: str = "",
        command_id: str = "",
    ):
        chains = authority_mesh_store.list_approval_chains()
        if tenant_id:
            chains = tuple(chain for chain in chains if chain.tenant_id == tenant_id)
        if status:
            chains = tuple(chain for chain in chains if chain.status.value == status)
        if command_id:
            chains = tuple(chain for chain in chains if chain.command_id == command_id)
        return {
            "approval_chains": [asdict(chain) for chain in chains],
            "count": len(chains),
        }

    @app.get("/commands/{command_id}/authority")
    def command_authority(command_id: str):
        chain = authority_obligation_mesh.approval_chain_for(command_id)
        obligations = authority_obligation_mesh.obligations_for(command_id)
        if chain is None and not obligations:
            raise HTTPException(404, detail="authority records not found")
        return {
            "command_id": command_id,
            "approval_chain": asdict(chain) if chain is not None else None,
            "obligations": [asdict(obligation) for obligation in obligations],
        }

    @app.get("/authority/obligations")
    def authority_obligations(
        tenant_id: str = "",
        status: str = "",
        command_id: str = "",
        owner_id: str = "",
        owner_team: str = "",
    ):
        obligations = authority_mesh_store.list_obligations(command_id)
        if tenant_id:
            obligations = tuple(obligation for obligation in obligations if obligation.tenant_id == tenant_id)
        if status:
            obligations = tuple(obligation for obligation in obligations if obligation.status.value == status)
        if owner_id:
            obligations = tuple(obligation for obligation in obligations if obligation.owner_id == owner_id)
        if owner_team:
            obligations = tuple(obligation for obligation in obligations if obligation.owner_team == owner_team)
        return {
            "obligations": [asdict(obligation) for obligation in obligations],
            "count": len(obligations),
        }

    @app.post("/authority/obligations/{obligation_id}/satisfy")
    def satisfy_authority_obligation(obligation_id: str, payload: dict[str, Any]):
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
    def escalate_overdue_authority_obligations():
        obligations = authority_obligation_mesh.escalate_overdue()
        return {
            "status": "escalated",
            "obligations": [asdict(obligation) for obligation in obligations],
            "count": len(obligations),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.get("/authority/escalations")
    def authority_escalations(tenant_id: str = "", command_id: str = ""):
        events = authority_mesh_store.list_escalation_events()
        if tenant_id:
            events = tuple(event for event in events if event.get("tenant_id") == tenant_id)
        if command_id:
            events = tuple(event for event in events if event.get("command_id") == command_id)
        return {
            "escalation_events": list(events),
            "count": len(events),
        }

    @app.get("/commands/{command_id}/closure")
    def command_closure(command_id: str):
        certificate = command_ledger.terminal_certificate_for(command_id)
        if certificate is None:
            raise HTTPException(404, detail="terminal closure certificate not found")
        return {
            "command_id": command_id,
            "terminal_certificate": certificate,
            "events": [
                {
                    "event_id": event.event_id,
                    "previous_state": event.previous_state.value,
                    "next_state": event.next_state.value,
                    "event_hash": event.event_hash,
                    "timestamp": event.timestamp,
                }
                for event in command_ledger.events_for(command_id)
            ],
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
    app.state.session_mgr = session_mgr
    app.state.event_log = event_log
    app.state.verifier = verifier

    return app


# Default app instance
app = create_gateway_app()
