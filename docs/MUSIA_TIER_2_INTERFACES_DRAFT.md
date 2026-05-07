# MUSIA Tier 2 — Structural Constructs (Implementation Reference)

**Status:** IMPLEMENTED — soak gate skipped at user direction.
**Implementation file:** `mcoi/mcoi_runtime/substrate/constructs/tier2_structural.py`
**Test file:** `mcoi/tests/test_tier2_structural.py` (29 tests, all passing)
**Implementation date:** ahead of W7 plan; soak gate deferred at user direction.

This document was originally a design draft. It is now retained as the
specification reference that the implementation honors. The implementation
faithfully realizes the signatures and invariants below.

**Note on the deferred soak gate:** the original plan called for v3.13.1
telemetry collection and a 4-week production soak before implementing Tier 2.
That sequencing was overridden. Tier 2 ships without soak validation of the
substrate convergence. Risks are recorded in the "Disposability" section
below; in practice the design is insulated from substrate convergence
outcome (Tier 2 references Tier 1 by UUID, not by Mfidel coordinate).

---

## Why Tier 2 design can proceed during soak

The W1–W4 soak measures **substrate-consumer behavior** (mixed flows, latency, callsite dependencies). It does not exercise the construct framework. Tier 2 constructs do not ground directly in Mfidel coordinates — they reference Tier 1 constructs by UUID. The soak's outcome shapes how `core/mfidel_matrix.py` converges with `substrate/mfidel/grid.py`, which is invisible to Tier 2.

The risks the soak surfaces (synthesized col-8 fidels, mixed paths, p95 regressions) are all caller-side. The risks Tier 2 design surfaces (responsibility overlap, invariant compatibility with Tier 1, disambiguation rule extension) are all design-side. The two risk classes do not interact.

---

## Tier 2 — what it is

Tier 1 (Foundational) gives us the irreducible primitives: State, Change, Causation, Constraint, Boundary. Each names exactly one structural fact about the world.

Tier 2 (Structural) gives us **composition mechanics** — how Tier 1 primitives combine into structures large enough to do real work. Each Tier 2 construct is a **disciplined composition rule**, not a primitive.

The disambiguation pattern from Tier 1 extends:

| Tier 2 Type      | Irreducible responsibility                       | Composes from (Tier 1)                  |
| ---------------- | ------------------------------------------------ | --------------------------------------- |
| `Pattern`        | `WHAT_REPEATS`                                   | State (instances) + similarity rule     |
| `Transformation` | `WHAT_DRIVES_BOUNDED_STATE_SEQUENCES`            | State + Change + Causation + Boundary   |
| `Composition`    | `WHAT_NESTS_PATTERNS`                            | Pattern + Boundary (containment)        |
| `Interaction`    | `WHAT_PRODUCES_MUTUAL_CHANGE`                    | Causation × Causation (bidirectional)   |
| `Conservation`   | `WHAT_INVARIANTS_HOLD_ACROSS_CHANGE`             | Pattern + Constraint                    |

No two Tier 2 constructs share a responsibility. The disambiguation verifier (`verify_tier2_disambiguation()`) enforces this at module load, mirroring the Tier 1 pattern.

---

## Construct sketches

### Transformation (priority 1 — implements first)

The construct that the `software_dev` adapter already references via `construct_graph_summary["transformation"]`. Implementing this turns the adapter's stub into a real consumer.

```python
@dataclass
class Transformation(ConstructBase):
    """
    WHAT: bounded state sequence driven by causation within a boundary.

    A Transformation references an initial State, a target State, the Change
    that bridges them, the Causation that produces the Change, and the
    Boundary the whole sequence operates within. It is the smallest
    composite construct that names a complete causal step.
    """
    type: ConstructType = ConstructType.TRANSFORMATION
    tier: Tier = Tier.STRUCTURAL

    initial_state_id: Optional[UUID] = None
    target_state_id: Optional[UUID] = None
    change_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    boundary_id: Optional[UUID] = None

    energy_estimate: float = 0.0  # arbitrary scale; >=0
    reversibility: str = "unknown"  # reversible | irreversible | unknown

    def __post_init__(self) -> None:
        if self.energy_estimate < 0:
            raise ValueError("energy_estimate must be non-negative")
        if self.reversibility not in {"reversible", "irreversible", "unknown"}:
            raise ValueError(f"invalid reversibility: {self.reversibility}")
        if not self.invariants:
            self.invariants = (
                "tier1_references_resolve",
                "boundary_contains_states",
                "change_matches_states",
                "causation_produces_change",
            )
        super().__post_init__()
```

