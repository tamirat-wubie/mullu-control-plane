"""Playwright browser adapter tests.

Purpose: prove the concrete browser adapter converts Playwright observations
into browser-worker evidence without opening raw browser control.
Governance scope: navigation context, screenshots, request observation, and
fail-closed missing context handling.
Dependencies: gateway.browser_playwright_adapter.
Invariants:
  - Browser actions require a governed navigation URL.
  - Successful actions carry before/after screenshot evidence references.
  - Browser sessions close after each request.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.browser_playwright_adapter import (  # noqa: E402
    PlaywrightAdapterProfile,
    PlaywrightBrowserAdapter,
)
from gateway.browser_worker import BrowserActionRequest  # noqa: E402


def test_playwright_adapter_extracts_text_and_writes_screenshots(tmp_path: Path) -> None:
    runtime = FakePlaywrightRuntime()
    adapter = PlaywrightBrowserAdapter(
        profile=PlaywrightAdapterProfile(evidence_dir=tmp_path),
        runtime_factory=lambda: runtime,
    )
    request = BrowserActionRequest(
        request_id="browser-playwright-1",
        tenant_id="tenant-1",
        capability_id="browser.extract_text",
        action="browser.extract_text",
        url="https://docs.mullusi.com/reference",
    )

    observation = adapter.perform(request)

    assert observation.succeeded is True
    assert observation.url_before == "https://docs.mullusi.com/reference"
    assert observation.url_after == "https://docs.mullusi.com/reference"
    assert observation.extracted_text == "Mullusi reference text"
    assert observation.screenshot_before_ref.endswith("browser-playwright-1-before.png")
    assert observation.screenshot_after_ref.endswith("browser-playwright-1-after.png")
    assert observation.network_requests == ("https://docs.mullusi.com/reference",)
    assert (tmp_path / "browser-playwright-1-before.png").exists()
    assert runtime.browser.closed is True


def test_playwright_adapter_uses_metadata_navigation_for_click(tmp_path: Path) -> None:
    runtime = FakePlaywrightRuntime()
    adapter = PlaywrightBrowserAdapter(
        profile=PlaywrightAdapterProfile(evidence_dir=tmp_path),
        runtime_factory=lambda: runtime,
    )
    request = BrowserActionRequest(
        request_id="browser-playwright-click",
        tenant_id="tenant-1",
        capability_id="browser.click",
        action="browser.click",
        selector="a.docs-link",
        metadata={"url_before": "https://docs.mullusi.com/start"},
    )

    observation = adapter.perform(request)

    assert observation.succeeded is True
    assert observation.url_before == "https://docs.mullusi.com/start"
    assert observation.url_after == "https://docs.mullusi.com/after-click"
    assert runtime.page.clicked_selectors == ("a.docs-link",)
    assert runtime.page.filled_values == ()
    assert observation.screenshot_after_ref.endswith("browser-playwright-click-after.png")


def test_playwright_adapter_blocks_missing_navigation_context(tmp_path: Path) -> None:
    adapter = PlaywrightBrowserAdapter(
        profile=PlaywrightAdapterProfile(evidence_dir=tmp_path),
        runtime_factory=FakePlaywrightRuntime,
    )
    request = BrowserActionRequest(
        request_id="browser-playwright-missing-url",
        tenant_id="tenant-1",
        capability_id="browser.click",
        action="browser.click",
        selector="button",
    )

    observation = adapter.perform(request)

    assert observation.succeeded is False
    assert observation.url_before == ""
    assert observation.url_after == ""
    assert observation.error == "browser action requires url or metadata.url_before"
    assert tuple(tmp_path.iterdir()) == ()


class FakePlaywrightRuntime:
    """Small sync Playwright stand-in for adapter tests."""

    def __init__(self) -> None:
        self.page = FakePage()
        self.browser = FakeBrowser(self.page)
        self.chromium = FakeChromium(self.browser)

    def __enter__(self) -> "FakePlaywrightRuntime":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class FakeChromium:
    def __init__(self, browser: "FakeBrowser") -> None:
        self._browser = browser

    def launch(self, *, headless: bool) -> "FakeBrowser":
        self._browser.headless = headless
        return self._browser


class FakeBrowser:
    def __init__(self, page: "FakePage") -> None:
        self._page = page
        self.closed = False
        self.headless = True

    def new_context(self, *, viewport: dict[str, int]) -> "FakeContext":
        return FakeContext(self._page, viewport)

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, page: "FakePage", viewport: dict[str, int]) -> None:
        self._page = page
        self.viewport = viewport
        self.closed = False

    def new_page(self) -> "FakePage":
        return self._page

    def close(self) -> None:
        self.closed = True


class FakePage:
    def __init__(self) -> None:
        self.url = ""
        self.clicked_selectors: tuple[str, ...] = ()
        self.filled_values: tuple[tuple[str, str], ...] = ()
        self._request_callback: Any = None

    def on(self, event_name: str, callback: Any) -> None:
        if event_name == "request":
            self._request_callback = callback

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.url = url
        if self._request_callback is not None:
            self._request_callback(FakeNetworkRequest(url))

    def locator(self, selector: str) -> "FakeLocator":
        return FakeLocator(self, selector)

    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_bytes(b"fake-png")

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        return None


class FakeLocator:
    def __init__(self, page: FakePage, selector: str) -> None:
        self._page = page
        self._selector = selector

    def inner_text(self, *, timeout: int) -> str:
        return "Mullusi reference text"

    def click(self, *, timeout: int) -> None:
        self._page.clicked_selectors = (*self._page.clicked_selectors, self._selector)
        self._page.url = "https://docs.mullusi.com/after-click"

    def fill(self, text: str, *, timeout: int) -> None:
        self._page.filled_values = (*self._page.filled_values, (self._selector, text))


class FakeNetworkRequest:
    def __init__(self, url: str) -> None:
        self.url = url
