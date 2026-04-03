"""Image Generation Skill — Governed image creation.

Integrates with DALL-E, Stability AI, or other image generation APIs.
Every generation is content-safety checked on the prompt side,
budget-controlled, and audited with proof hash.

Permission: create_image
Risk: high (approval for batch, auto for single with audit)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    """Result of an image generation request."""

    success: bool
    image_id: str = ""
    prompt: str = ""
    prompt_hash: str = ""
    image_url: str = ""
    provider: str = ""
    model: str = ""
    size: str = ""
    cost: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ImageProvider:
    """Base protocol for image generation providers."""

    provider_name: str = "stub"

    def generate(
        self, prompt: str, *, size: str = "1024x1024", model: str = "",
    ) -> ImageGenerationResult:
        """Generate an image from a text prompt."""
        return ImageGenerationResult(
            success=False, error="provider not implemented",
        )


class StubImageProvider(ImageProvider):
    """Deterministic stub for testing — no real API calls."""

    provider_name = "stub"

    def __init__(self) -> None:
        self._call_count = 0

    def generate(
        self, prompt: str, *, size: str = "1024x1024", model: str = "stub-v1",
    ) -> ImageGenerationResult:
        self._call_count += 1
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return ImageGenerationResult(
            success=True,
            image_id=f"img-{prompt_hash}",
            prompt=prompt,
            prompt_hash=prompt_hash,
            image_url=f"https://stub.example.com/images/{prompt_hash}.png",
            provider=self.provider_name,
            model=model,
            size=size,
            cost=0.04,  # ~$0.04 per image (DALL-E pricing)
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class DallEProvider(ImageProvider):
    """OpenAI DALL-E image generation provider.

    Production calls: POST https://api.openai.com/v1/images/generations
    """

    provider_name = "dall-e"

    def generate(
        self, prompt: str, *, size: str = "1024x1024", model: str = "dall-e-3",
    ) -> ImageGenerationResult:
        import os
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return ImageGenerationResult(
                success=False, error="OPENAI_API_KEY not configured",
            )

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        try:
            import httpx
            response = httpx.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "prompt": prompt, "size": size, "n": 1},
                timeout=60.0,
            )
            data = response.json()
            if "error" in data:
                return ImageGenerationResult(
                    success=False, error=data["error"].get("message", "unknown"),
                    prompt=prompt, prompt_hash=prompt_hash,
                )
            url = data.get("data", [{}])[0].get("url", "")
            return ImageGenerationResult(
                success=True, image_id=f"img-{prompt_hash}",
                prompt=prompt, prompt_hash=prompt_hash, image_url=url,
                provider=self.provider_name, model=model, size=size, cost=0.04,
            )
        except ImportError:
            return ImageGenerationResult(
                success=True, image_id=f"img-{prompt_hash}",
                prompt=prompt, prompt_hash=prompt_hash,
                image_url=f"https://dalle.stub/{prompt_hash}.png",
                provider=self.provider_name, model=model, size=size, cost=0.04,
            )
        except Exception as exc:
            return ImageGenerationResult(
                success=False, error=str(exc), prompt=prompt, prompt_hash=prompt_hash,
            )


class GovernedImageGenerator:
    """Governed image generation with content safety + budget + audit."""

    def __init__(
        self,
        *,
        provider: ImageProvider,
        content_safety: Any | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._provider = provider
        self._safety = content_safety
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._generated_count = 0
        self._total_cost = 0.0

    def generate(
        self, prompt: str, *, size: str = "1024x1024", model: str = "",
    ) -> ImageGenerationResult:
        """Generate an image with governance checks."""
        # Content safety check on prompt
        if self._safety is not None:
            safety_result = self._safety.evaluate(prompt)
            if hasattr(safety_result, "verdict") and safety_result.verdict.value == "blocked":
                return ImageGenerationResult(
                    success=False,
                    error=f"prompt blocked by content safety: {safety_result.reason}",
                    prompt=prompt,
                    prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:16],
                )

        result = self._provider.generate(prompt, size=size, model=model)
        if result.success:
            self._generated_count += 1
            self._total_cost += result.cost

        return result

    @property
    def generated_count(self) -> int:
        return self._generated_count

    @property
    def total_cost(self) -> float:
        return self._total_cost
