"""
Unified Configuration Manager

This module provides a centralized configuration management system that implements
the Single Source of Truth (SSOT) principle for all application configuration.

Configuration Priority (highest to lowest):
1. Runtime configuration (temporary overrides)
2. User settings (QSettings persistent storage)
3. Default configuration (from config.py)
"""

import logging
from typing import Any, Dict, List, Callable, Optional
from PyQt6.QtCore import QSettings

import config

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    {
        "name": "ConfigManager",
        "version": "1.0.0", 
        "description": "Unified configuration management implementing SSOT principle with hierarchical precedence.",
        "dependencies": ["PyQt6.QtCore", "config"],
        "interface": {
            "inputs": ["key: str", "value: Any", "persist: bool"],
            "outputs": "Unified configuration access with observer pattern"
        }
    }
    
    Singleton configuration manager that provides unified access to all application
    configuration with clear precedence rules and change notification system.
    """
    
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls) -> 'ConfigManager':
        """Ensure singleton pattern for global configuration access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration manager with SSOT hierarchy."""
        if hasattr(self, '_initialized'):
            return
            
        # Configuration storage layers (priority order)
        self._settings = QSettings(config.APP_NAME, "Settings")
        self._default_config = self._load_from_config_py()
        self._runtime_config: Dict[str, Any] = {}
        
        # Observer pattern for configuration changes
        self._observers: List[Callable[[str, Any], None]] = []
        
        self._initialized = True
        logger.info(f"ConfigManager initialized with organization: '{self._settings.organizationName()}', application: '{self._settings.applicationName()}'")
    
    def _load_from_config_py(self) -> Dict[str, Any]:
        """Load default configuration from config.py module."""
        try:
            default_config = {
                "app": {
                    "name": getattr(config, 'APP_NAME', 'AI Enhanced PDF Scholar'),
                    "version": getattr(config, 'APP_VERSION', '0.1.0')
                },
                "ui": getattr(config, 'UI_SETTINGS', {}),
                "responsive": getattr(config, 'RESPONSIVE_UI', {}),
                "chat": getattr(config, 'AI_CHAT', {}),
                "annotations": getattr(config, 'AI_ANNOTATIONS', {}),
                "llm": {
                    "model_name": "gemini-2.5-flash",
                    "timeout": 30
                },
                "rag": {
                    "enabled": True,
                    "cache_dir": "./rag_cache",
                    "chunk_size": 1000
                }
            }
            logger.info("Default configuration loaded from config.py")
            return default_config
        except Exception as e:
            logger.error(f"Failed to load default configuration: {e}")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with hierarchical precedence.
        
        Priority: runtime > user_settings > default_config > provided_default
        
        Args:
            key: Dot-separated configuration key (e.g., 'chat.panel.title')
            default: Fallback value if key not found
            
        Returns:
            Configuration value from highest priority source
        """
        # Check runtime configuration first (highest priority)
        if key in self._runtime_config:
            return self._runtime_config[key]
        
        # Check user settings (QSettings) 
        if self._settings.contains(key):
            return self._settings.value(key)
        
        # Check default configuration with nested key support
        default_value = self._get_nested_value(self._default_config, key)
        if default_value is not None:
            return default_value
        
        # Return provided default as last resort
        return default
    
    def set(self, key: str, value: Any, persist: bool = False) -> None:
        """
        Set configuration value with optional persistence.
        
        Args:
            key: Configuration key to set
            value: Value to set
            persist: If True, save to QSettings; if False, store in runtime only
        """
        if persist:
            self._settings.setValue(key, value)
            logger.debug(f"Persisted config: {key} = {value}")
        else:
            self._runtime_config[key] = value
            logger.debug(f"Runtime config: {key} = {value}")
        
        # Notify observers of configuration change
        self._notify_observers(key, value)
    
    def _get_nested_value(self, config_dict: Dict[str, Any], key: str) -> Any:
        """
        Get value from nested dictionary using dot notation.
        
        Args:
            config_dict: Dictionary to search
            key: Dot-separated key (e.g., 'chat.panel.title')
            
        Returns:
            Value if found, None otherwise
        """
        try:
            keys = key.split('.')
            current = config_dict
            
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return None
            
            return current
        except Exception as e:
            logger.debug(f"Failed to get nested value for key '{key}': {e}")
            return None
    
    def get_style_config(self, component: str, breakpoint: str = None) -> Dict[str, Any]:
        """
        Get component style configuration for specified breakpoint.
        
        Args:
            component: Component name (e.g., 'chat_panel', 'chat_input')
            breakpoint: Screen size breakpoint (e.g., 'small', 'medium', 'large')
            
        Returns:
            Style configuration dictionary for the component/breakpoint
        """
        if not breakpoint:
            breakpoint = self.get('current_breakpoint', 'medium')
        
        style_path = f'chat.design'
        base_styles = self.get(style_path, {})
        
        # Get component-specific styles
        component_path = f'chat.colors'
        component_styles = self.get(component_path, {})
        
        # Get responsive styles
        responsive_path = f'chat.responsive_design.{breakpoint}'
        responsive_styles = self.get(responsive_path, {})
        
        # Merge all style configurations
        merged_config = {
            **base_styles,
            **component_styles,
            **responsive_styles
        }
        
        logger.debug(f"Style config for {component}@{breakpoint}: {len(merged_config)} properties")
        return merged_config
    
    def subscribe(self, callback: Callable[[str, Any], None]) -> None:
        """
        Subscribe to configuration changes.
        
        Args:
            callback: Function to call when configuration changes (key, value)
        """
        self._observers.append(callback)
        logger.debug(f"Added configuration observer: {callback.__name__}")
    
    def unsubscribe(self, callback: Callable[[str, Any], None]) -> None:
        """
        Unsubscribe from configuration changes.
        
        Args:
            callback: Function to remove from observers
        """
        if callback in self._observers:
            self._observers.remove(callback)
            logger.debug(f"Removed configuration observer: {callback.__name__}")
    
    def _notify_observers(self, key: str, value: Any) -> None:
        """
        Notify all observers of configuration change.
        
        Args:
            key: Configuration key that changed
            value: New value
        """
        for observer in self._observers:
            try:
                observer(key, value)
            except Exception as e:
                logger.error(f"Error notifying observer {observer.__name__}: {e}")
    
    def get_all_keys(self) -> List[str]:
        """Get all available configuration keys from all sources."""
        keys = set()
        
        # Runtime keys
        keys.update(self._runtime_config.keys())
        
        # QSettings keys
        keys.update(self._settings.allKeys())
        
        # Default config keys (flatten nested structure)
        def flatten_keys(d, prefix=''):
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key
                keys.add(full_key)
                if isinstance(value, dict):
                    flatten_keys(value, full_key)
        
        flatten_keys(self._default_config)
        
        return sorted(list(keys))
    
    def reset_to_defaults(self) -> None:
        """Reset all configuration to default values."""
        self._runtime_config.clear()
        self._settings.clear()
        logger.info("Configuration reset to defaults")
        
        # Notify observers of reset
        for observer in self._observers:
            try:
                observer("__reset__", None)
            except Exception as e:
                logger.error(f"Error notifying observer of reset: {e}")
    
    def export_config(self) -> Dict[str, Any]:
        """Export current effective configuration for debugging."""
        exported = {}
        
        # Get all unique keys
        all_keys = self.get_all_keys()
        
        # Export effective values
        for key in all_keys:
            exported[key] = self.get(key)
        
        logger.info(f"Exported {len(exported)} configuration keys")
        return exported 