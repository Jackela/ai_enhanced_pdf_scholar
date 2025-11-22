from typing import Any

"""
Playwright Configuration for AI Enhanced PDF Scholar Web UI Tests
"""


# Playwright pytest configuration
def pytest_configure(config) -> None:
    """Pytest configuration hook."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end browser test"
    )

# Test configuration
BASE_URL = "http://localhost:8000"
BROWSER_TIMEOUT = 30000  # 30 seconds
DEFAULT_TIMEOUT = 5000   # 5 seconds

# Browser configuration for different environments
BROWSERS = {
    "chromium": {"headless": False, "slow_mo": 500},  # Visible for debugging
    "firefox": {"headless": True},   # Headless for CI
    "webkit": {"headless": True}     # Headless for CI
}

# Test data
TEST_PDF_CONTENT = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Hello World!) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""
