"""Adapter binding CDG-RCCM closure to the existing Universal Action Kernel."""

from __future__ import annotations

from typing import Any, Callable

from ..contracts import ProjectionCertificate, SettlementLevel


class UniversalActionClosureAdapter:
    """Prevent UniversalActionKernel.run from being called before closure."""

    def __init__(self, universal_action_kernel: Any) -> None:
        if not callable(getattr(universal_action_kernel, "run", None)):
            raise ValueError("universal_action_kernel must expose run(request)")
        self._kernel = universal_action_kernel

    def dispatch(
        self,
        *,
        closure_certificate: ProjectionCertificate,
        request: Any,
        authority_check: Callable[[Any], bool],
    ) -> Any:
        if not closure_certificate.valid:
            raise ValueError("closure_certificate_stale")
        if closure_certificate.level < SettlementLevel.CLOSURE_CERTIFIED:
            raise ValueError("closure_certificate_level_insufficient")
        if not authority_check(request):
            raise ValueError("universal_action_authority_rejected")
        return self._kernel.run(request)
