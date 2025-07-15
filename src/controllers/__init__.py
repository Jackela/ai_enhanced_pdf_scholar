"""
Controllers Module - Web API Controllers

This module provides Controller classes for the Web-based PDF Scholar platform.
Controllers act as intermediaries between the FastAPI endpoints and business logic services.

Architecture Principles:
- Controllers handle HTTP requests and coordinate service calls
- API endpoints remain thin routing layer
- Services remain pure business logic layer
- Controllers manage dependency injection and response formatting
"""

from .library_controller import LibraryController

__all__ = ["LibraryController"]
