"""
Complete Document Workflow E2E Tests

Tests the entire document lifecycle from upload to querying.
"""

import pytest
from pathlib import Path
from playwright.sync_api import Page, expect
import time
from typing import Dict, Any
from fixtures import *


class TestCompleteDocumentWorkflow:
    """Test complete document processing workflows."""

    @pytest.mark.e2e
    @pytest.mark.workflow
    def test_single_document_complete_workflow(
        self,
        page: Page,
        page_helper,
        api_client,
        test_pdf_files,
        web_server
    ):
        """
        Test complete workflow for a single document:
        Upload → Processing → Indexing → Querying → Download
        """
        # Navigate to the application
        page.goto(web_server)
        page_helper.wait_for_text("AI Enhanced PDF Scholar")

        # Step 1: Upload document
        upload_button = page.locator('[data-testid="upload-button"]')
        expect(upload_button).to_be_visible()
        upload_button.click()

        # Select file for upload
        file_input = page.locator('input[type="file"]')
        test_file = test_pdf_files["standard"]
        file_input.set_input_files(str(test_file))

        # Add metadata
        title_input = page.locator('[data-testid="document-title"]')
        title_input.fill("Test Research Paper")

        category_select = page.locator('[data-testid="document-category"]')
        category_select.select_option("Research")

        tags_input = page.locator('[data-testid="document-tags"]')
        tags_input.fill("machine-learning, AI, testing")

        # Submit upload
        submit_button = page.locator('[data-testid="upload-submit"]')
        submit_button.click()

        # Step 2: Wait for processing
        with page.expect_response("**/api/documents/*/status") as response_info:
            # Wait for processing to complete
            page_helper.wait_for_text("Processing complete", timeout=30000)

        response = response_info.value
        assert response.status == 200

        # Verify document appears in library
        page.goto(f"{web_server}/library")
        page_helper.wait_for_text("Test Research Paper")

        # Step 3: Verify indexing
        document_card = page.locator('[data-testid="document-card"]').filter(
            has_text="Test Research Paper"
        )
        expect(document_card).to_be_visible()

        # Check status indicator
        status_badge = document_card.locator('[data-testid="status-badge"]')
        expect(status_badge).to_have_text("Indexed")

        # Step 4: Query the document
        page.goto(f"{web_server}/rag")

        # Select document for querying
        doc_checkbox = page.locator('[data-testid="doc-select-Test Research Paper"]')
        doc_checkbox.check()

        # Enter query
        query_input = page.locator('[data-testid="rag-query-input"]')
        query_input.fill("What is the main topic of this document?")

        # Submit query
        query_button = page.locator('[data-testid="submit-query"]')
        with page.expect_response("**/api/rag/query") as response_info:
            query_button.click()

        # Verify response
        response = response_info.value
        assert response.status == 200

        response_container = page.locator('[data-testid="rag-response"]')
        expect(response_container).to_be_visible(timeout=10000)

        # Verify source attribution
        sources = page.locator('[data-testid="response-sources"]')
        expect(sources).to_contain_text("Test Research Paper")

        # Step 5: Download document
        page.goto(f"{web_server}/library")

        document_card = page.locator('[data-testid="document-card"]').filter(
            has_text="Test Research Paper"
        )
        download_button = document_card.locator('[data-testid="download-button"]')

        # Set up download handler
        with page.expect_download() as download_info:
            download_button.click()

        download = download_info.value
        assert download.suggested_filename.endswith('.pdf')

        # Verify download
        download_path = Path("tests_e2e/downloads") / download.suggested_filename
        download_path.parent.mkdir(exist_ok=True)
        download.save_as(download_path)
        assert download_path.exists()

        # Cleanup
        download_path.unlink()

    @pytest.mark.e2e
    @pytest.mark.workflow
    @pytest.mark.parallel
    def test_multiple_documents_parallel_processing(
        self,
        page: Page,
        page_helper,
        api_client,
        test_pdf_files,
        web_server
    ):
        """
        Test uploading and processing multiple documents in parallel.
        """
        # Navigate to batch upload
        page.goto(f"{web_server}/batch-upload")

        # Select multiple files
        file_input = page.locator('input[type="file"][multiple]')
        files = [
            test_pdf_files["standard"],
            test_pdf_files["with_citations"],
            test_pdf_files["special_chars"]
        ]
        file_input.set_input_files([str(f) for f in files])

        # Set batch metadata
        batch_category = page.locator('[data-testid="batch-category"]')
        batch_category.select_option("Research")

        batch_tags = page.locator('[data-testid="batch-tags"]')
        batch_tags.fill("batch-test, parallel-processing")

        # Submit batch upload
        submit_button = page.locator('[data-testid="batch-upload-submit"]')
        submit_button.click()

        # Monitor processing progress
        progress_container = page.locator('[data-testid="batch-progress"]')
        expect(progress_container).to_be_visible()

        # Wait for all documents to be processed
        for i in range(len(files)):
            progress_item = page.locator(f'[data-testid="progress-item-{i}"]')
            expect(progress_item).to_have_attribute("data-status", "completed", timeout=60000)

        # Verify all documents in library
        page.goto(f"{web_server}/library")

        for file in files:
            file_name = file.stem
            document_card = page.locator('[data-testid="document-card"]').filter(
                has_text=file_name
            )
            expect(document_card).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.workflow
    @pytest.mark.citations
    def test_document_with_citations_workflow(
        self,
        page: Page,
        page_helper,
        api_client,
        test_pdf_files,
        web_server
    ):
        """
        Test workflow for documents with citations.
        """
        # Upload document with citations
        page.goto(web_server)

        upload_button = page.locator('[data-testid="upload-button"]')
        upload_button.click()

        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(test_pdf_files["with_citations"]))

        # Enable citation extraction
        citation_toggle = page.locator('[data-testid="extract-citations-toggle"]')
        citation_toggle.check()

        # Submit upload
        submit_button = page.locator('[data-testid="upload-submit"]')
        submit_button.click()

        # Wait for processing with citation extraction
        page_helper.wait_for_text("Citation extraction complete", timeout=45000)

        # Navigate to document details
        page.goto(f"{web_server}/library")

        document_card = page.locator('[data-testid="document-card"]').filter(
            has_text="Document with Citations"
        )
        document_card.click()

        # Verify citations tab
        citations_tab = page.locator('[data-testid="citations-tab"]')
        citations_tab.click()

        # Check citation list
        citation_list = page.locator('[data-testid="citation-list"]')
        expect(citation_list).to_be_visible()

        # Verify at least one citation was extracted
        citations = citation_list.locator('[data-testid="citation-item"]')
        expect(citations).to_have_count(2, timeout=10000)  # Based on our test PDF

        # Verify citation details
        first_citation = citations.first
        expect(first_citation).to_contain_text("Smith et al.")
        expect(first_citation).to_contain_text("2024")

        # Test citation search
        search_input = page.locator('[data-testid="citation-search"]')
        search_input.fill("Johnson")

        # Verify filtered results
        filtered_citations = citation_list.locator('[data-testid="citation-item"]:visible')
        expect(filtered_citations).to_have_count(1)
        expect(filtered_citations.first).to_contain_text("Johnson")

    @pytest.mark.e2e
    @pytest.mark.workflow
    @pytest.mark.error_handling
    def test_document_processing_with_errors(
        self,
        page: Page,
        page_helper,
        api_client,
        invalid_files,
        web_server
    ):
        """
        Test document workflow with various error conditions.
        """
        page.goto(web_server)

        # Test 1: Upload non-PDF file
        upload_button = page.locator('[data-testid="upload-button"]')
        upload_button.click()

        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(invalid_files["not_pdf"]))

        # Verify error message
        error_message = page.locator('[data-testid="upload-error"]')
        expect(error_message).to_be_visible()
        expect(error_message).to_contain_text("Only PDF files are allowed")

        # Test 2: Upload corrupted PDF
        file_input.set_input_files(str(invalid_files["corrupted"]))

        submit_button = page.locator('[data-testid="upload-submit"]')
        submit_button.click()

        # Wait for processing error
        page_helper.wait_for_text("Processing failed", timeout=15000)

        error_details = page.locator('[data-testid="processing-error"]')
        expect(error_details).to_be_visible()
        expect(error_details).to_contain_text("corrupted")

        # Test 3: Retry mechanism
        retry_button = page.locator('[data-testid="retry-processing"]')
        expect(retry_button).to_be_visible()

        # Mock successful retry
        api_client.mock_api_response(
            "**/api/documents/*/retry",
            {"success": True, "message": "Processing restarted"},
            status=200
        )

        retry_button.click()

        # Verify retry initiated
        page_helper.wait_for_text("Processing restarted")

    @pytest.mark.e2e
    @pytest.mark.workflow
    @pytest.mark.performance
    def test_large_document_workflow_performance(
        self,
        page: Page,
        page_helper,
        api_client,
        test_pdf_files,
        web_server,
        performance_test_data
    ):
        """
        Test workflow performance with large documents.
        """
        # Start performance monitoring
        page.goto(web_server)

        # Measure initial page load
        initial_metrics = page_helper.measure_performance()
        assert initial_metrics['domContentLoaded'] < 2000  # 2 seconds

        # Upload large document
        upload_button = page.locator('[data-testid="upload-button"]')
        upload_button.click()

        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(test_pdf_files["large"]))

        # Measure upload time
        start_time = time.time()
        submit_button = page.locator('[data-testid="upload-submit"]')
        submit_button.click()

        # Wait for upload completion
        with page.expect_response("**/api/documents/upload") as response_info:
            upload_response = response_info.value

        upload_time = time.time() - start_time
        assert upload_time < performance_test_data['response_time_thresholds']['file_upload'] / 1000

        # Monitor processing progress
        progress_bar = page.locator('[data-testid="processing-progress"]')

        # Check progress updates
        progress_updates = []
        for _ in range(10):
            progress_value = progress_bar.get_attribute("aria-valuenow")
            progress_updates.append(int(progress_value))

            if progress_value == "100":
                break

            time.sleep(2)

        # Verify progress was incremental
        assert progress_updates == sorted(progress_updates)

        # Measure total processing time
        processing_start = time.time()
        page_helper.wait_for_text("Processing complete", timeout=120000)
        processing_time = time.time() - processing_start

        # Log performance metrics
        print(f"Large document processing metrics:")
        print(f"  - Upload time: {upload_time:.2f}s")
        print(f"  - Processing time: {processing_time:.2f}s")
        print(f"  - File size: 50 pages")

    @pytest.mark.e2e
    @pytest.mark.workflow
    @pytest.mark.cross_browser
    @pytest.mark.parametrize('browser_config', ['desktop_chrome', 'desktop_firefox', 'mobile_iphone'])
    def test_document_workflow_cross_browser(
        self,
        browser_context,
        test_pdf_files,
        web_server
    ):
        """
        Test document workflow across different browsers and devices.
        """
        page = browser_context.new_page()
        page.goto(web_server)

        # Adjust selectors based on viewport
        is_mobile = browser_context.viewport['width'] < 768

        if is_mobile:
            # Open mobile menu
            menu_button = page.locator('[data-testid="mobile-menu"]')
            menu_button.click()

        # Navigate to upload
        upload_link = page.locator('[data-testid="nav-upload"]')
        upload_link.click()

        # Verify upload page loads correctly
        upload_container = page.locator('[data-testid="upload-container"]')
        expect(upload_container).to_be_visible()

        # Test file selection
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(test_pdf_files["standard"]))

        # Verify file preview
        file_preview = page.locator('[data-testid="file-preview"]')
        expect(file_preview).to_be_visible()

        # Submit upload
        submit_button = page.locator('[data-testid="upload-submit"]')
        submit_button.click()

        # Verify upload success message
        success_message = page.locator('[data-testid="upload-success"]')
        expect(success_message).to_be_visible(timeout=10000)

        page.close()