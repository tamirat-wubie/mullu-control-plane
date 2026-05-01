"""Purpose: generate the proof coverage matrix witness.

Governance scope: records request-proof, action-proof, runtime-witness, and
audit-chain coverage for externally callable control-plane surfaces.
Dependencies: repository source tree, route decorators, JSON serialization.
Invariants: generated output is deterministic; representative HTTP routes map
to declared application routes or explicit wildcard families.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"
ASSURANCE_OUTPUT = REPO_ROOT / ".change_assurance" / "proof_coverage_matrix.json"
ROUTE_PATTERN = re.compile(r"@(?:router|app)\.(?:get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']")
ROUTER_PREFIX_PATTERN = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']")
FRAMEWORK_GENERATED_ROUTES = frozenset({"/docs", "/openapi.json", "/redoc"})
COVERAGE_LEVELS = ["gap", "read_model", "request_proof", "action_proof", "audit_chain"]
COVERAGE_STATES = ["proven", "witnessed", "unproven"]


def _surface(
    surface_id: str,
    paths: list[str],
    request_proof: str,
    action_proof: str,
    audit: str,
    coverage_state: str,
    evidence_files: list[str],
    notes: str,
    runtime_witnesses: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "surface_id": surface_id,
        "representative_paths": paths,
        "request_proof": request_proof,
        "action_proof": action_proof,
        "audit": audit,
        "coverage_state": coverage_state,
        "evidence_files": evidence_files,
        "notes": notes,
        "runtime_witnesses": runtime_witnesses or [],
    }


def proof_coverage_matrix() -> dict[str, Any]:
    gateway_witnesses = [
        "command_lifecycle_events_are_hash_linked",
        "terminal_closure_requires_evidence_refs",
        "successful_response_is_bound_to_response_evidence_closure",
    ]
    surfaces = [
        _surface(
            "gateway_capability_fabric",
            [
                "/webhook/*",
                "/capability-fabric/read-model",
                "/commands/{command_id}/closure",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/server.py",
                "gateway/capability_fabric.py",
                "mcoi/mcoi_runtime/core/command_capability_admission.py",
            ],
            "Gateway command admission, request receipt envelopes, and terminal closure expose runtime witnesses.",
            gateway_witnesses,
        ),
        _surface(
            "llm_streaming",
            ["/api/v1/stream", "/api/v1/chat/stream"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/app/streaming.py",
                "mcoi/tests/test_streaming.py",
                "mcoi/tests/test_server_phase200.py",
                "schemas/streaming_budget_enforcement.schema.json",
                "docs/41_streaming_budget_enforcement.md",
            ],
            "SSE responses include precharge, first-byte, chunk-debit, and final-reconcile proof identifiers.",
        ),
        _surface(
            "llm_completion",
            ["/api/v1/complete", "/api/v1/complete/safe", "/api/v1/complete/auto"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
            ],
            "Completion routes are governed through budget, model routing, and proof bridge checks.",
        ),
        _surface(
            "llm_chat_workflow",
            ["/api/v1/chat", "/api/v1/chat/workflow", "/api/v1/chat/workflow/history"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
            ],
            "Chat and workflow routes preserve governed request and action proof boundaries.",
        ),
        _surface(
            "cost_budget_read_models",
            ["/api/v1/budget", "/api/v1/costs", "/api/v1/costs/top-spenders"],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/governance/guards/budget.py",
            ],
            "Budget and cost surfaces expose bounded read models over governed spend state.",
        ),
        _surface(
            "model_experiment_control",
            ["/api/v1/models", "/api/v1/ab-test", "/api/v1/ab-test/summary"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            ["mcoi/mcoi_runtime/app/routers/llm.py"],
            "Model catalog and experiment control routes are declared as governed control surfaces.",
        ),
        _surface(
            "policy_version_registry",
            [
                "/api/v1/policies/{policy_id}/versions",
                "/api/v1/policies/{policy_id}/versions/{version}",
                "/api/v1/policies/{policy_id}/versions/{version}/promote",
                "/api/v1/policies/{policy_id}/rollback",
                "/api/v1/policies/{policy_id}/diff",
                "/api/v1/policies/{policy_id}/shadow/{shadow_version}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/policy_versions.py",
                "mcoi/mcoi_runtime/governance/policy/versioning.py",
                "mcoi/tests/test_policy_version_endpoints.py",
                "mcoi/tests/test_policy_versioning.py",
            ],
            "Policy version routes expose immutable artifact registration, promotion, rollback, diff, and shadow evaluation.",
        ),
        _surface(
            "pilot_provisioning",
            [
                "/api/v1/pilots/provision",
                "/api/v1/pilots/provisions",
                "/api/v1/pilots/provisions/{pilot_id}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/pilot.py",
                "mcoi/mcoi_runtime/app/pilot_init.py",
                "mcoi/tests/test_pilot_init.py",
                "docs/47_one_command_pilot_bringup.md",
            ],
            "Pilot provisioning returns deterministic scaffold artifacts, persists accepted provision records, and exposes bounded operator history read models.",
        ),
        _surface(
            "hosted_demo_sandbox",
            [
                "/api/v1/sandbox/summary",
                "/api/v1/sandbox/traces",
                "/api/v1/sandbox/lineage/{trace_id}",
                "/api/v1/sandbox/policy-evaluations",
            ],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/sandbox.py",
                "mcoi/mcoi_runtime/core/hosted_demo_sandbox.py",
                "mcoi/tests/test_hosted_demo_sandbox.py",
                "docs/48_hosted_demo_sandbox.md",
            ],
            "Hosted demo sandbox exposes deterministic read-only traces, lineage projections, and policy evaluations without runtime mutation.",
        ),
        _surface(
            "federated_control_plane",
            ["/api/v1/federation/summary"],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/federation.py",
                "mcoi/mcoi_runtime/core/federated_control_plane.py",
                "mcoi/tests/test_federated_control_plane.py",
                "docs/51_federated_control_plane.md",
            ],
            "Federated control-plane summary exposes signed policy distribution and local enforcement receipts without tenant data replication.",
        ),
        _surface(
            "gateway_webhook_ingress",
            ["/webhook/web", "/webhook/slack", "/webhook/telegram"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/router.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Webhook ingress binds tenant resolution, command ledger, and event-log evidence.",
        ),
        _surface(
            "gateway_approval_resolution",
            ["/webhook/approve/{request_id}", "/authority/approval-chains"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/approval.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Approval resolution exposes protected operator paths and audited chain state.",
        ),
        _surface(
            "authority_obligation_mesh",
            ["/authority/witness", "/authority/responsibility", "/authority/obligations", "/authority/escalations"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/authority_obligation_mesh.py",
                "tests/test_gateway/test_authority_obligation_mesh.py",
            ],
            "Authority and obligation surfaces expose unresolved responsibility state.",
            [
                "pending_approval_chain_count",
                "open_obligation_count",
                "overdue_obligation_count",
                "escalated_obligation_count",
            ],
        ),
        _surface(
            "gateway_runtime_witness",
            ["/gateway/witness", "/runtime/witness", "/anchors/latest"],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "scripts/preflight_deployment_witness.py",
                "scripts/collect_deployment_witness.py",
                "scripts/validate_mcp_capability_manifest.py",
                "tests/test_preflight_deployment_witness.py",
                "tests/test_collect_deployment_witness.py",
            ],
            "Runtime witness surfaces publish bounded operational and responsibility debt state; preflight validates configured MCP manifests before deployment witness readiness.",
            [
                "latest_command_event_hash",
                "latest_terminal_certificate_id",
                "open_obligation_count",
                "overdue_obligation_count",
            ],
        ),
        _surface(
            "runtime_conformance_attestation",
            ["/runtime/conformance"],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/conformance.py",
                "scripts/collect_runtime_conformance.py",
                "scripts/validate_mcp_capability_manifest.py",
                "schemas/runtime_conformance_certificate.schema.json",
                "tests/test_gateway/test_conformance.py",
                "tests/test_collect_runtime_conformance.py",
            ],
            "Runtime conformance certificate binds live witness, closure, fabric, isolation, lineage, authority, MCP manifest validity, proof-matrix, and document-drift checks into one signed attestation.",
            [
                "gateway_witness_valid",
                "runtime_witness_valid",
                "command_closure_canary_passed",
                "capability_admission_canary_passed",
                "dangerous_capability_isolation_canary_passed",
                "lineage_query_canary_passed",
                "authority_responsibility_debt_clear",
                "authority_directory_sync_receipt_valid",
            ],
        ),
        _surface(
            "replay_determinism",
            ["/api/v1/replay/{trace_id}/determinism"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/replay.py",
                "mcoi/mcoi_runtime/core/replay_determinism_harness.py",
                "mcoi/tests/test_replay_determinism_endpoints.py",
                "mcoi/tests/test_replay_determinism_harness.py",
                "docs/03_trace_and_replay.md",
            ],
            "Replay determinism route emits governed reports over completed traces with bounded operation specs.",
        ),
        _surface(
            "tool_invocation",
            ["/api/v1/tools/invoke", "/api/v1/workflow/tools"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data.py",
                "mcoi/mcoi_runtime/app/routers/workflow.py",
                "mcoi/mcoi_runtime/core/tool_use.py",
                "mcoi/mcoi_runtime/mcp/capability_bridge.py",
                "gateway/mcp_operator_read_model.py",
                "gateway/mcp_capability_fabric.py",
                "gateway/mcp_capabilities.py",
                "scripts/validate_mcp_capability_manifest.py",
                "examples/mcp_capability_manifest.json",
                "docs/55_mcp_capability_manifest.md",
                "tests/test_gateway/test_mcp_capability_fabric.py",
                "tests/test_validate_mcp_capability_manifest.py",
            ],
            "Tool invocation and MCP capability import bind action proof ids, capability policy receipts, authority-obligation ownership records, and validated operator manifests.",
        ),
        _surface(
            "governed_session",
            ["GovernedSession.llm", "GovernedSession.execute", "GovernedSession.query"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/core/governed_session.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
                "mcoi/tests/test_governed_session.py",
            ],
            "Session entry points return request-envelope proofs and retain action proof lineage.",
        ),
        _surface(
            "health_docs_exempt",
            ["/health", "/docs", "/openapi.json", "/redoc"],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            ["gateway/server.py"],
            "Operational liveness and documentation surfaces are outside the proof-critical path.",
        ),
        _surface(
            "lineage_query_api",
            [
                "/api/v1/lineage/resolve",
                "/api/v1/lineage/{trace_id}",
                "/api/v1/lineage/output/{output_id}",
                "/api/v1/lineage/command/{command_id}",
            ],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/lineage.py",
                "mcoi/mcoi_runtime/core/lineage_query.py",
                "docs/42_lineage_query_api.md",
                "schemas/lineage_query.schema.json",
                "schemas/trace_entry.schema.json",
                "schemas/replay_record.schema.json",
            ],
            "Lineage query API resolves read-only lineage:// URIs with bounded output, command, graph, and policy-version read models.",
        ),
    ]
    closure_actions = [
        {
            "action_id": "bind_tool_arguments_to_capability_policy_receipts",
            "surfaces": ["tool_invocation", "gateway_capability_fabric"],
            "status": "closed",
        },
        {
            "action_id": "bind_mcp_capabilities_to_authority_obligation_records",
            "surfaces": ["tool_invocation", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "publish_validated_mcp_capability_manifest_contract",
            "surfaces": ["tool_invocation", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "normalize_gateway_request_receipt_envelopes",
            "surfaces": ["gateway_capability_fabric"],
            "status": "closed",
        },
        {
            "action_id": "bound_authority_read_models_to_paginated_windows",
            "surfaces": ["gateway_approval_resolution", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "implement_lineage_query_routes_and_schema",
            "surfaces": ["lineage_query_api"],
            "status": "closed",
        },
        {
            "action_id": "connect_pilot_scaffold_to_hosted_provisioning_endpoint",
            "surfaces": ["pilot_provisioning"],
            "status": "closed",
        },
        {
            "action_id": "publish_hosted_demo_sandbox_read_models",
            "surfaces": ["hosted_demo_sandbox"],
            "status": "closed",
        },
        {
            "action_id": "publish_federated_control_plane_read_model",
            "surfaces": ["federated_control_plane"],
            "status": "closed",
        },
        {
            "action_id": "publish_runtime_conformance_attestation",
            "surfaces": ["runtime_conformance_attestation"],
            "status": "closed",
        },
    ]
    return {
        "schema_version": 1,
        "generated_by": "scripts/proof_coverage_matrix.py",
        "coverage_levels": COVERAGE_LEVELS,
        "coverage_states": COVERAGE_STATES,
        "coverage_summary": coverage_summary(surfaces),
        "surfaces": surfaces,
        "closure_actions": closure_actions,
    }


def coverage_summary(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic aggregate proof coverage counts."""
    by_state = {state: 0 for state in COVERAGE_STATES}
    by_request_proof = {level: 0 for level in COVERAGE_LEVELS}
    by_action_proof = {level: 0 for level in COVERAGE_LEVELS}
    by_audit = {level: 0 for level in COVERAGE_LEVELS}
    for surface in surfaces:
        by_state[surface["coverage_state"]] = by_state.get(surface["coverage_state"], 0) + 1
        by_request_proof[surface["request_proof"]] = by_request_proof.get(surface["request_proof"], 0) + 1
        by_action_proof[surface["action_proof"]] = by_action_proof.get(surface["action_proof"], 0) + 1
        by_audit[surface["audit"]] = by_audit.get(surface["audit"], 0) + 1
    return {
        "surface_count": len(surfaces),
        "by_coverage_state": by_state,
        "by_request_proof": by_request_proof,
        "by_action_proof": by_action_proof,
        "by_audit": by_audit,
    }


