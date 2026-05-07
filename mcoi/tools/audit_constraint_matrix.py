"""
Audit the constraint shape of every domain adapter.

Walks the adapter registry, probes each adapter with its minimal
request plus a battery of single-flag mutations, and aggregates every
``(constraint_domain, violation_response)`` tuple emitted across all
probes. The result is a Markdown matrix that materializes the
universality claim of the framework: 15 adapters share an identical
``UniversalRequest`` shape but populate distinct constraint vocabularies.

Output goes to ``mullu-control-plane/CONSTRAINT_MATRIX.md`` (one file
at repo root). The artifact is checked in; ``test_constraint_matrix.py``
asserts that the on-disk file matches what this tool would generate
right now, so PRs that change adapter governance must regenerate.

Run:
    python -m mcoi.tools.audit_constraint_matrix          # writes file
    python -m mcoi.tools.audit_constraint_matrix --check  # exits non-zero if stale
    python -m mcoi.tools.audit_constraint_matrix --print  # writes to stdout
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# Re-use the canonical adapter registry that the invariant tests use
# too — single source of truth. When adapter #16 lands, both this tool
# and tests/test_domain_adapter_invariants.py update from one place.
from mcoi_runtime.domain_adapters._registry import ADAPTERS, AdapterEntry


VIOLATION_LEVELS = ("block", "escalate", "warn")

# A handful of "safe" string tokens to probe per-element constraint
# emission for tuple-of-string fields. The adapters validate some
# tuple values against fixed enums (e.g. logistics.modes ∈ {air,sea,
# road,rail}); for those, the probe will fail and be skipped — that
# is the intended behavior.
PROBE_TOKENS = ("flag-x",)
# A few adapter-specific tokens picked because they bypass enum-style
# validation. These are best-effort; if a probe fails, it's skipped.
ADAPTER_PROBE_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    "logistics": {"modes": ("air",)},
    "environmental": {"affected_media": ("air",)},
    "cybersecurity": {"data_classifications": ("PII",)},
    "construction": {"trades_involved": ("structural", "mep_electrical")},
}


def _is_bool_field(f: dataclasses.Field) -> bool:
    """Detect bool fields under PEP-563 (string annotations)."""
    return str(f.type).strip() == "bool"


def _is_tuple_str_field(f: dataclasses.Field) -> bool:
    s = str(f.type).strip()
    return s.startswith("tuple[str") or s == "tuple[str, ...]"


def _probes_for(entry: AdapterEntry) -> Iterable[Any]:
    """Yield a battery of probe requests for one adapter.

    Strategy:
      1. Minimal request from the registry builder.
      2. Each bool field flipped to its opposite, one at a time.
      3. Each pair of bool fields set True simultaneously
         (catches emergency × incident interactions).
      4. Each empty tuple-of-string field populated with a probe token,
         using adapter-specific tokens when the field has enum
         validation.
    """
    base = entry.build()
    yield base

    fields = list(dataclasses.fields(base))
    bool_fields = [f.name for f in fields if _is_bool_field(f)]
    tuple_fields = [f.name for f in fields if _is_tuple_str_field(f)]

    # Single bool flips
    for fname in bool_fields:
        try:
            yield dataclasses.replace(base, **{fname: not getattr(base, fname)})
        except (ValueError, TypeError):
            pass

    # Bool pair True×True (combinatorial but bounded; ~5×5 per adapter)
    for f1 in bool_fields:
        for f2 in bool_fields:
            if f1 >= f2:
                continue
            try:
                yield dataclasses.replace(base, **{f1: True, f2: True})
            except (ValueError, TypeError):
                pass

    # Populate empty tuple-of-string fields with a probe token
    adapter_overrides = ADAPTER_PROBE_TOKENS.get(entry.name, {})
    for fname in tuple_fields:
        current = getattr(base, fname)
        if current:
            continue  # already populated; minimal probe covers it
        token = adapter_overrides.get(fname, PROBE_TOKENS)
        try:
            yield dataclasses.replace(base, **{fname: token})
        except (ValueError, TypeError):
            pass


def discover_constraints(
    entry: AdapterEntry,
) -> set[tuple[str, str]]:
    """Aggregate every (constraint_domain, violation_response) tuple
    emitted by this adapter under any probe. Probe failures (invalid
    combinations rejected by the adapter at translate time) are
    silently skipped — that is correct, those combinations cannot
    actually run."""
    seen: set[tuple[str, str]] = set()
    for probe in _probes_for(entry):
        try:
            uni = entry.translate_to_universal(probe)
        except (ValueError, TypeError, KeyError):
            continue
        for c in uni.constraint_set:
            domain = c.get("domain", "?")
            response = c.get("violation_response", "block")
            seen.add((domain, response))
    return seen


def _render_per_adapter_table(
    adapter_name: str,
    constraints: set[tuple[str, str]],
) -> str:
    if not constraints:
        return f"_No constraints emitted for {adapter_name} under any probe._\n"
    by_domain: dict[str, set[str]] = defaultdict(set)
    for domain, response in constraints:
        by_domain[domain].add(response)
    lines = [
        "| constraint_domain | block | escalate | warn |",
        "|---|:-:|:-:|:-:|",
    ]
    for domain in sorted(by_domain):
        responses = by_domain[domain]
        cells = " | ".join(
            "✓" if level in responses else " " for level in VIOLATION_LEVELS
        )
        lines.append(f"| {domain} | {cells} |")
    return "\n".join(lines) + "\n"


def _render_pattern_sections(
    by_adapter: dict[str, set[tuple[str, str]]],
) -> str:
    """Pick out cross-adapter patterns: universal-by-pattern (every
    adapter emits `<vertical>_correctness → block`), universal-by-name
    (literal same domain across all adapters), absolute (block-only),
    graded (multiple violation responses observed for the same domain),
    and unique-to-one-adapter."""
    # Aggregate: domain -> {(adapter, response)}
    domain_index: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for adapter, constraints in by_adapter.items():
        for domain, response in constraints:
            domain_index[domain].add((adapter, response))

    # The acceptance-criteria pattern: every adapter emits at least one
    # `<vertical>_correctness` constraint with `block`. The literal name
    # differs per adapter (clinical_correctness, financial_correctness,
    # etc.) so it doesn't show up as a single literal universal domain.
    # Detect the pattern structurally.
    correctness_per_adapter: dict[str, list[str]] = {}
    for adapter, constraints in by_adapter.items():
        names = sorted(
            {
                d for d, r in constraints
                if d.endswith("_correctness") and r == "block"
            }
        )
        if names:
            correctness_per_adapter[adapter] = names

    universal_pattern_correctness = (
        len(correctness_per_adapter) == len(by_adapter)
    )

    universal_domains: list[str] = []
    absolute_domains: list[str] = []  # block-only across all observers
    inverting_domains: list[str] = []  # multiple violation responses observed
    unique_domains: list[tuple[str, str]] = []  # (domain, only_adapter)

    for domain in sorted(domain_index):
        adapters_for_domain = {a for a, _ in domain_index[domain]}
        responses = {r for _, r in domain_index[domain]}
        if len(adapters_for_domain) == len(by_adapter):
            universal_domains.append(domain)
        elif len(adapters_for_domain) == 1:
            unique_domains.append((domain, next(iter(adapters_for_domain))))
        if responses == {"block"}:
            absolute_domains.append(
                f"{domain} ({', '.join(sorted(adapters_for_domain))})"
            )
        elif len(responses) >= 2:
            inverting_domains.append(
                f"{domain} ({', '.join(sorted(adapters_for_domain))} → "
                f"{'/'.join(sorted(responses))})"
            )

    parts: list[str] = []
    parts.append("## Cross-adapter patterns\n")

    parts.append(
        "### Universal pattern — `<vertical>_correctness → block`\n"
    )
    if universal_pattern_correctness:
        parts.append(
            f"Every one of the {len(by_adapter)} adapters emits at least one "
            f"constraint of the form `<vertical>_correctness` with "
            f"`violation_response = block`. This is the acceptance-criteria "
            f"contract: each `acceptance_criteria` entry on a domain request "
            f"becomes a `block` constraint in the universal envelope, which "
            f"the L9 layer of UCJA enforces. The exact names vary by domain "
            f"vocabulary:"
        )
        for adapter in sorted(correctness_per_adapter):
            names = correctness_per_adapter[adapter]
            parts.append(f"- `{adapter}` → `{', '.join(names)}`")
    else:
        missing = sorted(set(by_adapter) - set(correctness_per_adapter))
        parts.append(
            f"_Pattern not held: adapter(s) without `<vertical>_correctness "
            f"→ block`: {', '.join(missing)}._"
        )
    parts.append("")

    parts.append("### Universal by literal name — emitted by every adapter\n")
    if universal_domains:
        for d in universal_domains:
            parts.append(f"- `{d}`")
    else:
        parts.append(
            "_None — every adapter uses its own vocabulary; the "
            "`<vertical>_correctness` pattern above is the structural analog._"
        )
    parts.append("")

    parts.append(
        "### Absolute (block-only) — never relaxed by emergency or kind\n"
    )
    if absolute_domains:
        for d in absolute_domains:
            parts.append(f"- `{d}`")
    else:
        parts.append("_None._")
    parts.append("")

    parts.append(
        "### Graded — same constraint domain emits different "
        "violation responses depending on context\n"
    )
    parts.append(
        "These are the kind-inverting and emergency-relaxing constraints "
        "(see each adapter's source for the precise rule):\n"
    )
    if inverting_domains:
        for d in inverting_domains:
            parts.append(f"- `{d}`")
    else:
        parts.append("_None._")
    parts.append("")

    parts.append("### Unique to one adapter\n")
    if unique_domains:
        for domain, adapter in sorted(unique_domains):
            parts.append(f"- `{domain}` — `{adapter}`")
    else:
        parts.append("_None._")
    parts.append("")

    return "\n".join(parts)


def generate_matrix() -> str:
    """Return the full Markdown report as a string."""
    by_adapter: dict[str, set[tuple[str, str]]] = {}
    for entry in ADAPTERS:
        by_adapter[entry.name] = discover_constraints(entry)

    lines: list[str] = []
    lines.append("# Domain Adapter Constraint Matrix\n")
    lines.append(
        f"Generated by `mcoi/tools/audit_constraint_matrix.py` from the "
        f"live adapter registry ({len(ADAPTERS)} adapters as of generation "
        f"time). Each adapter is probed with its minimal request plus a "
        f"battery of single-flag mutations and bool-pair stress combinations; "
        f"the table below aggregates every "
        f"`(constraint_domain, violation_response)` tuple emitted across all "
        f"probes.\n"
    )
    lines.append(
        "**Why this exists.** The universality claim of the domain adapter "
        "framework is structural: every adapter projects domain actions "
        "into the same `UniversalRequest` shape. The table makes the claim "
        "machine-checkable — adding a new adapter regenerates this file; "
        "the test [`test_constraint_matrix.py`](mcoi/tests/test_constraint_matrix.py) "
        "fails if the checked-in file drifts from what the tool produces.\n"
    )
    lines.append("## Per-adapter constraint shape\n")

    for entry in ADAPTERS:
        lines.append(f"### {entry.name}\n")
        lines.append(_render_per_adapter_table(entry.name, by_adapter[entry.name]))
        lines.append("")

    lines.append(_render_pattern_sections(by_adapter))

    lines.append(
        "---\n\n"
        "_Regenerate with `python -m mcoi.tools.audit_constraint_matrix`._"
    )

    return "\n".join(lines) + "\n"


def repo_root() -> Path:
    """Resolve the repo root from this file's location."""
    return Path(__file__).resolve().parents[2]


