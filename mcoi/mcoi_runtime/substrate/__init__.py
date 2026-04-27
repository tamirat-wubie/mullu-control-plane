"""
MUSIA Substrate — Mfidel atomic encoding + 25-construct framework.

Foundational layer (L0/L1) introduced in v4.0.0.
Coexists with the existing core/ runtime; does not replace it.

The ``metrics`` submodule provides soak telemetry for the dual-Mfidel
convergence window. See ``substrate/metrics.py`` for the registry contract.

Note: do NOT re-export submodules from this __init__ via
``from mcoi_runtime.substrate import metrics as metrics`` — the static
import analyzer (test_import_analyzer) flags that as a self-cycle of the
package. Callers that need the metrics module should import it directly:

    from mcoi_runtime.substrate import metrics    # works without the alias
    from mcoi_runtime.substrate.metrics import REGISTRY
"""

