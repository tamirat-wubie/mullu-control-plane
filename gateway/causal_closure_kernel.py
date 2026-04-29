"""Gateway Causal Closure Kernel - terminal lifecycle conductor.

Purpose: Owns command execution truth after gateway ingress and before
    response delivery.
Governance scope: gateway command closure, response evidence, terminal
    certification, closure memory, and learning admission.
Dependencies: gateway command spine, governed platform session, capability
    dispatcher.
Invariants:
  - No success response is returned without terminal closure certification.
  - Terminal closure requires evidence references.
  - Router delivery never decides final operational truth.
  - Closure memory and learning admission follow the terminal certificate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Callable

from gateway.capability_isolation import (
    CapabilityExecutionBoundary,
    CapabilityIsolationPolicy,
    IsolatedCapabilityExecutor,
    LocalCapabilityExecutionWorker,
)
from gateway.command_spine import (
    ClosureDisposition,
    CommandEnvelope,
    CommandLedger,
    CommandState,
    GovernedAction,
    capability_passport_for,
    canonical_hash,
)
from gateway.proof_carrying_adapter import ProofCarryingCapabilityAdapter
from gateway.capability_dispatch import CapabilityDispatcher, CapabilityIntent


class ClosureResponseKind(StrEnum):
    """Response strength authorized by terminal closure."""

    SUCCESS = "success"
    RECOVERY = "recovery"
    CAUTION = "caution"
    REVIEW = "review"
    DENIAL = "denial"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class CausalClosureResult:
    """Gateway-facing result produced by the Causal Closure Kernel."""

    command_id: str
    disposition: ClosureDisposition | None
    response_kind: ClosureResponseKind
    response_body: str
    response_allowed: bool
    success_claim_allowed: bool
    metadata: dict[str, Any]


class CausalClosureKernel:
    """Executes governed commands until one terminal closure path is proven."""

    def __init__(
        self,
        *,
        commands: CommandLedger,
        platform: Any,
        skills: CapabilityDispatcher,
        skill_intent_loader: Callable[[CommandEnvelope], CapabilityIntent | None],
        error_recorder: Callable[[], None],
        clock: Callable[[], str] | None = None,
        isolation_policy: CapabilityIsolationPolicy | None = None,
        isolated_executor: IsolatedCapabilityExecutor | None = None,
    ) -> None:
        self._commands = commands
        self._platform = platform
        self._skills = skills
        self._skill_intent_loader = skill_intent_loader
        self._record_error = error_recorder
        self._isolation_policy = isolation_policy or CapabilityIsolationPolicy()
        if isolated_executor is not None:
            self._isolated_executor = isolated_executor
        elif self._isolation_policy.fail_closed_without_worker:
            self._isolated_executor = None
        else:
            self._isolated_executor = LocalCapabilityExecutionWorker(skills)
        self._proof_adapter = ProofCarryingCapabilityAdapter(clock=clock or commands._clock)

    def run(self, command_id: str) -> CausalClosureResult:
        """Run one command from approved/allowed state to certified closure."""
        command = self._commands.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")

        preflight = self._preflight(command)
        if preflight is not None:
            return preflight

        body = str(command.redacted_payload.get("body", ""))
        session: Any | None = None
        try:
            session = self._platform.connect(
                identity_id=command.actor_id,
                tenant_id=command.tenant_id,
            )
        except PermissionError:
            self._record_error()
            self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                detail={"cause": "platform_connect_denied"},
            )
            return self._non_terminal_result(
                command,
                ClosureResponseKind.DENIAL,
                "Access denied.",
                {"error": "access_denied", "command_id": command.command_id},
            )

        try:
            self._commands.transition(command.command_id, CommandState.BUDGET_RESERVED, budget_decision="session")
            self._commands.transition(command.command_id, CommandState.DISPATCHED, tool_name=command.intent)
            skill_intent = self._skill_intent_loader(command)
            if skill_intent is not None:
                skill_result = self._dispatch_skill(command, skill_intent)
                if skill_result is not None:
                    if skill_result.get("receipt_status") == "isolation_worker_required":
                        return self._review_result(
                            command,
                            body=str(skill_result.get(
                                "response",
                                "This capability requires an isolated execution worker before dispatch.",
                            )),
                            metadata={
                                **skill_result,
                                "error": "isolation_worker_required",
                                "command_id": command.command_id,
                            },
                            reason="isolation_worker_required",
                        )
                    return self._close_skill_result(command, skill_result)

            action = self._commands.governed_action_for(command.command_id)
            if action is None:
                raise RuntimeError("missing governed action")
            receipt_execution = self._proof_adapter.execute(
                command=command,
                governed_action=action,
                capability_passport=capability_passport_for(action.capability),
                executor=lambda: session.llm(body),
            )
            result = receipt_execution.result
            succeeded = bool(result.get("succeeded", True)) and not result.get("error")
            content = str(result.get("content", ""))
            response_body = content if succeeded else f"I couldn't process that: {result.get('error', '')}"
            return self._close_llm_result(
                command,
                response_body=response_body,
                succeeded=succeeded,
                proof_output=result,
            )
        except ValueError:
            self._commands.transition(command.command_id, CommandState.DENIED, detail={"cause": "content_blocked"})
            return self._non_terminal_result(
                command,
                ClosureResponseKind.DENIAL,
                "I can't process that request due to safety policies.",
                {"error": "content_blocked", "command_id": command.command_id},
            )
        except RuntimeError:
            self._record_error()
            response_body = "Service temporarily unavailable."
        except Exception:
            self._record_error()
            response_body = "An error occurred. Please try again."
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    self._record_error()

        self._commands.transition(command.command_id, CommandState.OBSERVED, output={"error": response_body})
        return self._non_terminal_result(
            command,
            ClosureResponseKind.FAILURE,
            response_body,
            {"command_id": command.command_id},
        )

    def _dispatch_skill(self, command: CommandEnvelope, skill_intent: CapabilityIntent) -> dict[str, Any] | None:
        """Dispatch skill intent through the governed execution boundary."""
        action = self._commands.governed_action_for(command.command_id)
        if action is None:
            raise RuntimeError("missing governed action")
        passport = self._commands.capability_passport_for_intent(command.intent)
        boundary = self._isolation_policy.boundary_for(passport)
        if not boundary.isolation_required:
            dispatch_metadata = self._capability_dispatch_metadata(command, action, boundary)
            receipt_execution = self._proof_adapter.execute(
                command=command,
                governed_action=action,
                capability_passport=passport,
                executor=lambda: self._skills.dispatch(
                    skill_intent,
                    command.tenant_id,
                    command.actor_id,
                    command_id=command.command_id,
                    conversation_id=command.conversation_id,
                    metadata=dispatch_metadata,
                ),
            )
            return receipt_execution.result
        if self._isolated_executor is None:
            self._record_error()
            return {
                "response": "This capability requires an isolated execution worker before dispatch.",
                "governed": True,
                "skill": skill_intent.action,
                "receipt_status": "isolation_worker_required",
                "capability_execution_boundary": asdict(boundary),
            }
        dispatch_metadata = self._capability_dispatch_metadata(command, action, boundary)
        receipt_execution = self._proof_adapter.execute(
            command=command,
            governed_action=action,
            capability_passport=passport,
            executor=lambda: self._isolated_executor.execute(
                intent=skill_intent,
                tenant_id=command.tenant_id,
                identity_id=command.actor_id,
                boundary=boundary,
                command_id=command.command_id,
                conversation_id=command.conversation_id,
                metadata=dispatch_metadata,
            )[0],
        )
        self._commands.transition(
            command.command_id,
            command.state,
            output={"proof_carrying_receipt": asdict(receipt_execution.receipt)},
            detail={
                "cause": "capability_execution_isolated",
                "capability_execution_boundary": asdict(boundary),
                "proof_carrying_receipt": asdict(receipt_execution.receipt),
                "execution_result": receipt_execution.execution_result.to_json_dict(),
            },
        )
        return receipt_execution.result

    def _capability_dispatch_metadata(
        self,
        command: CommandEnvelope,
        action: GovernedAction,
        boundary: CapabilityExecutionBoundary,
    ) -> dict[str, Any]:
        """Build command-side witness metadata for a capability handler."""
        events = self._commands.events_for(command.command_id)
        approval_event = next((event for event in reversed(events) if event.approval_id), None)
        budget_event = next(
            (event for event in reversed(events) if event.next_state is CommandState.BUDGET_RESERVED),
            None,
        )
        approval_id = action.approval_id or (approval_event.approval_id if approval_event is not None else "")
        if not approval_id:
            approval_id = "approval-not-required-" + canonical_hash({
                "command_id": command.command_id,
                "capability_id": action.capability,
                "risk_tier": action.risk_tier,
                "policy_version": command.policy_version,
            })[:16]
        budget_reservation_id = "budget-reservation-" + canonical_hash({
            "command_id": command.command_id,
            "capability_id": action.capability,
            "budget_decision": budget_event.budget_decision if budget_event is not None else "implicit",
            "budget_event_hash": budget_event.event_hash if budget_event is not None else "",
        })[:16]
        boundary_hash = canonical_hash(asdict(boundary))
        return {
            "command_id": command.command_id,
            "conversation_id": command.conversation_id,
            "trace_id": command.trace_id,
            "capability_id": action.capability,
            "risk_tier": action.risk_tier,
            "approval_id": approval_id,
            "approval_required": action.risk_tier in {"medium", "high"},
            "approval_witness_event_hash": approval_event.event_hash if approval_event is not None else "",
            "budget_reservation_id": budget_reservation_id,
            "budget_witness_event_hash": budget_event.event_hash if budget_event is not None else "",
            "isolation_boundary_id": f"isolation-boundary-{boundary_hash[:16]}",
            "isolation_boundary_hash": boundary_hash,
            "isolation_boundary": asdict(boundary),
        }

    def _preflight(self, command: CommandEnvelope) -> CausalClosureResult | None:
        governed_action = self._commands.governed_action_for(command.command_id)
        if governed_action is None:
            self._record_error()
            self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                detail={"cause": "missing_governed_action"},
            )
            return self._non_terminal_result(
                command,
                ClosureResponseKind.DENIAL,
                "This action cannot execute because its governed action contract is missing.",
                {"error": "missing_governed_action", "command_id": command.command_id},
            )
        if governed_action.risk_tier == "high" and not governed_action.predicted_effect_hash:
            self._record_error()
            self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                risk_tier=governed_action.risk_tier,
                detail={"cause": "missing_effect_prediction"},
            )
            return self._non_terminal_result(
                command,
                ClosureResponseKind.DENIAL,
                "This high-risk action cannot execute because its predicted effect contract is missing.",
                {"error": "missing_effect_prediction", "command_id": command.command_id},
            )
        if (
            governed_action.risk_tier == "high"
            and (not governed_action.rollback_plan_hash or not self._commands.recovery_plan_for(command.command_id))
        ):
            self._record_error()
            return self._review_result(
                command,
                body="This high-risk action requires a rollback or compensation plan before execution.",
                metadata={"error": "missing_recovery_plan", "command_id": command.command_id},
                reason="missing_recovery_plan",
            )
        if governed_action.risk_tier == "high":
            fracture = self._commands.fracture_test(command.command_id)
            if not fracture.passed:
                self._record_error()
                return self._review_result(
                    command,
                    body="This high-risk action requires review because fracture testing found a contradiction.",
                    metadata={
                        "error": "fracture_test_failed",
                        "command_id": command.command_id,
                        "fractures": fracture.fractures,
                        "fracture_result_hash": fracture.result_hash,
                    },
                    reason="fracture_test_failed",
                    evidence_refs=(fracture.result_hash,),
                )
        return None

    def _close_skill_result(self, command: CommandEnvelope, skill_result: dict[str, Any]) -> CausalClosureResult:
        response_body = skill_result.get("response", "Skill executed.")
        self._commands.transition(
            command.command_id,
            CommandState.OBSERVED,
            tool_name=command.intent,
            output=skill_result,
        )
        reconciliation = self._commands.observe_and_reconcile_effect(command.command_id, output=skill_result)
        if not reconciliation.reconciled:
            self._record_error()
            return self._review_result(
                command,
                body="This action could not be committed because observed effects did not match prediction.",
                metadata={
                    "error": "effect_reconciliation_failed",
                    "command_id": command.command_id,
                    "mismatch_reason": reconciliation.mismatch_reason,
                },
                reason="effect_reconciliation_failed",
            )
        self._commands.transition(command.command_id, CommandState.VERIFIED, detail={"verifier": "skill_dispatch"})
        self._commands.transition(command.command_id, CommandState.COMMITTED)
        return self._certify_committed(command, response_body=response_body, base_metadata=dict(skill_result))

    def _close_llm_result(
        self,
        command: CommandEnvelope,
        *,
        response_body: str,
        succeeded: bool,
        proof_output: dict[str, Any],
    ) -> CausalClosureResult:
        self._commands.transition(
            command.command_id,
            CommandState.OBSERVED,
            tool_name="llm_completion",
            output=proof_output,
        )
        reconciliation = self._commands.observe_and_reconcile_effect(
            command.command_id,
            output=proof_output,
        )
        if not reconciliation.reconciled:
            self._record_error()
            return self._review_result(
                command,
                body="This action could not be committed because observed effects did not match prediction.",
                metadata={
                    "error": "effect_reconciliation_failed",
                    "command_id": command.command_id,
                    "mismatch_reason": reconciliation.mismatch_reason,
                },
                reason="effect_reconciliation_failed",
            )
        self._commands.transition(command.command_id, CommandState.VERIFIED, detail={"verifier": "governed_session"})
        self._commands.transition(command.command_id, CommandState.COMMITTED)
        if not succeeded:
            return self._review_result(
                command,
                body=response_body,
                metadata={"error": "llm_completion_failed", "command_id": command.command_id},
                reason="llm_completion_failed",
            )
        return self._certify_committed(command, response_body=response_body, base_metadata={})

    def _certify_committed(
        self,
        command: CommandEnvelope,
        *,
        response_body: str,
        base_metadata: dict[str, Any],
    ) -> CausalClosureResult:
        receipt_promotions = self._commands.promote_provider_receipts_to_graph(command.command_id)
        claim = self._commands.record_operational_claim(
            command.command_id,
            text=f"Command {command.intent} completed.",
            verified=True,
        )
        response_closure = self._commands.close_success_response_evidence(
            command.command_id,
            claim_id=claim.claim_id,
        )
        self._commands.transition(
            command.command_id,
            CommandState.RESPONSE_EVIDENCE_CLOSED,
            detail={"response_evidence_closure": asdict(response_closure)},
        )
        certificate = self._commands.certify_terminal_closure(
            command.command_id,
            disposition=ClosureDisposition.COMMITTED,
            response_evidence_closure=response_closure,
            metadata={"response_kind": ClosureResponseKind.SUCCESS.value},
        )
        memory_entry = self._commands.promote_closure_memory(command.command_id)
        learning = self._commands.decide_closure_learning(command.command_id)
        self._commands.assert_success_response_allowed(command.command_id)
        metadata = {
            **base_metadata,
            "command_id": command.command_id,
            "terminal_certificate": asdict(certificate),
            "terminal_certificate_id": certificate.certificate_id,
            "closure_memory_entry": asdict(memory_entry),
            "learning_admission": asdict(learning),
            "claims": [asdict(claim)],
            "response_evidence_closure": asdict(response_closure),
            "provider_receipt_graph_promotions": [asdict(promotion) for promotion in receipt_promotions],
            "evidence": [asdict(record) for record in self._commands.evidence_for(command.command_id)],
        }
        return CausalClosureResult(
            command_id=command.command_id,
            disposition=ClosureDisposition.COMMITTED,
            response_kind=ClosureResponseKind.SUCCESS,
            response_body=response_body,
            response_allowed=True,
            success_claim_allowed=True,
            metadata=metadata,
        )

    def _review_result(
        self,
        command: CommandEnvelope,
        *,
        body: str,
        metadata: dict[str, Any],
        reason: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> CausalClosureResult:
        case_id = f"case-{command.command_id}-{reason}"
        if self._commands.terminal_certificate_for(command.command_id) is None:
            if not self._commands.evidence_for(command.command_id):
                self._commands.record_operational_claim(
                    command.command_id,
                    text=f"Command {command.intent} requires review.",
                    verified=False,
                    confidence=0.0,
                )
            self._commands.certify_terminal_closure(
                command.command_id,
                disposition=ClosureDisposition.REQUIRES_REVIEW,
                case_id=case_id,
                metadata={"reason": reason, "evidence_refs": evidence_refs},
            )
            memory_entry = self._commands.promote_closure_memory(command.command_id)
            learning = self._commands.decide_closure_learning(command.command_id)
        else:
            memory_entry = None
            learning = None
        certificate = self._commands.terminal_certificate_for(command.command_id)
        enriched = {
            **metadata,
            "command_id": command.command_id,
            "case_id": case_id,
            "terminal_certificate_id": certificate.certificate_id if certificate else None,
            "terminal_certificate": asdict(certificate) if certificate else None,
        }
        if memory_entry is not None:
            enriched["closure_memory_entry"] = asdict(memory_entry)
        if learning is not None:
            enriched["learning_admission"] = asdict(learning)
        return CausalClosureResult(
            command_id=command.command_id,
            disposition=ClosureDisposition.REQUIRES_REVIEW,
            response_kind=ClosureResponseKind.REVIEW,
            response_body=body,
            response_allowed=True,
            success_claim_allowed=False,
            metadata=enriched,
        )

    def _non_terminal_result(
        self,
        command: CommandEnvelope,
        response_kind: ClosureResponseKind,
        response_body: str,
        metadata: dict[str, Any],
    ) -> CausalClosureResult:
        return CausalClosureResult(
            command_id=command.command_id,
            disposition=None,
            response_kind=response_kind,
            response_body=response_body,
            response_allowed=True,
            success_claim_allowed=False,
            metadata=metadata,
        )
