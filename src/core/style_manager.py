"""
Unified Style Manager

This module provides centralized style management with template compilation
to eliminate CSS code duplication and enable responsive design.

Key Features:
- Template-based CSS generation with variable substitution
- Style caching for performance optimization
- Responsive design integration with ConfigManager
- Component-specific style compilation
"""

import logging
from typing import Dict, Any, Optional, List
from string import Template

from .config_manager import ConfigManager
from .style_templates import STYLE_TEMPLATES

logger = logging.getLogger(__name__)


class StyleManager:
    """
    {
        "name": "StyleManager",
        "version": "1.0.0",
        "description": "Centralized style management with template compilation and caching for consistent UI theming.",
        "dependencies": ["ConfigManager", "style_templates"],
        "interface": {
            "inputs": ["component: str", "variables: dict"],
            "outputs": "Compiled CSS stylesheet string"
        }
    }
    
    Unified style manager that compiles CSS templates with configuration variables
    to provide consistent, responsive styling across all UI components.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize style manager with configuration dependency.
        
        Args:
            config_manager: ConfigManager instance for accessing style variables
        """
        self._config = config_manager
        self._style_cache: Dict[str, str] = {}
        self._template_cache: Dict[str, Template] = {}
        
        # Subscribe to configuration changes to clear cache
        self._config.subscribe(self._on_config_changed)
        
        logger.info("StyleManager initialized with template caching")
    
    def get_component_style(self, component: str, **override_vars) -> str:
        """
        Get compiled CSS style for a component with optional variable overrides.
        
        Args:
            component: Component name (must exist in STYLE_TEMPLATES)
            **override_vars: Additional variables to override defaults
            
        Returns:
            Compiled CSS stylesheet string
            
        Raises:
            ValueError: If component template not found
        """
        if component not in STYLE_TEMPLATES:
            available = list(STYLE_TEMPLATES.keys())
            raise ValueError(f"Unknown component '{component}'. Available: {available}")
        
        # Create cache key from component and variables
        cache_key = self._create_cache_key(component, override_vars)
        
        # Return cached style if available
        if cache_key in self._style_cache:
            logger.debug(f"Cache hit for component '{component}'")
            return self._style_cache[cache_key]
        
        # Compile new style
        compiled_style = self._compile_style(component, override_vars)
        
        # Cache compiled style
        self._style_cache[cache_key] = compiled_style
        
        logger.debug(f"Compiled and cached style for component '{component}' ({len(compiled_style)} chars)")
        return compiled_style
    
    def _compile_style(self, component: str, override_vars: Dict[str, Any]) -> str:
        """
        Compile CSS template with configuration variables.
        
        Args:
            component: Component name
            override_vars: Variable overrides
            
        Returns:
            Compiled CSS string
        """
        try:
            # Get template (cached)
            template = self._get_template(component)
            
            # Get base variables from configuration
            base_vars = self._get_component_variables(component)
            
            # Merge with overrides
            variables = {**base_vars, **override_vars}
            
            # Compile template
            compiled = template.safe_substitute(variables)
            
            # Log any missing variables for debugging
            missing_vars = template.get_identifiers() - set(variables.keys())
            if missing_vars:
                logger.warning(f"Missing variables for {component}: {missing_vars}")
            
            return compiled
            
        except Exception as e:
            logger.error(f"Failed to compile style for {component}: {e}")
            return f"/* Error compiling style for {component}: {e} */"
    
    def _get_template(self, component: str) -> Template:
        """
        Get cached template for component.
        
        Args:
            component: Component name
            
        Returns:
            Compiled Template object
        """
        if component not in self._template_cache:
            template_str = STYLE_TEMPLATES[component]
            self._template_cache[component] = Template(template_str)
        
        return self._template_cache[component]
    
    def _get_component_variables(self, component: str) -> Dict[str, Any]:
        """
        Get default variables for component from configuration.
        
        Args:
            component: Component name
            
        Returns:
            Dictionary of style variables with defaults
        """
        # Get current breakpoint for responsive design
        current_breakpoint = self._config.get('current_breakpoint', 'medium')
        
        # Base variables from configuration
        variables = {}
        
        # Add responsive variables
        responsive_config = self._config.get(f'responsive.{current_breakpoint}', {})
        variables.update(responsive_config)
        
        # Add component-specific style configuration
        style_config = self._config.get_style_config(component, current_breakpoint)
        variables.update(style_config)
        
        # Add default values for common variables
        defaults = self._get_default_variables(component, current_breakpoint)
        for key, value in defaults.items():
            if key not in variables:
                variables[key] = value
        
        return variables
    
    def _get_default_variables(self, component: str, breakpoint: str) -> Dict[str, Any]:
        """
        Get default variable values for components to prevent template errors.
        
        Args:
            component: Component name
            breakpoint: Current responsive breakpoint
            
        Returns:
            Dictionary of default variables
        """
        # Base responsive values
        size_multiplier = {
            'small': 0.8,
            'medium': 1.0,
            'large': 1.2,
            'xlarge': 1.4
        }.get(breakpoint, 1.0)
        
        return {
            # Colors
            'gradient_start': '#667eea',
            'gradient_end': '#764ba2',
            'header_text_color': '#ffffff',
            'button_bg_color': '#0078d4',
            'button_text_color': '#ffffff',
            'button_hover_bg_color': '#106ebe',
            'button_pressed_bg_color': '#005a9e',
            'button_disabled_bg_color': '#cccccc',
            'button_disabled_text_color': '#666666',
            'input_bg_color': '#ffffff',
            'input_text_color': '#333333',
            'input_border_color': '#e0e0e0',
            'input_focus_border_color': '#667eea',
            'input_focus_bg_color': '#ffffff',
            'suggestion_bg_color': 'rgba(103, 126, 234, 0.08)',
            'suggestion_text_color': '#3c4043',
            'suggestion_border_color': 'rgba(103, 126, 234, 0.2)',
            'suggestion_hover_bg_color': 'rgba(103, 126, 234, 0.12)',
            'suggestion_hover_border_color': '#667eea',
            'user_bg_color': '#0078d4',
            'user_text_color': '#ffffff',
            'user_border_color': '#106ebe',
            'ai_bg_color': '#f8faff',
            'ai_text_color': '#1a1a1a',
            'ai_border_color': '#e3ecf7',
            'empty_text_color': '#5f6368',
            'empty_icon_color': '#ffffff',
            'empty_icon_bg': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            'empty_title_color': '#202124',
            'empty_desc_color': '#5f6368',
            'timestamp_color': '#888888',
            'loading_bg_color': 'rgba(255, 255, 255, 0.95)',
            'loading_text_color': '#333333',
            'loading_border_color': '#e0e0e0',
            
            # Fonts
            'input_font_family': 'Segoe UI, Arial, sans-serif',
            
            # Sizes (responsive)
            'border_radius': int(8 * size_multiplier),
            'header_border_radius': int(6 * size_multiplier),
            'button_border_radius': int(6 * size_multiplier),
            'suggestion_border_radius': int(8 * size_multiplier),
            'input_border_radius': int(6 * size_multiplier),
            'user_border_radius': int(12 * size_multiplier),
            'ai_border_radius': int(12 * size_multiplier),
            'empty_icon_radius': int(40 * size_multiplier),
            'loading_border_radius': int(8 * size_multiplier),
            
            # Padding (responsive)
            'padding': int(16 * size_multiplier),
            'margin': int(8 * size_multiplier),
            'header_padding': int(12 * size_multiplier),
            'button_padding': '8px 16px',
            'suggestion_padding': '8px 12px',
            'suggestion_margin': int(4 * size_multiplier),
            'input_padding': int(10 * size_multiplier),
            'input_focus_padding': int(9 * size_multiplier),
            'user_padding': int(12 * size_multiplier),
            'user_margin': '4px 20px 4px 40px',
            'ai_padding': int(12 * size_multiplier),
            'ai_margin': '4px 40px 4px 20px',
            'message_padding': int(8 * size_multiplier),
            'message_margin': int(4 * size_multiplier),
            'empty_padding': int(20 * size_multiplier),
            'empty_icon_padding': int(20 * size_multiplier),
            'container_padding': int(8 * size_multiplier),
            'container_margin': int(4 * size_multiplier),
            'loading_padding': int(16 * size_multiplier),
            
            # Font sizes (responsive)
            'header_font_size': int(16 * size_multiplier),
            'button_font_size': int(12 * size_multiplier),
            'suggestion_font_size': int(11 * size_multiplier),
            'input_font_size': int(13 * size_multiplier),
            'message_font_size': int(13 * size_multiplier),
            'timestamp_font_size': int(10 * size_multiplier),
            'empty_icon_size': int(48 * size_multiplier),
            'empty_title_size': int(18 * size_multiplier),
            'empty_desc_size': int(13 * size_multiplier),
            'loading_font_size': int(12 * size_multiplier),
            
            # Borders
            'input_border_width': 1,
            'input_focus_border_width': 2,
            'suggestion_border_width': 1,
            'user_border_width': 1,
            'ai_border_width': 1,
            'loading_border_width': 1,
            
            # Other dimensions
            'button_min_width': int(70 * size_multiplier),
            'spinner_size': int(20 * size_multiplier)
        }
    
    def _create_cache_key(self, component: str, override_vars: Dict[str, Any]) -> str:
        """
        Create cache key for component and variables.
        
        Args:
            component: Component name
            override_vars: Variable overrides
            
        Returns:
            Unique cache key string
        """
        # Include current breakpoint in cache key
        breakpoint = self._config.get('current_breakpoint', 'medium')
        var_hash = hash(str(sorted(override_vars.items())))
        return f"{component}_{breakpoint}_{var_hash}"
    
    def _on_config_changed(self, key: str, value: Any) -> None:
        """
        Handle configuration changes by clearing relevant cache entries.
        
        Args:
            key: Configuration key that changed
            value: New value
        """
        # Clear cache if style-related configuration changed
        if any(keyword in key for keyword in ['style', 'color', 'font', 'breakpoint', 'responsive']):
            self.clear_cache()
            logger.debug(f"Cleared style cache due to config change: {key}")
    
    def clear_cache(self) -> None:
        """Clear all cached styles to force recompilation."""
        self._style_cache.clear()
        logger.debug("Style cache cleared")
    
    def get_available_components(self) -> List[str]:
        """Get list of available component templates."""
        return list(STYLE_TEMPLATES.keys())
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for monitoring."""
        return {
            'style_cache_size': len(self._style_cache),
            'template_cache_size': len(self._template_cache),
            'available_templates': len(STYLE_TEMPLATES)
        } 