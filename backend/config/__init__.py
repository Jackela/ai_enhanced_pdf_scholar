"""
Unified Configuration Management System

This module provides a centralized configuration system that replaces
scattered configuration files with a cohesive, type-safe configuration
management approach.

Key benefits:
- Single source of truth for all configuration
- Environment-specific configuration with validation
- Type safety and documentation for all settings
- Reduced configuration drift and inconsistencies
- Easy testing with configuration overrides
"""

from .application_config import ApplicationConfig, get_application_config
from .environment import Environment, get_current_environment
from .validation import ConfigValidationError

__all__ = [
    "ApplicationConfig",
    "get_application_config",
    "Environment",
    "get_current_environment",
    "ConfigValidationError",
]
