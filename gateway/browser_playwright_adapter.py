"""Gateway Browser Playwright Adapter - concrete browser worker backend.

Purpose: perform restricted browser actions through Playwright while returning
observed effects to the signed browser-worker contract.
Governance scope: navigation context validation, screenshot evidence writing,
network observation, action allowlisting delegated by caller, and fail-closed
adapter errors.
Dependencies: gateway.browser_worker contracts and optional Playwright runtime.
Invariants:
  - The adapter does not decide policy; the browser worker gates policy first.
  - Every successful action returns before/after URL and screenshot references.
  - Browser sessions are per request and closed before returning.
  - Playwright import failure is reported as an unavailable adapter observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gateway.browser_worker import BrowserActionObservation, BrowserActionRequest


PlaywrightRuntimeFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class PlaywrightAdapterProfile:
    """Runtime profile for one Playwright browser adapter."""

    evidence_dir: Path = Path("/tmp/mullu-browser-evidence")
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    timeout_ms: int = 30_000
    wait_until: str = "domcontentloaded"

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_dir", Path(self.evidence_dir))
        if self.viewport_width <= 0:
            raise ValueError("viewport_width must be > 0")
        if self.viewport_height <= 0:
            raise ValueError("viewport_height must be > 0")
        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be > 0")
        if not isinstance(self.headless, bool):
            raise ValueError("headless must be a boolean")
        if self.wait_until not in {"commit", "domcontentloaded", "load", "networkidle"}:
            raise ValueError("wait_until is unsupported")


class PlaywrightBrowserAdapter:
    """Concrete Playwright implementation for browser-worker requests."""

    def __init__(
        self,
        *,
        profile: PlaywrightAdapterProfile | None = None,
        runtime_factory: PlaywrightRuntimeFactory | None = None,
    ) -> None:
        self._profile = profile or PlaywrightAdapterProfile()
        self._runtime_factory = runtime_factory or _default_runtime_factory

    def perform(self, request: BrowserActionRequest) -> BrowserActionObservation:
        """Perform one browser action and return observed effects."""
        start_url = _navigation_url(request)
        if not start_url:
            return BrowserActionObservation(
                succeeded=False,
                url_before="",
                url_after="",
                error="browser action requires url or metadata.url_before",
            )

        observed_requests: list[str] = []
        browser = None
        context = None
        try:
            with self._runtime_factory() as runtime:
                browser = runtime.chromium.launch(headless=self._profile.headless)
                context = browser.new_context(
                    viewport={
                        "width": self._profile.viewport_width,
                        "height": self._profile.viewport_height,
                    }
                )
                page = context.new_page()
                page.on("request", lambda network_request: observed_requests.append(network_request.url))
                page.goto(
                    start_url,
                    wait_until=self._profile.wait_until,
                    timeout=self._profile.timeout_ms,
                )
                url_before = str(page.url)
                screenshot_before_ref = self._screenshot_ref(
                    page=page,
                    request=request,
                    suffix="before",
                )
                extracted_text = self._perform_action(page, request)
                self._wait_for_settle(page)
                url_after = str(page.url)
                screenshot_after_ref = self._screenshot_ref(
                    page=page,
                    request=request,
                    suffix="after",
                )
                return BrowserActionObservation(
                    succeeded=True,
                    url_before=url_before,
                    url_after=url_after,
                    screenshot_before_ref=screenshot_before_ref,
                    screenshot_after_ref=screenshot_after_ref,
                    extracted_text=extracted_text,
                    network_requests=tuple(observed_requests),
                )
        except ImportError as exc:
            return _failed_observation(start_url, f"playwright unavailable: {exc.name or 'import failed'}")
        except Exception as exc:  # noqa: BLE001
            return _failed_observation(start_url, f"playwright action failed: {type(exc).__name__}")
        finally:
            _close_quietly(context)
            _close_quietly(browser)

    def _perform_action(self, page: Any, request: BrowserActionRequest) -> str:
        if request.action in {"browser.open", "browser.screenshot"}:
            return ""
        if request.action == "browser.extract_text":
            return str(page.locator("body").inner_text(timeout=self._profile.timeout_ms))
        if request.action == "browser.click":
            page.locator(request.selector).click(timeout=self._profile.timeout_ms)
            return ""
        if request.action == "browser.type":
            page.locator(request.selector).fill(request.text, timeout=self._profile.timeout_ms)
            return ""
        if request.action == "browser.submit":
            page.locator(request.selector).click(timeout=self._profile.timeout_ms)
            return ""
        raise ValueError(f"unsupported browser action: {request.action}")

    def _wait_for_settle(self, page: Any) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=min(self._profile.timeout_ms, 5_000))
        except Exception:  # noqa: BLE001
            return

    def _screenshot_ref(self, *, page: Any, request: BrowserActionRequest, suffix: str) -> str:
        self._profile.evidence_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{request.request_id}-{suffix}.png"
        screenshot_path = self._profile.evidence_dir / filename
        page.screenshot(path=str(screenshot_path), full_page=True)
        return f"evidence:browser-screenshot:{filename}"


def _default_runtime_factory() -> Any:
    from playwright.sync_api import sync_playwright

    return sync_playwright()


def _navigation_url(request: BrowserActionRequest) -> str:
    return request.url.strip() or str(request.metadata.get("url_before", "")).strip()


def _failed_observation(start_url: str, error: str) -> BrowserActionObservation:
    return BrowserActionObservation(
        succeeded=False,
        url_before=start_url,
        url_after=start_url,
        error=error,
    )


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    close = getattr(resource, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:  # noqa: BLE001
        return