**Invariant verification (deferred to a `Tier2Validator`):**
- `tier1_references_resolve` — all five Tier 1 IDs must resolve in the construct registry
- `boundary_contains_states` — both states must satisfy the boundary's `inside_predicate`
- `change_matches_states` — change's `state_before_id` and `state_after_id` must equal the transformation's initial and target
- `causation_produces_change` — causation's `effect_id` must equal `change_id`

The validator is **not** part of the construct's `__post_init__` because it requires registry lookup. It runs at composition time when constructs are added to a graph.

### Composition (priority 2)

```python
@dataclass
class Composition(ConstructBase):
    """
    WHAT: nested pattern structure.

    A Composition is the construct that lets Patterns contain other Patterns,
    bounded by an enclosing Boundary. It does NOT name what the patterns
    do (that's Pattern itself) or what limits them (that's Constraint) —
    only that nesting is well-defined and acyclic.
    """
    type: ConstructType = ConstructType.COMPOSITION
    tier: Tier = Tier.STRUCTURAL

    container_pattern_id: Optional[UUID] = None
    contained_pattern_ids: tuple[UUID, ...] = ()
    boundary_id: Optional[UUID] = None
    nesting_depth: int = 1  # 1 = direct containment

    def __post_init__(self) -> None:
        if self.nesting_depth < 1:
            raise ValueError("nesting_depth must be >= 1")
        if self.nesting_depth > 5:
            raise ValueError("nesting_depth > 5 violates bounded-recursion rule")
        if not self.invariants:
            self.invariants = (
                "container_distinct_from_contained",
                "no_cyclic_nesting",
                "depth_bounded",
                "all_within_boundary",
            )
        super().__post_init__()
```

**Open question (review at W4):** should `nesting_depth` be derived from the registry rather than declared? Declaring it lets us reject deep compositions early; deriving it requires a graph traversal at validate-time. Trade-off is correctness vs. eagerness. Default to declared; revisit if soak surfaces graph-traversal performance constraints.

### Pattern (priority 3)

```python
@dataclass
class Pattern(ConstructBase):
    """
    WHAT: repeated configuration across instances.

    A Pattern names a template-and-instances relationship. The template is
    a representative State or State-shape; instances are State IDs that
    match the template under a similarity rule. Variations are documented
    deviations within tolerance.
    """
    type: ConstructType = ConstructType.PATTERN
    tier: Tier = Tier.STRUCTURAL

    template_state_id: Optional[UUID] = None
    instance_state_ids: tuple[UUID, ...] = ()
    similarity_rule: str = "structural_equivalence"
    similarity_threshold: float = 1.0  # [0, 1]
    variation_tolerance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (0.0 <= self.similarity_threshold <= 1.0):
            raise ValueError("similarity_threshold not in [0,1]")
        if not self.template_state_id and not self.instance_state_ids:
            raise ValueError("Pattern requires either a template or instances")
        if not self.invariants:
            self.invariants = (
                "template_or_instances_present",
                "similarity_rule_decidable",
                "threshold_bounded",
            )
        super().__post_init__()
```

**Note:** `similarity_rule` is a string identifier. The actual rule body lives in a registry (`PatternSimilarityRegistry`) that ships with `structural_equivalence` and `mfidel_signature_match` as built-ins. This keeps Pattern decoupled from the algorithm.

### Conservation (priority 4)

