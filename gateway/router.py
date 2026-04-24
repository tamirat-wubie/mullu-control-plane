"""Gateway Router — Unified message ingress through governance.

Purpose: Receives normalized messages from channel adapters, resolves tenant
    identity, opens a GovernedSession, executes through the LLM pipeline,
    and returns the response through the originating channel.
Invariants:
  - Every message flows through GovernedSession (no bypass path).
  - Tenant is resolved from channel user identity, never from message content.
  - Failed governance checks return structured denial to the user.
  - Every message produces an audit trail entry.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from gateway.approval import ApprovalRequest, ApprovalRouter, ApprovalStatus
from gateway.authority import evaluate_approval_authority
from gateway.command_spine import CommandAnchor, CommandEnvelope, CommandLedger, CommandState, canonical_hash
from gateway.dedup import MessageDeduplicator
from gateway.skill_dispatch import SkillDispatcher, SkillIntent, detect_intent
from gateway.tenant_identity import InMemoryTenantIdentityStore, TenantIdentityStore, TenantMapping


@dataclass(frozen=True, slots=True)
class GatewayMessage:
    """Canonical inbound message from any channel."""

    message_id: str
    channel: str  # "whatsapp", "telegram", "slack", "discord", "web"
    sender_id: str  # Channel-specific user ID (phone number, user ID, etc.)
    body: str
    conversation_id: str = ""
    attachments: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    received_at: str = ""


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    """Response to send back through the originating channel."""

    message_id: str
    channel: str
    recipient_id: str
    body: str
    governed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(Protocol):
    """Protocol for channel-specific message handling."""

    @property
    def channel_name(self) -> str: ...

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool: ...


class GatewayRouter:
    """Routes messages from channels through governed execution.

    Flow:
    1. Receive GatewayMessage from channel adapter
    2. Resolve tenant from channel user identity
    3. Open GovernedSession
    4. Execute LLM call with message as prompt
    5. Return response through originating channel

    All operations are governed — no bypass path.
    """

    def __init__(
        self,
        *,
        platform: Any,  # Platform instance from governed_session.py
        clock: Callable[[], str] | None = None,
        approval_router: ApprovalRouter | None = None,
        skill_dispatcher: SkillDispatcher | None = None,
        deduplicator: MessageDeduplicator | None = None,
        command_ledger: CommandLedger | None = None,
        tenant_identity_store: TenantIdentityStore | None = None,
        defer_approved_execution: bool = False,
    ) -> None:
        self._platform = platform
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._approval = approval_router or ApprovalRouter(clock=self._clock)
        self._skills = skill_dispatcher or SkillDispatcher()
        self._dedup = deduplicator or MessageDeduplicator()
        self._commands = command_ledger or CommandLedger(clock=self._clock)
        self._tenant_identities = tenant_identity_store or InMemoryTenantIdentityStore(clock=self._clock)
        self._defer_approved_execution = defer_approved_execution
        self._channels: dict[str, ChannelAdapter] = {}
        self._message_count = 0
        self._duplicate_count = 0
        self._error_count = 0

    def register_channel(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._channels[adapter.channel_name] = adapter

    def register_tenant_mapping(self, mapping: TenantMapping) -> None:
        """Map a channel user identity to a tenant."""
        self._tenant_identities.save(mapping)

    def resolve_tenant(self, channel: str, sender_id: str) -> TenantMapping | None:
        """Resolve tenant from channel user identity."""
        return self._tenant_identities.resolve(channel, sender_id)

    def _parse_approval_command(self, body: str) -> tuple[str, bool] | None:
        """Parse a channel-native approval callback command."""
        normalized = body.strip()
        if normalized.startswith("approve:"):
            request_id = normalized.split(":", 1)[1].strip()
            if request_id:
                return request_id, True
        if normalized.startswith("deny:"):
            request_id = normalized.split(":", 1)[1].strip()
            if request_id:
                return request_id, False
        return None

    def _approval_status_text(self, status: ApprovalStatus) -> str:
        if status == ApprovalStatus.APPROVED:
            return "approved"
        if status == ApprovalStatus.EXPIRED:
            return "expired"
        return "denied"

    def _send_response(self, response: GatewayResponse) -> None:
        """Send a response through its registered channel adapter when present."""
        adapter = self._channels.get(response.channel)
        if adapter is None:
            return
        try:
            adapter.send(response.recipient_id, response.body)
        except Exception:
            pass

    def _intent_name(self, intent: SkillIntent | None) -> str:
        """Return the canonical command intent string."""
        if intent is None:
            return "llm_completion"
        return f"{intent.skill}.{intent.action}"

    def _command_payload(self, message: GatewayMessage, intent: SkillIntent | None) -> dict[str, Any]:
        """Build the canonical payload preserved across approval wait/resume."""
        payload: dict[str, Any] = {
            "message_id": message.message_id,
            "channel": message.channel,
            "sender_id": message.sender_id,
            "body": message.body,
            "conversation_id": message.conversation_id,
            "attachments": list(message.attachments),
            "metadata": dict(message.metadata),
        }
        if intent is not None:
            payload["skill_intent"] = {
                "skill": intent.skill,
                "action": intent.action,
                "params": dict(intent.params),
            }
        return payload

    def _create_command(
        self,
        message: GatewayMessage,
        mapping: TenantMapping,
        intent: SkillIntent | None,
    ) -> CommandEnvelope:
        """Create and tenant-bind the command for a non-approval message."""
        idempotency_key = canonical_hash({
            "channel": message.channel,
            "sender_id": message.sender_id,
            "message_id": message.message_id,
        })
        command = self._commands.create_command(
            tenant_id=mapping.tenant_id,
            actor_id=mapping.identity_id,
            source=message.channel,
            conversation_id=message.conversation_id,
            idempotency_key=idempotency_key,
            intent=self._intent_name(intent),
            payload=self._command_payload(message, intent),
        )
        self._commands.transition(command.command_id, CommandState.NORMALIZED)
        tenant_bound = self._commands.transition(command.command_id, CommandState.TENANT_BOUND)
        self._commands.bind_governed_action(tenant_bound.command_id)
        governed = self._commands.get(tenant_bound.command_id)
        if governed is None:
            raise RuntimeError("governed action binding lost command")
        return governed

    def _skill_intent_from_command(self, command: CommandEnvelope) -> SkillIntent | None:
        """Rebuild the stored skill intent without reclassifying message text."""
        raw = command.redacted_payload.get("skill_intent")
        if not isinstance(raw, dict):
            return None
        skill = raw.get("skill")
        action = raw.get("action")
        params = raw.get("params", {})
        if not isinstance(skill, str) or not isinstance(action, str) or not isinstance(params, dict):
            return None
        return SkillIntent(skill, action, dict(params))

    def _execute_command(self, command: CommandEnvelope, *, recipient_id: str) -> GatewayResponse:
        """Execute an allowed command through the stored canonical payload."""
        governed_action = self._commands.governed_action_for(command.command_id)
        if governed_action is None:
            self._error_count += 1
            self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                detail={"cause": "missing_governed_action"},
            )
            return GatewayResponse(
                message_id=self._gen_id("resp", command.command_id),
                channel=command.source,
                recipient_id=recipient_id,
                body="This action cannot execute because its governed action contract is missing.",
                governed=True,
                metadata={"error": "missing_governed_action", "command_id": command.command_id},
            )
        if governed_action.risk_tier == "high" and not governed_action.predicted_effect_hash:
            self._error_count += 1
            self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                risk_tier=governed_action.risk_tier,
                detail={"cause": "missing_effect_prediction"},
            )
            return GatewayResponse(
                message_id=self._gen_id("resp", command.command_id),
                channel=command.source,
                recipient_id=recipient_id,
                body="This high-risk action cannot execute because its predicted effect contract is missing.",
                governed=True,
                metadata={"error": "missing_effect_prediction", "command_id": command.command_id},
            )
        if (
            governed_action.risk_tier == "high"
            and (not governed_action.rollback_plan_hash or not self._commands.recovery_plan_for(command.command_id))
        ):
            self._error_count += 1
            self._commands.transition(
                command.command_id,
                CommandState.REQUIRES_REVIEW,
                risk_tier=governed_action.risk_tier,
                detail={"cause": "missing_recovery_plan"},
            )
            return GatewayResponse(
                message_id=self._gen_id("resp", command.command_id),
                channel=command.source,
                recipient_id=recipient_id,
                body="This high-risk action requires a rollback or compensation plan before execution.",
                governed=True,
                metadata={"error": "missing_recovery_plan", "command_id": command.command_id},
            )
        body = str(command.redacted_payload.get("body", ""))
        try:
            session = self._platform.connect(
                identity_id=command.actor_id,
                tenant_id=command.tenant_id,
            )
        except PermissionError:
            self._error_count += 1
            self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                detail={"cause": "platform_connect_denied"},
            )
            return GatewayResponse(
                message_id=self._gen_id("resp", command.command_id),
                channel=command.source,
                recipient_id=recipient_id,
                body="Access denied.",
                governed=True,
                metadata={"error": "access_denied", "command_id": command.command_id},
            )

        try:
            self._commands.transition(command.command_id, CommandState.BUDGET_RESERVED, budget_decision="session")
            self._commands.transition(command.command_id, CommandState.DISPATCHED, tool_name=command.intent)
            skill_intent = self._skill_intent_from_command(command)
            if skill_intent is not None:
                skill_result = self._skills.dispatch(skill_intent, command.tenant_id, command.actor_id)
                if skill_result is not None:
                    response_body = skill_result.get("response", "Skill executed.")
                    self._commands.transition(
                        command.command_id,
                        CommandState.OBSERVED,
                        tool_name=command.intent,
                        output=skill_result,
                    )
                    reconciliation = self._commands.observe_and_reconcile_effect(
                        command.command_id,
                        output=skill_result,
                    )
                    if not reconciliation.reconciled:
                        self._error_count += 1
                        return GatewayResponse(
                            message_id=self._gen_id("resp", command.command_id),
                            channel=command.source,
                            recipient_id=recipient_id,
                            body="This action could not be committed because observed effects did not match prediction.",
                            governed=True,
                            metadata={
                                "error": "effect_reconciliation_failed",
                                "command_id": command.command_id,
                                "mismatch_reason": reconciliation.mismatch_reason,
                            },
                    )
                    self._commands.transition(command.command_id, CommandState.VERIFIED, detail={"verifier": "skill_dispatch"})
                    self._commands.transition(command.command_id, CommandState.COMMITTED)
                    claim = self._commands.record_operational_claim(
                        command.command_id,
                        text=f"Command {command.intent} completed.",
                        verified=True,
                    )
                    response = GatewayResponse(
                        message_id=self._gen_id("resp", command.command_id),
                        channel=command.source,
                        recipient_id=recipient_id,
                        body=response_body,
                        governed=True,
                        metadata={
                            **skill_result,
                            "command_id": command.command_id,
                            "claims": [asdict(claim)],
                            "evidence": [asdict(record) for record in self._commands.evidence_for(command.command_id)],
                        },
                    )
                    self._commands.transition(
                        command.command_id,
                        CommandState.RESPONDED,
                        output={"body": response_body},
                    )
                    return response

            result = session.llm(body)
            response_body = result.content if result.succeeded else f"I couldn't process that: {result.error}"
            self._commands.transition(
                command.command_id,
                CommandState.OBSERVED,
                tool_name="llm_completion",
                output={"succeeded": bool(result.succeeded), "content": response_body},
            )
            reconciliation = self._commands.observe_and_reconcile_effect(
                command.command_id,
                output={"succeeded": bool(result.succeeded), "content": response_body},
            )
            if not reconciliation.reconciled:
                self._error_count += 1
                return GatewayResponse(
                    message_id=self._gen_id("resp", command.command_id),
                    channel=command.source,
                    recipient_id=recipient_id,
                    body="This action could not be committed because observed effects did not match prediction.",
                    governed=True,
                    metadata={
                        "error": "effect_reconciliation_failed",
                        "command_id": command.command_id,
                        "mismatch_reason": reconciliation.mismatch_reason,
                    },
            )
            self._commands.transition(command.command_id, CommandState.VERIFIED, detail={"verifier": "governed_session"})
            self._commands.transition(command.command_id, CommandState.COMMITTED)
            claim = self._commands.record_operational_claim(
                command.command_id,
                text=f"Command {command.intent} completed.",
                verified=bool(result.succeeded),
            )
            response = GatewayResponse(
                message_id=self._gen_id("resp", command.command_id),
                channel=command.source,
                recipient_id=recipient_id,
                body=response_body,
                governed=True,
                metadata={
                    "command_id": command.command_id,
                    "claims": [asdict(claim)],
                    "evidence": [asdict(record) for record in self._commands.evidence_for(command.command_id)],
                },
            )
            self._commands.transition(
                command.command_id,
                CommandState.RESPONDED,
                output={"body": response_body},
            )
            return response
        except ValueError:
            self._commands.transition(command.command_id, CommandState.DENIED, detail={"cause": "content_blocked"})
            return GatewayResponse(
                message_id=self._gen_id("resp", command.command_id),
                channel=command.source,
                recipient_id=recipient_id,
                body="I can't process that request due to safety policies.",
                governed=True,
                metadata={"error": "content_blocked", "command_id": command.command_id},
            )
        except RuntimeError:
            self._error_count += 1
            response_body = "Service temporarily unavailable."
        except Exception:
            self._error_count += 1
            response_body = "An error occurred. Please try again."
        finally:
            try:
                session.close()
            except Exception:
                pass

        self._commands.transition(command.command_id, CommandState.OBSERVED, output={"error": response_body})
        response = GatewayResponse(
            message_id=self._gen_id("resp", command.command_id),
            channel=command.source,
            recipient_id=recipient_id,
            body=response_body,
            governed=True,
            metadata={"command_id": command.command_id},
        )
        self._commands.transition(command.command_id, CommandState.RESPONDED, output={"body": response_body})
        return response

    def _approval_response(
        self,
        request_id: str,
        result: ApprovalRequest,
        *,
        recipient_id: str | None = None,
    ) -> GatewayResponse:
        """Build a governed approval-resolution response."""
        status = self._approval_status_text(result.status)
        return GatewayResponse(
            message_id=self._gen_id("apr-resp", request_id),
            channel=result.channel,
            recipient_id=recipient_id or result.identity_id,
            body=f"Request {request_id} has been {status}.",
            governed=True,
            metadata={"approval_resolved": True, "status": status},
        )

    def _approval_queued_response(
        self,
        request_id: str,
        result: ApprovalRequest,
        *,
        recipient_id: str,
    ) -> GatewayResponse:
        """Build an approval response for worker-deferred command dispatch."""
        return GatewayResponse(
            message_id=self._gen_id("apr-resp", request_id),
            channel=result.channel,
            recipient_id=recipient_id,
            body=f"Request {request_id} has been approved and queued for execution.",
            governed=True,
            metadata={
                "approval_resolved": True,
                "status": "approved",
                "request_id": request_id,
                "command_id": result.command_id,
                "queued": True,
            },
        )

    def _handle_approval_message(
        self,
        message: GatewayMessage,
        mapping: TenantMapping,
        request_id: str,
        approved: bool,
    ) -> GatewayResponse:
        """Resolve a channel-native approval callback for the mapped identity."""
        request = self._approval.lookup_request(request_id)
        if request is None:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("apr-resp", request_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="This approval request is no longer available.",
                governed=True,
                metadata={"error": "approval_not_found"},
            )
        if request.status == ApprovalStatus.EXPIRED:
            return self._approval_response(request_id, request, recipient_id=message.sender_id)
        authority = evaluate_approval_authority(
            request=request,
            resolver=mapping,
            governed_action=self._commands.governed_action_for(request.command_id) if request.command_id else None,
        )
        if not authority.allowed:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("apr-resp", request_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="You are not allowed to resolve this approval request.",
                governed=True,
                metadata={
                    "error": "approval_context_denied",
                    "authority_reason": authority.reason,
                    "required_roles": authority.required_roles,
                    "resolver_roles": authority.resolver_roles,
                },
            )
        result = self._approval.resolve(request_id, approved=approved, resolved_by=mapping.identity_id)
        if result is None:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("apr-resp", request_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="This approval request is no longer available.",
                governed=True,
                metadata={"error": "approval_not_found"},
            )
        if result.command_id:
            next_state = CommandState.APPROVED if result.status == ApprovalStatus.APPROVED else CommandState.DENIED
            self._commands.transition(
                result.command_id,
                next_state,
                approval_id=result.request_id,
                risk_tier=result.risk_tier.value,
            )
            if result.status == ApprovalStatus.APPROVED:
                command = self._commands.get(result.command_id)
                if command is not None:
                    if self._defer_approved_execution:
                        return self._approval_queued_response(
                            request_id,
                            result,
                            recipient_id=message.sender_id,
                        )
                    response = self._execute_command(command, recipient_id=message.sender_id)
                    return GatewayResponse(
                        message_id=response.message_id,
                        channel=response.channel,
                        recipient_id=response.recipient_id,
                        body=f"Request {request_id} has been approved. {response.body}",
                        governed=True,
                        metadata={
                            **response.metadata,
                            "approval_resolved": True,
                            "status": "approved",
                            "request_id": request_id,
                            "command_id": result.command_id,
                        },
                    )
        return self._approval_response(request_id, result, recipient_id=message.sender_id)

    def handle_message(self, message: GatewayMessage) -> GatewayResponse:
        """Process an inbound message through the full governance pipeline.

        This is the main entry point. Every message goes through:
        dedup → tenant resolution → session → content safety → LLM → PII redaction → audit → proof.
        """
        self._message_count += 1

        # 0. Deduplication — return cached response for retried webhooks
        dedup_result = self._dedup.check(message.channel, message.sender_id, message.message_id)
        if dedup_result.is_duplicate:
            self._duplicate_count += 1
            return dedup_result.cached_response

        # 1. Resolve tenant
        mapping = self.resolve_tenant(message.channel, message.sender_id)
        if mapping is None:
            self._error_count += 1
            resp = GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="I don't recognize your account. Please register first.",
                governed=True,
                metadata={"error": "tenant_not_found"},
            )
            self._dedup.record(message.channel, message.sender_id, message.message_id, resp)
            return resp

        approval_command = self._parse_approval_command(message.body)
        if approval_command is not None:
            request_id, approved = approval_command
            response = self._handle_approval_message(message, mapping, request_id, approved)
            adapter = self._channels.get(message.channel)
            if adapter is not None:
                try:
                    adapter.send(message.sender_id, response.body)
                except Exception:
                    pass
            self._dedup.record(message.channel, message.sender_id, message.message_id, response)
            return response

        intent = detect_intent(message.body)
        command = self._create_command(message, mapping, intent)
        self._commands.transition(command.command_id, CommandState.POLICY_EVALUATED)
        approval = self._approval.request_approval(
            tenant_id=mapping.tenant_id,
            identity_id=mapping.identity_id,
            channel=message.channel,
            action_description=command.intent,
            body=message.body,
            command_id=command.command_id,
            payload_hash=command.payload_hash,
            policy_version=command.policy_version,
        )
        if approval.status == ApprovalStatus.PENDING:
            self._commands.transition(
                command.command_id,
                CommandState.PENDING_APPROVAL,
                approval_id=approval.request_id,
                risk_tier=approval.risk_tier.value,
            )
            resp = GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body=f"This action requires approval (risk: {approval.risk_tier.value}). "
                     f"Request ID: {approval.request_id}",
                governed=True,
                metadata={
                    "approval_required": True,
                    "request_id": approval.request_id,
                    "command_id": command.command_id,
                    "payload_hash": command.payload_hash,
                },
            )
            self._dedup.record(message.channel, message.sender_id, message.message_id, resp)
            return resp

        self._commands.transition(
            command.command_id,
            CommandState.ALLOWED,
            approval_id=approval.request_id,
            risk_tier=approval.risk_tier.value,
        )
        response = self._execute_command(command, recipient_id=message.sender_id)
        self._send_response(response)
        self._dedup.record(message.channel, message.sender_id, message.message_id, response)
        return response

    def process_ready_commands(
        self,
        *,
        worker_id: str = "gateway-worker",
        limit: int = 10,
        lease_seconds: int = 300,
    ) -> list[GatewayResponse]:
        """Claim and execute ready commands for worker-driven dispatch."""
        responses: list[GatewayResponse] = []
        commands = self._commands.claim_ready_commands(
            worker_id=worker_id,
            limit=limit,
            lease_seconds=lease_seconds,
        )
        for command in commands:
            recipient_id = str(command.redacted_payload.get("sender_id", command.actor_id))
            try:
                response = self._execute_command(command, recipient_id=recipient_id)
                self._send_response(response)
                responses.append(response)
            finally:
                self._commands.release_command(command.command_id, worker_id)
        return responses

    def anchor_command_events(
        self,
        *,
        signing_secret: str,
        signature_key_id: str = "local",
    ) -> CommandAnchor | None:
        """Sign and persist an anchor for unanchored command events."""
        return self._commands.anchor_unanchored_events(
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
        )

    def handle_approval_callback(self, request_id: str, approved: bool, resolved_by: str = "user") -> GatewayResponse | None:
        """Handle an approval callback from a channel button press.

        Returns a GatewayResponse if the approval resolves successfully, None otherwise.
        """
        result = self._approval.resolve(request_id, approved=approved, resolved_by=resolved_by)
        if result is None:
            return None
        if result.command_id:
            next_state = CommandState.APPROVED if result.status == ApprovalStatus.APPROVED else CommandState.DENIED
            self._commands.transition(
                result.command_id,
                next_state,
                approval_id=result.request_id,
                risk_tier=result.risk_tier.value,
            )
            if result.status == ApprovalStatus.APPROVED:
                command = self._commands.get(result.command_id)
                if command is not None:
                    if self._defer_approved_execution:
                        return self._approval_queued_response(
                            request_id,
                            result,
                            recipient_id=result.identity_id,
                        )
                    response = self._execute_command(command, recipient_id=result.identity_id)
                    return GatewayResponse(
                        message_id=response.message_id,
                        channel=response.channel,
                        recipient_id=response.recipient_id,
                        body=f"Request {request_id} has been approved. {response.body}",
                        governed=True,
                        metadata={
                            **response.metadata,
                            "approval_resolved": True,
                            "status": "approved",
                            "request_id": request_id,
                            "command_id": result.command_id,
                        },
                    )
        return self._approval_response(request_id, result)

    def handle_external_approval_callback(
        self,
        request_id: str,
        *,
        approved: bool,
        resolver_channel: str,
        resolver_sender_id: str,
    ) -> GatewayResponse | None:
        """Handle an HTTP approval callback with explicit resolver identity."""
        request = self._approval.lookup_request(request_id)
        if request is None:
            return None
        if request.status == ApprovalStatus.EXPIRED:
            return self._approval_response(request_id, request, recipient_id=resolver_sender_id)

        resolver = self.resolve_tenant(resolver_channel, resolver_sender_id)
        if resolver is None:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("apr-resp", request_id),
                channel=request.channel,
                recipient_id=resolver_sender_id,
                body="You are not allowed to resolve this approval request.",
                governed=True,
                metadata={
                    "error": "approval_context_denied",
                    "authority_reason": "resolver_identity_not_found",
                    "required_roles": (),
                    "resolver_roles": (),
                    "request_id": request_id,
                },
            )

        authority = evaluate_approval_authority(
            request=request,
            resolver=resolver,
            governed_action=self._commands.governed_action_for(request.command_id) if request.command_id else None,
        )
        if not authority.allowed:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("apr-resp", request_id),
                channel=request.channel,
                recipient_id=resolver_sender_id,
                body="You are not allowed to resolve this approval request.",
                governed=True,
                metadata={
                    "error": "approval_context_denied",
                    "authority_reason": authority.reason,
                    "required_roles": authority.required_roles,
                    "resolver_roles": authority.resolver_roles,
                    "request_id": request_id,
                },
            )

        result = self._approval.resolve(request_id, approved=approved, resolved_by=resolver.identity_id)
        if result is None:
            return None
        if result.command_id:
            next_state = CommandState.APPROVED if result.status == ApprovalStatus.APPROVED else CommandState.DENIED
            self._commands.transition(
                result.command_id,
                next_state,
                approval_id=result.request_id,
                risk_tier=result.risk_tier.value,
            )
            if result.status == ApprovalStatus.APPROVED:
                command = self._commands.get(result.command_id)
                if command is not None:
                    if self._defer_approved_execution:
                        return self._approval_queued_response(
                            request_id,
                            result,
                            recipient_id=resolver_sender_id,
                        )
                    response = self._execute_command(command, recipient_id=resolver_sender_id)
                    return GatewayResponse(
                        message_id=response.message_id,
                        channel=response.channel,
                        recipient_id=response.recipient_id,
                        body=f"Request {request_id} has been approved. {response.body}",
                        governed=True,
                        metadata={
                            **response.metadata,
                            "approval_resolved": True,
                            "status": "approved",
                            "request_id": request_id,
                            "command_id": result.command_id,
                        },
                    )
        return self._approval_response(request_id, result, recipient_id=resolver_sender_id)

    @property
    def pending_approvals(self) -> int:
        return self._approval.pending_count

    def _gen_id(self, prefix: str, ref: str) -> str:
        return f"{prefix}-{hashlib.sha256(f'{ref}:{self._message_count}'.encode()).hexdigest()[:12]}"

    @property
    def message_count(self) -> int:
        return self._message_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def duplicate_count(self) -> int:
        return self._duplicate_count

    def summary(self) -> dict[str, Any]:
        return {
            "message_count": self._message_count,
            "duplicate_count": self._duplicate_count,
            "error_count": self._error_count,
            "channels": list(self._channels.keys()),
            "tenant_mappings": self._tenant_identities.count(),
            "tenant_identity_store": self._tenant_identities.status(),
            "dedup": self._dedup.status(),
            "command_ledger": self._commands.summary(),
        }
