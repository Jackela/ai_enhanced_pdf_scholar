"""
Core Architecture Components

This package contains the fundamental architecture components that implement
SSOT (Single Source of Truth) principles for the AI Enhanced PDF Scholar.

Key Components:
- ConfigManager: Unified configuration management with hierarchical precedence
- StyleManager: Centralized style compilation and template management
- StateManager: Global application state management with observer pattern
"""

from .config_manager import ConfigManager
from .style_manager import StyleManager
from .state_manager import StateManager

__all__ = ['ConfigManager', 'StyleManager', 'StateManager'] 