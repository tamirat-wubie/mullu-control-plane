"""Purpose: verify tenant isolation probe failures stay bounded and auditable.
Governance scope: isolation verification boundary tests only.
Dependencies: isolation_verifier.
Invariants: probe exceptions fail closed, raw probe detail is never exposed, history preserves bounded results.
"""

from __future__ import annotations

from mcoi_runtime.core.isolation_verifier import IsolationProbe, IsolationVerifier


NOW = "2026-04-04T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


def test_probe_exception_is_bounded_and_recorded() -> None:
    verifier = IsolationVerifier(clock=CLOCK)

    def stable_probe(tenant_a: str, tenant_b: str) -> IsolationProbe:
        return IsolationProbe(
            probe_name="stable",
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            isolated=True,
            detail="ok",
        )

    def crashing_probe(tenant_a: str, tenant_b: str) -> IsolationProbe:
        raise RuntimeError("secret probe failure")

    verifier.register_probe(stable_probe)
    verifier.register_probe(crashing_probe)

    report = verifier.verify("tenant-a", "tenant-b")
    history = verifier.history()

    assert report.all_isolated is False
    assert report.probes_run == 2
    assert report.probes_passed == 1
    assert report.probes[1].detail == "probe error (RuntimeError)"
    assert "secret probe failure" not in report.probes[1].detail
    assert history[0].probes[1].detail == "probe error (RuntimeError)"