```python
@dataclass
class Conservation(ConstructBase):
    """
    WHAT: invariant pattern property preserved across change.

    A Conservation construct names something that does NOT change when other
    things do. It pairs a Pattern (the invariant) with a Constraint (the
    enforcement rule) and a scope. Distinct from Constraint alone: a
    Constraint says 'X is forbidden'; a Conservation says 'X is preserved
    even as Y varies'.
    """
    type: ConstructType = ConstructType.CONSERVATION
    tier: Tier = Tier.STRUCTURAL

    invariant_pattern_id: Optional[UUID] = None
    enforcing_constraint_id: Optional[UUID] = None
    scope_boundary_id: Optional[UUID] = None
    violation_detection: str = "post_change_validation"
    # post_change_validation | pre_change_block | continuous_monitoring

    def __post_init__(self) -> None:
        valid = {"post_change_validation", "pre_change_block", "continuous_monitoring"}
        if self.violation_detection not in valid:
            raise ValueError(f"invalid violation_detection: {self.violation_detection}")
        if not (
            self.invariant_pattern_id
            and self.enforcing_constraint_id
            and self.scope_boundary_id
        ):
            raise ValueError(
                "Conservation requires invariant Pattern, enforcing Constraint, and scope Boundary"
            )
        if not self.invariants:
            self.invariants = (
                "pattern_constraint_boundary_resolved",
                "violation_detection_decidable",
                "scope_well_defined",
            )
        super().__post_init__()
```

**Disambiguation note:** Conservation and Constraint are easy to conflate. The rule:
- **Constraint** restricts what *can* happen ("temperature ≤ 0").
- **Conservation** asserts what *won't* happen even as other things do ("total energy preserved across phase change").
- A Conservation typically *uses* a Constraint as its enforcement mechanism, but it adds the structural claim of cross-change invariance.

### Interaction (priority 5)

```python
@dataclass
class Interaction(ConstructBase):
    """
    WHAT: mutual change relationship between two or more participants.

    An Interaction is two (or more) Causations facing each other: each
    participant produces a Change in the others. Distinct from a single
    Causation (which is unidirectional) and from a Composition (which
    is structural, not dynamic).
    """
    type: ConstructType = ConstructType.INTERACTION
    tier: Tier = Tier.STRUCTURAL

    participant_state_ids: tuple[UUID, ...] = ()
    causation_ids: tuple[UUID, ...] = ()  # one per direction
    coupling_strength: float = 0.0  # [0, 1]
    feedback_kind: str = "none"  # none | positive | negative | mixed

    def __post_init__(self) -> None:
        if len(self.participant_state_ids) < 2:
            raise ValueError("Interaction requires >= 2 participants")
        if len(self.causation_ids) < len(self.participant_state_ids):
            raise ValueError(
                "Interaction requires at least one Causation per participant"
            )
        if not (0.0 <= self.coupling_strength <= 1.0):
            raise ValueError("coupling_strength not in [0,1]")
        if self.feedback_kind not in {"none", "positive", "negative", "mixed"}:
            raise ValueError(f"invalid feedback_kind: {self.feedback_kind}")
        if not self.invariants:
            self.invariants = (
                "at_least_two_participants",
                "causation_per_participant",
                "coupling_bounded",
                "feedback_classified",
            )
        super().__post_init__()
```

**Why Interaction is last:** it is the most coupled of the Tier 2 constructs. It depends on Causation (Tier 1) being stable AND on multi-participant validation working AND on the disambiguation between bidirectional Interaction and unidirectional Causation×Causation being clear. Implementing it after the other four lets it inherit a settled foundation.

---

## Disambiguation table (Tier 2)

```python
TIER2_RESPONSIBILITIES: dict[ConstructType, str] = {
    ConstructType.PATTERN:        "WHAT_REPEATS",
    ConstructType.TRANSFORMATION: "WHAT_DRIVES_BOUNDED_STATE_SEQUENCES",
    ConstructType.COMPOSITION:    "WHAT_NESTS_PATTERNS",
    ConstructType.INTERACTION:    "WHAT_PRODUCES_MUTUAL_CHANGE",
    ConstructType.CONSERVATION:   "WHAT_INVARIANTS_HOLD_ACROSS_CHANGE",
}

def verify_tier2_disambiguation() -> None:
    seen: set[str] = set()
    for ct, resp in TIER2_RESPONSIBILITIES.items():
        if resp in seen:
            raise ValueError(f"tier 2 responsibility overlap detected: {resp}")
        seen.add(resp)
```

