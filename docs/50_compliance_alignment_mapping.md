# Compliance Alignment Mapping

Purpose: map Mullusi control-plane capabilities to SOC 2, HIPAA Security Rule, EU Act, and ISO/IEC 42001 alignment areas.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: `tests/fixtures/compliance_alignment_matrix.json`, `scripts/compliance_alignment_matrix.py`.
Invariants: this document claims alignment only; it does not claim certification, attestation, audit completion, legal advice, or regulatory approval.

## Source Boundary

| Framework | Source | Alignment basis |
|---|---|---|
| SOC 2 | AICPA SOC service overview | Trust-service categories including security, availability, processing integrity, confidentiality, and privacy |
| HIPAA Security Rule | HHS Security Rule overview | Administrative, physical, and technical safeguards for protected electronic health information |
| EU Act | European Commission high-risk deployer obligations | Use instructions, human oversight, monitoring, logging, incident communication, and affected-person transparency |
| ISO/IEC 42001 | ISO/IEC 42001 overview | Management system requirements for policy, risk, operation, performance evaluation, and continual improvement |

## Capability Map

| Mullusi capability | SOC 2 alignment | HIPAA alignment | EU Act alignment | ISO/IEC 42001 alignment |
|---|---|---|---|---|
| Hash-chain audit | Auditability and tamper evidence | Electronic activity traceability | Operation records for trace review | Retained evidence for management review |
| Lineage query API | Output decision-path reconstruction | Bounded trace read models | Causal record transparency | Managed lifecycle evidence |
| Policy versioning and shadow mode | Controlled policy change records | Governed policy change review | Shadow evaluation before promotion | Managed policy lifecycle |
| Streaming budget enforcement | Bounded resource use and deterministic settlement | Tenant budget constraint enforcement | Bounded behavior under constraint | Resource risk control with settlement evidence |
| Lambda safety guard chain | Injection and sensitive-data guardrails | Sensitive-data detection and scrubbing stage | Adversarial input and output control | Governed safety stage in execution chain |
| Tool permission primitives | Least-privilege invocation | Tenant-scoped capability authorization | Bounded execution authority | Capability contract before execution |
| Replay determinism harness | Incident reconstruction and repeatability | Deterministic decision review | Replayable decision path for review | Evidence for corrective action |
| Hosted demo sandbox | Public read-only evidence surface | No runtime mutation or sensitive tenant state | Bounded public trace examples | Public evidence without write access |

## Non-Claims

1. Mullusi does not claim SOC 2 certification through this mapping.
2. Mullusi does not claim HIPAA compliance through this mapping.
3. Mullusi does not claim EU Act conformity through this mapping.
4. Mullusi does not claim ISO/IEC 42001 certification through this mapping.
5. External publication requires review by qualified compliance counsel or auditors.

## Verification

Run:

```powershell
python scripts\compliance_alignment_matrix.py
```

The validator checks that every mapped capability covers all four target frameworks, every evidence file exists, and certification claims remain false.

STATUS:
  Completeness: 100%
  Invariants verified: alignment-only claim boundary, framework source references, evidence-backed mappings, no certification claim, validator command
  Open issues: none
  Next action: have compliance counsel review the mapping language before external publication
