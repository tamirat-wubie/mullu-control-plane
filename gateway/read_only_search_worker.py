"""Read-only local knowledge search worker.

Purpose: provide a Foundation Mode search worker path for local, text-like
knowledge sources without mutation, network, secrets, external tenant resources,
or spend.
Governance scope: worker lease authority, SearchDecisionReceipt admission,
source path containment, evidence-only retrieval, bounded reads, deterministic
ranking, and secret redaction.
Dependencies: pathlib, re, command-spine hashing, search governance receipts,
and worker mesh contracts.
Invariants:
  - Search execution requires a matching SearchDecisionReceipt.
  - Only knowledge-root-relative source files are accepted.
  - Retrieved content is evidence only and never instruction authority.
  - Requests containing mutation, network, or secret-bearing inputs fail closed.
  - Output excerpts are bounded and redacted before receipt publication.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.search_governance import (
    SEARCH_CAPABILITY_ID,
    SEARCH_DECISION_RECEIPT_SCHEMA_REF,
)
from gateway.worker_mesh import (
    WORKER_MESH_SCHEMA_REF,
    WorkerDispatchRequest,
    WorkerHandler,
    WorkerHandlerResult,
    WorkerLease,
    WorkerLeaseBudget,
    WorkerLeaseScope,
)


SEARCH_OPERATION = "search"
SEARCH_RECEIPT_VERSION = "search_receipt.v1"
SEARCH_BUDGET_POLICY_REF = "policy:search-decision-budget-gate"
DEFAULT_MAX_SOURCES = 25
DEFAULT_MAX_BYTES_PER_SOURCE = 262_144
DEFAULT_MAX_RESULT_COUNT = 5
SUPPORTED_SEARCH_EXTENSIONS = frozenset(
    {".txt", ".md", ".markdown", ".rst", ".json", ".yaml", ".yml", ".csv", ".tsv"}
)
SEARCH_RECEIPT_CONTRACT_EVIDENCE_REFS = (
    "schemas/search_receipt.schema.json",
    "examples/search_receipt.foundation.json",
    "scripts/validate_search_receipt.py",
    "tests/test_validate_search_receipt.py",
    "docs/78_search_receipt_contract.md",
    "docs/maps/MULLUSI_SEARCH_LAYER_MAP.md",
    "examples/sdlc/requirement_search_receipt_contract_20260614.json",
    "examples/sdlc/design_search_receipt_contract_20260614.json",
)
_MUTATION_KEYS = frozenset(
    {"write", "writes", "mutation", "mutations", "patch", "delete", "remove", "move", "rename", "command", "shell"}
)
_NETWORK_KEYS = frozenset({"url", "urls", "network", "network_targets", "endpoint", "host"})
_SECRET_KEYS = frozenset({"secret", "secrets", "token", "tokens", "password", "api_key", "private_key"})
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:api[_-]?key|secret|token|password|private[_-]?key)[a-z0-9_-]*)\b\s*[:=]\s*[^,\s]+"
)
_SOURCE_INSTRUCTION_PATTERN = re.compile(
    r"(?i)\b("
    r"ignore\s+(?:all\s+)?previous|"
    r"bypass\s+(?:governance|policy|approval|instructions?)|"
    r"disable\s+(?:governance|policy|safety)|"
    r"reveal\s+(?:secret|token|password|key)|"
    r"send\s+secrets?|"
    r"system\s+prompt|"
    r"developer\s+message|"
    r"call\s+(?:tool|function)|"
    r"execute\s+(?:command|shell)"
    r")\b"
)
_CONFLICT_POLARITY_PAIRS = (
    ("enabled", "disabled"),
    ("allowed", "blocked"),
    ("true", "false"),
    ("yes", "no"),
    ("present", "missing"),
    ("passed", "failed"),
    ("pass", "fail"),
)
_CONFLICT_POLARITY_TERMS = frozenset(term for pair in _CONFLICT_POLARITY_PAIRS for term in pair)
_SEARCH_INTENT_WORDS = frozenset({"search", "find", "lookup", "look", "up", "docs", "document", "documents", "knowledge", "for"})


@dataclass(frozen=True, slots=True)
class SearchInspectionBounds:
    """Bounded scan settings for local knowledge search."""

    max_sources: int = DEFAULT_MAX_SOURCES
    max_bytes_per_source: int = DEFAULT_MAX_BYTES_PER_SOURCE
    max_result_count: int = DEFAULT_MAX_RESULT_COUNT

    def __post_init__(self) -> None:
        _require_positive_int(self.max_sources, "max_sources")
        _require_positive_int(self.max_bytes_per_source, "max_bytes_per_source")
        _require_positive_int(self.max_result_count, "max_result_count")


def build_read_only_search_worker_lease(
    *,
    tenant_id: str,
    lease_id: str,
    issued_at: str,
    expires_at: str,
    worker_id: str = "knowledge-search-read-only-worker",
    max_operations: int = 10,
    knowledge_root_ref: str = "knowledge:local",
) -> WorkerLease:
    """Build the worker mesh lease for read-only local knowledge search."""
    return WorkerLease(
        worker_id=worker_id,
        capability=SEARCH_CAPABILITY_ID,
        tenant_id=tenant_id,
        lease_id=lease_id,
        allowed_operations=[SEARCH_OPERATION],
        forbidden_operations=["write", "delete", "move", "network", "shell", "web_search"],
        budget=WorkerLeaseBudget(max_operations=max_operations, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=[knowledge_root_ref],
            data_classes=["search_query_hash", "knowledge_source_metadata", "knowledge_text_excerpt"],
            network_allowlist=[],
        ),
        timeout_seconds=30,
        sandbox="local-read-only-search",
        policy_refs=["policy:foundation-mode:read-only-search-worker"],
        receipt_schema_ref=WORKER_MESH_SCHEMA_REF,
        verification_ref="verification:knowledge-search-read-only",
        recovery_ref="recovery:operator-review",
        expires_at=expires_at,
        issued_at=issued_at,
        metadata={
            "mutation_allowed": False,
            "external_network_allowed": False,
            "secrets_required": False,
            "spend_required": False,
            "retrieval_authority": "evidence_only",
            "search_decision_receipt_required": True,
            "supported_extensions": sorted(SUPPORTED_SEARCH_EXTENSIONS),
        },
    )


def create_read_only_search_handler(knowledge_root: Path) -> WorkerHandler:
    """Return a worker mesh handler bound to a local knowledge root."""
    resolved_root = knowledge_root.resolve()

    def handler(request: WorkerDispatchRequest) -> WorkerHandlerResult:
        return inspect_search_request(resolved_root, request)

    return handler


def inspect_search_request(
    knowledge_root: Path,
    request: WorkerDispatchRequest,
) -> WorkerHandlerResult:
    """Search local text-like knowledge sources from a worker mesh payload."""
    payload = dict(request.payload)
    denial = _payload_denial(payload)
    if denial:
        return WorkerHandlerResult(status="failed", error=denial)

    try:
        query = _required_text(payload.get("query"), "query")
        decision_receipt = _required_mapping(payload.get("search_decision_receipt"), "search_decision_receipt")
        decision_denial = _search_decision_denial(
            decision_receipt,
            request=request,
            query=query,
        )
        if decision_denial:
            return WorkerHandlerResult(status="failed", error=decision_denial)
        bounds = _bounds_from_payload(payload, decision_receipt=decision_receipt)
        relative_sources = _string_list(payload.get("sources", []), "sources")
        source_paths = _resolve_sources(
            knowledge_root=knowledge_root,
            relative_sources=relative_sources,
            max_sources=bounds.max_sources,
        )
    except ValueError as exc:
        return WorkerHandlerResult(status="failed", error=str(exc))

    results = []
    truncated_sources = 0
    for source_path in source_paths:
        try:
            source_result = _search_source(
                knowledge_root=knowledge_root,
                source_path=source_path,
                query=query,
                max_bytes_per_source=bounds.max_bytes_per_source,
            )
        except ValueError as exc:
            return WorkerHandlerResult(status="failed", error=str(exc))
        if source_result["truncated"] is True:
            truncated_sources += 1
        results.extend(source_result["matches"])

    ranked_results = sorted(
        results,
        key=lambda result: (result["relative_path"], result["line"], result["excerpt"]),
    )[: bounds.max_result_count]
    search_receipt = _build_search_receipt(
        request=request,
        decision_receipt=decision_receipt,
        ranked_results=ranked_results,
        relative_sources=relative_sources,
        bounds=bounds,
        truncated_sources=truncated_sources,
    )
    search_receipt_hash = canonical_hash(search_receipt)
    output = {
        "capability_id": SEARCH_CAPABILITY_ID,
        "operation": SEARCH_OPERATION,
        "knowledge_root_hash": canonical_hash(str(knowledge_root)),
        "query_hash": canonical_hash({"query": query}),
        "search_decision_receipt_id": decision_receipt["receipt_id"],
        "search_decision_receipt_hash": decision_receipt["receipt_hash"],
        "search_receipt_id": search_receipt["receipt_id"],
        "search_receipt_hash": search_receipt_hash,
        "request_payload_hash": canonical_hash(payload),
        "sources_considered": len(source_paths),
        "sources_searched": len(source_paths),
        "truncated_sources": truncated_sources,
        "result_count": len(ranked_results),
        "results": ranked_results,
        "search_receipt": search_receipt,
        "supported_extensions": sorted(SUPPORTED_SEARCH_EXTENSIONS),
        "bounds": {
            "max_sources": bounds.max_sources,
            "max_bytes_per_source": bounds.max_bytes_per_source,
            "max_result_count": bounds.max_result_count,
        },
        "proof_obligations": [
            "no_write_operation",
            "no_external_network",
            "source_path_boundary",
            "search_decision_receipt_required",
            "evidence_only_retrieval",
            "scan_bounds",
            "secret_redaction",
            "deterministic_traversal",
        ],
    }
    output_hash = canonical_hash(output)
    return WorkerHandlerResult(
        status="succeeded",
        output=output,
        evidence_refs=[
            f"knowledge-search:decision:{decision_receipt['receipt_hash'][:16]}",
            f"knowledge-search:boundary:{canonical_hash({'root': str(knowledge_root), 'sources': relative_sources})[:16]}",
            f"knowledge-search:result:{output_hash[:16]}",
            f"knowledge-search:search-receipt:{search_receipt_hash[:16]}",
        ],
        cost=0.0,
    )


def _build_search_receipt(
    *,
    request: WorkerDispatchRequest,
    decision_receipt: dict[str, Any],
    ranked_results: list[dict[str, Any]],
    relative_sources: list[str],
    bounds: SearchInspectionBounds,
    truncated_sources: int,
) -> dict[str, Any]:
    current_freshness_required = decision_receipt.get("freshness_state") == "source_required"
    evidence_items = _search_evidence_items(
        request=request,
        ranked_results=ranked_results,
        freshness_required=current_freshness_required,
    )
    citation_refs = [item["citation_ref"] for item in evidence_items]
    instruction_authority_errors = _instruction_authority_errors(ranked_results)
    conflict_refs = _conflict_refs(ranked_results)
    freshness_status = "unknown_blocked" if current_freshness_required else "not_required"
    freshness_proof_state = "Unknown" if current_freshness_required else "Pass"
    retrieval_errors = instruction_authority_errors if evidence_items else [_retrieval_failed_error(request.request_id)]
    receipt_state = _receipt_state(evidence_items=evidence_items, conflict_refs=conflict_refs)
    search_state = "LOCAL_SEARCH" if evidence_items else "SEARCH_FAILED_WITH_EXPLANATION"
    solver_outcome = (
        "AwaitingEvidence"
        if current_freshness_required or not evidence_items or conflict_refs
        else "SolvedVerified"
    )
    prompt_injection_detected = bool(instruction_authority_errors)
    conflict_handling = _conflict_handling(
        freshness_required=current_freshness_required,
        prompt_injection_detected=prompt_injection_detected,
        conflict_detected=bool(conflict_refs),
    )
    receipt_seed = canonical_hash(
        {
            "request_id": request.request_id,
            "decision_receipt_id": decision_receipt["receipt_id"],
            "citation_refs": citation_refs,
            "retrieval_errors": retrieval_errors,
        }
    )
    receipt_id = f"search-receipt-{receipt_seed[:16]}"
    dynamic_evidence_refs = [
        f"knowledge-search:decision:{decision_receipt['receipt_hash'][:16]}",
        (
            "knowledge-search:request:"
            f"{canonical_hash({'request_id': request.request_id, 'input_hash': request.input_hash})[:16]}"
        ),
        f"knowledge-search:receipt:{receipt_seed[:16]}",
    ]
    bounds_ref = canonical_hash(
        {
            "max_sources": bounds.max_sources,
            "max_bytes_per_source": bounds.max_bytes_per_source,
            "max_result_count": bounds.max_result_count,
        }
    )
    budget_result = _budget_result_from_decision(decision_receipt)
    return {
        "receipt_id": receipt_id,
        "receipt_version": SEARCH_RECEIPT_VERSION,
        "search_decision_ref": f"receipt://search-decision/{decision_receipt['receipt_id']}",
        "request_id": request.request_id,
        "tenant_id": request.tenant_id,
        "actor_id": str(decision_receipt.get("actor_id", "")),
        "created_at": request.requested_at or str(decision_receipt.get("generated_at", "")),
        "solver_outcome": solver_outcome,
        "receipt_state": receipt_state,
        "search_state": search_state,
        "freshness_result": {
            "freshness_required": current_freshness_required,
            "freshness_status": freshness_status,
            "current_info_claim_allowed": False,
            "max_age_seconds": None,
            "proof_state": freshness_proof_state,
            "rationale_refs": [
                "policy:foundation-mode:local-search-freshness",
                f"receipt://search-decision/{decision_receipt['receipt_id']}",
            ],
        },
        "source_plan_result": {
            "selected_sources": ["local_docs"],
            "attempted_sources": ["local_docs"],
            "tenant_scope_verified": True,
            "external_retrieval_performed": False,
            "connector_scope_ref": None,
            "rationale_refs": [
                "policy:foundation-mode:read-only-search-worker",
                "worker:knowledge-search-read-only-worker",
            ],
        },
        "cache_result": {
            "state": "not_checked",
            "cache_key_ref": None,
            "tenant_scoped": True,
            "stale_cache_used": False,
        },
        "budget_result": budget_result,
        "evidence_summary": {
            "evidence_count": len(evidence_items),
            "citation_count": len(citation_refs),
            "conflict_count": len(conflict_refs),
            "stale_source_count": 0,
            "retrieval_error_count": len(retrieval_errors),
            "content_body_included": False,
        },
        "evidence_items": evidence_items,
        "citation_refs": citation_refs,
        "conflict_refs": conflict_refs,
        "stale_source_refs": [],
        "retrieval_errors": retrieval_errors,
        "retrieval_safety_result": {
            "retrieved_content_authority": "evidence_only",
            "prompt_injection_guard_applied": True,
            "prompt_injection_detected": prompt_injection_detected,
            "source_instruction_authority_granted": False,
            "tool_instruction_from_source_allowed": False,
            "policy_instruction_from_source_allowed": False,
            "private_source_scope_verified": True,
            "conflict_handling": conflict_handling,
        },
        "governance_guards": {
            "execution_authority_granted": False,
            "connector_authority_granted": False,
            "answer_claim_authority_granted": False,
            "terminal_closure": False,
            "raw_secret_material_included": False,
            "retrieved_instruction_authority_granted": False,
            "mfidel_atomicity_preserved": True,
        },
        "receipt_envelope": {
            "uao_ref": f"uao://worker-search/{request.command_id}",
            "causal_decision_trace_ref": f"trace://worker-search/{request.request_id}",
            "receipt_ref": f"receipt://search-receipt/{receipt_id}",
        },
        "evidence_refs": _unique_texts(
            [
                *SEARCH_RECEIPT_CONTRACT_EVIDENCE_REFS,
                *dynamic_evidence_refs,
                f"knowledge-search:sources:{canonical_hash(relative_sources)[:16]}",
                f"knowledge-search:bounds:{bounds_ref[:16]}",
                f"knowledge-search:truncated-sources:{truncated_sources}",
            ]
        ),
        "metadata": {
            "raw_query_exposed": False,
            "result_excerpt_count": len(ranked_results),
            "local_source_count": len(relative_sources),
            "prompt_injection_marker_count": len(instruction_authority_errors),
            "conflict_marker_count": len(conflict_refs),
            "source_excerpt_body_excluded_from_receipt": True,
        },
    }


def _budget_result_from_decision(decision_receipt: dict[str, Any]) -> dict[str, Any]:
    decision_ref = f"receipt://search-decision/{decision_receipt['receipt_id']}"
    decision_budget_state = str(decision_receipt.get("budget_state") or "unknown")
    estimated_cost_units = _nonnegative_number_or_none(decision_receipt.get("estimated_cost_units"))
    budget_limit_units = _nonnegative_number_or_none(decision_receipt.get("budget_limit_units"))
    remaining_units = _remaining_budget_units(
        budget_limit_units=budget_limit_units,
        estimated_cost_units=estimated_cost_units,
    )
    state, proof_state, binding_state = _runtime_budget_binding_state(decision_budget_state)
    rationale_refs = _unique_texts(
        [
            SEARCH_BUDGET_POLICY_REF,
            "worker-budget:zero-cost-local-search",
            decision_ref,
        ]
    )
    evidence_refs = _unique_texts(
        [
            f"knowledge-search:decision:{str(decision_receipt.get('receipt_hash', ''))[:16]}",
            decision_ref,
            SEARCH_BUDGET_POLICY_REF,
        ]
    )
    return {
        "state": state,
        "actual_cost_class": "none",
        "approval_ref": None,
        "proof_state": proof_state,
        "budget_policy_ref": SEARCH_BUDGET_POLICY_REF,
        "budget_decision_ref": decision_ref,
        "decision_budget_state": decision_budget_state,
        "decision_estimated_cost_units": estimated_cost_units,
        "decision_budget_limit_units": budget_limit_units,
        "decision_budget_remaining_units": remaining_units,
        "budget_binding_state": binding_state,
        "budget_evidence_refs": evidence_refs,
        "rationale_refs": rationale_refs,
    }


def _runtime_budget_binding_state(decision_budget_state: str) -> tuple[str, str, str]:
    if decision_budget_state == "allowed":
        return "within_budget", "Pass", "bound_to_search_decision"
    if decision_budget_state == "not_required":
        return "not_applicable", "Pass", "not_applicable"
    if decision_budget_state == "blocked":
        return "blocked_by_budget", "Fail", "blocked_by_budget"
    return "unknown_blocked", "BudgetUnknown", "budget_unknown_blocked"


def _remaining_budget_units(
    *,
    budget_limit_units: float | None,
    estimated_cost_units: float | None,
) -> float | None:
    if budget_limit_units is None or estimated_cost_units is None:
        return None
    if budget_limit_units <= 0:
        return None
    return max(budget_limit_units - estimated_cost_units, 0.0)


def _nonnegative_number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return float(value)


def _search_evidence_items(
    *,
    request: WorkerDispatchRequest,
    ranked_results: list[dict[str, Any]],
    freshness_required: bool,
) -> list[dict[str, Any]]:
    evidence_items = []
    for result in ranked_results:
        source_ref = f"{result['relative_path']}#L{result['line']}"
        evidence_seed = canonical_hash(
            {
                "request_id": request.request_id,
                "source_ref": source_ref,
                "content_hash": result["content_hash"],
            }
        )
        evidence_items.append(
            {
                "evidence_ref": f"evidence://local-docs/{evidence_seed[:16]}",
                "source_type": "local_docs",
                "source_ref": source_ref,
                "citation_ref": f"citation://local-docs/{evidence_seed[:16]}",
                "observed_at": request.requested_at or None,
                "fresh_until": None,
                "freshness_status": "unknown" if freshness_required else "not_required",
                "trust_tier": "local_governed",
                "content_hash_ref": f"hash://sha256/{result['content_hash']}",
                "content_body": None,
            }
        )
    return evidence_items


def _retrieval_failed_error(request_id: str) -> dict[str, Any]:
    error_seed = canonical_hash({"request_id": request_id, "error": "no_local_search_evidence"})
    return {
        "error_ref": f"error://local-docs/{error_seed[:16]}",
        "source_type": "local_docs",
        "error_class": "retrieval_failed",
        "blocking": True,
        "rationale_refs": [
            "policy:foundation-mode:read-only-search-worker",
            "reason:no_local_search_evidence",
        ],
    }


def _instruction_authority_errors(ranked_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors = []
    for result in ranked_results:
        if result.get("source_instruction_marker") is not True:
            continue
        source_ref = f"{result['relative_path']}#L{result['line']}"
        error_seed = canonical_hash(
            {
                "source_ref": source_ref,
                "content_hash": result["content_hash"],
                "error": "instruction_authority_rejected",
            }
        )
        errors.append(
            {
                "error_ref": f"error://local-docs/{error_seed[:16]}",
                "source_type": "local_docs",
                "error_class": "instruction_authority_rejected",
                "blocking": False,
                "rationale_refs": [
                    "policy:retrieved-content-evidence-only",
                    f"source://local-docs/{canonical_hash(source_ref)[:16]}",
                ],
            }
        )
    return errors


def _conflict_refs(ranked_results: list[dict[str, Any]]) -> list[str]:
    claims_by_subject: dict[str, dict[str, set[str]]] = {}
    for result in ranked_results:
        subject = result.get("claim_subject")
        polarity = result.get("claim_polarity")
        if not isinstance(subject, str) or not subject:
            continue
        if not isinstance(polarity, str) or not polarity:
            continue
        source_ref = f"{result['relative_path']}#L{result['line']}"
        claims_by_subject.setdefault(subject, {}).setdefault(polarity, set()).add(source_ref)

    conflict_refs = []
    for subject, polarity_sources in sorted(claims_by_subject.items()):
        for positive, negative in _CONFLICT_POLARITY_PAIRS:
            if positive in polarity_sources and negative in polarity_sources:
                conflict_seed = canonical_hash(
                    {
                        "subject": subject,
                        "positive": sorted(polarity_sources[positive]),
                        "negative": sorted(polarity_sources[negative]),
                    }
                )
                conflict_refs.append(f"conflict://local-docs/{conflict_seed[:16]}")
                break
    return conflict_refs


def _receipt_state(*, evidence_items: list[dict[str, Any]], conflict_refs: list[str]) -> str:
    if not evidence_items:
        return "RETRIEVAL_FAILED"
    if conflict_refs:
        return "CONFLICT_DETECTED"
    return "EVIDENCE_AVAILABLE"


def _conflict_handling(
    *,
    freshness_required: bool,
    prompt_injection_detected: bool,
    conflict_detected: bool,
) -> str:
    if prompt_injection_detected:
        return "escalate"
    if freshness_required:
        return "block_current_claim"
    if conflict_detected:
        return "cite_conflict"
    return "cite_conflict"


def _unique_texts(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _payload_denial(payload: dict[str, Any]) -> str:
    keys = {str(key).strip().lower() for key in payload}
    if keys.intersection(_MUTATION_KEYS):
        return "mutation_input_forbidden"
    if keys.intersection(_NETWORK_KEYS):
        return "network_input_forbidden"
    if keys.intersection(_SECRET_KEYS):
        return "secret_input_forbidden"
    if _contains_secret_like_value(payload):
        return "secret_input_forbidden"
    return ""


def _contains_secret_like_value(value: Any) -> bool:
    if isinstance(value, str):
        return _SECRET_VALUE_PATTERN.search(value) is not None
    if isinstance(value, list):
        return any(_contains_secret_like_value(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_secret_like_value(item) for item in value.values())
    return False


def _search_decision_denial(
    receipt: dict[str, Any],
    *,
    request: WorkerDispatchRequest,
    query: str,
) -> str:
    if receipt.get("schema_ref") != SEARCH_DECISION_RECEIPT_SCHEMA_REF:
        return "search_decision_schema_invalid"
    if receipt.get("tenant_id") != request.tenant_id:
        return "search_decision_tenant_mismatch"
    if receipt.get("capability_id") != SEARCH_CAPABILITY_ID:
        return "search_decision_capability_mismatch"
    if receipt.get("query_hash") != canonical_hash({"query": query}):
        return "search_decision_query_hash_mismatch"
    if receipt.get("decision") != "allow_search":
        return "search_decision_not_allowed"
    if receipt.get("blocked_reasons"):
        return "search_decision_blocked"
    if receipt.get("retrieval_authority") != "evidence_only":
        return "search_retrieval_authority_invalid"
    if receipt.get("retrieval_instruction_authority_allowed") is not False:
        return "search_retrieval_instruction_authority_forbidden"
    if receipt.get("budget_state") not in {"allowed", "not_required"}:
        return "search_budget_not_allowed"
    if not receipt.get("receipt_hash"):
        return "search_decision_receipt_hash_required"
    if not receipt.get("receipt_id"):
        return "search_decision_receipt_id_required"
    return ""


def _bounds_from_payload(
    payload: dict[str, Any],
    *,
    decision_receipt: dict[str, Any],
) -> SearchInspectionBounds:
    max_result_count = _positive_int(
        payload.get("max_result_count", DEFAULT_MAX_RESULT_COUNT),
        "max_result_count",
    )
    decision_max_result_count = decision_receipt.get("max_result_count", 0)
    if not isinstance(decision_max_result_count, int) or isinstance(decision_max_result_count, bool):
        raise ValueError("search_decision_max_result_count_integer_required")
    if max_result_count > decision_max_result_count:
        raise ValueError("search_result_count_exceeds_decision")
    return SearchInspectionBounds(
        max_sources=_positive_int(payload.get("max_sources", DEFAULT_MAX_SOURCES), "max_sources"),
        max_bytes_per_source=_positive_int(
            payload.get("max_bytes_per_source", DEFAULT_MAX_BYTES_PER_SOURCE),
            "max_bytes_per_source",
        ),
        max_result_count=max_result_count,
    )


def _resolve_sources(
    *,
    knowledge_root: Path,
    relative_sources: list[str],
    max_sources: int,
) -> list[Path]:
    resolved_sources = []
    for relative_source in relative_sources:
        source_path = _resolve_knowledge_relative_path(knowledge_root, relative_source)
        if source_path.is_dir():
            raise ValueError("knowledge_source_file_required")
        if source_path.suffix.lower() not in SUPPORTED_SEARCH_EXTENSIONS:
            raise ValueError("knowledge_source_format_not_supported")
        resolved_sources.append(source_path)
    unique_sorted = sorted(set(resolved_sources), key=lambda path: path.relative_to(knowledge_root).as_posix())
    return unique_sorted[:max_sources]


def _resolve_knowledge_relative_path(knowledge_root: Path, relative_source: str) -> Path:
    if not relative_source or Path(relative_source).is_absolute():
        raise ValueError("source_path_boundary_violation")
    resolved = (knowledge_root / relative_source).resolve()
    try:
        resolved.relative_to(knowledge_root)
    except ValueError as exc:
        raise ValueError("source_path_boundary_violation") from exc
    if not resolved.exists():
        raise ValueError("knowledge_source_not_found")
    return resolved


def _search_source(
    *,
    knowledge_root: Path,
    source_path: Path,
    query: str,
    max_bytes_per_source: int,
) -> dict[str, Any]:
    raw_bytes = source_path.read_bytes()
    truncated = len(raw_bytes) > max_bytes_per_source
    bounded_bytes = raw_bytes[:max_bytes_per_source]
    try:
        text = bounded_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("knowledge_source_text_decode_failed") from exc
    relative_path = source_path.relative_to(knowledge_root).as_posix()
    return {
        "relative_path": relative_path,
        "truncated": truncated,
        "matches": _line_matches(
            text=text,
            query=query,
            relative_path=relative_path,
            content_hash=canonical_hash(raw_bytes.hex()),
        ),
    }


def _line_matches(
    *,
    text: str,
    query: str,
    relative_path: str,
    content_hash: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    query_terms = _query_terms(query)
    if not query_terms:
        return findings
    for line_number, line in enumerate(text.splitlines(), start=1):
        line_lower = line.lower()
        if all(term in line_lower for term in query_terms):
            findings.append(
                {
                    "relative_path": relative_path,
                    "line": line_number,
                    "excerpt": _redacted_excerpt(line),
                    "content_hash": content_hash,
                    "source_freshness": "local_snapshot",
                    "retrieval_authority": "evidence_only",
                    "source_instruction_marker": _source_instruction_marker(line),
                    "claim_subject": _claim_subject(line),
                    "claim_polarity": _claim_polarity(line),
                    "score": 1.0,
                }
            )
    return findings


def _query_terms(query: str) -> list[str]:
    terms = []
    for term in re.findall(r"[A-Za-z0-9_:-]+", query.lower()):
        if term not in _SEARCH_INTENT_WORDS:
            terms.append(term)
    return terms


def _redacted_excerpt(line: str) -> str:
    redacted = _SECRET_VALUE_PATTERN.sub(r"\1=[REDACTED]", line.strip())
    if len(redacted) > 160:
        return f"{redacted[:157]}..."
    return redacted


def _source_instruction_marker(line: str) -> bool:
    return _SOURCE_INSTRUCTION_PATTERN.search(line) is not None


def _claim_subject(line: str) -> str:
    terms = [
        term
        for term in re.findall(r"[A-Za-z0-9_:-]+", line.lower())
        if term not in _CONFLICT_POLARITY_TERMS
    ]
    return " ".join(terms)


def _claim_polarity(line: str) -> str:
    terms = set(re.findall(r"[A-Za-z0-9_:-]+", line.lower()))
    for positive, negative in _CONFLICT_POLARITY_PAIRS:
        if positive in terms:
            return positive
        if negative in terms:
            return negative
    return ""


def _string_list(value: Any, field_name: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError(f"{field_name}_list_required")
    result = []
    for item in values:
        text = _required_text(item, f"{field_name}_item")
        result.append(text)
    if not result:
        raise ValueError(f"{field_name}_required")
    return result


def _required_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}_object_required")
    return dict(value)


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}_string_required")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name}_required")
    return text


def _positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}_integer_required")
    if value <= 0:
        raise ValueError(f"{field_name}_positive_required")
    return value


def _require_positive_int(value: Any, field_name: str) -> None:
    _positive_int(value, field_name)
