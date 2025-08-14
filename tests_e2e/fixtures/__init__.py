"""
E2E Test Fixtures Package

This package contains reusable test fixtures for end-to-end testing.
"""

from .browser_fixtures import *
from .data_fixtures import *
from .api_fixtures import *
from .database_fixtures import *

__all__ = [
    # Browser fixtures
    'browser_context',
    'page',
    'mobile_browser',
    'multi_browser',

    # Data fixtures
    'test_pdf_file',
    'test_user',
    'test_documents',

    # API fixtures
    'api_client',
    'authenticated_api',

    # Database fixtures
    'clean_database',
    'seeded_database',
]