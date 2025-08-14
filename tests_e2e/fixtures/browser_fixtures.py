"""
Browser Fixtures for E2E Testing

Provides various browser configurations and utilities for comprehensive testing.
"""

import pytest
from typing import Generator, Dict, Any, List
from playwright.sync_api import (
    Playwright, Browser, BrowserContext, Page,
    BrowserType, ViewportSize
)
from pathlib import Path
import json


# Browser configurations
BROWSER_CONFIGS = {
    "desktop_chrome": {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "device_scale_factor": 1,
    },
    "desktop_firefox": {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Firefox/120.0",
        "device_scale_factor": 1,
    },
    "mobile_iphone": {
        "viewport": {"width": 390, "height": 844},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "device_scale_factor": 3,
        "has_touch": True,
        "is_mobile": True,
    },
    "tablet_ipad": {
        "viewport": {"width": 1024, "height": 1366},
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "device_scale_factor": 2,
        "has_touch": True,
    },
}


@pytest.fixture(scope="function")
def browser_context(playwright: Playwright, request) -> Generator[BrowserContext, None, None]:
    """
    Create a browser context with configurable options.

    Usage:
        @pytest.mark.parametrize('browser_config', ['desktop_chrome', 'mobile_iphone'])
        def test_responsive(browser_context):
            ...
    """
    # Get browser type from marker or default to chromium
    browser_name = request.node.get_closest_marker("browser")
    browser_type = browser_name.args[0] if browser_name else "chromium"

    # Get configuration
    config_name = getattr(request, "param", "desktop_chrome") if hasattr(request, "param") else "desktop_chrome"
    config = BROWSER_CONFIGS.get(config_name, BROWSER_CONFIGS["desktop_chrome"])

    # Launch browser
    browser_launcher = getattr(playwright, browser_type)
    headless = request.config.getoption("--headless", default=True)
    slow_mo = request.config.getoption("--slow-mo", default=0)

    browser = browser_launcher.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=['--no-sandbox', '--disable-setuid-sandbox'] if headless else []
    )

    # Create context with configuration
    context = browser.new_context(
        **config,
        ignore_https_errors=True,
        accept_downloads=True,
        locale='en-US',
        timezone_id='America/New_York',
        permissions=['geolocation', 'notifications'],
        color_scheme='light',
        record_video_dir='tests_e2e/videos' if request.config.getoption("--video", default=False) else None,
        record_har_path='tests_e2e/har/test.har' if request.config.getoption("--har", default=False) else None,
    )

    # Enable tracing if requested
    if request.config.getoption("--tracing", default=False):
        context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True
        )

    # Add request interceptor for network mocking
    def handle_route(route):
        # Add custom headers or modify requests
        headers = route.request.headers
        headers['X-Test-Request'] = 'true'
        route.continue_(headers=headers)

    # context.route("**/*", handle_route)

    yield context

    # Save trace if enabled
    if request.config.getoption("--tracing", default=False):
        trace_path = Path("tests_e2e/traces") / f"{request.node.name}.zip"
        trace_path.parent.mkdir(exist_ok=True)
        context.tracing.stop(path=str(trace_path))

    context.close()
    browser.close()


@pytest.fixture(scope="function")
def page(browser_context: BrowserContext, request) -> Generator[Page, None, None]:
    """
    Create a page with enhanced error handling and utilities.
    """
    page = browser_context.new_page()

    # Set default timeout
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(30000)

    # Add console log capture
    console_logs = []
    page.on("console", lambda msg: console_logs.append({
        "type": msg.type,
        "text": msg.text,
        "location": msg.location
    }))

    # Add error capture
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    # Add request failure capture
    failed_requests = []
    page.on("requestfailed", lambda req: failed_requests.append({
        "url": req.url,
        "failure": req.failure,
        "method": req.method
    }))

    # Attach logs to page for access in tests
    page.console_logs = console_logs
    page.page_errors = page_errors
    page.failed_requests = failed_requests

    yield page

    # Take screenshot on failure
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        screenshot_dir = Path("tests_e2e/screenshots")
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / f"{request.node.name}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)

        # Log console errors
        if page_errors:
            print(f"Page errors for {request.node.name}:")
            for error in page_errors:
                print(f"  - {error}")

        # Log failed requests
        if failed_requests:
            print(f"Failed requests for {request.node.name}:")
            for req in failed_requests:
                print(f"  - {req['method']} {req['url']}: {req['failure']}")

    page.close()


