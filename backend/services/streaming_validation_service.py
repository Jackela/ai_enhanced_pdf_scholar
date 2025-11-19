from typing import Any

"""
Streaming Validation Service
Advanced file validation service for streaming uploads with detailed PDF analysis.
"""

import logging
import re
from pathlib import Path

import aiofiles

from backend.api.streaming_models import StreamingValidationResult

logger = logging.getLogger(__name__)


class StreamingValidationService:
    """
    Advanced streaming file validation service.

    Features:
    - Streaming MIME type detection
    - PDF structure validation
    - Content security scanning
    - Progressive validation during upload
    - Memory-efficient processing
    """

    # PDF signatures and versions
    PDF_SIGNATURES = {
        b"%PDF-1.0": "1.0",
        b"%PDF-1.1": "1.1",
        b"%PDF-1.2": "1.2",
        b"%PDF-1.3": "1.3",
        b"%PDF-1.4": "1.4",
        b"%PDF-1.5": "1.5",
        b"%PDF-1.6": "1.6",
        b"%PDF-1.7": "1.7",
        b"%PDF-2.0": "2.0",
    }

    # Dangerous content patterns
    SECURITY_PATTERNS = {
        "javascript": [
            rb"/JavaScript\s*\(",
            rb"/JS\s*\(",
            rb"app\.alert\s*\(",
            rb"this\.print\s*\(",
            rb"this\.submitForm\s*\(",
        ],
        "embedded_files": [
            rb"/EmbeddedFiles",
            rb"/FileAttachment",
            rb"/EmbeddedFile",
        ],
        "forms": [
            rb"/AcroForm",
            rb"/XFA",
            rb"/Field",
        ],
        "external_references": [
            rb"/URI\s*\(",
            rb"/Launch",
            rb"/GoToR",
            rb"http://",
            rb"https://",
            rb"file://",
        ],
    }

    def __init__(self) -> None:
        # Validation statistics
        self.validation_stats = {
            "files_validated": 0,
            "validation_errors": 0,
            "security_warnings": 0,
        }

    async def validate_streaming_upload(
        self, file_path: str, chunk_size: int = 8192, max_scan_size: int | None = None
    ) -> StreamingValidationResult:
        """
        Validate uploaded file with streaming approach for memory efficiency.

        Args:
            file_path: Path to the uploaded file
            chunk_size: Size of chunks to read for validation
            max_scan_size: Maximum file size to scan (None for no limit)

        Returns:
            StreamingValidationResult: Comprehensive validation results
        """
        result = StreamingValidationResult()

        try:
            file_size = Path(file_path).stat().st_size

            # Limit scan size for very large files
            scan_size = file_size
            if max_scan_size and file_size > max_scan_size:
                scan_size = max_scan_size
                result.warnings.append(
                    f"Only scanned first {scan_size} bytes of {file_size} byte file"
                )

            # Perform streaming validation
            async with aiofiles.open(file_path, "rb") as f:
                # Read file header for signature detection
                header = await f.read(min(1024, scan_size))

                # Validate PDF signature
                pdf_validation = self._validate_pdf_signature(header)
                result.is_pdf = pdf_validation["is_pdf"]
                result.pdf_version = pdf_validation["version"]
                result.detected_mime_type = pdf_validation["mime_type"]
                result.file_signature = pdf_validation["signature"]

                if not result.is_pdf:
                    result.is_valid = False
                    result.validation_errors.extend(pdf_validation["errors"])
                    return result

                # Reset file pointer for full scan
                await f.seek(0)

                # Perform streaming content analysis
                content_analysis = await self._analyze_pdf_content_streaming(
                    f, scan_size, chunk_size
                )

                # Update result with content analysis
                result.page_count = content_analysis.get("page_count")
                result.is_encrypted = content_analysis.get("is_encrypted", False)
                result.validation_errors.extend(content_analysis.get("errors", []))
                result.warnings.extend(content_analysis.get("warnings", []))

                # Security scanning
                security_analysis = content_analysis.get("security_analysis", {})
                if security_analysis.get("threats_found"):
                    result.warnings.extend(security_analysis.get("warnings", []))

                # Final validation determination
                result.is_valid = len(result.validation_errors) == 0

                # Update statistics
                self.validation_stats["files_validated"] += 1
                if not result.is_valid:
                    self.validation_stats["validation_errors"] += 1
                if result.warnings:
                    self.validation_stats["security_warnings"] += 1

                logger.info(
                    f"File validation completed: {file_path} "
                    f"(valid: {result.is_valid}, PDF: {result.is_pdf}, "
                    f"version: {result.pdf_version}, pages: {result.page_count})"
                )

        except Exception as e:
            result.is_valid = False
            result.validation_errors.append(f"Validation error: {str(e)}")
            logger.error(f"File validation failed for {file_path}: {e}")
            self.validation_stats["validation_errors"] += 1

        return result

    def _validate_pdf_signature(self, header_bytes: bytes) -> dict[str, Any]:
        """
        Validate PDF file signature and extract version information.

        Args:
            header_bytes: First bytes of the file

        Returns:
            Dict: Signature validation results
        """
        result: Any = {
            "is_pdf": False,
            "version": None,
            "mime_type": "unknown",
            "signature": None,
            "errors": [],
        }

        try:
            # Check for PDF signature
            if not header_bytes.startswith(b"%PDF-"):
                result["errors"].append("File does not have a valid PDF signature")
                return result

            # Extract signature
            signature_end = header_bytes.find(b"\n")
            if signature_end == -1:
                signature_end = header_bytes.find(b"\r")
            if signature_end == -1:
                signature_end = min(20, len(header_bytes))

            signature = header_bytes[:signature_end]
            result["signature"] = signature.decode("ascii", errors="ignore")

            # Match[str] PDF version
            for pdf_sig, version in self.PDF_SIGNATURES.items():
                if header_bytes.startswith(pdf_sig):
                    result["is_pdf"] = True
                    result["version"] = version
                    result["mime_type"] = "application/pdf"
                    break

            # If no exact match, try to parse version manually
            if not result["is_pdf"] and header_bytes.startswith(b"%PDF-"):
                version_match = re.match(rb"%PDF-(\d+\.\d+)", header_bytes)
                if version_match:
                    result["is_pdf"] = True
                    result["version"] = version_match.group(1).decode("ascii")
                    result["mime_type"] = "application/pdf"

            if not result["is_pdf"]:
                result["errors"].append(
                    f"Unrecognized PDF version in signature: {result['signature']}"
                )

        except Exception as e:
            result["errors"].append(f"Signature validation error: {str(e)}")

        return result

    async def _analyze_pdf_content_streaming(
        self, file_handle, scan_size: int, chunk_size: int
    ) -> dict[str, Any]:
        """
        Analyze PDF content structure with streaming approach.

        Args:
            file_handle: Open file handle
            scan_size: Maximum bytes to scan
            chunk_size: Size of chunks to read

        Returns:
            Dict: Content analysis results
        """
        analysis: Any = {
            "page_count": None,
            "is_encrypted": False,
            "errors": [],
            "warnings": [],
            "security_analysis": {"threats_found": False, "warnings": []},
        }

        try:
            # Track PDF structure
            objects_found = set[str]()
            pages_found = set[str]()
            encryption_found = False

            # Security threat tracking
            security_threats: Any = {
                threat_type: [] for threat_type in self.SECURITY_PATTERNS.keys()
            }

            bytes_read = 0
            content_buffer = b""
            buffer_size = chunk_size * 4  # Keep 4 chunks in buffer for pattern matching

            # Stream through file content
            while bytes_read < scan_size:
                chunk = await file_handle.read(min(chunk_size, scan_size - bytes_read))
                if not chunk:
                    break

                content_buffer += chunk
                bytes_read += len(chunk)

                # Keep buffer size manageable
                if len(content_buffer) > buffer_size:
                    # Process current buffer
                    self._analyze_pdf_chunk(
                        content_buffer, objects_found, pages_found, security_threats
                    )

                    # Keep last part of buffer for pattern continuity
                    overlap_size = chunk_size
                    content_buffer = content_buffer[-overlap_size:]

                # Check for encryption markers in this chunk
                if not encryption_found:
                    encryption_found = self._check_encryption_markers(chunk)

            # Process remaining buffer
            if content_buffer:
                self._analyze_pdf_chunk(
                    content_buffer, objects_found, pages_found, security_threats
                )

            # Calculate page count
            if pages_found:
                analysis["page_count"] = len(pages_found)
            else:
                # Try alternative page counting method
                analysis["page_count"] = await self._estimate_page_count(file_handle)

            # Set encryption status
            analysis["is_encrypted"] = encryption_found

            # Analyze security threats
            threats_found = any(threats for threats in security_threats.values())
            analysis["security_analysis"]["threats_found"] = threats_found

            if threats_found:
                for threat_type, locations in security_threats.items():
                    if locations:
                        analysis["security_analysis"]["warnings"].append(
                            f"Potential {threat_type.replace('_', ' ')} detected at {len(locations)} locations"
                        )

            logger.debug(
                f"PDF content analysis: pages={analysis['page_count']}, "
                f"encrypted={analysis['is_encrypted']}, threats={threats_found}"
            )

        except Exception as e:
            analysis["errors"].append(f"Content analysis error: {str(e)}")
            logger.error(f"PDF content analysis failed: {e}")

        return analysis

    def _analyze_pdf_chunk(
        self,
        chunk: bytes,
        objects_found: set[int],
        pages_found: set[int],
        security_threats: dict[str, list[int]],
    ) -> None:
        """
        Analyze a chunk of PDF content for structure and security threats.

        Args:
            chunk: PDF content chunk
            objects_found: Set to track found objects
            pages_found: Set to track found pages
            security_threats: Dictionary to track security threats
        """
        try:
            # Find PDF objects
            object_pattern = rb"(\d+)\s+\d+\s+obj"
            for match in re.finditer(object_pattern, chunk):
                obj_num = int(match.group(1))
                objects_found.add(obj_num)

            # Find page objects
            page_pattern = rb"/Type\s*/Page\b"
            page_matches = list[Any](re.finditer(page_pattern, chunk))
            for i, match in enumerate(page_matches):
                pages_found.add(match.start())

            # Security threat detection
            for threat_type, patterns in self.SECURITY_PATTERNS.items():
                for pattern in patterns:
                    matches = list[Any](re.finditer(pattern, chunk, re.IGNORECASE))
                    for match in matches:
                        security_threats[threat_type].append(match.start())

        except Exception as e:
            logger.warning(f"Error analyzing PDF chunk: {e}")

    def _check_encryption_markers(self, chunk: bytes) -> bool:
        """
        Check for PDF encryption markers in content chunk.

        Args:
            chunk: Content chunk to analyze

        Returns:
            bool: True if encryption markers found
        """
        encryption_patterns = [
            rb"/Encrypt\b",
            rb"/Filter\s*/Standard",
            rb"/Filter\s*/V",
            rb"/R\s*\d+",
            rb"/P\s*-?\d+",
            rb"/U\s*<[0-9a-fA-F]+>",
            rb"/O\s*<[0-9a-fA-F]+>",
        ]

        for pattern in encryption_patterns:
            if re.search(pattern, chunk, re.IGNORECASE):
                return True

        return False

    async def _estimate_page_count(self, file_handle) -> int | None:
        """
        Estimate PDF page count by analyzing file structure.

        Args:
            file_handle: Open file handle

        Returns:
            Optional[int]: Estimated page count
        """
        try:
            # Save current position
            current_pos = await file_handle.tell()

            # Try to find trailer and root object
            await file_handle.seek(-1024, 2)  # Go to end of file
            trailer_data = await file_handle.read()

            # Look for page count in trailer or catalog
            count_patterns = [
                rb"/Count\s*(\d+)",
                rb"/N\s*(\d+)",
            ]

            for pattern in count_patterns:
                match = re.search(pattern, trailer_data)
                if match:
                    page_count = int(match.group(1))
                    # Restore file position
                    await file_handle.seek(current_pos)
                    return page_count

            # Restore file position
            await file_handle.seek(current_pos)

        except Exception as e:
            logger.debug(f"Page count estimation failed: {e}")

        return None

    async def validate_chunk_during_upload(
        self, chunk_data: bytes, chunk_id: int, is_first_chunk: bool = False
    ) -> tuple[bool, list[str], list[str]]:
        """
        Validate individual chunk during upload for early detection of issues.

        Args:
            chunk_data: Chunk binary data
            chunk_id: Sequential chunk identifier
            is_first_chunk: Whether this is the first chunk

        Returns:
            Tuple[bool, List[str], List[str]]: (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        is_valid = True

        try:
            # Validate first chunk for PDF signature
            if is_first_chunk:
                if not chunk_data.startswith(b"%PDF-"):
                    errors.append("File does not start with PDF signature")
                    is_valid = False
                else:
                    # Quick security check on first chunk
                    for threat_type, patterns in self.SECURITY_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, chunk_data[:1024], re.IGNORECASE):
                                warnings.append(
                                    f"Potential {threat_type.replace('_', ' ')} detected in file header"
                                )

            # Check for null bytes (potential corruption indicator)
            null_count = chunk_data.count(b"\x00")
            if null_count > len(chunk_data) * 0.1:  # > 10% null bytes
                warnings.append(
                    f"Chunk {chunk_id} contains unusually high number of null bytes"
                )

            # Basic binary content validation
            if len(chunk_data) == 0:
                errors.append(f"Chunk {chunk_id} is empty")
                is_valid = False

        except Exception as e:
            errors.append(f"Chunk validation error: {str(e)}")
            is_valid = False

        return is_valid, errors, warnings

    def get_validation_stats(self) -> dict[str, Any]:
        """Get current validation statistics."""
        return self.validation_stats.copy()

    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self.validation_stats = {
            "files_validated": 0,
            "validation_errors": 0,
            "security_warnings": 0,
        }
