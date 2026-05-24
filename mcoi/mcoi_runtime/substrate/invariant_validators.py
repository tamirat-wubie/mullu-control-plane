"""Built-in per-type invariant validators (USCL v3.3 / A1 detection).

These are concrete ``InvariantChecker`` predicates for the cascade's per-type
validator registry (see ``cascade.py`` and
``docs/INVARIANT_VALIDATOR_ROLLOUT_PROPOSAL.md``). Each is:

  - PURE / TOTAL / DETERMINISTIC — a predicate, no side effects;
  - written against the ``(dependent, changed) -> bool`` signature, so it can
    only compare a dependent against the one changed construct (not the rest
    of the graph);
  - assumption-free where possible (no reliance on under-specified field
    semantics).

IMPORTANT: defining a validator here does NOT enable it. Validators are inert
until registered via ``cascade.register_invariant_validator(type, checker)``.
Enabling one is a governance decision (it turns the gate from "reacts" to
"detects" for that type) and is intentionally left out of this module.
"""
from __future__ import annotations

from mcoi_runtime.substrate.constructs import Change, ConstructBase, ConstructType


def change_state_refs_are_states(
    dependent: ConstructBase, changed: ConstructBase
) -> bool:
    """A ``Change``'s ``state_before`` / ``state_after`` must reference ``State``
    constructs.

    Registered (when enabled) for ``ConstructType.CHANGE``. Returns ``False``
    (invariant violated) iff ``changed`` is referenced by the ``Change`` as one
    of its before/after states but is **not** a ``STATE`` construct — i.e. the
    causal record has been wired to call a non-state a "state". Otherwise
    ``True``.

    Assumption-free: it inspects only the reference's *type*, never the
    ``delta_vector`` semantics. This makes it a safe first enforcement — it can
    only reject genuinely malformed references, which should never occur in a
    healthy graph (so blast radius is near zero, but the integrity guarantee is
    real once enabled).
    """
    if not isinstance(dependent, Change):
        # Dispatched by dependent type, so this should always be a Change;
        # be total and non-committal for any other caller.
        return True
    referenced_as_state = changed.id in (
        dependent.state_before_id,
        dependent.state_after_id,
    )
    if referenced_as_state and changed.type is not ConstructType.STATE:
        return False
    return True
