"""Purpose: deterministic browser backend for governed browser automation.
Governance scope: browser backend adapter only — no real browser dependency.
Dependencies: browser contracts.
Invariants:
  - All state is explicit and inspectable.
  - No real browser process. Deterministic for testing.
  - Selector lookup is strict — no fuzzy matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from mcoi_runtime.contracts.browser import (
    ElementSelector,
    PageDescriptor,
    SelectorMatchResult,
    SelectorMatchStatus,
)


@dataclass
class SimulatedElement:
    """A simulated page element for deterministic testing."""

    selector_type: str
    selector_value: str
    tag: str = "div"
    text: str = ""
    value: str = ""


@dataclass
class SimulatedPage:
    """A simulated page with known elements."""

    url: str
    title: str
    elements: list[SimulatedElement] = field(default_factory=list)
    text_content: str = ""

    def to_descriptor(self) -> PageDescriptor:
        return PageDescriptor(
            url=self.url,
            title=self.title,
            text_content=self.text_content,
        )


class SimulatedBrowserBackend:
    """A deterministic browser backend for testing and governed simulation.

    Maintains explicit page state. All lookups are strict.
    No fuzzy matching. No real browser process.
    """

    def __init__(self) -> None:
        self._pages: dict[str, SimulatedPage] = {}
        self._current_page: SimulatedPage | None = None
        self._submitted: list[tuple[str, str]] = []  # (selector_value, value)

    def register_page(self, page: SimulatedPage) -> None:
        """Register a simulated page at a URL."""
        self._pages[page.url] = page

    def open_page(self, url: str) -> PageDescriptor:
        page = self._pages.get(url)
        if page is None:
            # Return a minimal page for unknown URLs
            page = SimulatedPage(url=url, title="Unknown Page")
        self._current_page = page
        return page.to_descriptor()

    def find_element(self, selector: ElementSelector) -> SelectorMatchResult:
        if self._current_page is None:
            return SelectorMatchResult(
                selector=selector, status=SelectorMatchStatus.NOT_FOUND,
            )
        matches = [
            e for e in self._current_page.elements
            if e.selector_type == selector.selector_type
            and e.selector_value == selector.selector_value
        ]
        if len(matches) == 0:
            return SelectorMatchResult(
                selector=selector, status=SelectorMatchStatus.NOT_FOUND,
            )
        if len(matches) > 1:
            return SelectorMatchResult(
                selector=selector, status=SelectorMatchStatus.AMBIGUOUS,
            )
        elem = matches[0]
        return SelectorMatchResult(
            selector=selector,
            status=SelectorMatchStatus.FOUND,
            element_text=elem.text,
            element_value=elem.value,
            element_tag=elem.tag,
        )

    def click_element(self, selector: ElementSelector) -> bool:
        match = self.find_element(selector)
        return match.found

    def fill_element(self, selector: ElementSelector, value: str) -> bool:
        if self._current_page is None:
            return False
        for elem in self._current_page.elements:
            if elem.selector_type == selector.selector_type and elem.selector_value == selector.selector_value:
                elem.value = value
                return True
        return False

    def submit_element(self, selector: ElementSelector) -> bool:
        match = self.find_element(selector)
        if match.found:
            self._submitted.append((selector.selector_value, match.element_value or ""))
            return True
        return False

    def get_current_page(self) -> PageDescriptor:
        if self._current_page is None:
            return PageDescriptor(url="about:blank", title="Blank")
        return self._current_page.to_descriptor()

    @property
    def submissions(self) -> list[tuple[str, str]]:
        return list(self._submitted)
