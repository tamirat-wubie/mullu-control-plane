# Deterministic Serialization Policy

Scope: all Mullu Platform modules that persist, hash, compare, or transmit structured data.

Deterministic serialization is a platform invariant, not a convenience. Without it, persistence, replay, trace comparison, hash comparison, ID preservation, and cross-runtime compatibility all become unreliable.

## Format

1. Wire format MUST be JSON.
2. Character encoding MUST be UTF-8.
3. Field names MUST be explicit strings matching their canonical schema definition.
4. Object structure MUST be stable — the same semantic state MUST produce the same bytes.

## Ordering rules

1. Object keys MUST be serialized in lexicographic (sorted) order.
2. Array/list order MUST be preserved as semantic order. Serialization MUST NOT reorder list elements.
3. Tuples MUST serialize as JSON arrays with preserved element order.
4. No serialization path may rely on language-native hash map ordering. Sorted-key serialization MUST be enforced explicitly.

## Separator and whitespace rules

1. Compact separators MUST be used: `(",", ":")` with no trailing whitespace.
2. No pretty-printing in persistence or hashing paths. Human-readable output is a display concern, not a storage concern.
3. ASCII-only encoding MUST be used (`ensure_ascii=True`) for hash stability across platforms.

## Null and optional field rules

1. `null` and absent are semantically different. A field set to `null` MUST serialize as `"field": null`. A field not present MUST NOT appear in the output.
2. Optional fields MUST NOT appear or disappear inconsistently for the same semantic state. If a field is `None`/`null`, it MUST always serialize the same way for that state.
3. Default values MUST serialize explicitly. Omission of default-valued fields is prohibited in persistence paths.

## Identity preservation rules

1. Identifiers MUST serialize exactly as stored. No normalization, truncation, or case conversion during serialization.
2. Load/save round-trips MUST NOT regenerate, reassign, or mutate identifiers.
3. Parent/child reference identifiers MUST be preserved unchanged through serialization.
4. Identity fields MUST NOT be derived from file paths, list positions, or any implicit source during deserialization.

## Hash computation rules

1. Hashes MUST be computed over the deterministic serialized form, not over in-memory object state.
2. Hash algorithm MUST be SHA-256 unless a specific contract declares otherwise.
3. Hash input MUST be the UTF-8 encoded bytes of the deterministic JSON string.
4. Two semantically identical objects MUST produce the same hash. Two semantically different objects MUST produce different hashes.

## Malformed input policy

1. Fail closed. Malformed input MUST raise an explicit error.
2. No silent coercion. A string `"123"` MUST NOT be silently coerced to integer `123` or vice versa.
3. No best-effort repair. Core persistence and replay paths MUST NOT attempt to fix malformed data.
4. Unknown fields MUST be rejected in strict-mode paths (persistence, replay). Extension fields are governed by their own contract.

## Type mapping

| Python type | JSON type | Notes |
|---|---|---|
| `str` | `string` | |
| `int` | `number` | No float conversion |
| `float` | `number` | |
| `bool` | `boolean` | |
| `None` | `null` | |
| `tuple` | `array` | Order preserved |
| `list` | `array` | Order preserved |
| `dict` | `object` | Keys sorted |
| `MappingProxyType` | `object` | Thaw before serialization, keys sorted |
| `StrEnum` | `string` | Serialize as `.value` |
| `frozen dataclass` | `object` | Field names as keys, keys sorted |

## Cross-runtime compatibility

1. Rust and Python MUST agree on field names, types, and semantic meanings as defined in `schemas/`.
2. Shared schemas in `schemas/` are the interchange authority. Runtime-local types MUST map to shared schemas without reinterpretation.
3. A record serialized by one runtime MUST be deserializable by the other runtime without data loss.
4. Enum values MUST use the shared schema string form, not language-specific internal representations.

## Enforcement

Any implementation that cannot demonstrate `serialize(deserialize(serialize(x))) == serialize(x)` for all its persisted types is noncompliant.
