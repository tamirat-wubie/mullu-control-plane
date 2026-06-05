# Tool-Call Permission Primitives

> **In one box:** The fine-grained rules for which tools an agent may call, with
> which arguments, for which tenant — the lock-and-key for tool use. New here? →
> [Plain-English Overview](explain/PLAIN_ENGLISH.md); unknown word? →
> [Glossary](GLOSSARY.md). *(Doc type: Reference.)*

Purpose: define the tenant-scoped capability grammar for governed tool calls.

Governance scope: agent tool invocation, argument-schema matching, budget
binding, and audit-required enforcement.

## Architecture

| Component | Responsibility | Input | Output |
|---|---|---|---|
| Permission primitive | Declares who may call which tool under which constraints | tenant, tool, schema, budget, audit flag | immutable permission |
| Schema matcher | Validates arguments against a bounded JSON-schema subset | schema and arguments | bounded error codes |
| Permission registry | Stores and evaluates permission primitives | tool call request | allow or deny decision |
| Governed tool registry hook | Enforces permission before execution | invocation context | result with permission decision |
| Operator API routes | Register, list, and evaluate permission primitives without invoking tools | permission payload or dry-run request | permission read model or decision |
| Hosted persistence selector | Selects in-memory or JSON-file registry from environment | `MULLU_TOOL_PERMISSION_REGISTRY_PATH` | startup registry posture |

## Grammar

```text
tenant:{tenant_id} may call tool:{tool_name}
with args matching schema:{schema_hash}
under budget:{budget_ref}
with audit_required:{true|false}
```

Example:

```text
tenant:tenant-1 may call tool:payments.send with args matching schema:schema-f68a4eec71139ac4 under budget:budget-1 with audit_required:true
```

## Evaluation Rules

1. Permission lookup is by exact `tenant_id` and `tool_name`.
2. Missing permission fails closed with `permission_not_found`.
3. Argument matching uses a bounded object-schema subset: `type`, `properties`, `required`, `additionalProperties`, `enum`, and `const`.
4. Budget reference must match exactly.
5. If `audit_required=true`, invocation must present audit context before execution.
6. Decisions include `argument_hash`, `schema_hash`, `permission_id`, bounded reason codes, and the published grammar sentence.
7. Governed tool execution cannot proceed when the permission decision is denied.

## Hosted Persistence

The default registry remains in-memory for foundation-mode local work. Hosted
operators that require durable permission history set:

```text
MULLU_TOOL_PERMISSION_REGISTRY_PATH=C:\mullu\stores\tool-permissions.json
```

Startup path validation requires an absolute `.json` file path, an existing
writable parent directory, and a non-directory target. When the file exists it
must carry schema version `1`, a `permissions` list, unique permission ids, and
records whose stored ids still match the deterministic tenant/tool/schema/
budget/audit identity. Malformed or tampered durable payloads fail startup
closed instead of dropping records silently.

## Reason Codes

| Code | Meaning |
|---|---|
| `permission_matched` | Permission, schema, budget, and audit context matched |
| `permission_not_found` | No permission exists for tenant/tool |
| `tenant_mismatch` | Permission tenant differs from request tenant |
| `tool_mismatch` | Permission tool differs from request tool |
| `schema_violation` | Arguments do not satisfy the declared schema subset |
| `budget_mismatch` | Request budget differs from permission budget |
| `audit_required` | Permission requires audit context and none was present |

STATUS:
  Completeness: 100%
  Invariants verified: exact tenant/tool lookup, fail-closed permission absence, bounded schema matching, exact budget binding, audit-required enforcement, deterministic argument hash, operator route exposure without tool execution, env-governed durable registry backing
  Open issues: none
  Next action: configure MULLU_TOOL_PERMISSION_REGISTRY_PATH in hosted operator environments that require durable tool permission history
