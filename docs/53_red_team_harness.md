# Red-Team Harness

Purpose: define the deterministic release-gate harness for adversarial governance checks.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: `mcoi_runtime.core.red_team_harness`, content safety chain, streaming budget protocol, tool permission primitives.
Invariants: cases are explicit, reproducible, offline, and fail release gating unless the configured pass rate is met.

## Coverage

| Category | Default cases | Expected control |
|---|---:|---|
| Prompt injection | 2 | Lambda input safety blocks or flags override attempts |
| Budget evasion | 2 | Streaming budget protocol emits cutoff or rejects invalid token input |
| Audit tampering | 2 | Stable hash mismatch detects event mutation |
| Policy bypass | 2 | Tool-call permission primitive denies missing audit or schema violation |

## Procedure

Run:

```powershell
python scripts\run_red_team_harness.py
```

Expected release-gate result:

```text
"pass_rate": 1.0
```

For CI artifact publication:

```powershell
python scripts\run_red_team_harness.py --output .change_assurance\red_team_harness.json --min-pass-rate 1.0
```

## Failure Semantics

| Failure | Meaning |
|---|---|
| `prompt_injection_missed` | Safety chain failed to block or flag a configured override attempt |
| `budget_evasion_missed` | Streaming protocol allowed output past reservation without cutoff |
| `audit_tampering_missed` | Mutated audit payload produced the same witness hash |
| `policy_bypass_missed` | Tool-call permission primitive allowed an adversarial request |

STATUS:
  Completeness: 100%
  Invariants verified: explicit corpus, deterministic report hash, category pass rates, offline execution, CI minimum pass-rate gate, CI artifact witness
  Open issues: none
  Next action: publish pass rates per release from `.change_assurance/red_team_harness.json`
