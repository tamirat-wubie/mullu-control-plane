"""Compatibility export for the governed swarm work fabric.

Purpose: expose the S2 swarm plane from the requested mcoi/swarm path while
keeping runtime implementation under mcoi_runtime.swarm.
Governance scope: import boundary only; authority, leases, traces, and proof
remain enforced by mcoi_runtime.swarm.
Dependencies: mcoi_runtime.swarm.
Invariants: this module adds no authority and performs no side effects.
"""

from mcoi_runtime.swarm import *  # noqa: F403
