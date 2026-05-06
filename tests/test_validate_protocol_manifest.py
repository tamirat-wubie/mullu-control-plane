"""Tests for the public governance protocol manifest.

Purpose: prove deployment orchestration receipts and effect assurance records
are indexed as public handoff contracts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_protocol_manifest and schema manifest JSON.
Invariants:
  - Every public top-level schema is listed in the protocol manifest.
  - Deployment orchestration receipts have a stable schema id and URN.
  - Effect assurance has a stable schema id and URN.
  - Missing public handoff schema entries fail closed.
"""

from __future__ import annotations

from scripts.validate_protocol_manifest import load_manifest, validate_protocol_manifest


def test_protocol_manifest_indexes_deployment_orchestration_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["deployment-orchestration-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/deployment_orchestration_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_agent_identity() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    identity_entry = entries["agent-identity"]
    runtime_entry = entries["agent-runtime-snapshot"]
    authority_entry = entries["enterprise-authority"]

    assert validate_protocol_manifest(manifest) == []
    assert identity_entry["path"] == "schemas/agent_identity.schema.json"
    assert identity_entry["urn"] == "urn:mullusi:schema:agent-identity:1"
    assert identity_entry["surface"] == "identity"
    assert runtime_entry["path"] == "schemas/agent_runtime_snapshot.schema.json"
    assert runtime_entry["urn"] == "urn:mullusi:schema:agent-runtime-snapshot:1"
    assert runtime_entry["surface"] == "runtime"
    assert authority_entry["path"] == "schemas/enterprise_authority.schema.json"
    assert authority_entry["urn"] == "urn:mullusi:schema:enterprise-authority:1"
    assert authority_entry["surface"] == "identity"


def test_protocol_manifest_indexes_claim_verification_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    claim_entry = entries["claim-verification-report"]

    assert validate_protocol_manifest(manifest) == []
    assert claim_entry["path"] == "schemas/claim_verification_report.schema.json"
    assert claim_entry["urn"] == "urn:mullusi:schema:claim-verification-report:1"
    assert claim_entry["surface"] == "claim"


def test_protocol_manifest_indexes_connector_self_healing_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    healing_entry = entries["connector-self-healing-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert healing_entry["path"] == "schemas/connector_self_healing_receipt.schema.json"
    assert healing_entry["urn"] == "urn:mullusi:schema:connector-self-healing-receipt:1"
    assert healing_entry["surface"] == "connector"


def test_protocol_manifest_indexes_collaboration_case() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    collaboration_entry = entries["collaboration-case"]
    commercial_entry = entries["commercial-metering-snapshot"]
    operational_entry = entries["operational-case"]

    assert validate_protocol_manifest(manifest) == []
    assert collaboration_entry["path"] == "schemas/collaboration_case.schema.json"
    assert collaboration_entry["urn"] == "urn:mullusi:schema:collaboration-case:1"
    assert collaboration_entry["surface"] == "collaboration"
    assert commercial_entry["path"] == "schemas/commercial_metering_snapshot.schema.json"
    assert commercial_entry["urn"] == "urn:mullusi:schema:commercial-metering-snapshot:1"
    assert commercial_entry["surface"] == "commercial"
    assert operational_entry["path"] == "schemas/operational_case.schema.json"
    assert operational_entry["urn"] == "urn:mullusi:schema:operational-case:1"
    assert operational_entry["surface"] == "case_management"


def test_protocol_manifest_indexes_connector_certification_registry() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    connector_entry = entries["connector-certification-registry"]
    commercial_entry = entries["commercial-metering-snapshot"]
    data_governance_entry = entries["data-governance-snapshot"]

    assert validate_protocol_manifest(manifest) == []
    assert connector_entry["path"] == "schemas/connector_certification_registry.schema.json"
    assert connector_entry["urn"] == "urn:mullusi:schema:connector-certification-registry:1"
    assert connector_entry["surface"] == "connector"
    assert commercial_entry["path"] == "schemas/commercial_metering_snapshot.schema.json"
    assert commercial_entry["urn"] == "urn:mullusi:schema:commercial-metering-snapshot:1"
    assert commercial_entry["surface"] == "commercial"
    assert data_governance_entry["path"] == "schemas/data_governance_snapshot.schema.json"
    assert data_governance_entry["urn"] == "urn:mullusi:schema:data-governance-snapshot:1"
    assert data_governance_entry["surface"] == "data_governance"


def test_protocol_manifest_indexes_deployment_orchestration_validation() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    validation_entry = entries["deployment-orchestration-receipt-validation"]

    assert validate_protocol_manifest(manifest) == []
    assert validation_entry["path"] == "schemas/deployment_orchestration_receipt_validation.schema.json"
    assert validation_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt-validation:1"
    assert validation_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_deployment_publication_closure_validation() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    validation_entry = entries["deployment-publication-closure-validation"]

    assert validate_protocol_manifest(manifest) == []
    assert validation_entry["path"] == "schemas/deployment_publication_closure_validation.schema.json"
    assert validation_entry["urn"] == "urn:mullusi:schema:deployment-publication-closure-validation:1"
    assert validation_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_effect_assurance_record() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    effect_entry = entries["effect-assurance"]
    eval_entry = entries["eval-run"]

    assert validate_protocol_manifest(manifest) == []
    assert effect_entry["path"] == "schemas/effect_assurance.schema.json"
    assert effect_entry["urn"] == "urn:mullusi:schema:effect-assurance:1"
    assert effect_entry["surface"] == "effect_assurance"
    assert eval_entry["path"] == "schemas/eval_run.schema.json"
    assert eval_entry["urn"] == "urn:mullusi:schema:eval-run:1"
    assert eval_entry["surface"] == "testing"


def test_protocol_manifest_indexes_promotion_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["general-agent-promotion-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/general_agent_promotion_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-closure-plan:1"
    assert plan_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_policy_proof_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    policy_proof_entry = entries["policy-proof-report"]
    policy_studio_entry = entries["policy-studio-session"]

    assert validate_protocol_manifest(manifest) == []
    assert policy_proof_entry["path"] == "schemas/policy_proof_report.schema.json"
    assert policy_proof_entry["urn"] == "urn:mullusi:schema:policy-proof-report:1"
    assert policy_proof_entry["surface"] == "policy"
    assert policy_studio_entry["path"] == "schemas/policy_studio_session.schema.json"
    assert policy_studio_entry["urn"] == "urn:mullusi:schema:policy-studio-session:1"
    assert policy_studio_entry["surface"] == "policy"


def test_protocol_manifest_indexes_capability_adapter_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["capability-adapter-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/capability_adapter_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:capability-adapter-closure-plan:1"
    assert plan_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_capability_upgrade_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    upgrade_entry = entries["capability-upgrade-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert upgrade_entry["path"] == "schemas/capability_upgrade_plan.schema.json"
    assert upgrade_entry["urn"] == "urn:mullusi:schema:capability-upgrade-plan:1"
    assert upgrade_entry["surface"] == "capability"


def test_protocol_manifest_indexes_autonomous_test_generation_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    test_generation_entry = entries["autonomous-test-generation-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert test_generation_entry["path"] == "schemas/autonomous_test_generation_plan.schema.json"
    assert test_generation_entry["urn"] == "urn:mullusi:schema:autonomous-test-generation-plan:1"
    assert test_generation_entry["surface"] == "testing"


def test_protocol_manifest_indexes_capability_candidate_package() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    candidate_entry = entries["capability-candidate"]

    assert validate_protocol_manifest(manifest) == []
    assert candidate_entry["path"] == "schemas/capability_candidate.schema.json"
    assert candidate_entry["urn"] == "urn:mullusi:schema:capability-candidate:1"
    assert candidate_entry["surface"] == "capability"


def test_protocol_manifest_indexes_capability_maturity_assessment() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    maturity_entry = entries["capability-maturity"]

    assert validate_protocol_manifest(manifest) == []
    assert maturity_entry["path"] == "schemas/capability_maturity.schema.json"
    assert maturity_entry["urn"] == "urn:mullusi:schema:capability-maturity:1"
    assert maturity_entry["surface"] == "capability"


def test_protocol_manifest_indexes_domain_operating_pack() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    domain_entry = entries["domain-operating-pack"]

    assert validate_protocol_manifest(manifest) == []
    assert domain_entry["path"] == "schemas/domain_operating_pack.schema.json"
    assert domain_entry["urn"] == "urn:mullusi:schema:domain-operating-pack:1"
    assert domain_entry["surface"] == "domain"


def test_protocol_manifest_indexes_trust_ledger_bundle() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-bundle"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_bundle.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-bundle:1"
    assert trust_entry["surface"] == "evidence"


def test_protocol_manifest_indexes_trust_ledger_anchor_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-anchor-receipt"]
    compliance_entry = entries["risk-compliance-mapping-snapshot"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_anchor_receipt.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-anchor-receipt:1"
    assert trust_entry["surface"] == "evidence"
    assert compliance_entry["path"] == "schemas/risk_compliance_mapping_snapshot.schema.json"
    assert compliance_entry["urn"] == "urn:mullusi:schema:risk-compliance-mapping-snapshot:1"
    assert compliance_entry["surface"] == "compliance"


def test_protocol_manifest_indexes_memory_lattice_admission() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    lattice_entry = entries["memory-lattice"]

    assert validate_protocol_manifest(manifest) == []
    assert lattice_entry["path"] == "schemas/memory_lattice.schema.json"
    assert lattice_entry["urn"] == "urn:mullusi:schema:memory-lattice:1"
    assert lattice_entry["surface"] == "memory"


def test_protocol_manifest_indexes_multimodal_operation_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    multimodal_entry = entries["multimodal-operation-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert multimodal_entry["path"] == "schemas/multimodal_operation_receipt.schema.json"
    assert multimodal_entry["urn"] == "urn:mullusi:schema:multimodal-operation-receipt:1"
    assert multimodal_entry["surface"] == "multimodal"


def test_protocol_manifest_indexes_physical_action_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    physical_entry = entries["physical-action-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert physical_entry["path"] == "schemas/physical_action_receipt.schema.json"
    assert physical_entry["urn"] == "urn:mullusi:schema:physical-action-receipt:1"
    assert physical_entry["surface"] == "safety"


def test_protocol_manifest_indexes_temporal_operation_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    temporal_entry = entries["temporal-operation-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert temporal_entry["path"] == "schemas/temporal_operation_receipt.schema.json"
    assert temporal_entry["urn"] == "urn:mullusi:schema:temporal-operation-receipt:1"
    assert temporal_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_evidence_freshness_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    evidence_entry = entries["temporal-evidence-freshness-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert evidence_entry["path"] == "schemas/temporal_evidence_freshness_receipt.schema.json"
    assert evidence_entry["urn"] == "urn:mullusi:schema:temporal-evidence-freshness-receipt:1"
    assert evidence_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_memory_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    memory_entry = entries["temporal-memory-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert memory_entry["path"] == "schemas/temporal_memory_receipt.schema.json"
    assert memory_entry["urn"] == "urn:mullusi:schema:temporal-memory-receipt:1"
    assert memory_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_memory_refresh_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    refresh_entry = entries["temporal-memory-refresh-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert refresh_entry["path"] == "schemas/temporal_memory_refresh_receipt.schema.json"
    assert refresh_entry["urn"] == "urn:mullusi:schema:temporal-memory-refresh-receipt:1"
    assert refresh_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_scheduler_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    scheduler_entry = entries["temporal-scheduler-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert scheduler_entry["path"] == "schemas/temporal_scheduler_receipt.schema.json"
    assert scheduler_entry["urn"] == "urn:mullusi:schema:temporal-scheduler-receipt:1"
    assert scheduler_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_sla_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    sla_entry = entries["temporal-sla-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert sla_entry["path"] == "schemas/temporal_sla_receipt.schema.json"
    assert sla_entry["urn"] == "urn:mullusi:schema:temporal-sla-receipt:1"
    assert sla_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_promotion_environment_bindings() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    binding_entry = entries["general-agent-promotion-environment-bindings"]

    assert validate_protocol_manifest(manifest) == []
    assert binding_entry["path"] == "schemas/general_agent_promotion_environment_bindings.schema.json"
    assert binding_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-environment-bindings:1"
    assert binding_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_environment_binding_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["general-agent-promotion-environment-binding-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/general_agent_promotion_environment_binding_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-environment-binding-receipt:1"
    assert receipt_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_handoff_packet() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    packet_entry = entries["general-agent-promotion-handoff-packet"]

    assert validate_protocol_manifest(manifest) == []
    assert packet_entry["path"] == "schemas/general_agent_promotion_handoff_packet.schema.json"
    assert packet_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-handoff-packet:1"
    assert packet_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_gateway_publication_readiness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    readiness_entry = entries["gateway-publication-readiness"]

    assert validate_protocol_manifest(manifest) == []
    assert readiness_entry["path"] == "schemas/gateway_publication_readiness.schema.json"
    assert readiness_entry["urn"] == "urn:mullusi:schema:gateway-publication-readiness:1"
    assert readiness_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_gateway_publication_receipt_validation() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    validation_entry = entries["gateway-publication-receipt-validation"]

    assert validate_protocol_manifest(manifest) == []
    assert validation_entry["path"] == "schemas/gateway_publication_receipt_validation.schema.json"
    assert validation_entry["urn"] == "urn:mullusi:schema:gateway-publication-receipt-validation:1"
    assert validation_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_operational_intelligence_contracts() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    goal_entry = entries["goal"]
    simulation_entry = entries["simulation-receipt"]
    world_state_entry = entries["world-state"]

    assert validate_protocol_manifest(manifest) == []
    assert goal_entry["path"] == "schemas/goal.schema.json"
    assert goal_entry["urn"] == "urn:mullusi:schema:goal:1"
    assert goal_entry["surface"] == "planning"
    assert simulation_entry["path"] == "schemas/simulation_receipt.schema.json"
    assert simulation_entry["urn"] == "urn:mullusi:schema:simulation-receipt:1"
    assert simulation_entry["surface"] == "simulation"
    assert world_state_entry["path"] == "schemas/world_state.schema.json"
    assert world_state_entry["urn"] == "urn:mullusi:schema:world-state:1"
    assert world_state_entry["surface"] == "world"


def test_protocol_manifest_indexes_workflow_mining_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    workflow_entry = entries["workflow-mining-report"]
    workflow_run_entry = entries["workflow-run"]

    assert validate_protocol_manifest(manifest) == []
    assert workflow_entry["path"] == "schemas/workflow_mining_report.schema.json"
    assert workflow_entry["urn"] == "urn:mullusi:schema:workflow-mining-report:1"
    assert workflow_entry["surface"] == "workflow"
    assert workflow_run_entry["path"] == "schemas/workflow_run.schema.json"
    assert workflow_run_entry["urn"] == "urn:mullusi:schema:workflow-run:1"
    assert workflow_run_entry["surface"] == "workflow"


def test_protocol_manifest_indexes_terminal_closure_certificate() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    closure_entry = entries["terminal-closure-certificate"]

    assert validate_protocol_manifest(manifest) == []
    assert closure_entry["path"] == "schemas/terminal_closure_certificate.schema.json"
    assert closure_entry["urn"] == "urn:mullusi:schema:terminal-closure-certificate:1"
    assert closure_entry["surface"] == "closure"


def test_protocol_manifest_indexes_worker_mesh_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    worker_entry = entries["worker-mesh"]

    assert validate_protocol_manifest(manifest) == []
    assert worker_entry["path"] == "schemas/worker_mesh.schema.json"
    assert worker_entry["urn"] == "urn:mullusi:schema:worker-mesh:1"
    assert worker_entry["surface"] == "worker"


def test_protocol_manifest_indexes_reflex_deployment_witness_envelope() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    envelope_entry = entries["reflex-deployment-witness-envelope"]

    assert validate_protocol_manifest(manifest) == []
    assert envelope_entry["path"] == "schemas/reflex_deployment_witness_envelope.schema.json"
    assert envelope_entry["urn"] == "urn:mullusi:schema:reflex-deployment-witness-envelope:1"
    assert envelope_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_reflex_validator_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["reflex-deployment-witness-validator-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/reflex_deployment_witness_validator_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:reflex-deployment-witness-validator-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_production_evidence_endpoint_contracts() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    production_entry = entries["production-evidence-witness"]
    capability_entry = entries["capability-evidence-endpoint"]
    audit_entry = entries["audit-verification-endpoint"]
    proof_entry = entries["proof-verification-endpoint"]

    assert validate_protocol_manifest(manifest) == []
    assert production_entry["path"] == "schemas/production_evidence_witness.schema.json"
    assert production_entry["urn"] == "urn:mullusi:schema:production-evidence-witness:1"
    assert production_entry["surface"] == "deployment"
    assert capability_entry["path"] == "schemas/capability_evidence_endpoint.schema.json"
    assert capability_entry["urn"] == "urn:mullusi:schema:capability-evidence-endpoint:1"
    assert capability_entry["surface"] == "capability"
    assert audit_entry["path"] == "schemas/audit_verification_endpoint.schema.json"
    assert audit_entry["urn"] == "urn:mullusi:schema:audit-verification-endpoint:1"
    assert audit_entry["surface"] == "audit"
    assert proof_entry["path"] == "schemas/proof_verification_endpoint.schema.json"
    assert proof_entry["urn"] == "urn:mullusi:schema:proof-verification-endpoint:1"
    assert proof_entry["surface"] == "proof"


def test_protocol_manifest_indexes_finance_approval_packet_proof() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}

    assert entries["finance-approval-packet-proof"]["path"] == "schemas/finance_approval_packet_proof.schema.json"
    assert entries["finance-approval-packet-proof"]["urn"] == "urn:mullusi:schema:finance-approval-packet-proof:1"
    assert entries["finance-approval-packet-proof"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-plan"]["path"] == (
        "schemas/finance_approval_live_handoff_plan.schema.json"
    )
    assert entries["finance-approval-live-handoff-plan"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-plan:1"
    )
    assert entries["finance-approval-live-handoff-plan"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-closure-run"]["path"] == (
        "schemas/finance_approval_live_handoff_closure_run.schema.json"
    )
    assert entries["finance-approval-live-handoff-closure-run"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-closure-run:1"
    )
    assert entries["finance-approval-live-handoff-closure-run"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-chain-validation"]["path"] == (
        "schemas/finance_approval_live_handoff_chain_validation.schema.json"
    )
    assert entries["finance-approval-live-handoff-chain-validation"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-chain-validation:1"
    )
    assert entries["finance-approval-live-handoff-chain-validation"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-preflight"]["path"] == (
        "schemas/finance_approval_live_handoff_preflight.schema.json"
    )
    assert entries["finance-approval-live-handoff-preflight"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-preflight:1"
    )
    assert entries["finance-approval-live-handoff-preflight"]["surface"] == "finance"
    assert entries["finance-approval-email-calendar-binding-receipt"]["path"] == (
        "schemas/finance_approval_email_calendar_binding_receipt.schema.json"
    )
    assert entries["finance-approval-email-calendar-binding-receipt"]["urn"] == (
        "urn:mullusi:schema:finance-approval-email-calendar-binding-receipt:1"
    )
    assert entries["finance-approval-email-calendar-binding-receipt"]["surface"] == "finance"
    assert entries["finance-approval-email-calendar-live-receipt"]["path"] == (
        "schemas/finance_approval_email_calendar_live_receipt.schema.json"
    )
    assert entries["finance-approval-email-calendar-live-receipt"]["urn"] == (
        "urn:mullusi:schema:finance-approval-email-calendar-live-receipt:1"
    )
    assert entries["finance-approval-email-calendar-live-receipt"]["surface"] == "finance"
    assert entries["finance-approval-handoff-packet"]["path"] == "schemas/finance_approval_handoff_packet.schema.json"
    assert entries["finance-approval-handoff-packet"]["urn"] == (
        "urn:mullusi:schema:finance-approval-handoff-packet:1"
    )
    assert entries["finance-approval-handoff-packet"]["surface"] == "finance"
    assert entries["finance-approval-operator-summary"]["path"] == (
        "schemas/finance_approval_operator_summary.schema.json"
    )
    assert entries["finance-approval-operator-summary"]["urn"] == (
        "urn:mullusi:schema:finance-approval-operator-summary:1"
    )
    assert entries["finance-approval-operator-summary"]["surface"] == "finance"
    assert validate_protocol_manifest(manifest) == []


def test_protocol_manifest_rejects_missing_deployment_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "deployment-orchestration-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "deployment_orchestration_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_effect_assurance_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "effect-assurance"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "effect_assurance.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_closure_plan_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-closure-plan"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_closure_plan.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_capability_adapter_closure_plan_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "capability-adapter-closure-plan"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "capability_adapter_closure_plan.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_environment_bindings_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-environment-bindings"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_environment_bindings.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_environment_binding_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-environment-binding-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_environment_binding_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_handoff_packet_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-handoff-packet"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_handoff_packet.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_terminal_closure_certificate_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "terminal-closure-certificate"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "terminal_closure_certificate.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_finance_live_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "finance-approval-email-calendar-live-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "finance_approval_email_calendar_live_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_finance_operator_summary_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "finance-approval-operator-summary"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "finance_approval_operator_summary.schema.json" in errors[0]
    assert "schemas/" in errors[0]
