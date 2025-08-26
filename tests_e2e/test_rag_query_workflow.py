"""
RAG Query Workflow E2E Tests

Tests for document querying, response validation, and RAG functionality.
"""

import time

import pytest
from fixtures import *
from playwright.sync_api import Page, expect


class TestRAGQueryWorkflow:
    """Test RAG (Retrieval-Augmented Generation) query workflows."""

    @pytest.mark.e2e
    @pytest.mark.rag
    def test_simple_rag_query(
        self,
        page: Page,
        page_helper,
        api_client,
        seeded_database,
        web_server
    ):
        """Test basic RAG query functionality."""
        # Navigate to RAG interface
        page.goto(f"{web_server}/rag")
        page_helper.wait_for_text("AI-Powered Document Q&A")

        # Select documents for context
        doc_selector = page.locator('[data-testid="document-selector"]')
        doc_selector.click()

        # Select first 3 documents
        doc_options = page.locator('[data-testid="doc-option"]')
        for i in range(min(3, doc_options.count())):
            doc_options.nth(i).click()

        # Close selector
        page.click('body')  # Click outside to close

        # Verify selected documents shown
        selected_docs = page.locator('[data-testid="selected-documents"]')
        expect(selected_docs).to_contain_text("3 documents selected")

        # Enter query
        query_input = page.locator('[data-testid="rag-query-input"]')
        query_input.fill("What are the main topics covered in these documents?")

        # Submit query
        submit_button = page.locator('[data-testid="submit-query"]')

        # Monitor API call
        with page.expect_response("**/api/rag/query") as response_info:
            submit_button.click()

        response = response_info.value
        assert response.status == 200

        # Wait for response
        response_container = page.locator('[data-testid="rag-response"]')
        expect(response_container).to_be_visible(timeout=15000)

        # Verify response structure
        response_text = response_container.locator('[data-testid="response-text"]')
        expect(response_text).not_to_be_empty()

        # Verify sources
        sources_section = page.locator('[data-testid="response-sources"]')
        expect(sources_section).to_be_visible()

        source_items = sources_section.locator('[data-testid="source-item"]')
        assert source_items.count() > 0

        # Verify confidence score
        confidence = page.locator('[data-testid="confidence-score"]')
        expect(confidence).to_be_visible()
        confidence_value = float(confidence.get_attribute("data-score"))
        assert 0 <= confidence_value <= 1

        # Verify processing time
        processing_time = page.locator('[data-testid="processing-time"]')
        expect(processing_time).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.rag
    def test_complex_multi_turn_conversation(
        self,
        page: Page,
        page_helper,
        api_client,
        seeded_database,
        web_server
    ):
        """Test multi-turn conversation with context retention."""
        page.goto(f"{web_server}/rag")

        # Select documents
        doc_selector = page.locator('[data-testid="document-selector"]')
        doc_selector.click()

        select_all = page.locator('[data-testid="select-all-docs"]')
        select_all.click()
        page.click('body')

        # First query
        query_input = page.locator('[data-testid="rag-query-input"]')
        query_input.fill("What is machine learning?")

        submit_button = page.locator('[data-testid="submit-query"]')
        submit_button.click()

        # Wait for first response
        first_response = page.locator('[data-testid="conversation-message"]').first
        expect(first_response).to_be_visible(timeout=15000)

        # Follow-up query
        query_input.fill("Can you provide more details about supervised learning?")
        submit_button.click()

        # Wait for second response
        messages = page.locator('[data-testid="conversation-message"]')
        expect(messages).to_have_count(4, timeout=15000)  # 2 queries + 2 responses

        # Verify context retention
        second_response = messages.nth(3)
        expect(second_response).to_contain_text("supervised")

        # Third query referencing previous
        query_input.fill("How does this compare to what you mentioned earlier?")
        submit_button.click()

        # Verify conversation flow
        expect(messages).to_have_count(6, timeout=15000)

        # Test conversation export
        export_button = page.locator('[data-testid="export-conversation"]')

        with page.expect_download() as download_info:
            export_button.click()

        download = download_info.value
        assert download.suggested_filename.endswith('.json') or download.suggested_filename.endswith('.txt')

        # Test clear conversation
        clear_button = page.locator('[data-testid="clear-conversation"]')
        clear_button.click()

        # Confirm clear
        confirm_dialog = page.locator('[data-testid="confirm-dialog"]')
        confirm_button = confirm_dialog.locator('[data-testid="confirm-action"]')
        confirm_button.click()

        # Verify conversation cleared
        expect(messages).to_have_count(0)

    @pytest.mark.e2e
    @pytest.mark.rag
    def test_rag_with_filters_and_options(
        self,
        page: Page,
        page_helper,
        api_client,
        seeded_database,
        web_server
    ):
        """Test RAG queries with various filters and options."""
        page.goto(f"{web_server}/rag")

        # Open advanced options
        advanced_button = page.locator('[data-testid="advanced-options"]')
        advanced_button.click()

        advanced_panel = page.locator('[data-testid="advanced-panel"]')
        expect(advanced_panel).to_be_visible()

        # Set temperature/creativity
        temperature_slider = advanced_panel.locator('[data-testid="temperature-slider"]')
        temperature_slider.fill("0.3")  # More focused responses

        # Set max tokens
        max_tokens = advanced_panel.locator('[data-testid="max-tokens"]')
        max_tokens.fill("500")

        # Enable citation mode
        citation_mode = advanced_panel.locator('[data-testid="citation-mode"]')
        citation_mode.check()

        # Set language
        language_select = advanced_panel.locator('[data-testid="response-language"]')
        language_select.select_option("en")

        # Select specific document types
        doc_type_filter = advanced_panel.locator('[data-testid="doc-type-filter"]')
        doc_type_filter.select_option("Research")

        # Set date range for documents
        date_from = advanced_panel.locator('[data-testid="doc-date-from"]')
        date_to = advanced_panel.locator('[data-testid="doc-date-to"]')

        from datetime import datetime, timedelta
        today = datetime.now()
        month_ago = today - timedelta(days=30)

        date_from.fill(month_ago.strftime("%Y-%m-%d"))
        date_to.fill(today.strftime("%Y-%m-%d"))

        # Apply filters
        apply_button = advanced_panel.locator('[data-testid="apply-advanced"]')
        apply_button.click()

        # Submit query with filters
        query_input = page.locator('[data-testid="rag-query-input"]')
        query_input.fill("Summarize the key findings from recent research papers")

        submit_button = page.locator('[data-testid="submit-query"]')
        submit_button.click()

        # Wait for response
        response_container = page.locator('[data-testid="rag-response"]')
        expect(response_container).to_be_visible(timeout=15000)

        # Verify citations are included
        citations = response_container.locator('[data-testid="inline-citation"]')
        assert citations.count() > 0

        # Verify response length constraint
        response_text = response_container.locator('[data-testid="response-text"]').text_content()
        word_count = len(response_text.split())
        assert word_count <= 500  # Approximate token to word conversion

    @pytest.mark.e2e
    @pytest.mark.rag
    @pytest.mark.performance
    def test_rag_query_performance(
        self,
        page: Page,
        page_helper,
        api_client,
        seeded_database,
        web_server,
        performance_test_data
    ):
        """Test RAG query performance with various complexities."""
        page.goto(f"{web_server}/rag")

        # Select all documents for comprehensive context
        doc_selector = page.locator('[data-testid="document-selector"]')
        doc_selector.click()
        select_all = page.locator('[data-testid="select-all-docs"]')
        select_all.click()
        page.click('body')

        query_complexities = performance_test_data['query_complexity']
        performance_results = []

        for complexity in query_complexities:
            # Prepare query based on complexity
            if complexity['type'] == 'simple':
                query = "What is AI?"
            elif complexity['type'] == 'moderate':
                query = "Explain the differences between supervised and unsupervised learning with examples"
            else:  # complex
                query = ("Provide a comprehensive analysis of machine learning algorithms, "
                        "their applications, advantages, disadvantages, and future trends. "
                        "Include specific examples and case studies from the documents.")

            query_input = page.locator('[data-testid="rag-query-input"]')
            query_input.fill(query)

            # Measure query time
            start_time = time.time()

            submit_button = page.locator('[data-testid="submit-query"]')
            with page.expect_response("**/api/rag/query") as response_info:
                submit_button.click()

            # Wait for response
            response_container = page.locator('[data-testid="rag-response"]')
            expect(response_container).to_be_visible(timeout=30000)

            query_time = time.time() - start_time

            # Verify performance threshold
            assert query_time < complexity['expected_time'] * 2  # Allow 2x buffer

            performance_results.append({
                'complexity': complexity['type'],
                'query_time': query_time,
                'expected': complexity['expected_time'],
                'passed': query_time < complexity['expected_time'] * 2
            })

            # Clear for next test
            clear_button = page.locator('[data-testid="clear-conversation"]')
            clear_button.click()
            confirm_button = page.locator('[data-testid="confirm-action"]')
            confirm_button.click()

            time.sleep(1)  # Brief pause between queries

        # Log performance results
        print("\nRAG Query Performance Results:")
        for result in performance_results:
            status = "✅" if result['passed'] else "❌"
            print(f"{status} {result['complexity']}: {result['query_time']:.2f}s (expected: {result['expected']}s)")

    @pytest.mark.e2e
    @pytest.mark.rag
    def test_rag_error_handling(
        self,
        page: Page,
        page_helper,
        api_client,
        web_server
    ):
        """Test RAG error handling and recovery."""
        page.goto(f"{web_server}/rag")

        # Test 1: Query without selecting documents
        query_input = page.locator('[data-testid="rag-query-input"]')
        query_input.fill("Test query without documents")

        submit_button = page.locator('[data-testid="submit-query"]')
        submit_button.click()

        # Verify error message
        error_message = page.locator('[data-testid="error-message"]')
        expect(error_message).to_be_visible()
        expect(error_message).to_contain_text("Please select at least one document")

        # Test 2: Empty query
        doc_selector = page.locator('[data-testid="document-selector"]')
        doc_selector.click()
        first_doc = page.locator('[data-testid="doc-option"]').first
        first_doc.click()
        page.click('body')

        query_input.clear()
        submit_button.click()

        # Verify validation error
        validation_error = page.locator('[data-testid="validation-error"]')
        expect(validation_error).to_be_visible()
        expect(validation_error).to_contain_text("Please enter a query")

        # Test 3: Network error simulation
        # Intercept and fail the API request
        page.route("**/api/rag/query", lambda route: route.abort())

        query_input.fill("Test network error")
        submit_button.click()

        # Verify network error handling
        network_error = page.locator('[data-testid="network-error"]')
        expect(network_error).to_be_visible(timeout=10000)

        retry_button = network_error.locator('[data-testid="retry-button"]')
        expect(retry_button).to_be_visible()

        # Remove route interception
        page.unroute("**/api/rag/query")

        # Test retry
        retry_button.click()

        # Should work now
        response_container = page.locator('[data-testid="rag-response"]')
        expect(response_container).to_be_visible(timeout=15000)

        # Test 4: Timeout handling
        # Set very short timeout
        page.set_default_timeout(1000)

        # Mock slow response
        def slow_response(route):
            time.sleep(5)
            route.continue_()

        page.route("**/api/rag/query", slow_response)

        query_input.fill("Test timeout")

        try:
            submit_button.click()
            page.wait_for_selector('[data-testid="rag-response"]', timeout=1000)
        except:
            # Expected timeout
            timeout_error = page.locator('[data-testid="timeout-error"]')
            expect(timeout_error).to_be_visible()

        # Reset timeout
        page.set_default_timeout(30000)
        page.unroute("**/api/rag/query")

    @pytest.mark.e2e
    @pytest.mark.rag
    def test_rag_response_actions(
        self,
        page: Page,
        page_helper,
        api_client,
        seeded_database,
        web_server
    ):
        """Test actions available on RAG responses."""
        page.goto(f"{web_server}/rag")

        # Setup and submit query
        doc_selector = page.locator('[data-testid="document-selector"]')
        doc_selector.click()
        first_doc = page.locator('[data-testid="doc-option"]').first
        first_doc.click()
        page.click('body')

        query_input = page.locator('[data-testid="rag-query-input"]')
        query_input.fill("Explain the main concepts")

        submit_button = page.locator('[data-testid="submit-query"]')
        submit_button.click()

        # Wait for response
        response_container = page.locator('[data-testid="rag-response"]')
        expect(response_container).to_be_visible(timeout=15000)

        # Test copy response
        copy_button = response_container.locator('[data-testid="copy-response"]')
        copy_button.click()

        # Verify copy feedback
        copy_feedback = page.locator('[data-testid="copy-feedback"]')
        expect(copy_feedback).to_be_visible()
        expect(copy_feedback).to_contain_text("Copied")

        # Test share response
        share_button = response_container.locator('[data-testid="share-response"]')
        share_button.click()

        share_dialog = page.locator('[data-testid="share-dialog"]')
        expect(share_dialog).to_be_visible()

        share_link = share_dialog.locator('[data-testid="share-link"]')
        share_url = share_link.get_attribute("value")
        assert share_url.startswith("http")

        # Close share dialog
        close_share = share_dialog.locator('[data-testid="close-dialog"]')
        close_share.click()

        # Test feedback (thumbs up/down)
        thumbs_up = response_container.locator('[data-testid="feedback-positive"]')
        thumbs_up.click()

        # Verify feedback recorded
        expect(thumbs_up).to_have_class("active")

        # Test regenerate response
        regenerate_button = response_container.locator('[data-testid="regenerate-response"]')
        regenerate_button.click()

        # Wait for new response
        page_helper.wait_for_text("Regenerating response", timeout=5000)

        # Verify new response generated
        regenerated_response = page.locator('[data-testid="rag-response"]').last
        expect(regenerated_response).to_be_visible(timeout=15000)

        # Test view sources in detail
        view_sources = response_container.locator('[data-testid="view-sources-detail"]')
        view_sources.click()

        sources_modal = page.locator('[data-testid="sources-modal"]')
        expect(sources_modal).to_be_visible()

        # Verify source details
        source_entries = sources_modal.locator('[data-testid="source-entry"]')
        assert source_entries.count() > 0

        # Check source has required information
        first_source = source_entries.first
        expect(first_source).to_contain_text("Document:")
        expect(first_source).to_contain_text("Page:")
        expect(first_source).to_contain_text("Relevance:")

        # Close modal
        close_modal = sources_modal.locator('[data-testid="close-modal"]')
        close_modal.click()
