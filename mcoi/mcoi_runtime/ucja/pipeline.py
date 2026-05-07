"""
UCJA Pipeline Runner.

Runs L0–L9 in order. Halts on first non-PASS layer result. Returns the
draft (possibly partial) plus terminal verdict.

The pipeline is the outer governance gate: a request that fails L0 never
reaches the SCCCE cognitive cycle. A request that passes all 10 layers
produces a complete JobDefinition that the cycle consumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from mcoi_runtime.ucja.job_draft import JobDraft, LayerResult, LayerVerdict
from mcoi_runtime.ucja.layers import DEFAULT_LAYERS, Layer


@dataclass
class PipelineOutcome:
    """Result of running the UCJA pipeline."""

    draft: JobDraft
    terminal_verdict: LayerVerdict
    halted_at_layer: Optional[str] = None
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.terminal_verdict == LayerVerdict.PASS

    @property
    def reclassified(self) -> bool:
        return self.terminal_verdict == LayerVerdict.RECLASSIFY

    @property
    def rejected(self) -> bool:
        return self.terminal_verdict == LayerVerdict.REJECT


@dataclass
class UCJAPipeline:
    """Composable pipeline. Default uses the 10 spec layers; tests can
    inject a shorter list.
    """

    layers: tuple[tuple[str, Layer], ...] = field(
        default_factory=lambda: DEFAULT_LAYERS
    )

    def run(self, request_payload: dict[str, Any]) -> PipelineOutcome:
        draft = JobDraft(request_payload=dict(request_payload))

        for layer_name, layer_fn in self.layers:
            new_draft, result = layer_fn(draft)
            draft = new_draft.with_layer(layer_name, result)

            if result.verdict != LayerVerdict.PASS:
                return PipelineOutcome(
                    draft=draft,
                    terminal_verdict=result.verdict,
                    halted_at_layer=layer_name,
                    reason=result.reason,
                )

        return PipelineOutcome(
            draft=draft,
            terminal_verdict=LayerVerdict.PASS,
            halted_at_layer=None,
            reason="all 10 layers passed",
        )
