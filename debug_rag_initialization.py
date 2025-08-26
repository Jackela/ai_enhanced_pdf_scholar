#!/usr/bin/env python3
"""
Debug script to test RAG service initialization
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_config():
    """Test configuration loading"""
    try:
        from config import Config
        api_key = Config.get_gemini_api_key()
        logger.info(f"API Key configured: {api_key is not None}")
        if api_key:
            logger.info(f"API Key length: {len(api_key)}")
            logger.info(f"API Key starts with: {api_key[:10]}...")
        return api_key
    except Exception as e:
        logger.error(f"Configuration test failed: {e}")
        return None

def test_database():
    """Test database connection"""
    try:
        from src.database.connection import DatabaseConnection

        db_dir = Path.home() / ".ai_pdf_scholar"
        db_dir.mkdir(exist_ok=True)
        db_path = str(db_dir / "documents.db")

        db = DatabaseConnection(db_path)
        logger.info(f"Database connection successful: {db_path}")
        return db
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return None

def test_rag_service_initialization():
    """Test RAG service initialization step by step"""
    try:
        # Test configuration
        api_key = test_config()
        if not api_key:
            logger.error("No API key available")
            return False

        # Test database
        db = test_database()
        if not db:
            logger.error("Database connection failed")
            return False

        # Test RAG service initialization
        from src.services.enhanced_rag_service import EnhancedRAGService

        # Check if it's a test key
        test_api_keys = [
            "your_gemini_api_key_here",
            "your_actual_gemini_api_key_here",
            "test_api_key_for_local_testing",
            "test-api-key"
        ]

        is_test_mode = api_key in test_api_keys or api_key.startswith("test")
        logger.info(f"Test mode: {is_test_mode}")

        # Initialize vector storage
        vector_storage_dir = Path.home() / ".ai_pdf_scholar" / "vector_indexes"
        vector_storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Vector storage directory: {vector_storage_dir}")
        logger.info(f"Vector storage exists: {vector_storage_dir.exists()}")

        # Initialize RAG service
        logger.info("Initializing RAG service...")
        rag_service = EnhancedRAGService(
            api_key=api_key,
            db_connection=db,
            vector_storage_dir=str(vector_storage_dir),
            test_mode=is_test_mode,
        )

        logger.info("RAG service initialized successfully!")

        # Test basic functionality
        cache_info = rag_service.get_cache_info()
        logger.info(f"Cache info: {cache_info}")

        return True

    except Exception as e:
        logger.error(f"RAG service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=== RAG Service Debug Test ===")
    success = test_rag_service_initialization()
    logger.info(f"Test result: {'SUCCESS' if success else 'FAILED'}")
