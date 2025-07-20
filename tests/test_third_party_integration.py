"""
Third-Party Library Integration Tests
Tests integration with optional citation parsing libraries for enhanced accuracy.
"""

import pytest
from unittest.mock import Mock, patch
from src.services.citation_parsing_service import CitationParsingService


class TestThirdPartyIntegration:
    """Test integration with third-party citation parsing libraries."""

    def test_citation_parsing_without_third_party_libraries(self):
        """Test that parsing works even without third-party libraries installed."""
        service = CitationParsingService()
        
        sample_text = """
        Smith, J. (2023). Machine Learning Fundamentals. Journal of AI, 15(3), 123-145.
        Brown, A. et al. (2022). Deep Learning Applications. Conference Proceedings, 45-52.
        """
        
        # Parse with third-party disabled
        citations = service.parse_citations_from_text(sample_text, use_third_party=False)
        
        # Should still work with regex parser
        assert isinstance(citations, list)
        assert len(citations) >= 1
        
        # Check that basic fields are extracted
        first_citation = citations[0] if citations else {}
        assert "raw_text" in first_citation
        assert "confidence_score" in first_citation

    def test_refextract_integration(self):
        """Test integration with refextract library (simulated)."""
        # This test simulates refextract behavior without requiring the actual library
        service = CitationParsingService()
        
        # Test the helper methods that would process refextract output
        mock_ref_data = {
            'raw_ref': 'Smith, J. (2023). Test Paper. Journal of Testing, 1(1), 1-10.',
            'author': [{'full_name': 'Smith, J.'}],
            'title': {'title': 'Test Paper'},
            'year': {'year': '2023'},
            'journal': {'title': 'Journal of Testing'},
            'doi': {'value': '10.1000/test.2023.001'}
        }
        
        # Test helper methods
        authors = service._extract_refextract_authors(mock_ref_data)
        assert authors == 'Smith, J.'
        
        year = service._extract_refextract_year(mock_ref_data)
        assert year == 2023
        
        journal = service._extract_refextract_journal(mock_ref_data)
        assert journal == 'Journal of Testing'
        
        citation_type = service._classify_refextract_type(mock_ref_data)
        assert citation_type == 'journal'

    def test_citation_deduplication(self):
        """Test that duplicate citations are properly merged."""
        service = CitationParsingService()
        
        # Create similar citations from different sources
        primary_citations = [
            {
                "raw_text": "Smith, J. (2023). Test Paper. Journal.",
                "authors": "Smith, J.",
                "confidence_score": 0.85
            }
        ]
        
        fallback_citations = [
            {
                "raw_text": "Smith, J. (2023). Test Paper. Journal.",  # Exact duplicate
                "authors": "Smith, John",
                "confidence_score": 0.6
            },
            {
                "raw_text": "Brown, A. (2022). Different Paper. Other Journal.",  # Different citation
                "authors": "Brown, A.",
                "confidence_score": 0.7
            }
        ]
        
        merged = service._merge_and_deduplicate_citations(primary_citations, fallback_citations)
        
        # Should have 2 citations (duplicate removed, different one kept)
        assert len(merged) == 2
        
        # Primary citation should be kept (higher confidence)
        assert any(c.get('confidence_score') == 0.85 for c in merged)
        
        # Different citation should be added
        assert any(c.get('authors') == 'Brown, A.' for c in merged)

    def test_text_similarity_calculation(self):
        """Test text similarity calculation for deduplication."""
        service = CitationParsingService()
        
        # Identical texts
        similarity = service._calculate_text_similarity("test text", "test text")
        assert similarity == 1.0
        
        # Completely different texts
        similarity = service._calculate_text_similarity("abc", "xyz")
        assert similarity == 0.0
        
        # Partially similar texts
        similarity = service._calculate_text_similarity("abcdef", "abcxyz")
        assert 0.0 < similarity < 1.0
        
        # Empty strings
        similarity = service._calculate_text_similarity("", "test")
        assert similarity == 0.0

    def test_refextract_helper_methods(self):
        """Test helper methods for extracting data from refextract results."""
        service = CitationParsingService()
        
        # Test author extraction
        ref_data = {'author': [{'full_name': 'Smith, J.'}, {'full_name': 'Brown, A.'}]}
        authors = service._extract_refextract_authors(ref_data)
        assert authors == 'Smith, J., Brown, A.'
        
        # Test year extraction
        ref_data = {'year': {'year': '2023'}}
        year = service._extract_refextract_year(ref_data)
        assert year == 2023
        
        # Test journal extraction
        ref_data = {'journal': {'title': 'Journal of Testing'}}
        journal = service._extract_refextract_journal(ref_data)
        assert journal == 'Journal of Testing'
        
        # Test type classification
        ref_data = {'journal': {'title': 'Test Journal'}}
        citation_type = service._classify_refextract_type(ref_data)
        assert citation_type == 'journal'

    def test_graceful_fallback_on_third_party_errors(self):
        """Test that system gracefully falls back when third-party libraries fail."""
        service = CitationParsingService()
        sample_text = "Smith, J. (2023). Test Paper. Journal of Testing."
        
        # Even without third-party libraries, should not raise exception
        try:
            citations = service.parse_citations_from_text(sample_text, use_third_party=True)
            # Should still return results from regex parser
            assert isinstance(citations, list)
        except Exception as e:
            pytest.fail(f"System should handle missing third-party libraries gracefully, but raised: {e}")

    def test_performance_comparison(self):
        """Test that third-party integration doesn't significantly slow down parsing."""
        import time
        
        service = CitationParsingService()
        sample_text = """
        Smith, J. (2023). Machine Learning Fundamentals. Journal of AI, 15(3), 123-145.
        Brown, A. et al. (2022). Deep Learning Applications. Conference Proceedings, 45-52.
        Johnson, K. (2021). Neural Networks Today. Tech Review, 8(2), 67-89.
        """ * 10  # Repeat to make it larger
        
        # Test without third-party
        start_time = time.time()
        citations_regex = service.parse_citations_from_text(sample_text, use_third_party=False)
        regex_time = time.time() - start_time
        
        # Test with third-party (will fall back to regex if not available)
        start_time = time.time()
        citations_enhanced = service.parse_citations_from_text(sample_text, use_third_party=True)
        enhanced_time = time.time() - start_time
        
        # Enhanced version should not be more than 3x slower
        assert enhanced_time < regex_time * 3
        
        # Should extract at least as many citations
        assert len(citations_enhanced) >= len(citations_regex)

    def test_enhanced_parsing_accuracy_simulation(self):
        """Simulate how third-party libraries improve parsing accuracy."""
        service = CitationParsingService()
        
        # Use a simpler citation that our regex can handle reliably
        simple_citation = "Smith, J. (2023). Test Paper. Journal of Testing, 1(1), 1-10."
        
        # Test with regex only
        regex_citations = service._parse_with_regex(simple_citation)
        
        # Test the enhanced interface (will fall back to regex if third-party not available)
        enhanced_citations = service.parse_citations_from_text(simple_citation, use_third_party=True)
        
        # Enhanced should extract at least as many citations
        assert len(enhanced_citations) >= len(regex_citations)
        
        # If any citations were found, they should have reasonable confidence scores
        for citation in enhanced_citations:
            assert 0.1 <= citation['confidence_score'] <= 1.0