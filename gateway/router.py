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
import hmac
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from gateway.approval import ApprovalRequest, ApprovalRouter, ApprovalStatus
from gateway.authority import evaluate_approval_authority
from gateway.authority_obligation_mesh import ApprovalChain, ApprovalChainStatus, AuthorityObligationMesh
from gateway.capability_isolation import CapabilityIsolationPolicy, IsolatedCapabilityExecutor
from gateway.causal_closure_kernel import CausalClosureKernel
from gateway.command_spine import CommandAnchor, CommandEnvelope, CommandLedger, CommandState, canonical_hash
from gateway.dedup import MessageDeduplicator
from gateway.memory_constitution import (
    GovernedMemoryStore,
    InMemoryGovernedMemoryStore,
    governed_memory_cell_from_mapping,
)
from gateway.capability_dispatch import CapabilityDispatcher, CapabilityIntent
from gateway.intent_resolver import CapabilityIntentResolver
from gateway.mcp_capability_fabric import MCPAuthorityRecords, install_mcp_authority_records
from gateway.plan import CapabilityPlan, CapabilityPlanBuilder, CapabilityPlanStep
from gateway.plan_executor import CapabilityPlanExecutor, CapabilityPlanStepResult
from gateway.plan_ledger import CapabilityPlanLedger, CapabilityPlanWitnessRecord
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
        capability_dispatcher: CapabilityDispatcher | None = None,
        skill_dispatcher: CapabilityDispatcher | None = None,
        intent_resolver: CapabilityIntentResolver | None = None,
        deduplicator: MessageDeduplicator | None = None,
        command_ledger: CommandLedger | None = None,
        tenant_identity_store: TenantIdentityStore | None = None,
        memory_store: GovernedMemoryStore | None = None,
        authority_obligation_mesh: AuthorityObligationMesh | None = None,
        plan_ledger: CapabilityPlanLedger | None = None,
        defer_approved_execution: bool = False,
        environment: str = "local_dev",
        isolated_capability_executor: IsolatedCapabilityExecutor | None = None,
        mcp_authority_records: MCPAuthorityRecords | None = None,
    ) -> None:
        if capability_dispatcher is not None and skill_dispatcher is not None:
            raise ValueError("use capability_dispatcher or skill_dispatcher, not both")
        self._platform = platform
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._approval = approval_router or ApprovalRouter(clock=self._clock)
        self._capabilities = capability_dispatcher or skill_dispatcher or CapabilityDispatcher()
        self._intent_resolver = intent_resolver or CapabilityIntentResolver()
        self._dedup = deduplicator or MessageDeduplicator()
        self._commands = command_ledger or CommandLedger(clock=self._clock)
        self._tenant_identities = tenant_identity_store or InMemoryTenantIdentityStore(clock=self._clock)
        self._memory = memory_store or InMemoryGovernedMemoryStore(clock=self._clock)
        self._plan_builder = CapabilityPlanBuilder(
            resolver=self._intent_resolver,
            capability_passport_loader=self._commands.capability_passport_for_intent,
        )
        self._plan_ledger = plan_ledger or CapabilityPlanLedger(clock=self._clock)
        self._authority_obligation_mesh = authority_obligation_mesh or AuthorityObligationMesh(
            commands=self._commands,
            clock=self._clock,
        )
        if mcp_authority_records is not None:
            install_mcp_authority_records(self._authority_obligation_mesh, mcp_authority_records)
        self._defer_approved_execution = defer_approved_execution
        self._closure_kernel = CausalClosureKernel(
            commands=self._commands,
            platform=self._platform,
            capability_dispatcher=self._capabilities,
            capability_intent_loader=self._capability_intent_from_command,
            error_recorder=self._record_error,
            clock=self._clock,
            isolation_policy=CapabilityIsolationPolicy(environment=environment),
            isolated_executor=isolated_capability_executor,
        )
        self._skills = self._capabilities
        self._channels: dict[str, ChannelAdapter] = {}
        self._message_count = 0
        self._duplicate_count = 0
        self._error_count = 0
        self._error_reasons: dict[str, int] = {}

    def register_channel(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._channels[adapter.channel_name] = adapter

    def register_tenant_mapping(self, mapping: TenantMapping) -> None:
        """Map a channel user identity to a tenant."""
        self._tenant_identities.save(mapping)
        self._admit_mapping_memory(mapping)

    def resolve_tenant(self, channel: str, sender_id: str) -> TenantMapping | None:
        """Resolve tenant from channel user identity."""
        return self._tenant_identities.resolve(channel, sender_id)

    def governed_memory_for(self, mapping: TenantMapping, *, allowed_use: str, scope: str = "") -> list[Any]:
        """Return governed memory cells usable for one mapped identity."""
        return self._memory.query(
            tenant_id=mapping.tenant_id,
            owner_id=mapping.identity_id,
            allowed_use=allowed_use,
            scope=scope,
        )

    def _admit_mapping_memory(self, mapping: TenantMapping) -> None:
        """Admit explicit memory cells carried by tenant mapping metadata."""
        raw_cells = mapping.metadata.get("memory_cells", ())
        if not isinstance(raw_cells, (list, tuple)):
            return
        for raw_cell in raw_cells:
            if not isinstance(raw_cell, dict):
                continue
            cell = governed_memory_cell_from_mapping(
                raw_cell,
                tenant_id=mapping.tenant_id,
                owner_id=mapping.identity_id,
            )
            self._memory.admit(cell)

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

    def _send_response(self, response: GatewayResponse) -> GatewayResponse:
        """Send a response through its registered channel adapter when present."""
        adapter = self._channels.get(response.channel)
        if adapter is None:
            return replace(
                response,
                metadata={
                    **response.metadata,
                    "delivery_status": "skipped_no_adapter",
                },
            )
        try:
            sent = bool(adapter.send(response.recipient_id, response.body))
        except Exception:
            self._record_error("adapter_exception")
            return replace(
                response,
                metadata={
                    **response.metadata,
                    "delivery_status": "failed",
                    "delivery_error_type": "adapter_exception",
                },
            )
        if not sent:
            self._record_error("adapter_rejected")
            return replace(
                response,
                metadata={
                    **response.metadata,
                    "delivery_status": "failed",
                    "delivery_error_type": "adapter_rejected",
                },
            )
        return replace(
            response,
            metadata={
                **response.metadata,
                "delivery_status": "sent",
            },
        )

    def _intent_name(self, intent: CapabilityIntent | None) -> str:
        """Return the canonical command intent string."""
        if intent is None:
            return "llm_completion"
        return intent.capability_id

    def _command_payload(self, message: GatewayMessage, intent: CapabilityIntent | None) -> dict[str, Any]:
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
            payload["capability_intent"] = {
                "domain": intent.domain,
                "action": intent.action,
                "capability_id": intent.capability_id,
                "params": dict(intent.params),
            }
            payload["skill_intent"] = {
                "skill": intent.domain,
                "domain": intent.domain,
                "action": intent.action,
                "capability_id": intent.capability_id,
                "params": dict(intent.params),
            }
        return payload

    def _intent_from_step(self, step: CapabilityPlanStep) -> CapabilityIntent:
        """Convert a validated plan step into a command intent."""
        domain, action = step.capability_id.split(".", 1)
        return CapabilityIntent(domain=domain, action=action, params=dict(step.params))

    def _create_command(
        self,
        message: GatewayMessage,
        mapping: TenantMapping,
        intent: CapabilityIntent | None,
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
        self._authority_obligation_mesh.prepare_authority(tenant_bound.command_id)
        governed = self._commands.get(tenant_bound.command_id)
        if governed is None:
            raise RuntimeError("governed action binding lost command")
        return governed

    def _capability_intent_from_command(self, command: CommandEnvelope) -> CapabilityIntent | None:
        """Rebuild the stored capability intent without reclassifying message text."""
        raw = command.redacted_payload.get("capability_intent")
        if not isinstance(raw, dict):
            raw = command.redacted_payload.get("skill_intent")
        if not isinstance(raw, dict):
            return None
        skill = raw.get("domain") or raw.get("skill")
        action = raw.get("action")
        params = raw.get("params", {})
        if not isinstance(skill, str) or not isinstance(action, str) or not isinstance(params, dict):
            return None
        return CapabilityIntent(skill, action, dict(params))

    def _skill_intent_from_command(self, command: CommandEnvelope) -> CapabilityIntent | None:
        """Compatibility alias for older tests and persisted call paths."""
        return self._capability_intent_from_command(command)

    def _record_error(self, reason_code: str = "gateway_runtime_error") -> None:
        """Record a kernel-visible gateway error."""
        self._error_count += 1
        self._error_reasons[reason_code] = self._error_reasons.get(reason_code, 0) + 1

    def _execute_command(self, command: CommandEnvelope, *, recipient_id: str) -> GatewayResponse:
        """Execute an allowed command through the stored canonical payload."""
        closure = self._closure_kernel.run(command.command_id)
        certificate = self._commands.terminal_certificate_for(command.command_id)
        if certificate is not None:
            self._authority_obligation_mesh.open_post_closure_obligations(
                command_id=command.command_id,
                certificate=certificate,
            )
        response = GatewayResponse(
            message_id=f"resp-{command.command_id}",
            channel=command.source,
            recipient_id=recipient_id,
            body=closure.response_body,
            governed=True,
            metadata={
                **closure.metadata,
                "closure_response_kind": closure.response_kind.value,
                "closure_disposition": closure.disposition.value if closure.disposition else None,
                "response_allowed": closure.response_allowed,
                "success_claim_allowed": closure.success_claim_allowed,
                "terminal_certificate_id": certificate.certificate_id if certificate else "",
            },
        )
        self._commands.transition(
            command.command_id,
            CommandState.RESPONDED,
            output={"body": closure.response_body},
            detail={
                "causal_closure_result": {
                    "disposition": closure.disposition.value if closure.disposition else None,
                    "response_kind": closure.response_kind.value,
                    "response_allowed": closure.response_allowed,
                    "success_claim_allowed": closure.success_claim_allowed,
                },
                "success_claim": closure.success_claim_allowed,
            },
        )
        return response

    def _execute_plan(
        self,
        *,
        plan: CapabilityPlan,
        message: GatewayMessage,
        mapping: TenantMapping,
        initial_results: tuple[CapabilityPlanStepResult, ...] = (),
    ) -> GatewayResponse:
        """Execute a multi-step plan as governed child commands."""

        def execute_step(
            step: CapabilityPlanStep,
            completed: dict[str, CapabilityPlanStepResult],
        ) -> CapabilityPlanStepResult:
            step_message = GatewayMessage(
                message_id=f"{message.message_id}:{plan.plan_id}:{step.step_id}",
                channel=message.channel,
                sender_id=message.sender_id,
                body=str(step.params.get("brief") or step.params.get("query") or step.params.get("body") or message.body),
                conversation_id=message.conversation_id,
                attachments=message.attachments,
                metadata={
                    **message.metadata,
                    "plan_id": plan.plan_id,
                    "plan_step_id": step.step_id,
                    "depends_on": step.depends_on,
                    "completed_steps": tuple(completed),
                },
                received_at=message.received_at,
            )
            intent = self._intent_from_step(step)
            try:
                command = self._create_command(step_message, mapping, intent)
            except ValueError as exc:
                reason_code = (
                    "plan_step_capability_admission_rejected"
                    if str(exc).startswith("capability fabric admission rejected:")
                    else "plan_step_command_binding_rejected"
                )
                self._record_error(reason_code)
                return CapabilityPlanStepResult(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    succeeded=False,
                    error=reason_code,
                )
            self._commands.transition(command.command_id, CommandState.POLICY_EVALUATED)
            approval = self._approval.request_approval(
                tenant_id=mapping.tenant_id,
                identity_id=mapping.identity_id,
                channel=message.channel,
                action_description=command.intent,
                body=step_message.body,
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
                return CapabilityPlanStepResult(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    succeeded=False,
                    command_id=command.command_id,
                    error=f"approval_required:{approval.request_id}",
                )
            self._commands.transition(
                command.command_id,
                CommandState.ALLOWED,
                approval_id=approval.request_id,
                risk_tier=approval.risk_tier.value,
            )
            response = self._execute_command(command, recipient_id=message.sender_id)
            certificate = self._commands.terminal_certificate_for(command.command_id)
            return CapabilityPlanStepResult(
                step_id=step.step_id,
                capability_id=step.capability_id,
                succeeded=bool(certificate and response.metadata.get("response_allowed", True)),
                command_id=command.command_id,
                terminal_certificate_id=certificate.certificate_id if certificate else "",
                output={
                    "response_body": response.body,
                    "metadata": response.metadata,
                },
                error="" if certificate else "missing_terminal_certificate",
            )

        execution = CapabilityPlanExecutor(execute_step).execute(plan, initial_results=initial_results)
        if not execution.succeeded:
            self._record_error("plan_execution_failed")
            failure_witness = self._plan_ledger.record_failure(plan=plan, execution=execution)
            return GatewayResponse(
                message_id=self._gen_id("plan-resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="This plan could not be completed under governance.",
                governed=True,
                metadata={
                    "error": "plan_execution_failed",
                    "plan_id": plan.plan_id,
                    "plan_error": execution.error,
                    "plan_failure_witness": asdict(failure_witness),
                    "plan_failure_witness_id": failure_witness.witness_id,
                    "step_results": [asdict(result) for result in execution.step_results],
                    "evidence_hash": execution.evidence_hash,
                },
            )
        certificate = self._plan_ledger.certify(plan=plan, execution=execution)
        return GatewayResponse(
            message_id=self._gen_id("plan-resp", message.message_id),
            channel=message.channel,
            recipient_id=message.sender_id,
            body="Plan completed under governed capability closure.",
            governed=True,
            metadata={
                "plan_id": plan.plan_id,
                "plan_terminal_certificate": asdict(certificate),
                "plan_terminal_certificate_id": certificate.certificate_id,
                "step_results": [asdict(result) for result in execution.step_results],
                "evidence_hash": execution.evidence_hash,
            },
        )

    def recover_waiting_plan(self, plan_id: str) -> GatewayResponse:
        """Resume a plan that was blocked waiting for step approval."""
        existing_certificate = self._plan_ledger.certificate_for(plan_id)
        if existing_certificate is not None:
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="wait_for_approval",
                status="rejected",
                reason="plan_already_certified",
                terminal_certificate_id=existing_certificate.certificate_id,
            )
            raise ValueError("plan already has terminal certificate")
        witness = self._latest_failed_plan_witness(plan_id)
        if witness is None:
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="unknown",
                status="rejected",
                reason="failed_plan_witness_not_found",
            )
            raise KeyError(f"unknown failed plan_id: {plan_id}")
        recovery_decision = witness.detail.get("recovery_decision", {})
        if not isinstance(recovery_decision, dict) or recovery_decision.get("recovery_action") != "wait_for_approval":
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action=str(recovery_decision.get("recovery_action", "unknown"))
                if isinstance(recovery_decision, dict)
                else "unknown",
                status="rejected",
                reason="plan_not_waiting_for_approval",
                witness_id=witness.witness_id,
            )
            raise ValueError("plan is not waiting for approval")
        plan = _plan_from_witness(witness)
        step_results = _step_results_from_witness(witness)
        failed_step_id = str(recovery_decision.get("failed_step_id", ""))
        failed_result = next((result for result in step_results if result.step_id == failed_step_id), None)
        if failed_result is None or not failed_result.command_id:
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="wait_for_approval",
                status="rejected",
                reason="approval_wait_missing_failed_command_id",
                witness_id=witness.witness_id,
                detail={"failed_step_id": failed_step_id},
            )
            raise ValueError("approval-wait witness does not include a failed command id")
        certificate = self._commands.terminal_certificate_for(failed_result.command_id)
        if certificate is None:
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="wait_for_approval",
                status="blocked",
                reason="approval_wait_command_not_terminal",
                witness_id=witness.witness_id,
                detail={"command_id": failed_result.command_id},
            )
            raise ValueError("approval-wait command has not reached terminal closure")
        command = self._commands.get(failed_result.command_id)
        if command is None:
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="wait_for_approval",
                status="rejected",
                reason="approval_wait_command_missing",
                witness_id=witness.witness_id,
                terminal_certificate_id=certificate.certificate_id,
                detail={"command_id": failed_result.command_id},
            )
            raise ValueError("approval-wait command is missing from command ledger")
        recovered_failed_result = CapabilityPlanStepResult(
            step_id=failed_result.step_id,
            capability_id=failed_result.capability_id,
            succeeded=True,
            command_id=failed_result.command_id,
            terminal_certificate_id=certificate.certificate_id,
            output={"recovered_from_approval": True},
        )
        initial_results = tuple(
            recovered_failed_result if result.step_id == failed_step_id else result
            for result in step_results
        )
        message = GatewayMessage(
            message_id=f"recover:{plan_id}:{witness.witness_id}",
            channel=command.source,
            sender_id=str(command.redacted_payload.get("sender_id", command.actor_id)),
            body=plan.goal,
            conversation_id=command.conversation_id,
            attachments=tuple(command.redacted_payload.get("attachments", ())),
            metadata={"recovered_plan_id": plan_id, "recovery_witness_id": witness.witness_id},
        )
        mapping = TenantMapping(
            channel=command.source,
            sender_id=str(command.redacted_payload.get("sender_id", command.actor_id)),
            tenant_id=plan.tenant_id,
            identity_id=plan.identity_id,
        )
        response = self._execute_plan(plan=plan, message=message, mapping=mapping, initial_results=initial_results)
        if response.metadata.get("plan_terminal_certificate_id"):
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="wait_for_approval",
                status="succeeded",
                reason="plan_recovered",
                witness_id=witness.witness_id,
                terminal_certificate_id=str(response.metadata["plan_terminal_certificate_id"]),
                detail={"command_id": failed_result.command_id},
            )
        else:
            self._record_plan_recovery_attempt(
                plan_id=plan_id,
                recovery_action="wait_for_approval",
                status="blocked",
                reason=str(response.metadata.get("plan_error", "plan_recovery_incomplete")),
                witness_id=witness.witness_id,
                detail={"command_id": failed_result.command_id},
            )
        return response

    def _latest_failed_plan_witness(self, plan_id: str) -> CapabilityPlanWitnessRecord | None:
        witnesses = self._plan_ledger.witnesses_for(plan_id)
        for witness in reversed(witnesses):
            if not witness.succeeded:
                return witness
        return None

    def _record_plan_recovery_attempt(
        self,
        *,
        plan_id: str,
        recovery_action: str,
        status: str,
        reason: str,
        witness_id: str = "",
        terminal_certificate_id: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        self._plan_ledger.record_recovery_attempt(
            plan_id=plan_id,
            recovery_action=recovery_action,
            status=status,
            reason=reason,
            witness_id=witness_id,
            terminal_certificate_id=terminal_certificate_id,
            detail=detail,
        )

    def _approval_chain_pending_response(
        self,
        request_id: str,
        result: ApprovalRequest,
        chain: ApprovalChain,
        *,
        recipient_id: str,
    ) -> GatewayResponse:
        """Return a governed response when approval is recorded but quorum is incomplete."""
        return GatewayResponse(
            message_id=self._gen_id("apr-resp", request_id),
            channel=result.channel,
            recipient_id=recipient_id,
            body=(
                f"Request {request_id} approval was recorded. "
                f"Authority path {chain.chain_id} still requires "
                f"{chain.required_approver_count - len(chain.approvals_received)} approval(s)."
            ),
            governed=True,
            metadata={
                "approval_resolved": True,
                "approval_chain_pending": True,
                "status": result.status.value,
                "command_id": result.command_id,
                "chain_id": chain.chain_id,
                "approvals_received": chain.approvals_received,
                "required_approver_count": chain.required_approver_count,
            },
        )

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
            self._record_error("approval_not_found")
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
            self._record_error("approval_context_denied")
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
            self._record_error("approval_not_found")
            return GatewayResponse(
                message_id=self._gen_id("apr-resp", request_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="This approval request is no longer available.",
                governed=True,
                metadata={"error": "approval_not_found"},
            )
        if result.command_id:
            chain = self._authority_obligation_mesh.record_approval(
                command_id=result.command_id,
                approver_id=mapping.identity_id,
                approver_roles=tuple(mapping.roles),
                approved=result.status == ApprovalStatus.APPROVED,
            )
            next_state = CommandState.APPROVED if result.status == ApprovalStatus.APPROVED else CommandState.DENIED
            self._commands.transition(
                result.command_id,
                next_state,
                approval_id=result.request_id,
                risk_tier=result.risk_tier.value,
            )
            if result.status == ApprovalStatus.APPROVED:
                if chain is not None and chain.status not in {
                    ApprovalChainStatus.SATISFIED,
                    ApprovalChainStatus.NOT_REQUIRED,
                }:
                    return self._approval_chain_pending_response(
                        request_id,
                        result,
                        chain,
                        recipient_id=message.sender_id,
                    )
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
            self._record_error("tenant_not_found")
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
            response = self._send_response(response)
            self._dedup.record(message.channel, message.sender_id, message.message_id, response)
            return response

        plan = self._plan_builder.build(
            message=message.body,
            tenant_id=mapping.tenant_id,
            identity_id=mapping.identity_id,
        )
        if plan is not None and len(plan.steps) > 1:
            response = self._execute_plan(plan=plan, message=message, mapping=mapping)
            response = self._send_response(response)
            self._dedup.record(message.channel, message.sender_id, message.message_id, response)
            return response

        intent = self._intent_resolver.resolve(message.body)
        try:
            command = self._create_command(message, mapping, intent)
        except ValueError as exc:
            if not str(exc).startswith("capability fabric admission rejected:"):
                raise
            self._record_error("capability_admission_rejected")
            resp = GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="This command requires capability review before execution.",
                governed=True,
                metadata={
                    "error": "capability_admission_rejected",
                    "reason": str(exc),
                },
            )
            self._dedup.record(message.channel, message.sender_id, message.message_id, resp)
            return resp
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
        response = self._send_response(response)
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
                response = self._send_response(response)
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
            chain = self._authority_obligation_mesh.approval_chain_for(result.command_id)
            chain = self._authority_obligation_mesh.record_approval(
                command_id=result.command_id,
                approver_id=resolved_by,
                approver_roles=chain.required_roles if chain is not None else (),
                approved=result.status == ApprovalStatus.APPROVED,
            )
            next_state = CommandState.APPROVED if result.status == ApprovalStatus.APPROVED else CommandState.DENIED
            self._commands.transition(
                result.command_id,
                next_state,
                approval_id=result.request_id,
                risk_tier=result.risk_tier.value,
            )
            if result.status == ApprovalStatus.APPROVED:
                command = self._commands.get(result.command_id)
                if chain is not None and chain.status not in {
                    ApprovalChainStatus.SATISFIED,
                    ApprovalChainStatus.NOT_REQUIRED,
                }:
                    single_non_self_resolver = (
                        command is not None
                        and chain.required_approver_count <= 1
                        and result.resolved_by
                        and result.resolved_by != command.actor_id
                    )
                    if not single_non_self_resolver:
                        return self._approval_chain_pending_response(
                            request_id,
                            result,
                            chain,
                            recipient_id=result.identity_id,
                        )
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
            self._record_error("approval_context_denied")
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
            self._record_error("approval_context_denied")
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
            self._authority_obligation_mesh.record_approval(
                command_id=result.command_id,
                approver_id=resolver.identity_id,
                approver_roles=tuple(resolver.roles),
                approved=result.status == ApprovalStatus.APPROVED,
            )
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
            "error_reasons": dict(sorted(self._error_reasons.items())),
            "channels": list(self._channels.keys()),
            "tenant_mappings": self._tenant_identities.count(),
            "tenant_identity_store": self._tenant_identities.status(),
            "memory_store": self._memory.status(),
            "dedup": self._dedup.status(),
            "command_ledger": self._commands.summary(),
            "authority_obligation_mesh": self._authority_obligation_mesh.summary(),
        }

    def runtime_witness(self, *, environment: str, signature_key_id: str, signing_secret: str) -> dict[str, Any]:
        """Publish a signed witness for gateway closure and anchor state."""
        ledger_summary = self._commands.summary()
        state_counts = dict(ledger_summary.get("states", {}))
        anchors = self._commands.list_anchors(limit=1)
        latest_anchor = anchors[0] if anchors else None
        latest_certificate = self._commands.latest_terminal_certificate()
        responsibility_witness = self._authority_obligation_mesh.responsibility_witness()
        witness_payload = {
            "witness_id": self._gen_id("runtime-witness", ledger_summary.get("last_event_hash", "")),
            "environment": environment,
            "runtime_status": "healthy",
            "gateway_status": "healthy" if self._error_count == 0 else "degraded",
            "latest_command_event_hash": ledger_summary.get("last_event_hash", ""),
            "latest_anchor_id": latest_anchor.anchor_id if latest_anchor else None,
            "latest_terminal_certificate_id": (
                latest_certificate.certificate_id if latest_certificate is not None else None
            ),
            "open_case_count": int(state_counts.get(CommandState.REQUIRES_REVIEW.value, 0)),
            "active_accepted_risk_count": responsibility_witness.active_accepted_risk_count,
            "active_compensation_review_count": responsibility_witness.active_compensation_review_count,
            "requires_review_count": responsibility_witness.requires_review_count,
            "responsibility_debt_clear": responsibility_witness.responsibility_debt_clear,
            "pending_approval_chain_count": responsibility_witness.pending_approval_chain_count,
            "overdue_approval_chain_count": responsibility_witness.overdue_approval_chain_count,
            "expired_approval_chain_count": responsibility_witness.expired_approval_chain_count,
            "open_obligation_count": responsibility_witness.open_obligation_count,
            "overdue_obligation_count": responsibility_witness.overdue_obligation_count,
            "escalated_obligation_count": responsibility_witness.escalated_obligation_count,
            "unowned_high_risk_capability_count": responsibility_witness.unowned_high_risk_capability_count,
            "unresolved_reconciliation_count": int(state_counts.get(CommandState.REQUIRES_REVIEW.value, 0)),
            "last_change_certificate_id": None,
            "signed_at": self._clock(),
            "signature_key_id": signature_key_id,
        }
        signature_payload = canonical_hash(witness_payload)
        signature = hmac.new(
            signing_secret.encode("utf-8"),
            signature_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            **witness_payload,
            "signature": f"hmac-sha256:{signature}",
        }


