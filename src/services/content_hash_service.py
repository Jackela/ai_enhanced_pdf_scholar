"""
Content Hash Service
Provides content-based hashing for intelligent document deduplication.
Supports both file-level and content-level hashing for different use cases.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class ContentHashError(Exception):
    """Raised when content hashing fails."""

    pass


class ContentHashService:
    """
    {
        "name": "ContentHashService",
        "version": "1.0.0",
        "description": "Service for generating content-based hashes.",
        "dependencies": ["PyMuPDF", "hashlib"],
        "interface": {
            "inputs": ["file_path: str"],
            "outputs": "Content hashes for deduplication and caching"
        }
    }
    Provides intelligent content hashing for document deduplication.
    Supports multiple hashing strategies for different use cases.
    """

    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for large file processing

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        Calculate SHA-256 hash of file content.
        This hash is based on the raw file bytes and will detect any changes
        to the file, including metadata changes.
        Args:
            file_path: Path to the file
        Returns:
            16-character hex hash string
        Raises:
            ContentHashError: If hashing fails
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise ContentHashError(f"File not found: {file_path}")
            if not path.is_file():
                raise ContentHashError(f"Path is not a file: {file_path}")
            # Use streaming hash calculation for large files
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(ContentHashService.CHUNK_SIZE):
                    hasher.update(chunk)
            # Return first 16 characters for shorter keys
            file_hash = hasher.hexdigest()[:16]
            logger.debug(f"Calculated file hash for {file_path}: {file_hash}")
            return file_hash
        except Exception as e:
            logger.error(f"Failed to calculate file hash for {file_path}: {e}")
            raise ContentHashError(f"File hashing failed: {e}") from e

    @staticmethod
    def calculate_content_hash(file_path: str) -> str:
        """
        Calculate hash based on PDF text content only.
        This hash ignores formatting, metadata, and positioning, focusing only
        on the actual text content. Useful for detecting semantically identical
        documents with different formatting or metadata.
        Args:
            file_path: Path to the PDF file
        Returns:
            16-character hex hash string
        Raises:
            ContentHashError: If content extraction or hashing fails
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise ContentHashError(f"File not found: {file_path}")
            if not str(path).lower().endswith(".pdf"):
                raise ContentHashError(f"File must be a PDF: {file_path}")
            # Extract text content from PDF
            text_content = ContentHashService._extract_pdf_text(file_path)
            # Normalize text for consistent hashing
            normalized_text = ContentHashService._normalize_text(text_content)
            # Calculate hash of normalized content
            hasher = hashlib.sha256()
            hasher.update(normalized_text.encode("utf-8"))
            content_hash = hasher.hexdigest()[:16]
            logger.debug(f"Calculated content hash for {file_path}: {content_hash}")
            return content_hash
        except Exception as e:
            logger.error(f"Failed to calculate content hash for {file_path}: {e}")
            raise ContentHashError(f"Content hashing failed: {e}") from e

    @staticmethod
    def calculate_combined_hashes(file_path: str) -> tuple[str, str]:
        """
        Calculate both file and content hashes in one operation.
        More efficient than calling both methods separately for the same file.
        Args:
            file_path: Path to the PDF file
        Returns:
            Tuple of (file_hash, content_hash)
        Raises:
            ContentHashError: If hashing fails
        """
        try:
            # Calculate file hash first (faster, can fail early)
            file_hash = ContentHashService.calculate_file_hash(file_path)
            # Calculate content hash (slower, PDF-specific)
            content_hash = ContentHashService.calculate_content_hash(file_path)
            logger.debug(
                f"Calculated hashes for {file_path}: file={file_hash}, content={content_hash}"
            )
            return file_hash, content_hash
        except Exception as e:
            logger.error(f"Failed to calculate combined hashes for {file_path}: {e}")
            raise ContentHashError(f"Combined hashing failed: {e}") from e

    @staticmethod
    def _extract_pdf_text(file_path: str) -> str:
        """
        Extract all text content from PDF file.
        Args:
            file_path: Path to the PDF file
        Returns:
            Concatenated text from all pages
        Raises:
            ContentHashError: If PDF processing fails
        """
        try:
            text_content = []
            with fitz.open(file_path) as pdf_doc:
                for page_num in range(len(pdf_doc)):
                    page = pdf_doc[page_num]
                    page_text = page.get_text()
                    if page_text.strip():  # Only add non-empty pages
                        text_content.append(page_text)
            # Join all page text with newlines
            full_text = "\n".join(text_content)
            if not full_text.strip():
                logger.warning(f"No text content extracted from PDF: {file_path}")
                # Use filename as fallback for PDFs with no extractable text
                return Path(file_path).stem
            logger.debug(f"Extracted {len(full_text)} characters from PDF: {file_path}")
            return full_text
        except Exception as e:
            logger.error(f"Failed to extract PDF text from {file_path}: {e}")
            raise ContentHashError(f"PDF text extraction failed: {e}") from e

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text content for consistent hashing.
        Removes variations that don't affect semantic content:
        - Extra whitespace
        - Case differences
        - Line ending variations
        Args:
            text: Raw text content
        Returns:
            Normalized text
        """
        if not text:
            return ""
        # Convert to lowercase for case-insensitive comparison
        normalized = text.lower()
        # Normalize whitespace
        # Replace multiple whitespace characters with single spaces
        import re

        normalized = re.sub(r"\s+", " ", normalized)
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        logger.debug(f"Normalized text: {len(text)} -> {len(normalized)} characters")
        return normalized

    @staticmethod
    def validate_pdf_file(file_path: str) -> bool:
        """
        Validate that file is a readable PDF.
        Args:
            file_path: Path to the file
        Returns:
            True if file is a valid PDF
        """
        try:
            path = Path(file_path)
            # Check file existence and extension
            if not path.exists() or not path.is_file():
                return False
            if not str(path).lower().endswith(".pdf"):
                return False
            # Try to open with PyMuPDF
            with fitz.open(file_path) as pdf_doc:
                # Check if we can read basic properties
                page_count = len(pdf_doc)
                if page_count <= 0:
                    return False
            logger.debug(f"PDF validation passed for: {file_path}")
            return True
        except Exception as e:
            logger.debug(f"PDF validation failed for {file_path}: {e}")
            return False

    @staticmethod
    def get_file_info(file_path: str) -> dict[str, Any]:
        """
        Get comprehensive file information for debugging and logging.
        Args:
            file_path: Path to the file
        Returns:
            Dictionary with file information
        """
        try:
            path = Path(file_path)
            info = {
                "file_path": str(path.absolute()),
                "file_name": path.name,
                "file_size": path.stat().st_size if path.exists() else 0,
                "file_exists": path.exists(),
                "is_pdf": str(path).lower().endswith(".pdf"),
                "is_valid_pdf": False,
                "page_count": 0,
                "text_length": 0,
                "file_hash": None,
                "content_hash": None,
            }
            if info["is_pdf"] and path.exists():
                try:
                    # Validate PDF and get metadata
                    info["is_valid_pdf"] = ContentHashService.validate_pdf_file(
                        file_path
                    )
                    if info["is_valid_pdf"]:
                        with fitz.open(file_path) as pdf_doc:
                            info["page_count"] = len(pdf_doc)
                        # Calculate hashes
                        file_hash, content_hash = (
                            ContentHashService.calculate_combined_hashes(file_path)
                        )
                        info["file_hash"] = file_hash
                        info["content_hash"] = content_hash
                        # Get text length
                        text_content = ContentHashService._extract_pdf_text(file_path)
                        info["text_length"] = len(text_content)
                except Exception as e:
                    logger.debug(
                        f"Could not get detailed PDF info for {file_path}: {e}"
                    )
            return info
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return {"error": str(e)}
