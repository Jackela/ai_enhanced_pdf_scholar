"""
Playwright Test Configuration
"""

import pytest
import time
import subprocess
import sys
import threading
from pathlib import Path
from playwright.sync_api import Playwright, Browser, BrowserContext, Page

# Test configuration
BASE_URL = "http://localhost:8000"
SERVER_STARTUP_TIMEOUT = 10  # seconds


class WebServerManager:
    """Manages the web server for testing."""
    
    def __init__(self):
        self.process = None
        self.is_running = False
    
    def start_server(self):
        """Start the web server in a separate process."""
        if self.is_running:
            return True
            
        try:
            # Start server in background
            self.process = subprocess.Popen(
                [sys.executable, "web_main.py", "--host", "localhost", "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            start_time = time.time()
            while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
                try:
                    import requests
                    response = requests.get(f"{BASE_URL}/health", timeout=1)
                    if response.status_code == 200:
                        self.is_running = True
                        print(f"✅ Web server started on {BASE_URL}")
                        return True
                except:
                    time.sleep(0.5)
                    continue
            
            print("❌ Web server failed to start within timeout")
            return False
            
        except Exception as e:
            print(f"❌ Error starting web server: {e}")
            return False
    
    def stop_server(self):
        """Stop the web server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.is_running = False
        print("🛑 Web server stopped")


# Global server manager
server_manager = WebServerManager()


@pytest.fixture(scope="session", autouse=True)
def web_server():
    """Start web server for the entire test session."""
    if not server_manager.start_server():
        pytest.skip("Could not start web server")
    
    yield BASE_URL
    
    server_manager.stop_server()


@pytest.fixture(scope="function")
def browser_context(playwright: Playwright):
    """Create a new browser context for each test."""
    browser = playwright.chromium.launch(
        headless=False,  # Set to True for CI
        slow_mo=500      # Slow down for debugging
    )
    
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True
    )
    
    yield context
    
    context.close()
    browser.close()


@pytest.fixture(scope="function")
def page(browser_context: BrowserContext):
    """Create a new page for each test."""
    page = browser_context.new_page()
    
    # Set default timeout
    page.set_default_timeout(10000)
    
    yield page
    
    page.close()


@pytest.fixture
def test_pdf_file():
    """Create a test PDF file."""
    pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj  
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT/F1 12 Tf 72 720 Td(Test PDF Content)Tj ET
endstream endobj
xref 0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer<</Size 5/Root 1 0 R>>
startxref 300
%%EOF"""
    
    test_file = Path("test_document.pdf")
    test_file.write_bytes(pdf_content)
    
    yield test_file
    
    # Cleanup
    if test_file.exists():
        test_file.unlink() 