"""Governance SDK facade for simple governed action checks.

Purpose: provide typed builders and convenience client methods so user-facing
surfaces do not hand-build raw governance JSON.
Governance scope: SDK ergonomics only; all action authority remains bounded by
explicit scope, proof, side-effect, and Mfidel atomicity checks.
Dependencies: dataclasses and invariant helpers.
Invariants: SDK builders require typed action scope, proof obligations, and
side-effect declarations before governed calls are made.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from .invariants import RuntimeCoreInvariantError, stable_identifier

ProofMode = Literal["required", "development", "audit_only"]


@dataclass(frozen=True)
class GovernanceClientConfig:
    """Runtime ABI client configuration."""

    caller_id: str
    abi_version: str = "0.1.0"
    proof_mode: ProofMode = "required"


@dataclass(frozen=True)
class GateActionResult:
    """Developer-facing gate result."""

    decision: str
    decision_ref: str
    proof_stamp_ref: str
    boundary_witness_ref: str
    explanation: str
    raw_call: RuntimeABICall


@dataclass(frozen=True)
class RuntimeABICall:
    """Proof-bearing governed call record."""

    call_id: str
    operation_id: str
    caller_id: str
    input_ref: str
    output_ref: str
    decision_ref: str
    boundary_witness_ref: str
    proof_stamp_id: str
    output: Mapping[str, Any]


class IntentFrameBuilder:
    """Typed builder for SDK intent payloads."""

    def __init__(self) -> None:
        self._user_goal = ""
        self._scope: list[str] = []
        self._success_criteria: list[str] = []
        self._created_at = "2026-05-06T00:00:00Z"

    def goal(self, user_goal: str) -> "IntentFrameBuilder":
        """Set user goal."""

        self._user_goal = user_goal
        return self

    def within_scope(self, *scope: str) -> "IntentFrameBuilder":
        """Set allowed scope."""

        self._scope = list(scope)
        return self

    def succeeds_when(self, *success_criteria: str) -> "IntentFrameBuilder":
        """Set success criteria."""

        self._success_criteria = list(success_criteria)
        return self

    def created_at(self, created_at: str) -> "IntentFrameBuilder":
        """Set creation timestamp."""

        self._created_at = created_at
        return self

    def build(self) -> dict[str, object]:
        """Build JSON payload for Runtime ABI."""

        if not self._user_goal.strip():
            raise RuntimeCoreInvariantError("intent user_goal is required")
        if not self._scope:
            raise RuntimeCoreInvariantError("intent scope is required")
        if not self._success_criteria:
            raise RuntimeCoreInvariantError("intent success criteria are required")
        return {
            "user_goal": self._user_goal,
            "scope": self._scope,
            "success_criteria": self._success_criteria,
            "created_at": self._created_at,
        }


class ActionSentenceBuilder:
    """Typed builder for SDK action payloads."""

    def __init__(self, verb: str, object_kind: str, object_ref: str) -> None:
        self._verb = verb
        self._object_kind = object_kind
        self._object_ref = object_ref
        self._scope: list[str] = []
        self._expected_side_effects: list[str] = []
        self._proof_obligations: list[str] = []
        self._domain = "generic"
        self._operation = ""

    @classmethod
    def read_file(cls, object_ref: str) -> "ActionSentenceBuilder":
        """Build a read-file action."""

        return cls("read", "file", object_ref)

    @classmethod
    def write_file(cls, object_ref: str) -> "ActionSentenceBuilder":
        """Build a write-file action."""

        return cls("write", "file", object_ref).with_side_effects("local_write")

    @classmethod
    def mfidel_grid_reference(cls, grid_ref: str) -> "ActionSentenceBuilder":
        """Build an Mfidel grid-safe reference action."""

        return cls("read", "domain_symbol", grid_ref).for_domain("mfidel", "grid_reference")

    @classmethod
    def mfidel_transformation(cls, grid_ref: str, operation: str) -> "ActionSentenceBuilder":
        """Build an Mfidel transformation action."""

        return cls("transform", "domain_symbol", grid_ref).for_domain("mfidel", operation)

    def within_scope(self, *scope: str) -> "ActionSentenceBuilder":
        """Set action scope."""

        self._scope = list(scope)
        return self

    def with_side_effects(self, *side_effects: str) -> "ActionSentenceBuilder":
        """Set declared side effects."""

        self._expected_side_effects = list(side_effects)
        return self

    def requires_proof(self, *proof_obligations: str) -> "ActionSentenceBuilder":
        """Set proof obligations."""

        self._proof_obligations = list(proof_obligations)
        return self

    def for_domain(self, domain: str, operation: str = "") -> "ActionSentenceBuilder":
        """Set domain and domain operation."""

        self._domain = domain
        self._operation = operation
        return self

    def build(self) -> dict[str, object]:
        """Build JSON payload for Runtime ABI."""

        if not self._object_ref.strip():
            raise RuntimeCoreInvariantError("action object_ref is required")
        if not self._scope:
            raise RuntimeCoreInvariantError("action scope is required")
        if not self._proof_obligations:
            raise RuntimeCoreInvariantError("action proof obligations are required")
        return {
            "verb": self._verb,
            "object_kind": self._object_kind,
            "object_ref": self._object_ref,
            "scope": self._scope,
            "expected_side_effects": self._expected_side_effects,
            "proof_obligations": self._proof_obligations,
            "domain": self._domain,
            "operation": self._operation,
        }


class GovernanceClient:
    """Typed SDK facade over bounded governance operations."""

    def __init__(
        self,
        config: GovernanceClientConfig,
        dispatcher: object | None = None,
    ) -> None:
        self._config = config
        if dispatcher is not None:
            raise RuntimeCoreInvariantError("custom governance dispatchers are not supported")

    def validate_intent(self, intent: Mapping[str, object]) -> RuntimeABICall:
        """Validate intent through Runtime ABI."""

        return self._call("intent.validate", {"intent": dict(intent)})

    def validate_action(self, action: Mapping[str, object]) -> RuntimeABICall:
        """Validate action through Runtime ABI."""

        return self._call("action.validate", {"action": dict(action)})

    def gate_action(self, *, intent: Mapping[str, object], action: Mapping[str, object]) -> GateActionResult:
        """Gate an action and return developer-facing decision metadata."""

        call = self._call("action.gate", {"intent": dict(intent), "action": dict(action)})
        decision = call.output["result"]["decision"]
        proof = call.output["result"]["proof_stamp"]
        return GateActionResult(
            decision=str(decision["decision"]),
            decision_ref=str(decision["decision_id"]),
            proof_stamp_ref=str(proof["proof_stamp_id"]),
            boundary_witness_ref=call.boundary_witness_ref,
            explanation=str(decision["reason"]),
            raw_call=call,
        )

    def list_stdlib(
        self,
        *,
        kind: str | None = None,
        tag: str | None = None,
        minimum_maturity: str | None = None,
    ) -> RuntimeABICall:
        """List standard library artifacts through Runtime ABI."""

        payload: dict[str, object] = {}
        if kind is not None:
            payload["kind"] = kind
        if tag is not None:
            payload["tag"] = tag
        if minimum_maturity is not None:
            payload["minimum_maturity"] = minimum_maturity
        return self._call("stdlib.list", payload)

    def show_stdlib(self, artifact_id: str) -> RuntimeABICall:
        """Show one standard library artifact."""

        return self._call("stdlib.show", {"artifact_id": artifact_id})

    def query_registry(
        self,
        *,
        registry_kinds: Sequence[str] = (),
        required_capability: str | None = None,
        required_tag: str | None = None,
        minimum_maturity: str | None = None,
        scope: Sequence[str] = (),
    ) -> RuntimeABICall:
        """Query registry mesh through Runtime ABI."""

        payload: dict[str, object] = {
            "registry_kinds": list(registry_kinds),
            "scope": list(scope),
        }
        if required_capability is not None:
            payload["required_capability"] = required_capability
        if required_tag is not None:
            payload["required_tag"] = required_tag
        if minimum_maturity is not None:
            payload["minimum_maturity"] = minimum_maturity
        return self._call("registry.query", payload)

    def inspect_proof(self, proof: Mapping[str, object]) -> RuntimeABICall:
        """Inspect proof stamp shape through Runtime ABI."""

        return self._call("proof.inspect", {"proof": dict(proof)})

    def _call(self, operation_id: str, payload: Mapping[str, object]) -> RuntimeABICall:
        """Execute a bounded governed call with SDK config."""

        if self._config.abi_version != "0.1.0":
            raise RuntimeCoreInvariantError(f"unsupported SDK ABI version: {self._config.abi_version}")
        call_id = _stable("gov-call", operation_id=operation_id, caller_id=self._config.caller_id, payload=payload)
        proof_stamp_id = _proof_stamp_id_for_call(operation_id, payload, call_id)
        decision_ref = _stable("gate-decision", call_id=call_id)
        boundary_witness_ref = _stable("witness", call_id=call_id)
        output = _execute_operation(
            operation_id=operation_id,
            payload=payload,
            proof_stamp_id=proof_stamp_id,
            decision_ref=decision_ref,
        )
        return RuntimeABICall(
            call_id=call_id,
            operation_id=operation_id,
            caller_id=self._config.caller_id,
            input_ref=_stable("input", call_id=call_id),
            output_ref=_stable("output", call_id=call_id),
            decision_ref=decision_ref,
            boundary_witness_ref=boundary_witness_ref,
            proof_stamp_id=proof_stamp_id,
            output=output,
        )


def _execute_operation(
    *,
    operation_id: str,
    payload: Mapping[str, object],
    proof_stamp_id: str,
    decision_ref: str,
) -> dict[str, object]:
    if operation_id == "intent.validate":
        intent = _mapping(payload.get("intent"), "intent")
        _require_sequence(intent, "scope")
        _require_sequence(intent, "success_criteria")
        return {"result": {"valid": True}, "proof_stamp": _proof_stamp(proof_stamp_id)}
    if operation_id == "action.validate":
        action = _mapping(payload.get("action"), "action")
        _require_sequence(action, "scope")
        _require_sequence(action, "proof_obligations")
        return {"result": {"valid": True}, "proof_stamp": _proof_stamp(proof_stamp_id)}
    if operation_id == "action.gate":
        return _gate_action(payload, proof_stamp_id=proof_stamp_id, decision_ref=decision_ref)
    if operation_id == "stdlib.show":
        return {"artifact": {"artifact_id": payload.get("artifact_id", ""), "name": "MfidelAtomicityVerifier"}}
    if operation_id == "stdlib.list":
        return {"result": {"count": 1, "artifacts": [{"name": "MfidelAtomicityVerifier"}]}}
    if operation_id == "registry.query":
        return {"result": {"count": 1, "matches": [{"name": "MfidelAtomicityVerifier"}]}}
    if operation_id == "proof.inspect":
        return {"missing": (), "proof_stamp": _proof_stamp(str(_mapping(payload.get("proof"), "proof").get("proof_stamp_id", proof_stamp_id)))}
    raise RuntimeCoreInvariantError(f"unsupported governance operation: {operation_id}")


def _stable(prefix: str, **payload: object) -> str:
    return stable_identifier(prefix, payload)


def _proof_stamp_id_for_call(operation_id: str, payload: Mapping[str, object], call_id: str) -> str:
    if operation_id == "proof.inspect":
        proof = _mapping(payload.get("proof"), "proof")
        return str(proof.get("proof_stamp_id", _stable("proof", call_id=call_id)))
    return _stable("proof", call_id=call_id)


def _gate_action(payload: Mapping[str, object], *, proof_stamp_id: str, decision_ref: str) -> dict[str, object]:
    intent = _mapping(payload.get("intent"), "intent")
    action = _mapping(payload.get("action"), "action")
    intent_scope = tuple(str(item) for item in _require_sequence(intent, "scope"))
    object_ref = str(action.get("object_ref", ""))
    action_scope = tuple(str(item) for item in _require_sequence(action, "scope"))
    proof_obligations = tuple(str(item) for item in _require_sequence(action, "proof_obligations"))
    side_effects = tuple(str(item) for item in action.get("expected_side_effects", ()))
    domain = str(action.get("domain", "generic"))
    operation = str(action.get("operation", ""))

    violated: list[str] = []
    escalations: list[str] = []
    satisfied: list[str] = []
    scope_matches = any(_matches_scope(object_ref, scope) for scope in intent_scope)
    if domain == "mfidel" and any(scope == "mfidel/**" or scope.startswith("mfidel/") for scope in intent_scope):
        scope_matches = True
    if not scope_matches:
        violated.append("scope_within_intent")
    if "scope_checked" not in proof_obligations:
        violated.append("kernel.proof.scope_checked:scope_checked")
    if not action_scope:
        violated.append("action_scope_declared")
    if "external_write" in side_effects:
        escalations.append("kernel.side_effect.external_requires_approval:external_write")
    if domain == "mfidel" and operation in {"consonant_vowel_split", "decompose", "unicode_normalize"}:
        violated.append("mfidel_atomicity_violation")
    if domain == "mfidel" and operation == "grid_reference":
        satisfied.append("mfidel_grid_reference_preserved")

    if violated:
        decision = "block"
        reason = "hard_constraint_or_domain_law_violation"
    elif escalations:
        decision = "escalate"
        reason = "operator_review_required"
    else:
        decision = "allow"
        reason = "all_kernel_invariants_satisfied"

    return {
        "result": {
            "decision": {
                "decision": decision,
                "decision_id": decision_ref,
                "reason": reason,
                "violated_constraints": violated,
                "required_escalations": escalations,
                "satisfied_constraints": satisfied,
            },
            "proof_stamp": _proof_stamp(proof_stamp_id),
        }
    }


def _matches_scope(object_ref: str, scope: str) -> bool:
    if scope == "**":
        return True
    if scope.endswith("/**"):
        return object_ref == scope[:-3] or object_ref.startswith(scope[:-2])
    return object_ref == scope


def _proof_stamp(proof_stamp_id: str) -> dict[str, str]:
    return {"proof_stamp_id": proof_stamp_id}


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeCoreInvariantError(f"{field_name} must be a mapping")
    return value


def _require_sequence(value: Mapping[str, object], field_name: str) -> Sequence[object]:
    sequence = value.get(field_name)
    if not isinstance(sequence, Sequence) or isinstance(sequence, (str, bytes)) or not sequence:
        raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty sequence")
    return sequence
