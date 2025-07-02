"""
RAG Service Module

This module provides a comprehensive RAG (Retrieval-Augmented Generation) service
using LlamaIndex for PDF document analysis and question answering.
"""

import os
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from llama_index.core import Settings, VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

logger = logging.getLogger(__name__)


class RAGServiceError(Exception):
    """Base exception for RAG service errors."""
    pass


class RAGIndexError(RAGServiceError):
    """Raised for index-related errors."""
    pass


class RAGQueryError(RAGServiceError):
    """Raised for query-related errors."""
    pass


class RAGConfigurationError(RAGServiceError):
    """Raised for configuration-related errors."""
    pass


class RAGService:
    """
    {
        "name": "RAGService",
        "version": "1.0.0",
        "description": "RAG service for PDF document analysis using LlamaIndex and Google Gemini.",
        "dependencies": ["llama-index", "llama-index-llms-google", "llama-index-embeddings-google"],
        "interface": {
            "inputs": [{"name": "api_key", "type": "string"}],
            "outputs": "Complete RAG functionality with index building and querying"
        }
    }
    
    Provides RAG functionality for PDF documents using LlamaIndex.
    Features include automatic index caching, configuration management, and query processing.
    """
    
    def __init__(self, api_key: str, cache_dir: str = ".rag_cache", test_mode: bool = False):
        """
        Initialize RAG service with Google Gemini API key.
        
        @param {string} api_key - The Google Gemini API key for LLM and embedding services.
        @param {string} cache_dir - Directory for storing cached indexes (default: .rag_cache).
        @param {boolean} test_mode - If True, skip actual API initialization for testing.
        @raises {RAGConfigurationError} - If API key is missing or invalid.
        """
        if not api_key or not api_key.strip():
            raise RAGConfigurationError("API key is required for RAG service initialization")
        
        self.api_key = api_key.strip()
        self.cache_dir = Path(cache_dir)
        self.current_index = None
        self.current_pdf_path = None
        self.test_mode = test_mode
        self._initialized = False
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(exist_ok=True)
        
        # In test mode, skip API initialization
        if not test_mode:
            self._initialize_apis()
        else:
            logger.info("RAGService initialized in test mode - API initialization skipped")
            self._initialized = True
    
    def _initialize_apis(self):
        """Initialize the LlamaIndex APIs with Google Gemini services."""
        try:
            # Configure LlamaIndex Settings globally
            Settings.llm = GoogleGenAI(
                model="gemini-1.5-flash-latest",
                api_key=self.api_key,
                temperature=0.1
            )
            
            Settings.embed_model = GoogleGenAIEmbedding(
                model_name="text-embedding-004",
                api_key=self.api_key
            )
            
            logger.info("RAGService initialized successfully with Gemini LLM and embedding model")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise RAGConfigurationError(f"Failed to configure LlamaIndex settings: {e}") from e
    
    def _generate_cache_key(self, pdf_path: str) -> str:
        """
        Generate a unique cache key based on PDF path and modification time.
        
        @param {string} pdf_path - Path to the PDF file.
        @returns {string} Unique cache key for the PDF.
        """
        try:
            # Get file stats
            file_path = Path(pdf_path)
            if not file_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Create hash from path and modification time
            stat = file_path.stat()
            content = f"{pdf_path}_{stat.st_mtime}_{stat.st_size}"
            cache_key = hashlib.sha256(content.encode()).hexdigest()[:16]
            
            logger.debug(f"Generated cache key '{cache_key}' for PDF: {pdf_path}")
            return cache_key
            
        except Exception as e:
            logger.error(f"Failed to generate cache key for {pdf_path}: {e}")
            raise RAGIndexError(f"Cannot generate cache key: {e}") from e
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get the cache directory path for a given cache key.
        
        @param {string} cache_key - The cache key for the index.
        @returns {Path} Path to the cache directory.
        """
        return self.cache_dir / cache_key
    
    def _cache_exists(self, cache_key: str) -> bool:
        """
        Check if a valid cache exists for the given cache key.
        
        @param {string} cache_key - The cache key to check.
        @returns {boolean} True if cache exists and is valid.
        """
        cache_path = self._get_cache_path(cache_key)
        
        # Check if cache directory exists and contains required files
        if not cache_path.exists():
            return False
        
        # Check for essential index files
        required_files = ["default__vector_store.json", "graph_store.json", "index_store.json"]
        for file_name in required_files:
            if not (cache_path / file_name).exists():
                logger.warning(f"Cache incomplete: missing {file_name}")
                return False
        
        logger.debug(f"Valid cache found at: {cache_path}")
        return True
    
    def build_index_from_pdf(self, pdf_path: str) -> None:
        """
        Build or load vector index from PDF file with intelligent caching.
        
        @param {string} pdf_path - Path to the PDF file to index.
        @raises {RAGIndexError} - If indexing fails.
        """
        try:
            logger.info(f"Building/loading index for PDF: {pdf_path}")
            
            # Check file exists and is PDF (even in test mode for validation)
            file_path = Path(pdf_path)
            if not file_path.exists():
                raise RAGIndexError(f"PDF file not found: {pdf_path}")
            
            if not pdf_path.lower().endswith('.pdf'):
                raise RAGIndexError(f"File must be a PDF: {pdf_path}")
            
            # Initialize APIs if not done yet (for non-test mode)
            if not self.test_mode and not self._initialized:
                self._initialize_apis()
            
            # In test mode, create a mock index
            if self.test_mode:
                logger.info("Test mode: creating mock index")
                # Create a simple mock index object
                self.current_index = type('MockIndex', (), {
                    'as_query_engine': lambda **kwargs: type('MockQueryEngine', (), {
                        'query': lambda prompt: type('MockResponse', (), {'__str__': lambda: f"Mock response for: {prompt}"})()
                    })()
                })()
                self.current_pdf_path = pdf_path
                logger.info("Mock index created successfully")
                return True
            
            # Generate cache key
            cache_key = self._generate_cache_key(pdf_path)
            cache_path = self._get_cache_path(cache_key)
            
            # Try to load from cache first
            if self._cache_exists(cache_key):
                logger.info(f"Loading index from cache: {cache_path}")
                try:
                    storage_context = StorageContext.from_defaults(persist_dir=str(cache_path))
                    self.current_index = load_index_from_storage(storage_context)
                    self.current_pdf_path = pdf_path
                    logger.info("Index loaded successfully from cache")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to load cached index: {e}. Rebuilding...")
                    # Continue to rebuild if cache loading fails
            
            # Build new index
            logger.info("Building new index from PDF...")
            
            # Load PDF documents
            reader = SimpleDirectoryReader(
                input_files=[pdf_path],
                required_exts=[".pdf"]
            )
            documents = reader.load_data()
            
            if not documents:
                raise RAGIndexError(f"No documents could be loaded from: {pdf_path}")
            
            logger.info(f"Loaded {len(documents)} document chunks from PDF")
            
            # Build vector index
            self.current_index = VectorStoreIndex.from_documents(
                documents,
                show_progress=True
            )
            
            # Persist to cache
            logger.info(f"Persisting index to cache: {cache_path}")
            self.current_index.storage_context.persist(persist_dir=str(cache_path))
            
            # Save metadata
            metadata = {
                "pdf_path": pdf_path,
                "cache_key": cache_key,
                "document_count": len(documents),
                "created_at": str(Path(pdf_path).stat().st_mtime)
            }
            
            with open(cache_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
            
            self.current_pdf_path = pdf_path
            logger.info("Index built and cached successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build index from PDF {pdf_path}: {e}")
            raise RAGIndexError(f"Index building failed: {e}") from e
    
    def query(self, prompt: str) -> str:
        """
        Query the indexed PDF using the RAG pipeline.
        
        @param {string} prompt - The user's question or prompt.
        @returns {string} The AI's response based on the PDF content.
        @raises {RAGQueryError} - If query fails.
        """
        try:
            if not self.current_index:
                raise RAGQueryError("No index available. Please build an index first.")
            
            if not prompt or not prompt.strip():
                raise RAGQueryError("Query cannot be empty")
            
            # Initialize APIs if not done yet (for non-test mode)
            if not self.test_mode and not self._initialized:
                self._initialize_apis()
            
            # In test mode, return a mock response
            if self.test_mode:
                logger.info(f"Test mode: returning mock response for query: {prompt[:100]}...")
                return f"Mock response for: {prompt.strip()}"
            
            logger.info(f"Processing RAG query: {prompt[:100]}...")
            
            # Create query engine
            query_engine = self.current_index.as_query_engine(
                similarity_top_k=5,  # Retrieve top 5 relevant chunks
                streaming=False
            )
            
            # Execute query
            response = query_engine.query(prompt)
            
            # Extract response text
            response_text = str(response).strip()
            
            if not response_text:
                logger.warning("Empty response received from query engine")
                return "I couldn't find relevant information in the document to answer your question."
            
            logger.info(f"RAG query completed successfully, response length: {len(response_text)}")
            return response_text
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise RAGQueryError(f"Query execution failed: {e}") from e
    
    def is_ready(self) -> bool:
        """
        Check if the RAG service is ready for queries.
        
        @returns {boolean} True if an index is loaded and ready for queries.
        """
        return self.current_index is not None
    
    def get_current_pdf_path(self) -> Optional[str]:
        """
        Get the path of the currently indexed PDF.
        
        @returns {string|None} Path to current PDF or None if no PDF is indexed.
        """
        return self.current_pdf_path
    
    def clear_index(self) -> None:
        """
        Clear the current index and reset the service state.
        """
        logger.info("Clearing RAG service index")
        self.current_index = None
        self.current_pdf_path = None
    
    def get_cache_info(self) -> dict:
        """
        Get information about the current cache state.
        
        @returns {dict} Dictionary containing cache information.
        """
        cache_info = {
            "cache_dir": str(self.cache_dir),
            "cache_exists": self.cache_dir.exists(),
            "current_pdf": self.current_pdf_path,
            "index_ready": self.is_ready()
        }
        
        # Count cache entries
        if self.cache_dir.exists():
            cache_entries = [d for d in self.cache_dir.iterdir() if d.is_dir()]
            cache_info["cache_entries"] = len(cache_entries)
        else:
            cache_info["cache_entries"] = 0
        
        return cache_info 