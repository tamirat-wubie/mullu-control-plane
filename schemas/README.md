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
| `autonomous_test_generation_plan.schema.json` | Canonical activation-blocked test generation plan from failure traces |
| `capability_adapter_closure_plan.schema.json` | Canonical adapter source closure action plan |
| `capability_candidate.schema.json` | Canonical forge-generated candidate capability package |
| `capability_descriptor.schema.json` | Canonical capability declaration |
| `capability_maturity.schema.json` | Canonical evidence-derived capability maturity assessment |
| `capability_registry_entry.schema.json` | Universal governed capability registry entry |
| `capability_upgrade_plan.schema.json` | Canonical governed capability upgrade proposal plan |
| `collaboration_case.schema.json` | Canonical non-terminal collaboration case with approval separation and control evidence |
| `deployment_orchestration_receipt.schema.json` | Canonical gateway deployment handoff receipt |
| `deployment_witness.schema.json` | Canonical live gateway deployment witness artifact |
| `domain_capsule.schema.json` | Domain capsule operating-model package |
| `effect_assurance.schema.json` | Canonical planned, observed, and reconciled effect record |
| `general_agent_promotion_closure_plan.schema.json` | Canonical promotion closure action plan |
| `general_agent_promotion_environment_bindings.schema.json` | Canonical presence-only operator environment binding contract |
| `general_agent_promotion_environment_binding_receipt.schema.json` | Canonical presence-only operator environment binding receipt |
| `general_agent_promotion_handoff_packet.schema.json` | Canonical promotion handoff packet |
| `goal.schema.json` | Canonical governed goal compilation contract |
| `policy_decision.schema.json` | Canonical policy gate outcome |
| `execution_result.schema.json` | Canonical execution outcome |
| `trace_entry.schema.json` | Canonical causal audit entry |
| `replay_record.schema.json` | Canonical replay and audit capture |
| `simulation_receipt.schema.json` | Canonical causal simulation dry-run receipt |
| `streaming_budget_enforcement.schema.json` | Canonical predictive streaming budget event |
| `temporal_operation_receipt.schema.json` | Canonical runtime-owned temporal operation receipt |
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

## Notes

The schemas stay conservative by keeping canonical meaning in shared docs and future growth in `metadata` or `extensions`. If shared behavior changes, update docs and schemas in the same change.
