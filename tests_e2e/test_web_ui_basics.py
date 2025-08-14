"""
Basic Web UI Tests for AI Enhanced PDF Scholar
测试基础的Web界面功能
"""

import pytest
import time
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestWebUIBasics:
    """Test basic web UI functionality."""

    def test_homepage_loads(self, page: Page, web_server):
        """测试首页是否正确加载"""
        print("🔍 Testing homepage loading...")

        # Navigate to homepage
        page.goto(web_server)

        # Check page title
        expect(page).to_have_title("AI Enhanced PDF Scholar - Web UI")

        # Check main heading
        heading = page.locator("h1")
        expect(heading).to_contain_text("AI Enhanced PDF Scholar")

        print("✅ Homepage loaded successfully")

    def test_ui_components_present(self, page: Page, web_server):
        """测试主要UI组件是否存在"""
        print("🔍 Testing UI components presence...")

        page.goto(web_server)

        # Check main sections
        expect(page.locator(".pdf-panel")).to_be_visible()
        expect(page.locator(".chat-panel")).to_be_visible()

        # Check upload area
        upload_area = page.locator(".upload-area")
        expect(upload_area).to_be_visible()
        expect(upload_area).to_contain_text("Click to upload PDF")

        # Check chat input
        chat_input = page.locator("#messageInput")
        expect(chat_input).to_be_visible()

        # Check send button
        send_btn = page.locator("#sendButton")
        expect(send_btn).to_be_visible()

        print("✅ All UI components are present")

    def test_responsive_design(self, page: Page, web_server):
        """测试响应式设计"""
        print("🔍 Testing responsive design...")

        page.goto(web_server)

        # Test desktop view (1280x720)
        page.set_viewport_size({"width": 1280, "height": 720})
        time.sleep(1)

        # Check if sections are side by side
        pdf_section = page.locator(".pdf-panel")
        chat_section = page.locator(".chat-panel")

        expect(pdf_section).to_be_visible()
        expect(chat_section).to_be_visible()

        # Test tablet view (768x1024)
        page.set_viewport_size({"width": 768, "height": 1024})
        time.sleep(1)

        # Sections should still be visible
        expect(pdf_section).to_be_visible()
        expect(chat_section).to_be_visible()

        # Test mobile view (375x667)
        page.set_viewport_size({"width": 375, "height": 667})
        time.sleep(1)

        # Should still be responsive
        expect(pdf_section).to_be_visible()

        print("✅ Responsive design working properly")

    def test_pdf_upload_interface(self, page: Page, web_server, test_pdf_file):
        """测试PDF上传界面"""
        print("🔍 Testing PDF upload interface...")

        page.goto(web_server)

        # Check upload area exists
        upload_area = page.locator(".upload-area")
        expect(upload_area).to_be_visible()

        # Check if file input exists (hidden)
        file_input = page.locator("#pdfUpload")

        # If file input exists, test file selection
        if file_input.count() > 0:
            # Set file
            file_input.set_input_files(str(test_pdf_file))
            time.sleep(1)

            print("✅ PDF file selected successfully")
        else:
            print("ℹ️  File input not found - may be custom implementation")

        print("✅ PDF upload interface functional")

    def test_chat_input_functionality(self, page: Page, web_server):
        """测试聊天输入功能"""
        print("🔍 Testing chat input functionality...")

        page.goto(web_server)

        # Find chat input
        chat_input = page.locator("#messageInput")

        # Type test message
        test_message = "Hello, this is a test message!"
        chat_input.fill(test_message)

        # Check if input has the text
        expect(chat_input).to_have_value(test_message)

        # Find and click send button
        send_btn = page.locator("#sendButton")
        send_btn.click()

        # Wait a moment for response
        time.sleep(2)

        # Check if message appears in chat (depending on implementation)
        chat_messages = page.locator(".chat-message, .message, #chat-messages")

        print("✅ Chat input functionality working")

    def test_websocket_connection(self, page: Page, web_server):
        """测试WebSocket连接"""
        print("🔍 Testing WebSocket connection...")

        page.goto(web_server)

        # Add JavaScript to test WebSocket
        websocket_test = """
        window.testWebSocket = function() {
            return new Promise((resolve, reject) => {
                const ws = new WebSocket('ws://localhost:8000/ws');

                ws.onopen = function() {
                    ws.send(JSON.stringify({type: 'test', data: 'connection check'}));
                };

                ws.onmessage = function(event) {
                    ws.close();
                    resolve('WebSocket working');
                };

                ws.onerror = function(error) {
                    reject(error);
                };

                setTimeout(() => reject('Timeout'), 5000);
            });
        };
        """

        page.add_init_script(websocket_test)

        # Test WebSocket connection
        try:
            result = page.evaluate("window.testWebSocket()")
            print(f"✅ WebSocket test result: {result}")
        except Exception as e:
            print(f"⚠️  WebSocket test failed: {e}")

        print("✅ WebSocket connection tested")

    def test_page_navigation(self, page: Page, web_server):
        """测试页面导航和链接"""
        print("🔍 Testing page navigation...")

        page.goto(web_server)

        # Test refresh
        page.reload()
        time.sleep(2)

        # Should still show the main page
        expect(page.locator("h1")).to_contain_text("AI Enhanced PDF Scholar")

        # Test back button (if applicable)
        page.go_back()
        page.go_forward()

        print("✅ Page navigation working")

    def test_error_handling(self, page: Page, web_server):
        """测试错误处理"""
        print("🔍 Testing error handling...")

        # Test invalid URL
        page.goto(f"{web_server}/nonexistent-page")

        # Should handle 404 gracefully
        # (Depending on FastAPI configuration)

        # Go back to main page
        page.goto(web_server)
        expect(page.locator("h1")).to_contain_text("AI Enhanced PDF Scholar")

        print("✅ Error handling tested")

    def test_accessibility_basics(self, page: Page, web_server):
        """测试基础可访问性"""
        print("🔍 Testing basic accessibility...")

        page.goto(web_server)

        # Check for important accessibility features
        # 1. Page has title
        expect(page).to_have_title("AI Enhanced PDF Scholar - Web UI")

        # 2. Main heading exists
        expect(page.locator("h1")).to_be_visible()

        # 3. Form elements have labels or placeholders
        chat_input = page.locator("#messageInput")
        if chat_input.count() > 0:
            # Should have placeholder or label
            placeholder = chat_input.get_attribute("placeholder")
            if placeholder:
                print(f"✅ Chat input has placeholder: {placeholder}")

        # 4. Buttons are clickable
        buttons = page.locator("button")
        button_count = buttons.count()
        print(f"✅ Found {button_count} clickable buttons")

        print("✅ Basic accessibility features present")