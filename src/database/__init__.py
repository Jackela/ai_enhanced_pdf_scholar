"""
Database Module

This package provides database connectivity, models, and migration utilities
for the AI Enhanced PDF Scholar application.
"""

from .connection import DatabaseConnection
from .models import DocumentModel, VectorIndexModel
from .migrations import DatabaseMigrator

__all__ = [
    'DatabaseConnection',
    'DocumentModel', 
    'VectorIndexModel',
    'DatabaseMigrator'
]