"""Purpose: compile execution requests into formal typed intent records.
Governance scope: Universal Action Orchestration intent admission before
    capability lookup, authority proof, planning, simulation, or dispatch.
Dependencies: governed action contracts, dispatcher request shape, and runtime
    invariant helpers.
Invariants:
  - Raw dispatch text cannot enter capability admission directly.
  - Template action type must match the compiled intent name.
  - Compiled intent hashes bind actor, tenant, objective, route, template,
    bindings, risk, and mode into a deterministic proof surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from mcoi_runtime.contracts.governed_action import TypedIntentRecord
from mcoi_runtime.core.dispatcher import DispatchRequest

from .invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)


INTENT_IR_SCHEMA = "mullu.intent_ir.v1"
INTENT_IR_COMPILER_VERSION = "intent-ir-compiler.v1"


@dataclass(frozen=True, slots=True)
class IntentCompilationCertificate:
    """Proof that a request was reduced to formal typed intent before admission."""

    certificate_id: str
    compiler_version: str
    intent_schema: str
    typed_intent: TypedIntentRecord
    intent_hash: str
    compiled_at: str


class IntentCompilationError(RuntimeCoreInvariantError):
    """Raised when a request cannot be reduced to governed typed intent."""


class IntentIRCompiler:
    """Compile bounded request structure into a typed intent record."""

    def compile(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        command_id: str,
        objective: str,
        dispatch_request: DispatchRequest,
        risk: str,
        mode: str,
        issued_at: str,
    ) -> IntentCompilationCertificate:
        """Return a certificate for one typed intent compilation.

        Input contract: dispatch_request must expose a concrete route, template
        action type, and mapping-shaped bindings.
        Output contract: returns a deterministic certificate carrying a
        TypedIntentRecord and stable hash.
        Error contract: raises IntentCompilationError with a bounded reason code
        when the request is structurally invalid.
        """
        actor_id = ensure_non_empty_text("actor_id", actor_id)
        tenant_id = ensure_non_empty_text("tenant_id", tenant_id)
        command_id = ensure_non_empty_text("command_id", command_id)
        objective = ensure_non_empty_text("objective", objective)
        mode = ensure_non_empty_text("mode", mode)
        risk = ensure_non_empty_text("risk", risk)
        intent_name = ensure_non_empty_text(
            "dispatch_request.route", dispatch_request.route
        )
        if not isinstance(dispatch_request.template, Mapping):
            raise IntentCompilationError("intent_template_must_be_mapping")
        if not isinstance(dispatch_request.bindings, Mapping):
            raise IntentCompilationError("intent_bindings_must_be_mapping")
        template_action_type = dispatch_request.template.get("action_type")
        if (
            not isinstance(template_action_type, str)
            or not template_action_type.strip()
        ):
            raise IntentCompilationError("intent_template_action_type_missing")
        template_action_type = template_action_type.strip()
        if template_action_type != intent_name:
            raise IntentCompilationError("intent_template_action_type_mismatch")
        input_hash = stable_identifier(
            "typed-intent-input",
            {
                "actor_id": actor_id,
                "tenant_id": tenant_id,
                "command_id": command_id,
                "intent_name": intent_name,
                "objective": objective,
                "mode": mode,
                "risk": risk,
                "template": dispatch_request.template,
                "bindings": dict(dispatch_request.bindings),
            },
        )
        typed_intent = TypedIntentRecord(
            command_id=command_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            intent_name=intent_name,
            objective=objective,
            input_hash=input_hash,
        )
        intent_hash = stable_identifier(
            "typed-intent",
            {
                "schema": INTENT_IR_SCHEMA,
                "compiler_version": INTENT_IR_COMPILER_VERSION,
                "typed_intent": typed_intent.to_dict(),
            },
        )
        certificate_id = stable_identifier(
            "intent-compilation-cert",
            {
                "command_id": command_id,
                "intent_hash": intent_hash,
                "issued_at": issued_at,
            },
        )
        return IntentCompilationCertificate(
            certificate_id=certificate_id,
            compiler_version=INTENT_IR_COMPILER_VERSION,
            intent_schema=INTENT_IR_SCHEMA,
            typed_intent=typed_intent,
            intent_hash=intent_hash,
            compiled_at=issued_at,
        )
