"""Purpose: stub model provider — deterministic local model adapter for testing/development.
Governance scope: model orchestration adapter only.
Dependencies: model contracts.
Invariants:
  - No real LLM calls.
  - Deterministic output based on input hash.
  - Response digest is computed, not fabricated.
  - Validation status starts as pending (validator applies after).
"""

from __future__ import annotations

from typing import Callable

import hashlib

from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)
from mcoi_runtime.core.invariants import stable_identifier


class StubModelAdapter:
    """Deterministic local model adapter that produces predictable responses.

    For testing and development. Does not call any real model API.
    Output is a deterministic hash of the input prompt_hash.
    """

    def __init__(self, *, clock: Callable[[], str], output_prefix: str = "stub-output") -> None:
        self._clock = clock
        self._prefix = output_prefix

    def invoke(self, invocation: ModelInvocation) -> ModelResponse:
        output_content = f"{self._prefix}:{invocation.prompt_hash}"
        output_digest = hashlib.sha256(output_content.encode("utf-8")).hexdigest()

        response_id = stable_identifier("stub-resp", {
            "invocation_id": invocation.invocation_id,
            "prompt_hash": invocation.prompt_hash,
        })

        return ModelResponse(
            response_id=response_id,
            invocation_id=invocation.invocation_id,
            status=ModelStatus.SUCCEEDED,
            output_digest=output_digest,
            completed_at=self._clock(),
            validation_status=ValidationStatus.PENDING,
            output_tokens=len(output_content),
            actual_cost=0.0,
        )
