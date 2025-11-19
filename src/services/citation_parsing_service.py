"""
Citation Parsing Service Implementation
Implements text parsing algorithms for citation extraction following SOLID principles.
Enhanced with third-party library integration for improved accuracy.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Third-party library imports (optional dependencies)
try:
    import refextract

    REFEXTRACT_AVAILABLE = True
except ImportError:
    REFEXTRACT_AVAILABLE = False

REFEXTRACT_AVAILABLE: bool = REFEXTRACT_AVAILABLE

# requests not currently used but kept for potential future use
REQUESTS_AVAILABLE: bool = False

logger = logging.getLogger(__name__)


class CitationParsingService:
    """
    {
        "name": "CitationParsingService",
        "version": "1.0.0",
        "description": "Text parsing service for citation extraction following SOLID principles.",
        "dependencies": [],
        "interface": {
            "inputs": ["text content"],
            "outputs": "Parsed citation data"
        }
    }
    Citation parsing service providing text analysis for citation extraction.
    Follows Single Responsibility Principle - handles only text parsing logic.
    No external dependencies - pure parsing algorithms.
    """

    def __init__(self) -> None:
        """Initialize citation parsing service."""
        # Common citation patterns
        self.author_patterns: list[str] = [
            r"([A-Z][a-z]+(?:,\s*[A-Z]\.?)+)",  # Smith, J.
            r"([A-Z][a-z]+(?:\s+[A-Z]\.?)+)",  # Smith J.
            r"([A-Z][a-z]+(?:\s*et\s+al\.?))",  # Smith et al.
        ]

        self.year_patterns: list[str] = [
            r"\((\d{4}[a-z]?)\)",  # (2023) or (2023a)
            r"(\d{4}[a-z]?)\.",  # 2023. or 2023a.
        ]

        self.doi_patterns: list[str] = [
            r"https?://doi\.org/([^\s]+)",
            r"DOI:\s*([^\s]+)",
            r"doi:\s*([^\s]+)",
        ]

    def parse_citations_from_text(
        self, text_content: str, use_third_party: bool = True
    ) -> list[dict[str, Any]]:
        """
        Parse citations from text content using multiple approaches.

        Args:
            text_content: Text to parse citations from
            use_third_party: Whether to use third-party libraries for enhanced accuracy

        Returns:
            List of parsed citation dictionaries
        """
        try:
            logger.debug("Starting citation parsing from text")
            citations = []

            # Try third-party libraries first for better accuracy
            if use_third_party and REFEXTRACT_AVAILABLE:
                citations.extend(self._parse_with_refextract(text_content))

            # Try AnyStyle API if available and configured
            if use_third_party and REQUESTS_AVAILABLE:
                anystyle_citations = self._parse_with_anystyle_api(text_content)
                citations.extend(anystyle_citations)

            # Always run our regex-based parser for additional coverage
            fallback_citations = self._parse_with_regex(text_content)

            # Merge results, avoiding duplicates
            citations = self._merge_and_deduplicate_citations(
                citations, fallback_citations
            )

            logger.debug(
                f"Parsed {len(citations)} citations from text (third-party: {use_third_party})"
            )
            return citations

        except Exception as e:
            logger.error(f"Failed to parse citations from text: {e}")
            raise

    def _parse_with_refextract(self, text_content: str) -> list[dict[str, Any]]:
        """Parse citations using CERN's refextract library."""
        try:
            if not REFEXTRACT_AVAILABLE:
                return []

            logger.debug("Using refextract for citation parsing")

            # refextract expects structured text, so we process it appropriately
            result = refextract.extract_references_from_string(text_content)

            citations = []
            for ref_data in result.get("references", []):
                citation = {
                    "raw_text": ref_data.get("raw_ref", ""),
                    "authors": self._extract_refextract_authors(ref_data),
                    "title": (
                        ref_data.get("title", {}).get("title")
                        if ref_data.get("title")
                        else None
                    ),
                    "publication_year": self._extract_refextract_year(ref_data),
                    "journal_or_venue": self._extract_refextract_journal(ref_data),
                    "doi": (
                        ref_data.get("doi", {}).get("value")
                        if ref_data.get("doi")
                        else None
                    ),
                    "citation_type": self._classify_refextract_type(ref_data),
                    "confidence_score": 0.85,  # refextract typically has high confidence
                }

                if citation["raw_text"] and len(citation["raw_text"]) > 10:
                    citations.append(citation)

            logger.debug(f"refextract extracted {len(citations)} citations")
            return citations

        except Exception as e:
            logger.warning(f"refextract parsing failed: {e}")
            return []

    def _parse_with_anystyle_api(self, text_content: str) -> list[dict[str, Any]]:
        """Parse citations using AnyStyle.io API (if available)."""
        try:
            if not REQUESTS_AVAILABLE:
                return []

            # This would require AnyStyle API configuration
            # For now, return empty list[Any] as it needs API setup
            logger.debug("AnyStyle API not configured, skipping")
            return []

        except Exception as e:
            logger.warning(f"AnyStyle API parsing failed: {e}")
            return []

    def _parse_with_regex(self, text_content: str) -> list[dict[str, Any]]:
        """Parse citations using our enhanced regex patterns."""
        try:
            citations = []

            # Enhanced citation pattern matching for academic references
            # Focus on patterns that reliably indicate citation starts
            citation_patterns = [
                # Multi-author with complex punctuation: "Author, A., Author, B., ... & Author, Z. (Year)"
                r"(?:^|\s)([A-Z][a-zA-Z]+(?:,\s*[A-Z]\.?)+(?:,\s*[A-Z][a-zA-Z]+(?:,\s*[A-Z]\.?)*)*.*?(?:&|and)\s*[A-Z][a-zA-Z]+.*?\(\d{4}[a-z]?\).*?\.)",
                # Standard academic citation: "Author, F. (Year). Title. Journal."
                r"(?:^|\s)([A-Z][a-zA-Z]+,\s*[A-Z]\.?.*?\(\d{4}[a-z]?\).*?\.)",
                # Multiple authors with et al: "Author, F. et al. (Year). Title."
                r"(?:^|\s)([A-Z][a-zA-Z]+(?:,\s*[A-Z]\.?)?\s*et\s+al\.?.*?\(\d{4}[a-z]?\).*?\.)",
                # Full name format: "LastName, FirstName (Year)"
                r"(?:^|\s)([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+.*?\(\d{4}[a-z]?\).*?\.)",
                # Abbreviated format: "LastName F. (Year)"
                r"(?:^|\s)([A-Z][a-zA-Z]+\s+[A-Z]\.?.*?\(\d{4}[a-z]?\).*?\.)",
            ]

            # Pre-filter text to remove obvious non-citation sentences
            filtered_text = self._prefilter_citation_text(text_content)

            for pattern in citation_patterns:
                matches = re.finditer(pattern, filtered_text, re.MULTILINE | re.DOTALL)
                for match in matches:
                    citation_text = match.group(1).strip()

                    # Enhanced filtering for valid citations
                    if self._is_valid_citation_candidate(citation_text):
                        citation_data = self._parse_single_citation(citation_text)
                        if citation_data and self._validate_citation_quality(
                            citation_data
                        ):
                            citations.append(citation_data)

            # Remove duplicates and low-quality citations
            citations = self._deduplicate_and_filter_citations(citations)

            return citations

        except Exception as e:
            logger.warning(f"Regex parsing failed: {e}")
            return []

    def _parse_single_citation(self, citation_text: str) -> dict[str, Any] | None:
        """Parse a single citation text into structured data."""
        try:
            citation_data = {
                "raw_text": citation_text,
                "authors": self.extract_authors(citation_text),
                "title": self.extract_title(citation_text),
                "publication_year": self.extract_year(citation_text),
                "journal_or_venue": self.extract_venue(citation_text),
                "doi": self.extract_doi(citation_text),
                "citation_type": self.classify_citation_type(citation_text),
                "confidence_score": 0.0,  # Will be calculated
            }

            # Calculate confidence score
            citation_data["confidence_score"] = self.calculate_confidence_score(
                citation_data
            )

            return citation_data

        except Exception as e:
            logger.warning(f"Failed to parse citation '{citation_text[:50]}...': {e}")
            return None

    def extract_authors(self, citation_text: str) -> str | None:
        """
        Extract authors from citation text with enhanced accuracy.

        Args:
            citation_text: Citation text to extract authors from

        Returns:
            Extracted first author or None
        """
        try:
            # Clean the input text
            text = citation_text.strip()

            # Strategy 1: Handle complex multi-author citations first
            # Pattern: "FirstAuthor, A., SecondAuthor, B., ... & LastAuthor, Z. (Year)"
            complex_multiauthor = re.search(
                r"^(?:.*?\b)?([A-Z][a-zA-Z]+(?:,\s*[A-Z]\.?)+)(?:,\s*[A-Z][a-zA-Z]+(?:,\s*[A-Z]\.?)*)*.*?(?:&|and)\s*[A-Z][a-zA-Z]+.*?\(\d{4}[a-z]?\)",
                text,
            )
            if complex_multiauthor:
                first_author = complex_multiauthor.group(1).strip()
                return self._normalize_author_name(first_author)

            # Strategy 2: Look for standard "Author, F." patterns at the start
            standard_patterns = [
                # "LastName, F." at start
                r"^(?:.*?\b)?([A-Z][a-zA-Z]+,\s*[A-Z]\.?)(?=\s*(?:,|\.|&|et\s+al|\())",
                # "LastName, FirstName" at start
                r"^(?:.*?\b)?([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+)(?=\s*(?:,|\.|&|et\s+al|\())",
                # "LastName F." format
                r"^(?:.*?\b)?([A-Z][a-zA-Z]+\s+[A-Z]\.?)(?=\s*(?:,|\.|&|et\s+al|\())",
            ]

            for pattern in standard_patterns:
                match = re.search(pattern, text)
                if match:
                    author = match.group(1).strip()
                    return self._normalize_author_name(author)

            # Strategy 3: Look for author before year marker
            year_match = re.search(r"\(\d{4}[a-z]?\)", text)
            if year_match:
                before_year = text[: year_match.start()].strip()

                # Extract the last complete author name before the year
                author_before_year_patterns = [
                    # "LastName, F." format
                    r"([A-Z][a-zA-Z]+,\s*[A-Z]\.?)(?=\s*$|\s*\.$)",
                    # "LastName, FirstName" format
                    r"([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+)(?=\s*$|\s*\.$)",
                    # "LastName F." format
                    r"([A-Z][a-zA-Z]+\s+[A-Z]\.?)(?=\s*$|\s*\.$)",
                    # Just "LastName"
                    r"([A-Z][a-zA-Z]+)(?=\s*$|\s*\.$)",
                ]

                for pattern in author_before_year_patterns:
                    matches = re.findall(pattern, before_year)
                    if matches:
                        # Take the first occurrence (leftmost = first author)
                        author = matches[0].strip()
                        return self._normalize_author_name(author)

            # Strategy 4: Extract from the very beginning, assuming citation starts with author
            beginning_patterns = [
                r"^([A-Z][a-zA-Z]+,\s*[A-Z]\.?)",  # "LastName, F."
                r"^([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+)",  # "LastName, FirstName"
                r"^([A-Z][a-zA-Z]+\s+[A-Z]\.?)",  # "LastName F."
                r"^([A-Z][a-zA-Z]+)",  # Just "LastName"
            ]

            for pattern in beginning_patterns:
                match = re.search(pattern, text)
                if match:
                    author = match.group(1).strip()
                    if len(author) > 2:  # Avoid single letters
                        return self._normalize_author_name(author)

            return None

        except Exception as e:
            logger.warning(f"Failed to extract authors from citation: {e}")
            return None

    def extract_title(self, citation_text: str) -> str | None:
        """
        Extract title from citation text.

        Args:
            citation_text: Citation text to extract title from

        Returns:
            Extracted title or None
        """
        try:
            # Look for quoted titles
            quoted_title = re.search(r'["""]([^"""]+)["""]', citation_text)
            if quoted_title:
                return quoted_title.group(1).strip()

            # Look for text between author and year
            year_match = re.search(r"\(\d{4}[a-z]?\)", citation_text)
            if year_match:
                before_year = citation_text[: year_match.start()]
                # Try to find title after author name
                # Look for pattern: Author. Title. or Author (year) Title
                parts = before_year.split(".")
                if len(parts) >= 2:
                    potential_title = parts[1].strip()
                    if len(potential_title) > 5:
                        return potential_title

                # Alternative: look for title after author comma
                author_end = re.search(r"[A-Z][a-z]+,\s*[A-Z]\.?\s*", before_year)
                if author_end:
                    after_author = before_year[author_end.end() :].strip()
                    # Remove leading punctuation
                    after_author = re.sub(r"^[.,\s]+", "", after_author)
                    if len(after_author) > 5:
                        return after_author

            # Fallback: look for capitalized text that could be a title
            # Look for pattern after author names
            title_pattern = r"[A-Z][a-z]+(?:,\s*[A-Z]\.?\s*)*\s+(.+?)(?:\.|$)"
            title_match = re.search(title_pattern, citation_text)
            if title_match:
                potential_title = title_match.group(1).strip()
                if len(potential_title) > 5 and not re.match(
                    r"^\(\d{4}", potential_title
                ):
                    return potential_title

            return None

        except Exception as e:
            logger.warning(f"Failed to extract title from citation: {e}")
            return None

    def extract_year(self, citation_text: str) -> int | None:
        """
        Extract publication year from citation text.

        Args:
            citation_text: Citation text to extract year from

        Returns:
            Extracted year or None
        """
        try:
            for pattern in self.year_patterns:
                match = re.search(pattern, citation_text)
                if match:
                    year_str = match.group(1)
                    # Extract just the numeric part
                    year_num = re.search(r"(\d{4})", year_str)
                    if year_num:
                        year = int(year_num.group(1))
                        # Validate year range
                        if 1900 <= year <= 2030:
                            return year

            return None

        except Exception as e:
            logger.warning(f"Failed to extract year from citation: {e}")
            return None

    def extract_venue(self, citation_text: str) -> str | None:
        """
        Extract publication venue from citation text.

        Args:
            citation_text: Citation text to extract venue from

        Returns:
            Extracted venue or None
        """
        try:
            # Look for journal patterns after year
            year_match = re.search(r"\(\d{4}[a-z]?\)", citation_text)
            if year_match:
                after_year = citation_text[year_match.end() :].strip()
                # Remove leading punctuation
                after_year = re.sub(r"^[.,\s]+", "", after_year)

                # Look for journal/venue name
                venue_match = re.search(r"^([^,.]+)", after_year)
                if venue_match:
                    venue = venue_match.group(1).strip()
                    if len(venue) > 3:
                        return venue

            return None

        except Exception as e:
            logger.warning(f"Failed to extract venue from citation: {e}")
            return None

    def extract_doi(self, citation_text: str) -> str | None:
        """
        Extract DOI from citation text.

        Args:
            citation_text: Citation text to extract DOI from

        Returns:
            Extracted DOI or None
        """
        try:
            for pattern in self.doi_patterns:
                match = re.search(pattern, citation_text, re.IGNORECASE)
                if match:
                    doi = match.group(1).strip()
                    # Clean up DOI
                    doi = re.sub(r"[.,\s]+$", "", doi)  # Remove trailing punctuation
                    return doi

            return None

        except Exception as e:
            logger.warning(f"Failed to extract DOI from citation: {e}")
            return None

    def classify_citation_type(self, citation_text: str) -> str:
        """
        Classify citation type based on text patterns.

        Args:
            citation_text: Citation text to classify

        Returns:
            Citation type (journal, conference, book, thesis, etc.)
        """
        try:
            text_lower = citation_text.lower()

            # Conference patterns
            conference_indicators = [
                "proceedings",
                "conference",
                "workshop",
                "symposium",
                "icml",
                "nips",
                "iclr",
                "cvpr",
                "acl",
                "emnlp",
            ]
            if any(indicator in text_lower for indicator in conference_indicators):
                return "conference"

            # Journal patterns
            journal_indicators = [
                "journal",
                "review",
                "quarterly",
                "annual",
                "magazine",
                "nature",
                "science",
                "cell",
                "lancet",
            ]
            if any(indicator in text_lower for indicator in journal_indicators):
                return "journal"

            # Book patterns
            book_indicators = [
                "press",
                "publisher",
                "edition",
                "book",
                "handbook",
                "cambridge",
                "oxford",
                "springer",
                "wiley",
                "mit press",
            ]
            if any(indicator in text_lower for indicator in book_indicators):
                return "book"

            # Thesis patterns
            thesis_indicators = ["thesis", "dissertation", "phd", "master"]
            if any(indicator in text_lower for indicator in thesis_indicators):
                return "thesis"

            # Default to unknown
            return "unknown"

        except Exception as e:
            logger.warning(f"Failed to classify citation type: {e}")
            return "unknown"

    def calculate_confidence_score(self, citation_data: dict[str, Any]) -> float:
        """
        Calculate confidence score for parsed citation.

        Args:
            citation_data: Parsed citation data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            score = 0.0
            max_score = 0.0

            # Authors present and well-formed
            if citation_data.get("authors"):
                authors = citation_data["authors"]
                if len(authors) > 3 and "," in authors:
                    score += 0.25
                elif len(authors) > 3:
                    score += 0.15
                max_score += 0.25
            else:
                max_score += 0.25

            # Title present and substantial
            if citation_data.get("title"):
                title = citation_data["title"]
                if len(title) > 10:
                    score += 0.25
                elif len(title) > 5:
                    score += 0.15
                max_score += 0.25
            else:
                max_score += 0.25

            # Year present and reasonable
            if citation_data.get("publication_year"):
                year = citation_data["publication_year"]
                if 1950 <= year <= 2030:
                    score += 0.2
                max_score += 0.2
            else:
                max_score += 0.2

            # Venue/journal present
            if citation_data.get("journal_or_venue"):
                score += 0.15
                max_score += 0.15
            else:
                max_score += 0.15

            # DOI present (bonus)
            if citation_data.get("doi"):
                score += 0.15
                max_score += 0.15
            else:
                max_score += 0.15

            # Normalize score
            final_score = (
                score / max_score if max_score > 0 else 0.1
            )  # Minimum score for having raw text

            # Ensure score is within bounds and not zero
            return max(0.1, min(1.0, final_score))

        except Exception as e:
            logger.warning(f"Failed to calculate confidence score: {e}")
            return 0.1  # Low confidence for error cases

    # Helper methods for refextract integration
    def _extract_refextract_authors(self, ref_data: dict[str, Any]) -> str | None:
        """Extract authors from refextract data."""
        try:
            if "author" in ref_data:
                authors = ref_data["author"]
                if isinstance(authors, list[Any]) and authors:
                    # Join multiple authors
                    return ", ".join(
                        [a.get("full_name", "") for a in authors if a.get("full_name")]
                    )
                elif isinstance(authors, dict[str, Any]):
                    return authors.get("full_name")
            return None
        except Exception:
            return None

    def _extract_refextract_year(self, ref_data: dict[str, Any]) -> int | None:
        """Extract year from refextract data."""
        try:
            if "year" in ref_data:
                year_data = ref_data["year"]
                if isinstance(year_data, dict[str, Any]):
                    year_str = year_data.get("year", "")
                elif isinstance(year_data, str):
                    year_str = year_data
                else:
                    return None

                # Extract numeric year
                year_match = re.search(r"(\d{4})", str(year_str))
                if year_match:
                    return int(year_match.group(1))
            return None
        except Exception:
            return None

    def _extract_refextract_journal(self, ref_data: dict[str, Any]) -> str | None:
        """Extract journal from refextract data."""
        try:
            if "journal" in ref_data:
                journal_data = ref_data["journal"]
                if isinstance(journal_data, dict[str, Any]):
                    return journal_data.get("title")
                elif isinstance(journal_data, str):
                    return journal_data
            return None
        except Exception:
            return None

    def _classify_refextract_type(self, ref_data: dict[str, Any]) -> str:
        """Classify citation type from refextract data."""
        try:
            if "journal" in ref_data:
                return "journal"
            elif "book" in ref_data or "publisher" in ref_data:
                return "book"
            elif any(
                conf_word in str(ref_data).lower()
                for conf_word in ["proceedings", "conference", "workshop"]
            ):
                return "conference"
            else:
                return "unknown"
        except Exception:
            return "unknown"

    def _merge_and_deduplicate_citations(
        self, primary_citations: list[Any], fallback_citations: list[Any]
    ) -> list[dict[str, Any]]:
        """Merge citations from different sources and remove duplicates."""
        try:
            all_citations = list[Any](primary_citations)  # Start with primary results

            # Add fallback citations that don't duplicate primary ones
            for fallback_cite in fallback_citations:
                is_duplicate = False
                fallback_text = fallback_cite.get("raw_text", "").strip().lower()

                for existing_cite in all_citations:
                    existing_text = existing_cite.get("raw_text", "").strip().lower()

                    # Simple similarity check - if 80% of text matches, consider duplicate
                    if len(fallback_text) > 0 and len(existing_text) > 0:
                        similarity = self._calculate_text_similarity(
                            fallback_text, existing_text
                        )
                        if similarity > 0.8:
                            is_duplicate = True
                            break

                if not is_duplicate:
                    all_citations.append(fallback_cite)

            return all_citations

        except Exception as e:
            logger.warning(f"Failed to merge citations: {e}")
            return primary_citations + fallback_citations

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity between two strings."""
        try:
            if not text1 or not text2:
                return 0.0

            # Simple character-based similarity
            longer = text1 if len(text1) > len(text2) else text2
            shorter = text2 if len(text1) > len(text2) else text1

            if len(longer) == 0:
                return 1.0

            # Count matching characters
            matches = sum(
                1 for c1, c2 in zip(shorter, longer, strict=False) if c1 == c2
            )
            return matches / len(longer)

        except Exception:
            return 0.0

    def _prefilter_citation_text(self, text_content: str) -> str:
        """Pre-filter text to remove obvious non-citation content."""
        try:
            lines = text_content.split("\n")
            filtered_lines = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Skip lines that are clearly not citations
                skip_patterns = [
                    r"^\s*Abstract\s*:",
                    r"^\s*Introduction\s*:",
                    r"^\s*Conclusion\s*:",
                    r"^\s*References\s*:",
                    r"^\s*Figure\s+\d+",
                    r"^\s*Table\s+\d+",
                    r"^\s*Section\s+\d+",
                    r"^\s*Chapter\s+\d+",
                ]

                should_skip = any(
                    re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns
                )
                if not should_skip:
                    filtered_lines.append(line)

            return "\n".join(filtered_lines)

        except Exception:
            return text_content

    def _is_valid_citation_candidate(self, citation_text: str) -> bool:
        """Check if text is a valid citation candidate."""
        try:
            text = citation_text.strip()

            # Must have minimum length
            if len(text) < 20:
                return False

            # Must contain a year in parentheses
            if not re.search(r"\(\d{4}[a-z]?\)", text):
                return False

            # Must start with something that looks like an author name
            if not re.search(r"^(?:.*?\b)?[A-Z][a-zA-Z]+", text):
                return False

            # Should not start with common non-citation words
            bad_starts = [
                "this",
                "that",
                "these",
                "those",
                "the",
                "a",
                "an",
                "recent",
                "modern",
                "current",
                "new",
                "old",
                "previous",
                "foundational",
                "important",
                "significant",
                "major",
                "object",
                "subject",
                "method",
                "approach",
                "technique",
                "work",
                "study",
                "research",
                "paper",
                "article",
            ]

            first_word = text.split()[0].lower() if text.split() else ""
            if first_word in bad_starts:
                return False

            # Should have proper punctuation
            return not (not text.endswith(".") and not text.endswith(".)."))

        except Exception:
            return False

    def _validate_citation_quality(self, citation_data: dict[str, Any]) -> bool:
        """Validate that a parsed citation meets quality standards."""
        try:
            # Must have basic required fields
            if not citation_data.get("raw_text"):
                return False

            # Should have at least authors or title
            if not citation_data.get("authors") and not citation_data.get("title"):
                return False

            # If authors exist, they should look reasonable
            if citation_data.get("authors"):
                authors = citation_data["authors"]
                # Authors should contain letters and basic punctuation
                if not re.search(r"[A-Za-z]", authors):
                    return False
                # Authors shouldn't be just common words
                if authors.lower() in [
                    "the",
                    "this",
                    "that",
                    "work",
                    "study",
                    "research",
                    "paper",
                ]:
                    return False

            # Year should be reasonable if present
            if citation_data.get("publication_year"):
                year = citation_data["publication_year"]
                if not (1900 <= year <= 2030):
                    return False

            return True

        except Exception:
            return False

    def _deduplicate_and_filter_citations(
        self, citations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove duplicates and filter low-quality citations."""
        try:
            filtered_citations = []
            seen_texts = set[str]()

            for citation in citations:
                raw_text = citation.get("raw_text", "").strip().lower()

                # Skip if we've seen very similar text
                is_duplicate = False
                for seen_text in seen_texts:
                    if self._calculate_text_similarity(raw_text, seen_text) > 0.8:
                        is_duplicate = True
                        break

                if not is_duplicate and self._validate_citation_quality(citation):
                    filtered_citations.append(citation)
                    seen_texts.add(raw_text)

            # Sort by confidence score descending
            filtered_citations.sort(
                key=lambda x: x.get("confidence_score", 0), reverse=True
            )

            return filtered_citations

        except Exception:
            return citations

    def _normalize_author_name(self, author: str) -> str:
        """Normalize author name to consistent format."""
        try:
            author = author.strip()

            # Handle "LastName F." format - convert to "LastName, F."
            if "," not in author and " " in author:
                parts = author.split()
                if len(parts) >= 2:
                    # Check if the last part looks like an initial
                    last_part = parts[-1]
                    if len(last_part) <= 3 and (
                        last_part.endswith(".") or len(last_part) == 1
                    ):
                        last_name = " ".join(parts[:-1])
                        initial = last_part
                        author = f"{last_name}, {initial}"

            # Clean up extra spaces and punctuation
            author = re.sub(r"\s+", " ", author)
            author = re.sub(r"\s*,\s*", ", ", author)

            return author

        except Exception:
            return author