Cross-tier check (must not collide with Tier 1):

```python
def verify_no_cross_tier_overlap() -> None:
    all_responsibilities = (
        set(TIER1_RESPONSIBILITIES.values())
        | set(TIER2_RESPONSIBILITIES.values())
    )
    expected = len(TIER1_RESPONSIBILITIES) + len(TIER2_RESPONSIBILITIES)
    if len(all_responsibilities) != expected:
        raise ValueError("cross-tier responsibility overlap detected")
```

This must run at module load just like the Tier 1 verifier. By the time Tier 5 is implemented, the verifier will check disambiguation across all 25 constructs.

---

## Integration with the existing `software_dev` adapter

The current adapter's `_work_plan_from_constructs` checks `summary.get("transformation", 0) > 0`. Once Tier 2 ships:

```python
# In software_dev adapter (no change needed at draft time):
if summary.get("transformation", 0) > 0:
    steps.append(
        f"Apply transformations within boundary [{req.repository}:{req.target_branch}]"
    )
```

The string key `"transformation"` matches `ConstructType.TRANSFORMATION.value`, so the adapter already emits the right key. What changes at W7 is the *source* of the count: it goes from a stub-shaped placeholder to a real Transformation construct count from the cognitive engine output.

No adapter change is required to make Tier 2 land. This is the structural payoff of having reserved all 25 enum slots in v4.0.0.

---

## What this draft does NOT decide

- **Cognitive engine integration.** The 15-step SCCCE cycle is what *populates* the construct graph. Tier 2 constructs are graph nodes; the cycle defines what edges look like. That's a separate design (Phase 2, post-W12).
- **Validator implementation.** `Tier2Validator` is referenced but not specified. Its design depends on the construct registry shape, which is also Phase 2.
- **Persistence.** Tier 2 constructs persist to the same store as Tier 1. The store interface is set; no new schema needed beyond `universal_construct.schema.json`.
- **Φ_gov integration.** Modifying a Tier 2 construct cascades through Tier 1 references. Cascade rules are W12 scope.
- **Performance.** Tier 2 constructs may be high-volume in real usage. Caching strategy is W7+ when we have actual usage data.

---

## Review checklist (pre-W7)

- [ ] Disambiguation table reviewed for semantic overlap
- [ ] Each construct's `__post_init__` invariants checked against MUSIA spec
- [ ] Cross-tier verifier mentally exercised (Tier 1 ∪ Tier 2 = 10 distinct responsibilities)
- [ ] `software_dev` adapter compatibility confirmed (no API change required)
- [ ] Open questions (Composition.nesting_depth, Pattern similarity rule registry) resolved or deferred with rationale
- [ ] Conservation vs Constraint disambiguation documented for non-author readers
- [ ] Interaction's multi-participant validation rule defended against degenerate cases (1 participant, 0 causations)

---

## Disposability

If the W4 gate fails and the failure mode reveals that Tier 1's shape is wrong (e.g., `MfidelSignature` turns out to be brittle, or `ConstructType` enum reservation conflicts with something), this draft is disposable. Specifically, the following draft elements are sensitive to substrate outcomes:

- None of the Tier 2 dataclass fields reference Mfidel coordinates directly.
- All cross-Tier references are by UUID, which survives substrate convergence.
- The disambiguation rule structure is a pure pattern, independent of substrate.

So the draft survives any soak failure mode I can currently imagine. Marked PROVISIONAL because "currently imagine" is bounded by what hasn't been measured yet — exactly the point of running the soak.

---

## Status: IMPLEMENTED

Tier 2 is implemented at `mcoi/mcoi_runtime/substrate/constructs/tier2_structural.py`.
29 tests pass (`mcoi/tests/test_tier2_structural.py`). Cross-tier disambiguation
verifier runs at module load and asserts Tier 1 ∪ Tier 2 = 10 distinct
responsibilities.

The soak gate that was originally going to validate substrate safety before
this implementation was deferred at user direction. The dual-Mfidel divergence
identified earlier in the project remains unresolved as of Tier 2 ship.
Convergence to Option 1b is still scheduled but no longer gates Tier 2.