def discover_declared_routes(repo_root: Path = REPO_ROOT) -> set[str]:
    route_roots = [repo_root / "mcoi" / "mcoi_runtime" / "app" / "routers", repo_root / "gateway"]
    routes = set(FRAMEWORK_GENERATED_ROUTES)
    for route_root in route_roots:
        if not route_root.exists():
            continue
        for python_file in route_root.rglob("*.py"):
            if "__pycache__" in python_file.parts:
                continue
            source = python_file.read_text(encoding="utf-8")
            file_routes = ROUTE_PATTERN.findall(source)
            routes.update(file_routes)
            prefixes = ROUTER_PREFIX_PATTERN.findall(source)
            for prefix in prefixes:
                routes.update(f"{prefix}{route}" for route in file_routes if route.startswith("/"))
    return routes


def validate_matrix_routes(matrix: dict[str, Any], routes: set[str]) -> list[str]:
    missing: list[str] = []
    for surface in matrix["surfaces"]:
        if surface.get("coverage_state") == "unproven":
            continue
        for path in surface["representative_paths"]:
            if not path.startswith("/"):
                continue
            if path.endswith("*"):
                if not any(route.startswith(path[:-1]) for route in routes):
                    missing.append(path)
                continue
            if path not in routes:
                missing.append(path)
    return missing


def write_matrix(path: Path, matrix: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or validate the proof coverage matrix.")
    parser.add_argument("--output", type=Path, default=CANONICAL_OUTPUT)
    parser.add_argument("--assurance-output", type=Path, default=ASSURANCE_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = proof_coverage_matrix()
    missing_routes = validate_matrix_routes(matrix, discover_declared_routes())
    if missing_routes:
        raise SystemExit(f"Representative routes are not declared: {', '.join(sorted(missing_routes))}")
    if args.check:
        expected = json.dumps(matrix, indent=2, sort_keys=True) + "\n"
        actual = args.output.read_text(encoding="utf-8")
        if actual != expected:
            raise SystemExit(f"{args.output} is stale; run scripts/proof_coverage_matrix.py")
        return 0
    write_matrix(args.output, matrix)
    write_matrix(args.assurance_output, matrix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
