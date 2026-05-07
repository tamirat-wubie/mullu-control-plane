"""Purpose: read-only hosted demo sandbox read models.

Governance scope: public sandbox demonstration data for traces, lineage, and
policy evaluations. This module does not mutate runtime state and does not
execute provider calls.
Dependencies: deterministic hashing only.
Invariants: responses are deterministic; every demo output is explicitly marked
read-only; lineage references are bounded to seeded traces.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


SANDBOX_BASE_URL = "https://sandbox.mullusi.com"


@dataclass(frozen=True, slots=True)
class SandboxTraceFrame:
    """Single read-only demo trace frame."""

    frame_id: str
    sequence: int
    operation: str
    tenant_id: str
    policy_version: str
    model_version: str
    budget_ref: str
    proof_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "sequence": self.sequence,
            "operation": self.operation,
            "tenant_id": self.tenant_id,
            "policy_version": self.policy_version,
            "model_version": self.model_version,
            "budget_ref": self.budget_ref,
            "proof_id": self.proof_id,
            "frame_hash": _stable_hash(
                {
                    "frame_id": self.frame_id,
                    "sequence": self.sequence,
                    "operation": self.operation,
                    "tenant_id": self.tenant_id,
                    "policy_version": self.policy_version,
                    "model_version": self.model_version,
                    "budget_ref": self.budget_ref,
                    "proof_id": self.proof_id,
                }
            ),
        }


@dataclass(frozen=True, slots=True)
class SandboxTrace:
    """Seeded read-only trace for sandbox inspection."""

    trace_id: str
    title: str
    frames: tuple[SandboxTraceFrame, ...]

    def to_dict(self) -> dict[str, Any]:
        frames = [frame.to_dict() for frame in self.frames]
        return {
            "trace_id": self.trace_id,
            "title": self.title,
            "frames": frames,
            "frame_count": len(frames),
            "trace_hash": _stable_hash({"trace_id": self.trace_id, "frames": frames}),
            "lineage_uri": f"lineage://trace/{self.trace_id}?depth=25&verify=true",
            "read_only": True,
        }


@dataclass(frozen=True, slots=True)
class SandboxPolicyEvaluation:
    """Seeded read-only policy evaluation."""

    evaluation_id: str
    tenant_id: str
    policy_version: str
    subject: str
    verdict: str
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "evaluation_id": self.evaluation_id,
            "tenant_id": self.tenant_id,
            "policy_version": self.policy_version,
            "subject": self.subject,
            "verdict": self.verdict,
            "reason_codes": list(self.reason_codes),
            "read_only": True,
        }
        return {**payload, "evaluation_hash": _stable_hash(payload)}


class HostedDemoSandbox:
    """Read-only sandbox projection used by hosted demo endpoints."""

    def __init__(self) -> None:
        self._traces = _seed_traces()
        self._policy_evaluations = _seed_policy_evaluations()

    def summary(self) -> dict[str, Any]:
        return {
            "sandbox_url": SANDBOX_BASE_URL,
            "read_only": True,
            "trace_count": len(self._traces),
            "policy_evaluation_count": len(self._policy_evaluations),
            "lineage_query_examples": [
                f"lineage://trace/{trace.trace_id}?depth=25&verify=true"
                for trace in self._traces
            ],
            "governed": True,
        }

    def traces(self) -> list[dict[str, Any]]:
        return [trace.to_dict() for trace in self._traces]

    def policy_evaluations(self) -> list[dict[str, Any]]:
        return [evaluation.to_dict() for evaluation in self._policy_evaluations]

    def lineage(self, trace_id: str) -> dict[str, Any] | None:
        trace = next((item for item in self._traces if item.trace_id == trace_id), None)
        if trace is None:
            return None
        nodes = []
        edges = []
        previous_node_id = ""
        for frame in trace.frames:
            node_id = f"node:{frame.frame_id}"
            nodes.append(
                {
                    "node_id": node_id,
                    "node_type": frame.operation,
                    "trace_id": trace.trace_id,
                    "policy_version": frame.policy_version,
                    "model_version": frame.model_version,
                    "tenant_id": frame.tenant_id,
                    "budget_ref": frame.budget_ref,
                    "proof_id": frame.proof_id,
                    "parent_node_ids": [previous_node_id] if previous_node_id else [],
                    "read_only": True,
                }
            )
            if previous_node_id:
                edges.append({"from_node_id": previous_node_id, "to_node_id": node_id, "relation": "caused"})
            previous_node_id = node_id
        document = {
            "schema_version": 1,
            "lineage_uri": f"lineage://trace/{trace.trace_id}?depth=25&verify=true",
            "root_ref": {"ref_type": "trace", "ref_id": trace.trace_id},
            "verified": True,
            "verification": {"reason_codes": [], "checked_nodes": len(nodes), "checked_edges": len(edges)},
            "nodes": nodes,
            "edges": edges,
            "read_only": True,
            "governed": True,
        }
        document_hash = _stable_hash(document)
        return {
            **document,
            "document_id": f"sandbox-lineage:{document_hash[:16]}",
            "document_hash": f"sha256:{document_hash}",
        }


def _seed_traces() -> tuple[SandboxTrace, ...]:
    return (
        SandboxTrace(
            trace_id="sandbox-trace-budget-cutoff",
            title="Streaming budget cutoff with final settlement",
            frames=(
                SandboxTraceFrame(
                    "frame-1", 1, "request.accepted", "sandbox-tenant", "policy:v1",
                    "model:v1", "budget-demo", "proof:request"
                ),
                SandboxTraceFrame(
                    "frame-2", 2, "budget.reserved", "sandbox-tenant", "policy:v1",
                    "model:v1", "budget-demo", "proof:reserve"
                ),
                SandboxTraceFrame(
                    "frame-3", 3, "stream.cutoff", "sandbox-tenant", "policy:v1",
                    "model:v1", "budget-demo", "proof:cutoff"
                ),
            ),
        ),
        SandboxTrace(
            trace_id="sandbox-trace-policy-shadow",
            title="Policy v2 shadow evaluation beside active policy",
            frames=(
                SandboxTraceFrame(
                    "frame-4", 1, "policy.active_evaluated", "sandbox-tenant", "policy:v1",
                    "model:v1", "budget-demo", "proof:policy-active"
                ),
                SandboxTraceFrame(
                    "frame-5", 2, "policy.shadow_evaluated", "sandbox-tenant", "policy:v2-shadow",
                    "model:v1", "budget-demo", "proof:policy-shadow"
                ),
                SandboxTraceFrame(
                    "frame-6", 3, "response.returned", "sandbox-tenant", "policy:v1",
                    "model:v1", "budget-demo", "proof:response"
                ),
            ),
        ),
    )


def _seed_policy_evaluations() -> tuple[SandboxPolicyEvaluation, ...]:
    return (
        SandboxPolicyEvaluation(
            evaluation_id="sandbox-policy-allow-read",
            tenant_id="sandbox-tenant",
            policy_version="policy:v1",
            subject="lineage.read",
            verdict="allow",
            reason_codes=("policy_conditions_satisfied",),
        ),
        SandboxPolicyEvaluation(
            evaluation_id="sandbox-policy-deny-tool",
            tenant_id="sandbox-tenant",
            policy_version="policy:v1",
            subject="tool.payment.write",
            verdict="deny",
            reason_codes=("tool_permission_not_found",),
        ),
    )


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()