@pytest.fixture
def mobile_browser(playwright: Playwright) -> Generator[BrowserContext, None, None]:
    """
    Create a mobile browser context for mobile-specific testing.
    """
    iphone = playwright.devices['iPhone 14 Pro']
    browser = playwright.webkit.launch(headless=True)
    context = browser.new_context(
        **iphone,
        ignore_https_errors=True,
        locale='en-US',
    )

    yield context

    context.close()
    browser.close()


@pytest.fixture
def multi_browser(playwright: Playwright) -> Generator[Dict[str, Browser], None, None]:
    """
    Create multiple browser instances for cross-browser testing.
    """
    browsers = {
        'chromium': playwright.chromium.launch(headless=True),
        'firefox': playwright.firefox.launch(headless=True),
        'webkit': playwright.webkit.launch(headless=True),
    }

    yield browsers

    for browser in browsers.values():
        browser.close()


class PageHelper:
    """
    Helper class with common page interactions and assertions.
    """

    def __init__(self, page: Page):
        self.page = page

    def wait_for_element(self, selector: str, state: str = "visible", timeout: int = 10000):
        """Wait for an element to be in a specific state."""
        return self.page.wait_for_selector(selector, state=state, timeout=timeout)

    def wait_for_text(self, text: str, timeout: int = 10000):
        """Wait for text to appear on the page."""
        return self.page.wait_for_selector(f"text={text}", timeout=timeout)

    def click_and_wait(self, selector: str, wait_for: str = None):
        """Click an element and wait for navigation or another element."""
        if wait_for:
            with self.page.expect_navigation():
                self.page.click(selector)
            self.wait_for_element(wait_for)
        else:
            self.page.click(selector)

    def fill_form(self, form_data: Dict[str, Any]):
        """Fill a form with multiple fields."""
        for selector, value in form_data.items():
            if isinstance(value, bool):
                # Handle checkboxes
                if value:
                    self.page.check(selector)
                else:
                    self.page.uncheck(selector)
            elif isinstance(value, list):
                # Handle multi-select
                self.page.select_option(selector, value)
            else:
                # Handle text inputs
                self.page.fill(selector, str(value))

    def get_table_data(self, table_selector: str) -> List[Dict[str, str]]:
        """Extract data from a table."""
        headers = self.page.eval_on_selector_all(
            f"{table_selector} thead th",
            "elements => elements.map(el => el.textContent.trim())"
        )

        rows = self.page.eval_on_selector_all(
            f"{table_selector} tbody tr",
            """rows => rows.map(row => {
                const cells = Array.from(row.querySelectorAll('td'));
                return cells.map(cell => cell.textContent.trim());
            })"""
        )

        return [dict(zip(headers, row)) for row in rows]

    def wait_for_api_response(self, url_pattern: str, timeout: int = 10000):
        """Wait for a specific API response."""
        with self.page.expect_response(url_pattern, timeout=timeout) as response_info:
            return response_info.value

    def mock_api_response(self, url_pattern: str, response_data: Dict[str, Any], status: int = 200):
        """Mock an API response."""
        def handle(route):
            route.fulfill(
                status=status,
                content_type="application/json",
                body=json.dumps(response_data)
            )

        self.page.route(url_pattern, handle)

    def take_full_page_screenshot(self, name: str):
        """Take a full page screenshot with a specific name."""
        screenshot_dir = Path("tests_e2e/screenshots")
        screenshot_dir.mkdir(exist_ok=True)
        path = screenshot_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=True)
        return path

    def measure_performance(self):
        """Measure page performance metrics."""
        metrics = self.page.evaluate("""() => {
            const timing = performance.timing;
            const navigation = performance.getEntriesByType('navigation')[0];

            return {
                domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                loadComplete: timing.loadEventEnd - timing.navigationStart,
                firstPaint: navigation.firstPaint || 0,
                firstContentfulPaint: navigation.firstContentfulPaint || 0,
                resources: performance.getEntriesByType('resource').length
            };
        }""")

        return metrics


@pytest.fixture
def page_helper(page: Page) -> PageHelper:
    """
    Provide a page helper with common utilities.
    """
    return PageHelper(page)