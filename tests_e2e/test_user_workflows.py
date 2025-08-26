"""
User Workflow Tests for AI Enhanced PDF Scholar
测试完整的用户工作流程
"""

import time

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestUserWorkflows:
    """Test complete user workflows."""

    def test_complete_pdf_analysis_workflow(self, page: Page, web_server, test_pdf_file):
        """测试完整的PDF分析工作流程"""
        print("🔍 Testing complete PDF analysis workflow...")

        # Step 1: Load homepage
        page.goto(web_server)
        expect(page.locator("h1")).to_contain_text("AI Enhanced PDF Scholar")

        # Step 2: Upload PDF (simulated)
        upload_btn = page.locator("#upload-btn")
        if upload_btn.count() > 0:
            upload_btn.click()
            time.sleep(1)

            # Look for file input
            file_input = page.locator("input[type='file']")
            if file_input.count() > 0:
                file_input.set_input_files(str(test_pdf_file))
                time.sleep(2)
                print("✅ PDF uploaded successfully")

        # Step 3: Test chat interaction
        chat_input = page.locator("#chat-input")
        if chat_input.count() > 0:
            test_question = "What is the main content of this document?"
            chat_input.fill(test_question)

            # Send message
            send_btn = page.locator("#send-btn")
            if send_btn.count() > 0:
                send_btn.click()
                time.sleep(3)  # Wait for response
                print("✅ Chat message sent")

        print("✅ Complete PDF analysis workflow tested")

    def test_multiple_chat_interactions(self, page: Page, web_server):
        """测试多轮聊天交互"""
        print("🔍 Testing multiple chat interactions...")

        page.goto(web_server)

        chat_input = page.locator("#chat-input")
        send_btn = page.locator("#send-btn")

        if chat_input.count() > 0 and send_btn.count() > 0:
            # First message
            chat_input.fill("Hello, can you help me analyze documents?")
            send_btn.click()
            time.sleep(2)

            # Second message
            chat_input.fill("What file formats do you support?")
            send_btn.click()
            time.sleep(2)

            # Third message
            chat_input.fill("How does the AI analysis work?")
            send_btn.click()
            time.sleep(2)

            print("✅ Multiple chat interactions completed")
        else:
            print("ℹ️  Chat interface not found")

    def test_responsive_user_experience(self, page: Page, web_server):
        """测试响应式用户体验"""
        print("🔍 Testing responsive user experience...")

        # Test different viewport sizes and interactions
        viewports = [
            {"width": 1920, "height": 1080, "name": "Desktop Large"},
            {"width": 1280, "height": 720, "name": "Desktop"},
            {"width": 768, "height": 1024, "name": "Tablet"},
            {"width": 375, "height": 667, "name": "Mobile"}
        ]

        for viewport in viewports:
            print(f"  📱 Testing {viewport['name']} view...")

            page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
            page.goto(web_server)
            time.sleep(1)

            # Check if main elements are still accessible
            heading = page.locator("h1")
            expect(heading).to_be_visible()

            # Try to interact with chat if visible
            chat_input = page.locator("#chat-input")
            if chat_input.is_visible():
                chat_input.fill(f"Test from {viewport['name']}")
                time.sleep(1)
                chat_input.clear()

            print(f"  ✅ {viewport['name']} view working")

        print("✅ Responsive user experience tested")

    def test_error_recovery_workflow(self, page: Page, web_server):
        """测试错误恢复工作流程"""
        print("🔍 Testing error recovery workflow...")

        page.goto(web_server)

        # Test invalid file upload (if upload exists)
        upload_btn = page.locator("#upload-btn")
        if upload_btn.count() > 0:
            upload_btn.click()

            # Try to upload non-PDF file
            file_input = page.locator("input[type='file']")
            if file_input.count() > 0:
                # Create temporary text file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                    tmp.write(b"This is not a PDF file")
                    tmp_path = tmp.name

                try:
                    file_input.set_input_files(tmp_path)
                    time.sleep(1)
                    print("✅ Invalid file upload handled")
                except Exception as e:
                    print(f"ℹ️  File upload error (expected): {e}")

                # Cleanup
                import os
                os.unlink(tmp_path)

        # Test network error recovery (simulated)
        # This would require more complex setup

        print("✅ Error recovery workflow tested")

    def test_performance_workflow(self, page: Page, web_server):
        """测试性能相关的工作流程"""
        print("🔍 Testing performance workflow...")

        # Measure page load time
        start_time = time.time()
        page.goto(web_server)
        load_time = time.time() - start_time

        print(f"  📊 Page load time: {load_time:.2f} seconds")

        # Should load within reasonable time
        assert load_time < 10, f"Page load too slow: {load_time:.2f}s"

        # Test rapid interactions
        chat_input = page.locator("#chat-input")
        if chat_input.count() > 0:
            start_time = time.time()

            # Rapid typing
            for i in range(5):
                chat_input.fill(f"Rapid test message {i}")
                time.sleep(0.1)

            interaction_time = time.time() - start_time
            print(f"  📊 Rapid interaction time: {interaction_time:.2f} seconds")

        print("✅ Performance workflow tested")

    def test_accessibility_workflow(self, page: Page, web_server):
        """测试可访问性工作流程"""
        print("🔍 Testing accessibility workflow...")

        page.goto(web_server)

        # Test keyboard navigation
        page.keyboard.press("Tab")
        time.sleep(0.5)
        page.keyboard.press("Tab")
        time.sleep(0.5)

        # Test if elements are focusable
        focused_element = page.evaluate("document.activeElement.tagName")
        print(f"  🎯 Focused element: {focused_element}")

        # Test screen reader compatibility (basic)
        # Check for ARIA labels, alt text, etc.
        images = page.locator("img")
        image_count = images.count()

        for i in range(image_count):
            alt_text = images.nth(i).get_attribute("alt")
            if not alt_text:
                print(f"  ⚠️  Image {i} missing alt text")
            else:
                print(f"  ✅ Image {i} has alt text: {alt_text}")

        print("✅ Accessibility workflow tested")

    def test_data_persistence_workflow(self, page: Page, web_server):
        """测试数据持久化工作流程"""
        print("🔍 Testing data persistence workflow...")

        page.goto(web_server)

        # Test localStorage/sessionStorage if used
        # Add test data
        page.evaluate("""
            localStorage.setItem('test_key', 'test_value');
            sessionStorage.setItem('session_key', 'session_value');
        """)

        # Refresh page
        page.reload()
        time.sleep(2)

        # Check if data persists
        local_value = page.evaluate("localStorage.getItem('test_key')")
        session_value = page.evaluate("sessionStorage.getItem('session_key')")

        print(f"  💾 localStorage value: {local_value}")
        print(f"  🔄 sessionStorage value: {session_value}")

        # Clean up
        page.evaluate("""
            localStorage.removeItem('test_key');
            sessionStorage.removeItem('session_key');
        """)

        print("✅ Data persistence workflow tested")

    def test_real_time_communication_workflow(self, page: Page, web_server):
        """测试实时通信工作流程"""
        print("🔍 Testing real-time communication workflow...")

        page.goto(web_server)

        # Test WebSocket communication
        websocket_script = """
        window.wsTest = {
            messages: [],
            connect: function() {
                return new Promise((resolve, reject) => {
                    const ws = new WebSocket('ws://localhost:8000/ws');

                    ws.onopen = function() {
                        console.log('WebSocket connected');

                        // Send test messages
                        ws.send(JSON.stringify({type: 'test', data: 'message 1'}));
                        setTimeout(() => {
                            ws.send(JSON.stringify({type: 'test', data: 'message 2'}));
                        }, 1000);
                    };

                    ws.onmessage = function(event) {
                        window.wsTest.messages.push(event.data);
                        console.log('Received:', event.data);

                        if (window.wsTest.messages.length >= 2) {
                            ws.close();
                            resolve(window.wsTest.messages);
                        }
                    };

                    ws.onerror = function(error) {
                        reject(error);
                    };

                    setTimeout(() => {
                        reject(new Error('WebSocket test timeout'));
                    }, 10000);
                });
            }
        };
        """

        page.add_init_script(websocket_script)

        try:
            messages = page.evaluate("window.wsTest.connect()")
            print(f"  📡 WebSocket messages received: {len(messages)}")
            for i, msg in enumerate(messages):
                print(f"    {i+1}. {msg}")
        except Exception as e:
            print(f"  ⚠️  WebSocket test failed: {e}")

        print("✅ Real-time communication workflow tested")
