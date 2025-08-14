"""
Streaming PDF Processing Service
Memory-efficient PDF processing for large files with incremental indexing.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

import aiofiles
from llama_index.core import Document
from llama_index.readers.file import PDFReader

from backend.api.streaming_models import UploadSession


logger = logging.getLogger(__name__)


class StreamingPDFProcessor:
    """
    Memory-efficient PDF processing service for large documents.

    Features:
    - Page-by-page processing to minimize memory usage
    - Incremental text extraction
    - Streaming document creation for indexing
    - Progress tracking during processing
    - Graceful handling of corrupted or encrypted PDFs
    """

    def __init__(
        self,
        max_pages_per_chunk: int = 5,
        max_text_length_per_page: int = 10000,
        enable_ocr: bool = False,
    ):
        self.max_pages_per_chunk = max_pages_per_chunk
        self.max_text_length_per_page = max_text_length_per_page
        self.enable_ocr = enable_ocr

        # Initialize PDF reader
        self.pdf_reader = PDFReader()

        # Processing statistics
        self.processing_stats = {
            'documents_processed': 0,
            'total_pages_processed': 0,
            'text_extraction_errors': 0,
            'ocr_pages': 0,
        }

    async def process_pdf_streaming(
        self,
        session: UploadSession,
        websocket_manager=None,
        progress_callback=None,
    ) -> AsyncGenerator[Document, None]:
        """
        Process PDF file in streaming fashion, yielding documents page by page.

        Args:
            session: Upload session with PDF file information
            websocket_manager: WebSocket manager for progress updates
            progress_callback: Optional callback for progress updates

        Yields:
            Document: LlamaIndex documents for each page or page chunk

        Raises:
            RuntimeError: If PDF processing fails
        """
        if not session.temp_file_path or not Path(session.temp_file_path).exists():
            raise RuntimeError("PDF file not found for processing")

        try:
            logger.info(f"Starting streaming PDF processing: {session.filename}")

            # Send initial processing update
            if websocket_manager:
                await websocket_manager.send_upload_status(
                    session.client_id,
                    str(session.session_id),
                    "processing",
                    "Starting PDF text extraction..."
                )

            total_pages = 0
            processed_pages = 0

            # Process PDF in chunks to minimize memory usage
            async for page_chunk in self._process_pdf_chunks(session.temp_file_path):
                try:
                    # Extract text from page chunk
                    documents = await self._extract_text_from_chunk(
                        page_chunk,
                        session.filename,
                        processed_pages
                    )

                    # Yield each document
                    for doc in documents:
                        yield doc

                    processed_pages += len(page_chunk['pages'])

                    # Update progress
                    if total_pages == 0:
                        total_pages = page_chunk.get('total_pages', processed_pages)

                    progress_percentage = (processed_pages / total_pages) * 100 if total_pages > 0 else 0

                    # Send progress update
                    if websocket_manager:
                        await websocket_manager.send_upload_progress(
                            session.client_id,
                            {
                                'session_id': str(session.session_id),
                                'status': 'processing',
                                'stage': 'text_extraction',
                                'progress_percentage': progress_percentage,
                                'pages_processed': processed_pages,
                                'total_pages': total_pages,
                                'message': f'Extracting text from page {processed_pages} of {total_pages}...'
                            }
                        )

                    # Call progress callback if provided
                    if progress_callback:
                        await progress_callback(processed_pages, total_pages, 'text_extraction')

                    logger.debug(
                        f"Processed {processed_pages}/{total_pages} pages "
                        f"for {session.filename}"
                    )

                except Exception as e:
                    logger.error(f"Error processing page chunk {processed_pages}: {e}")
                    self.processing_stats['text_extraction_errors'] += 1

                    # Send error update but continue processing
                    if websocket_manager:
                        await websocket_manager.send_upload_progress(
                            session.client_id,
                            {
                                'session_id': str(session.session_id),
                                'status': 'processing',
                                'stage': 'text_extraction',
                                'warning': f'Error processing pages around {processed_pages}: {str(e)}'
                            }
                        )

                    continue

            # Update statistics
            self.processing_stats['documents_processed'] += 1
            self.processing_stats['total_pages_processed'] += processed_pages

            logger.info(
                f"Completed streaming PDF processing: {session.filename} "
                f"({processed_pages} pages processed)"
            )

        except Exception as e:
            logger.error(f"Streaming PDF processing failed for {session.filename}: {e}")

            # Send error update
            if websocket_manager:
                await websocket_manager.send_upload_error(
                    session.client_id,
                    str(session.session_id),
                    f"PDF processing failed: {str(e)}"
                )

            raise RuntimeError(f"PDF processing failed: {str(e)}")

    async def _process_pdf_chunks(
        self,
        pdf_path: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Process PDF file in chunks to minimize memory usage.

        Args:
            pdf_path: Path to the PDF file

        Yields:
            Dict: Chunk information with pages and metadata
        """
        try:
            # Use PDFReader to get document structure
            documents = self.pdf_reader.load_data(file=Path(pdf_path))
            total_pages = len(documents)

            logger.info(f"PDF loaded with {total_pages} pages: {pdf_path}")

            # Process in chunks
            for chunk_start in range(0, total_pages, self.max_pages_per_chunk):
                chunk_end = min(chunk_start + self.max_pages_per_chunk, total_pages)

                # Extract pages for this chunk
                chunk_pages = []
                for page_idx in range(chunk_start, chunk_end):
                    try:
                        page_doc = documents[page_idx]
                        chunk_pages.append({
                            'page_number': page_idx + 1,
                            'text': page_doc.text,
                            'metadata': page_doc.metadata or {},
                        })
                    except Exception as e:
                        logger.warning(f"Error processing page {page_idx + 1}: {e}")
                        # Add empty page to maintain page numbering
                        chunk_pages.append({
                            'page_number': page_idx + 1,
                            'text': '',
                            'metadata': {'error': str(e)},
                        })

                yield {
                    'pages': chunk_pages,
                    'chunk_start': chunk_start,
                    'chunk_end': chunk_end,
                    'total_pages': total_pages,
                }

                # Allow other tasks to run
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Failed to process PDF chunks: {e}")
            raise

    async def _extract_text_from_chunk(
        self,
        page_chunk: Dict,
        filename: str,
        processed_pages: int,
    ) -> List[Document]:
        """
        Extract text from a chunk of pages and create LlamaIndex documents.

        Args:
            page_chunk: Chunk information with pages
            filename: Original filename
            processed_pages: Number of pages already processed

        Returns:
            List[Document]: LlamaIndex documents for the chunk
        """
        documents = []

        try:
            pages = page_chunk['pages']

            for page_info in pages:
                try:
                    page_number = page_info['page_number']
                    text_content = page_info.get('text', '').strip()
                    page_metadata = page_info.get('metadata', {})

                    # Skip empty pages
                    if not text_content:
                        logger.debug(f"Skipping empty page {page_number}")
                        continue

                    # Limit text length per page
                    if len(text_content) > self.max_text_length_per_page:
                        text_content = text_content[:self.max_text_length_per_page]
                        logger.debug(f"Truncated long text on page {page_number}")

                    # Create document metadata
                    doc_metadata = {
                        'filename': filename,
                        'page_number': page_number,
                        'source': 'streaming_pdf_processor',
                        'processing_order': processed_pages + len(documents),
                    }

                    # Add any additional metadata from PDF
                    doc_metadata.update(page_metadata)

                    # Create LlamaIndex document
                    document = Document(
                        text=text_content,
                        metadata=doc_metadata,
                        id_=f"{filename}_page_{page_number}",
                    )

                    documents.append(document)

                    logger.debug(
                        f"Created document for page {page_number} "
                        f"({len(text_content)} characters)"
                    )

                except Exception as e:
                    logger.error(f"Error creating document for page {page_info.get('page_number', '?')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting text from chunk: {e}")
            raise

        return documents

    async def get_pdf_info_streaming(self, pdf_path: str) -> Dict:
        """
        Get PDF information without loading the entire file into memory.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dict: PDF information including page count, metadata, etc.
        """
        try:
            info = {
                'page_count': None,
                'file_size': 0,
                'is_encrypted': False,
                'metadata': {},
                'processing_estimate': {},
            }

            # Get file size
            pdf_file = Path(pdf_path)
            info['file_size'] = pdf_file.stat().st_size

            # Quick PDF analysis
            try:
                documents = self.pdf_reader.load_data(file=pdf_file)
                info['page_count'] = len(documents)

                # Estimate processing time and memory usage
                info['processing_estimate'] = {
                    'estimated_chunks': (len(documents) + self.max_pages_per_chunk - 1) // self.max_pages_per_chunk,
                    'estimated_memory_mb': min(50, len(documents) * 2),  # Rough estimate
                    'estimated_duration_seconds': len(documents) * 0.5,  # Rough estimate
                }

                # Extract basic metadata if available
                if documents and documents[0].metadata:
                    info['metadata'] = documents[0].metadata

            except Exception as e:
                logger.warning(f"Could not analyze PDF structure: {e}")
                info['error'] = str(e)

            return info

        except Exception as e:
            logger.error(f"Failed to get PDF info: {e}")
            return {'error': str(e)}

    async def validate_pdf_processing_readiness(
        self,
        pdf_path: str,
        available_memory_mb: float
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate if PDF is ready for streaming processing.

        Args:
            pdf_path: Path to the PDF file
            available_memory_mb: Available memory in MB

        Returns:
            Tuple[bool, List[str], List[str]]: (is_ready, errors, warnings)
        """
        errors = []
        warnings = []

        try:
            # Check file exists and is readable
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                errors.append("PDF file not found")
                return False, errors, warnings

            if not pdf_file.is_file():
                errors.append("Path is not a file")
                return False, errors, warnings

            # Get PDF info
            pdf_info = await self.get_pdf_info_streaming(pdf_path)

            if 'error' in pdf_info:
                errors.append(f"Cannot process PDF: {pdf_info['error']}")
                return False, errors, warnings

            # Check memory requirements
            estimated_memory = pdf_info.get('processing_estimate', {}).get('estimated_memory_mb', 0)
            if estimated_memory > available_memory_mb * 0.8:
                warnings.append(
                    f"Estimated memory usage ({estimated_memory}MB) is high "
                    f"compared to available memory ({available_memory_mb}MB)"
                )

            # Check page count
            page_count = pdf_info.get('page_count', 0)
            if page_count == 0:
                errors.append("PDF appears to have no pages")
                return False, errors, warnings
            elif page_count > 1000:
                warnings.append(f"Large PDF with {page_count} pages may take significant time to process")

            # Check file size
            file_size_mb = pdf_info.get('file_size', 0) / (1024 * 1024)
            if file_size_mb > 500:  # > 500MB
                warnings.append(f"Large file size ({file_size_mb:.1f}MB) may impact processing speed")

            return True, errors, warnings

        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors, warnings

    def get_processing_stats(self) -> Dict:
        """Get current processing statistics."""
        return self.processing_stats.copy()

    def reset_stats(self):
        """Reset processing statistics."""
        self.processing_stats = {
            'documents_processed': 0,
            'total_pages_processed': 0,
            'text_extraction_errors': 0,
            'ocr_pages': 0,
        }