def artifact_path() -> Path:
    return repo_root() / "CONSTRAINT_MATRIX.md"


def main(argv: list[str] | None = None) -> int:
    # On Windows, the default stdout codec is cp1252 which can't render
    # the Unicode checkmark used in the matrix. Force UTF-8 for both
    # stdout and stderr so --print works on any platform.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass  # not all streams support reconfigure (e.g. piped through cmd)

    parser = argparse.ArgumentParser(
        description="Audit the constraint shape of every domain adapter.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the on-disk artifact differs from "
        "what would be generated now (CI mode).",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Write the generated matrix to stdout instead of disk.",
    )
    args = parser.parse_args(argv)

    matrix = generate_matrix()

    if args.print:
        sys.stdout.write(matrix)
        return 0

    target = artifact_path()
    if args.check:
        if not target.exists():
            sys.stderr.write(
                f"CONSTRAINT_MATRIX.md missing at {target}; "
                f"run without --check to generate.\n"
            )
            return 1
        existing = target.read_text(encoding="utf-8")
        if existing != matrix:
            sys.stderr.write(
                "CONSTRAINT_MATRIX.md is stale. Regenerate with "
                "`python -m mcoi.tools.audit_constraint_matrix`.\n"
            )
            return 1
        return 0

    target.write_text(matrix, encoding="utf-8")
    sys.stdout.write(f"wrote {target}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
