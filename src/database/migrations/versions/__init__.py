"""
Migration Versions

Individual migration files organized by version number.

Naming Convention:
- XXX_description.py (e.g., 001_initial_schema.py)
- XXX must be a 3-digit version number
- description should be a snake_case description
- Each file contains one migration class

Example:
- 001_initial_schema.py
- 002_add_content_hash.py  
- 003_add_citation_tables.py
"""

# This file ensures the versions directory is treated as a Python package