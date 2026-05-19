# Reference

> **In one box:** Precise, complete, neutral facts about how each part of the
> system works — field names, rules, contracts, invariants. Reference docs do
> **not** teach or motivate; they state the truth so you can look things up.
> If you want the big picture in plain words, read the
> [Plain-English Overview](../explain/PLAIN_ENGLISH.md) instead; if you want to
> *do* something, see [How-To Guides](../how-to/).

Every special term is defined in one sentence in the [Glossary](../GLOSSARY.md).

---

## The architecture, plane by plane

The system is documented as numbered `NN_*.md` files in the parent
[`docs/`](../) folder. Each is one subsystem ("plane"). The most load-bearing:

| # | Subsystem | What it pins down |
| --- | --- | --- |
| [00](../00_platform_overview.md) | Platform Overview | Where each responsibility lives; naming boundaries |
| [01](../01_shared_invariants.md) | Shared Invariants | The rules that are always true (the safety guarantees) |
| [02](../02_shared_contracts.md) | Shared Contracts | Exact data shapes shared across components |
| [03](../03_trace_and_replay.md) | Trace & Replay | How actions are recorded and re-run |
| [04](../04_policy_and_verification.md) | Policy & Verification | How actions are checked before/after running |
| [05](../05_learning_admission.md) | Learning Admission | How new knowledge is vetted before use |
| [06](../06_capability_planes.md) | Capability Planes | The bounded responsibility areas and their edges |
| [07](../07_identity_lattice.md) | Identity Lattice | The ID system that makes auditing possible |
| [08](../08_error_taxonomy.md) | Error Taxonomy | The required structure for every error |
| [09](../09_memory_hierarchy.md) | Memory Hierarchy | Memory tiers and promotion rules |

Higher-numbered docs (`10`–`66`+) cover specific planes — communication, world
state, skills, capability forge, trust ledger, and more. The
[Glossary](../GLOSSARY.md) tells you which number to open for a given concept.

## Cross-project maps

| Map | Use it to see... |
| --- | --- |
| [System Boundary Map](../../../docs/mullu-system-boundary-map.md) | Where the whole system starts and stops |
| [Trust Boundary Map](../../../docs/mullu-trust-boundary-map.md) | Where trust is established and checked |
| [PHI_CANONICAL_SPEC.md](../PHI_CANONICAL_SPEC.md) | The canonical reasoning-order spec |

---

← Back to [Start Here](../START_HERE.md) · [Glossary](../GLOSSARY.md)
