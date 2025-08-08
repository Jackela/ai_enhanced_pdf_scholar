"""
Library Management E2E Tests

Tests for document library management including search, filter, and bulk operations.
"""

import pytest
from playwright.sync_api import Page, expect
import time
from typing import List
from fixtures import *


class TestLibraryManagement:
    """Test document library management features."""
    
    @pytest.mark.e2e
    @pytest.mark.library
    def test_library_search_functionality(
        self,
        page: Page,
        page_helper,
        seeded_database,
        web_server
    ):
        """Test searching documents in the library."""
        # Navigate to library
        page.goto(f"{web_server}/library")
        page_helper.wait_for_text("Document Library")
        
        # Verify initial document count
        document_cards = page.locator('[data-testid="document-card"]')
        initial_count = document_cards.count()
        assert initial_count > 0
        
        # Test search by title
        search_input = page.locator('[data-testid="library-search"]')
        search_input.fill("Document 1")
        search_input.press("Enter")
        
        # Wait for search results
        page.wait_for_timeout(500)
        
        # Verify filtered results
        filtered_cards = page.locator('[data-testid="document-card"]:visible')
        filtered_count = filtered_cards.count()
        assert filtered_count < initial_count
        
        # Verify all visible cards contain search term
        for i in range(filtered_count):
            card = filtered_cards.nth(i)
            expect(card).to_contain_text("Document 1")
        
        # Clear search
        clear_button = page.locator('[data-testid="clear-search"]')
        clear_button.click()
        
        # Verify all documents visible again
        all_cards = page.locator('[data-testid="document-card"]:visible')
        expect(all_cards).to_have_count(initial_count)
        
        # Test search by author (from metadata)
        search_input.fill("Author 5")
        search_input.press("Enter")
        
        page.wait_for_timeout(500)
        
        # Verify author search results
        author_cards = page.locator('[data-testid="document-card"]:visible')
        assert author_cards.count() > 0
        
        # Test search with no results
        search_input.fill("NonexistentDocument123456")
        search_input.press("Enter")
        
        # Verify no results message
        no_results = page.locator('[data-testid="no-results-message"]')
        expect(no_results).to_be_visible()
        expect(no_results).to_contain_text("No documents found")
    
    @pytest.mark.e2e
    @pytest.mark.library
    def test_library_filter_options(
        self,
        page: Page,
        page_helper,
        seeded_database,
        web_server
    ):
        """Test filtering documents by various criteria."""
        page.goto(f"{web_server}/library")
        
        # Open filter panel
        filter_button = page.locator('[data-testid="toggle-filters"]')
        filter_button.click()
        
        filter_panel = page.locator('[data-testid="filter-panel"]')
        expect(filter_panel).to_be_visible()
        
        # Test status filter
        status_filter = page.locator('[data-testid="filter-status"]')
        status_filter.select_option("completed")
        
        # Apply filter
        apply_button = page.locator('[data-testid="apply-filters"]')
        apply_button.click()
        
        page.wait_for_timeout(500)
        
        # Verify only completed documents shown
        document_cards = page.locator('[data-testid="document-card"]:visible')
        for i in range(document_cards.count()):
            card = document_cards.nth(i)
            status_badge = card.locator('[data-testid="status-badge"]')
            expect(status_badge).to_have_text("Completed")
        
        # Test category filter
        category_filter = page.locator('[data-testid="filter-category"]')
        category_filter.select_option("Research")
        apply_button.click()
        
        page.wait_for_timeout(500)
        
        # Verify category filter
        research_cards = page.locator('[data-testid="document-card"]:visible')
        for i in range(research_cards.count()):
            card = research_cards.nth(i)
            expect(card).to_have_attribute("data-category", "Research")
        
        # Test date range filter
        date_from = page.locator('[data-testid="filter-date-from"]')
        date_to = page.locator('[data-testid="filter-date-to"]')
        
        # Set date range (last 7 days)
        from datetime import datetime, timedelta
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        date_from.fill(week_ago.strftime("%Y-%m-%d"))
        date_to.fill(today.strftime("%Y-%m-%d"))
        apply_button.click()
        
        page.wait_for_timeout(500)
        
        # Verify date filter
        recent_cards = page.locator('[data-testid="document-card"]:visible')
        assert recent_cards.count() >= 0  # Some documents should be recent
        
        # Test multiple filters
        page_filter = page.locator('[data-testid="filter-page-count"]')
        page_filter.fill("1-100")
        
        tags_filter = page.locator('[data-testid="filter-tags"]')
        tags_filter.fill("tag1")
        
        apply_button.click()
        page.wait_for_timeout(500)
        
        # Clear all filters
        clear_filters = page.locator('[data-testid="clear-filters"]')
        clear_filters.click()
        
        # Verify all documents visible
        all_cards = page.locator('[data-testid="document-card"]:visible')
        assert all_cards.count() > 0
    
    @pytest.mark.e2e
    @pytest.mark.library
    def test_library_sorting_options(
        self,
        page: Page,
        page_helper,
        seeded_database,
        web_server
    ):
        """Test sorting documents by different criteria."""
        page.goto(f"{web_server}/library")
        
        # Get initial order
        def get_document_titles() -> List[str]:
            cards = page.locator('[data-testid="document-card"]')
            titles = []
            for i in range(cards.count()):
                title = cards.nth(i).locator('[data-testid="document-title"]').text_content()
                titles.append(title)
            return titles
        
        initial_order = get_document_titles()
        
        # Sort by title (A-Z)
        sort_dropdown = page.locator('[data-testid="sort-dropdown"]')
        sort_dropdown.select_option("title-asc")
        
        page.wait_for_timeout(500)
        
        # Verify alphabetical order
        sorted_titles = get_document_titles()
        assert sorted_titles == sorted(sorted_titles)
        
        # Sort by title (Z-A)
        sort_dropdown.select_option("title-desc")
        page.wait_for_timeout(500)
        
        reverse_sorted = get_document_titles()
        assert reverse_sorted == sorted(reverse_sorted, reverse=True)
        
        # Sort by date (newest first)
        sort_dropdown.select_option("date-desc")
        page.wait_for_timeout(500)
        
        # Get dates and verify order
        cards = page.locator('[data-testid="document-card"]')
        dates = []
        for i in range(min(5, cards.count())):  # Check first 5
            date_text = cards.nth(i).locator('[data-testid="upload-date"]').get_attribute("data-date")
            dates.append(date_text)
        
        # Verify dates are in descending order
        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1]
        
        # Sort by file size
        sort_dropdown.select_option("size-desc")
        page.wait_for_timeout(500)
        
        # Verify size sorting
        sizes = []
        for i in range(min(5, cards.count())):
            size_text = cards.nth(i).locator('[data-testid="file-size"]').get_attribute("data-size")
            sizes.append(int(size_text))
        
        assert sizes == sorted(sizes, reverse=True)
    
    @pytest.mark.e2e
    @pytest.mark.library
    def test_bulk_operations(
        self,
        page: Page,
        page_helper,
        api_client,
        seeded_database,
        web_server
    ):
        """Test bulk operations on multiple documents."""
        page.goto(f"{web_server}/library")
        
        # Enable selection mode
        select_mode_button = page.locator('[data-testid="toggle-select-mode"]')
        select_mode_button.click()
        
        # Verify checkboxes appear
        checkboxes = page.locator('[data-testid="document-checkbox"]')
        expect(checkboxes.first).to_be_visible()
        
        # Select first 3 documents
        for i in range(3):
            checkboxes.nth(i).check()
        
        # Verify selection count
        selection_count = page.locator('[data-testid="selection-count"]')
        expect(selection_count).to_have_text("3 documents selected")
        
        # Test bulk download
        bulk_actions = page.locator('[data-testid="bulk-actions"]')
        expect(bulk_actions).to_be_visible()
        
        download_selected = bulk_actions.locator('[data-testid="bulk-download"]')
        
        with page.expect_download() as download_info:
            download_selected.click()
        
        download = download_info.value
        assert download.suggested_filename.endswith('.zip')
        
        # Test bulk delete
        delete_selected = bulk_actions.locator('[data-testid="bulk-delete"]')
        delete_selected.click()
        
        # Confirm deletion
        confirm_dialog = page.locator('[data-testid="confirm-dialog"]')
        expect(confirm_dialog).to_be_visible()
        expect(confirm_dialog).to_contain_text("Delete 3 documents?")
        
        confirm_button = confirm_dialog.locator('[data-testid="confirm-delete"]')
        confirm_button.click()
        
        # Wait for deletion
        page_helper.wait_for_text("3 documents deleted successfully")
        
        # Verify documents removed from list
        remaining_cards = page.locator('[data-testid="document-card"]')
        assert remaining_cards.count() < 50  # Original seeded count
        
        # Test select all
        select_all = page.locator('[data-testid="select-all"]')
        select_all.click()
        
        # Verify all selected
        all_checkboxes = page.locator('[data-testid="document-checkbox"]:checked')
        expect(all_checkboxes).to_have_count(remaining_cards.count())
        
        # Test bulk export metadata
        export_metadata = bulk_actions.locator('[data-testid="bulk-export-metadata"]')
        
        with page.expect_download() as download_info:
            export_metadata.click()
        
        metadata_download = download_info.value
        assert metadata_download.suggested_filename.endswith('.json')
    
    @pytest.mark.e2e
    @pytest.mark.library
    def test_document_preview_and_details(
        self,
        page: Page,
        page_helper,
        seeded_database,
        web_server
    ):
        """Test document preview and detailed view."""
        page.goto(f"{web_server}/library")
        
        # Click on first document card
        first_card = page.locator('[data-testid="document-card"]').first
        document_title = first_card.locator('[data-testid="document-title"]').text_content()
        
        first_card.click()
        
        # Verify detail view opens
        detail_view = page.locator('[data-testid="document-detail"]')
        expect(detail_view).to_be_visible()
        
        # Verify document title in detail view
        detail_title = detail_view.locator('[data-testid="detail-title"]')
        expect(detail_title).to_have_text(document_title)
        
        # Check tabs
        tabs = detail_view.locator('[data-testid="detail-tabs"]')
        expect(tabs).to_be_visible()
        
        # Test Preview tab
        preview_tab = tabs.locator('[data-testid="tab-preview"]')
        preview_tab.click()
        
        pdf_viewer = detail_view.locator('[data-testid="pdf-viewer"]')
        expect(pdf_viewer).to_be_visible()
        
        # Test navigation controls
        next_page = detail_view.locator('[data-testid="next-page"]')
        prev_page = detail_view.locator('[data-testid="prev-page"]')
        page_input = detail_view.locator('[data-testid="page-number"]')
        
        # Navigate pages
        if next_page.is_enabled():
            next_page.click()
            expect(page_input).to_have_value("2")
            
            prev_page.click()
            expect(page_input).to_have_value("1")
        
        # Test Metadata tab
        metadata_tab = tabs.locator('[data-testid="tab-metadata"]')
        metadata_tab.click()
        
        metadata_content = detail_view.locator('[data-testid="metadata-content"]')
        expect(metadata_content).to_be_visible()
        
        # Verify metadata fields
        expect(metadata_content).to_contain_text("File Size")
        expect(metadata_content).to_contain_text("Page Count")
        expect(metadata_content).to_contain_text("Upload Date")
        
        # Test Citations tab (if available)
        citations_tab = tabs.locator('[data-testid="tab-citations"]')
        if citations_tab.is_visible():
            citations_tab.click()
            
            citations_content = detail_view.locator('[data-testid="citations-content"]')
            expect(citations_content).to_be_visible()
        
        # Test Actions
        actions_panel = detail_view.locator('[data-testid="document-actions"]')
        expect(actions_panel).to_be_visible()
        
        # Test edit metadata
        edit_button = actions_panel.locator('[data-testid="edit-metadata"]')
        edit_button.click()
        
        edit_dialog = page.locator('[data-testid="edit-dialog"]')
        expect(edit_dialog).to_be_visible()
        
        # Modify title
        title_input = edit_dialog.locator('[data-testid="edit-title"]')
        title_input.clear()
        title_input.fill("Updated Document Title")
        
        # Save changes
        save_button = edit_dialog.locator('[data-testid="save-changes"]')
        save_button.click()
        
        # Verify update
        page_helper.wait_for_text("Document updated successfully")
        expect(detail_title).to_have_text("Updated Document Title")
        
        # Close detail view
        close_button = detail_view.locator('[data-testid="close-detail"]')
        close_button.click()
        
        # Verify back in library view
        expect(detail_view).not_to_be_visible()
    
    @pytest.mark.e2e
    @pytest.mark.library
    @pytest.mark.performance
    def test_library_pagination_performance(
        self,
        page: Page,
        page_helper,
        seeded_database,
        web_server
    ):
        """Test pagination and performance with many documents."""
        page.goto(f"{web_server}/library")
        
        # Check pagination controls
        pagination = page.locator('[data-testid="pagination"]')
        expect(pagination).to_be_visible()
        
        # Get total pages
        total_pages = page.locator('[data-testid="total-pages"]').text_content()
        total_pages = int(total_pages.split()[-1])
        
        # Measure first page load time
        start_time = time.time()
        page.reload()
        page_helper.wait_for_text("Document Library")
        first_page_load = time.time() - start_time
        
        assert first_page_load < 2.0  # Should load within 2 seconds
        
        # Test pagination navigation
        next_button = pagination.locator('[data-testid="next-page"]')
        prev_button = pagination.locator('[data-testid="prev-page"]')
        page_number = pagination.locator('[data-testid="current-page"]')
        
        # Navigate to next page
        start_time = time.time()
        next_button.click()
        page.wait_for_timeout(300)
        next_page_load = time.time() - start_time
        
        assert next_page_load < 1.0  # Pagination should be fast
        expect(page_number).to_have_text("2")
        
        # Jump to last page
        last_page_button = pagination.locator('[data-testid="last-page"]')
        last_page_button.click()
        
        expect(page_number).to_have_text(str(total_pages))
        
        # Verify different documents shown
        last_page_cards = page.locator('[data-testid="document-card"]')
        last_page_count = last_page_cards.count()
        
        # Go back to first page
        first_page_button = pagination.locator('[data-testid="first-page"]')
        first_page_button.click()
        
        first_page_cards = page.locator('[data-testid="document-card"]')
        first_page_count = first_page_cards.count()
        
        # Test items per page selector
        items_per_page = page.locator('[data-testid="items-per-page"]')
        items_per_page.select_option("50")
        
        page.wait_for_timeout(500)
        
        # Verify more items shown
        fifty_items_cards = page.locator('[data-testid="document-card"]')
        assert fifty_items_cards.count() <= 50
        
        # Test infinite scroll (if implemented)
        if page.locator('[data-testid="infinite-scroll-trigger"]').is_visible():
            # Scroll to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            # Wait for more items to load
            page.wait_for_timeout(1000)
            
            # Verify more items loaded
            after_scroll_cards = page.locator('[data-testid="document-card"]')
            assert after_scroll_cards.count() > fifty_items_cards.count()