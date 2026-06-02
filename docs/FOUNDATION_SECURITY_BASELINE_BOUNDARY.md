<!--
Purpose: define the Foundation Mode security-baseline boundary before any security-readiness or compliance claim.
Governance scope: local security planning, threat-model questions, dependency-audit questions, static-scan questions, access-control questions, data-exposure questions, supply-chain questions, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_security_baseline_witness.awaiting_evidence.json, scripts/validate_foundation_security_baseline_boundary.py.
Invariants: no security baseline verification claim, no secret scan pass claim, no vulnerability scan pass claim, no dependency audit pass claim, no approved threat model, no access-control verification claim, no approved data-exposure review, no approved supply-chain review, no compliance certification claim, no customer-security readiness claim, and no deployment claim.
-->

# Foundation Security Baseline Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** security-baseline preparation means listing the local security
> questions that must be answered before trust claims are made. It does not
> claim that scans passed, dependencies are safe, a threat model is approved,
> access control is verified, compliance is certified, customer security is
> ready, or deployment is allowed.

Witness packet: [`../examples/foundation_security_baseline_witness.awaiting_evidence.json`](../examples/foundation_security_baseline_witness.awaiting_evidence.json)

Rule: Security-baseline preparation is a local planning boundary, not
permission to claim security readiness.

No security baseline verification, secret scan pass, vulnerability scan pass,
dependency audit pass, approved threat model, access-control verification,
approved data-exposure review, approved supply-chain review, compliance
certification, customer-security readiness, or deployment claim is permitted by
this boundary.

## What This Boundary Solves

Foundation Mode already blocks real secrets, credential activation, paid
infrastructure, runtime exposure, and data handling. A broader security
baseline is still needed because future trust claims require more than keeping
secrets out of Git. The project also needs threat-model, dependency, scan,
access-control, data-exposure, and supply-chain questions before any later
promotion.

This is preparation only:

1. The repository can name security-baseline surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature security or compliance claims.
4. No live scan result, private target, dependency target, secret value,
   customer record, certification, or deployment is created by this document or
   validator.

## Current State

```text
security_baseline_boundary_state=AwaitingEvidence
security_baseline_verified=false
secret_scan_pass_claimed=false
vulnerability_scan_pass_claimed=false
dependency_audit_pass_claimed=false
threat_model_approved=false
access_control_verified=false
data_exposure_review_approved=false
supply_chain_review_approved=false
compliance_certification_claimed=false
customer_security_ready_claimed=false
deployment_allowed=false
```

## Security-Baseline Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Security scope inventory | List security areas to inspect later. | Do not claim the baseline is verified. |
| Threat-model questions | Draft abuse, authority, and exposure questions. | Do not approve the threat model. |
| Dependency-audit questions | Draft dependency and lockfile questions. | Do not claim dependency audit pass. |
| Static-scan questions | Draft code and configuration scan questions. | Do not claim secret, vulnerability, or static-scan pass. |
| Access-control questions | Draft actor, role, tenant, and approval questions. | Do not claim access control is verified. |
| Data-exposure questions | Draft data flow and redaction questions. | Do not approve data-exposure handling. |
| Supply-chain questions | Draft package, tool, and build-source questions. | Do not approve supply-chain review. |
| Security-review readiness questions | Draft future review entry criteria. | Do not claim compliance or customer-security readiness. |

## Operator Procedure

1. Record only public-safe categories and questions.
2. Keep scan targets, private paths, provider values, account identifiers,
   dependency target values, and findings with sensitive detail outside Git.
3. Treat every security-baseline surface as `AwaitingEvidence`.
4. Before any future security-readiness claim, require current scan evidence,
   dependency evidence, threat-model evidence, access-control evidence,
   data-exposure evidence, and review closure.
5. Do not convert this planning boundary into compliance, customer-security, or
   deployment readiness.

## Validation

Run:

```powershell
python scripts/validate_foundation_security_baseline_boundary.py
```

The validator checks that the security-baseline witness:

1. keeps baseline verification, scan-pass claims, dependency-audit pass,
   threat-model approval, access-control verification, data-exposure approval,
   supply-chain approval, compliance certification, customer-security
   readiness, and deployment disabled;
2. keeps every surface in `AwaitingEvidence`;
3. rejects URL, email, private path, secret, scanner target, dependency target,
   access target, compliance target, or finding-target shaped values; and
4. rejects readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare secrets/credentials safely | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: security baseline verification blocked, scan-pass claims blocked, dependency-audit pass blocked, threat-model approval blocked, access-control verification blocked, data-exposure approval blocked, supply-chain approval blocked, compliance certification blocked, customer-security readiness blocked, deployment blocked
  Open issues: scan evidence, dependency-audit evidence, threat-model evidence, access-control evidence, data-exposure evidence, supply-chain evidence, and compliance review remain AwaitingEvidence
  Next action: run the security-baseline boundary validator before any future security-readiness claim
