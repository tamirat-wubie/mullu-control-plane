# Schema Compatibility Policy

These schemas define the canonical shared JSON interchange surface for Mullu Platform.
The public Mullu Governance Protocol manifest lives at
`schemas/mullu_governance_protocol.manifest.json` and declares which schema
files are open wire contracts. Runtime modules under `mcoi/`, `gateway/`, and
`scripts/` remain reference implementation surfaces, not protocol contracts.

## Compatibility Rules

1. Root objects are strict. Unknown top-level fields are rejected unless they are carried inside `metadata` or `extensions`.
2. `metadata` and `extensions` are the only forward-compatible escape hatches.
3. Shared docs in `docs/` define meaning. Schemas define field names, required fields, and enums for interchange.
4. Existing field meanings are stable. Do not repurpose an existing field for a different semantic role.
5. Additive changes are preferred. New required fields or reinterpreted enums require a coordinated docs, schema, and runtime update.
6. Python and Rust implementations must map to these fields without reinterpretation.
7. `workflow` and `plan` are shared coordination surfaces. They do not redefine policy, verification, or execution semantics.

## File Map

| File | Purpose |
| --- | --- |
| `agent_identity.schema.json` | Canonical user-owned agent identity, scope, budget, delegation, and reputation record |
| `audit_verification_endpoint.schema.json` | Canonical live gateway audit-chain verification response |
| `autonomous_test_generation_plan.schema.json` | Canonical activation-blocked test generation plan from failure traces |
| `capability_adapter_closure_plan.schema.json` | Canonical adapter source closure action plan |
| `capability_candidate.schema.json` | Canonical forge-generated candidate capability package |
| `capability_descriptor.schema.json` | Canonical capability declaration |
| `capability_evidence_endpoint.schema.json` | Canonical live gateway capability evidence projection |
| `capability_maturity.schema.json` | Canonical evidence-derived capability maturity assessment |
| `collaboration_case.schema.json` | Canonical governed collaboration case with approval separation and non-terminal closure |
| `capability_registry_entry.schema.json` | Universal governed capability registry entry |
| `capability_upgrade_plan.schema.json` | Canonical governed capability upgrade proposal plan |
| `claim_verification_report.schema.json` | Canonical claim graph verification report for support, contradiction, freshness, and execution admission |
| `commercial_metering_snapshot.schema.json` | Canonical commercial metering snapshot with plans, usage, provider costs, decisions, and tenant billing summaries |
| `data_governance_snapshot.schema.json` | Canonical data governance lifecycle snapshot with decisions and retention controls |
| `deployment_orchestration_receipt.schema.json` | Canonical gateway deployment handoff receipt |
| `deployment_witness.schema.json` | Canonical live gateway deployment witness artifact |
| `domain_capsule.schema.json` | Domain capsule operating-model package |
| `effect_assurance.schema.json` | Canonical planned, observed, and reconciled effect record |
| `finance_approval_email_calendar_binding_receipt.schema.json` | Canonical redacted connector-token presence receipt for finance live handoff |
| `finance_approval_email_calendar_live_receipt.schema.json` | Canonical redacted live email/calendar receipt for finance approval handoff evidence |
| `finance_approval_handoff_packet.schema.json` | Canonical operator handoff packet for finance approval proof-pilot and live blockers |
| `finance_approval_live_handoff_chain_validation.schema.json` | Canonical aggregate chain validation report for finance approval live handoff artifacts |
| `finance_approval_live_handoff_closure_run.schema.json` | Canonical dry-run command sequence for finance approval live handoff closure |
| `finance_approval_live_handoff_plan.schema.json` | Canonical finance approval live email handoff promotion plan |
| `finance_approval_live_handoff_preflight.schema.json` | Canonical four-step preflight report for finance approval live handoff readiness |
| `finance_approval_packet_proof.schema.json` | Canonical proof export for governed finance approval packet closure or review |
| `physical_action_receipt.schema.json` | Canonical no-effect physical action safety receipt |
| `general_agent_promotion_closure_plan.schema.json` | Canonical promotion closure action plan |
| `general_agent_promotion_environment_bindings.schema.json` | Canonical presence-only operator environment binding contract |
| `general_agent_promotion_environment_binding_receipt.schema.json` | Canonical presence-only operator environment binding receipt |
| `general_agent_promotion_handoff_packet.schema.json` | Canonical promotion handoff packet |
| `gateway_observability_snapshot.schema.json` | Canonical gateway observability summary with bounded run metrics |
| `goal.schema.json` | Canonical governed goal compilation contract |
| `policy_decision.schema.json` | Canonical policy gate outcome |
| `production_evidence_witness.schema.json` | Canonical live gateway production evidence witness response |
| `proof_verification_endpoint.schema.json` | Canonical live gateway proof verification response |
| `execution_result.schema.json` | Canonical execution outcome |
| `trace_entry.schema.json` | Canonical causal audit entry |
| `replay_record.schema.json` | Canonical replay and audit capture |
| `simulation_receipt.schema.json` | Canonical causal simulation dry-run receipt |
| `streaming_budget_enforcement.schema.json` | Canonical predictive streaming budget event |
| `temporal_evidence_freshness_receipt.schema.json` | Canonical governed evidence freshness recheck receipt |
| `temporal_operation_receipt.schema.json` | Canonical runtime-owned temporal operation receipt |
| `temporal_reapproval_receipt.schema.json` | Canonical governed execution-time approval recheck receipt |
| `temporal_dispatch_window_receipt.schema.json` | Canonical governed dispatch-window admission receipt |
| `temporal_budget_window_receipt.schema.json` | Canonical governed tenant-local budget-window admission receipt |
| `temporal_memory_receipt.schema.json` | Canonical governed temporal memory use receipt |
| `temporal_memory_refresh_receipt.schema.json` | Canonical governed temporal memory refresh workflow receipt |
| `temporal_scheduler_receipt.schema.json` | Canonical governed scheduled wakeup and lease receipt |
| `temporal_sla_receipt.schema.json` | Canonical governed SLA, business-window, and escalation receipt |
| `terminal_closure_certificate.schema.json` | Canonical final command closure certificate |
| `trust_ledger_anchor_receipt.schema.json` | Canonical signed external proof anchor receipt for trust ledger bundles |
| `trust_ledger_bundle.schema.json` | Canonical signed evidence bundle for terminal closure anchoring |
| `verification_result.schema.json` | Canonical verification closure |
| `learning_admission.schema.json` | Canonical learning admission decision |
| `memory_lattice.schema.json` | Canonical memory planning and execution admission claim |
| `multimodal_operation_receipt.schema.json` | Canonical governed multimodal operation admission receipt |
| `environment_fingerprint.schema.json` | Canonical environment fingerprint |
| `lineage_query.schema.json` | Canonical lineage query response document |
| `multimodal_operation_receipt.schema.json` | Canonical governed multimodal operation receipt |
| `world_state.schema.json` | Canonical world-state graph projection |
| `worker_mesh.schema.json` | Canonical networked worker lease and dispatch receipt |
| `workflow.schema.json` | Shared workflow descriptor interchange surface |
| `plan.schema.json` | Shared plan definition |
| `policy_proof_report.schema.json` | Canonical policy prover result and counterexample report |
| `policy_studio_session.schema.json` | Canonical read-only policy studio session with simulations and bounded probe report |

## Notes

The schemas stay conservative by keeping canonical meaning in shared docs and future growth in `metadata` or `extensions`. If shared behavior changes, update docs and schemas in the same change.
