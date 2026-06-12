# Invariant fuzz execution

v17 generated deterministic invariant fuzz banks. v18 executes them against a strict harness.

```text
InvariantFuzzRunReport
  → strict baseline mind
  → optional password-forbid lawbook migration
  → EvolutionEngine::evaluate per case
  → public projection leak check for secret probes
  → InvariantFuzzExecutionReport
```

The harness checks:

```text
empty patch rejects
wrong target rejects
immutable identity mutation rejects
required key removal rejects
password insertion rejects under strict lawbook
valid expansion accepts
secret projection probes may accept only if public Γ does not leak them
```

The execution report records pass/fail counts, unexpected accepts, unexpected rejects, projection leak status, and a hash over the full result bank.