def _plan_from_witness(witness: CapabilityPlanWitnessRecord) -> CapabilityPlan:
    snapshot = witness.detail.get("plan_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("plan witness does not include a plan snapshot")
    raw_steps = snapshot.get("steps", ())
    if not isinstance(raw_steps, list):
        raise ValueError("plan witness snapshot steps must be a list")
    steps: list[CapabilityPlanStep] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise ValueError("plan witness snapshot step must be an object")
        steps.append(CapabilityPlanStep(
            step_id=str(raw_step["step_id"]),
            capability_id=str(raw_step["capability_id"]),
            params=dict(raw_step.get("params", {})),
            depends_on=tuple(str(item) for item in raw_step.get("depends_on", ())),
        ))
    return CapabilityPlan(
        plan_id=str(snapshot["plan_id"]),
        tenant_id=str(snapshot["tenant_id"]),
        identity_id=str(snapshot["identity_id"]),
        goal=str(snapshot["goal"]),
        steps=tuple(steps),
        risk_tier=str(snapshot["risk_tier"]),
        approval_required=bool(snapshot["approval_required"]),
        evidence_required=tuple(str(item) for item in snapshot.get("evidence_required", ())),
        metadata=dict(snapshot.get("metadata", {})),
    )


def _step_results_from_witness(witness: CapabilityPlanWitnessRecord) -> tuple[CapabilityPlanStepResult, ...]:
    raw_results = witness.detail.get("step_results", ())
    if not isinstance(raw_results, list):
        raise ValueError("plan witness step_results must be a list")
    results: list[CapabilityPlanStepResult] = []
    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            raise ValueError("plan witness step_result must be an object")
        results.append(CapabilityPlanStepResult(
            step_id=str(raw_result["step_id"]),
            capability_id=str(raw_result["capability_id"]),
            succeeded=bool(raw_result["succeeded"]),
            command_id=str(raw_result.get("command_id", "")),
            terminal_certificate_id=str(raw_result.get("terminal_certificate_id", "")),
            output=dict(raw_result.get("output", {})),
            error=str(raw_result.get("error", "")),
        ))
    return tuple(results)
