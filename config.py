"""
Application Configuration

This file contains the configuration settings for the AI Enhanced PDF Scholar application.
It follows a modular approach to keep settings organized and easy to manage.
"""

import os

# --- Application Metadata ---
# Used for display purposes, like in the 'About' dialog.
APP_NAME = "AI Enhanced PDF Scholar"
APP_VERSION = "0.1.0"

# --- UI Configuration ---
# Default settings for the main application window.
UI_SETTINGS = {
    "default_window_title": f"{APP_NAME} v{APP_VERSION}",
    "default_width": 1200,
    "default_height": 800,
    "min_width": 800,
    "min_height": 600,
}

# --- Responsive Design Configuration ---
# Settings for responsive UI that adapts to different screen sizes
RESPONSIVE_UI = {
    # Screen size breakpoints (width in pixels)
    "breakpoints": {
        "small": 1024,      # Tablets/small laptops
        "medium": 1440,     # Standard laptops
        "large": 1920,      # Desktop monitors
        "xlarge": 2560      # Large displays
    },
    
    # Chat panel responsive settings
    "chat_panel": {
        # Panel width as percentage of total window width
        "width_ratio": {
            "small": 0.35,      # 35% for small screens
            "medium": 0.30,     # 30% for medium screens  
            "large": 0.25,      # 25% for large screens
            "xlarge": 0.20      # 20% for very large screens
        },
        # Minimum and maximum absolute widths (in pixels)
        "min_width": 280,
        "max_width": 500,
        
        # Spacing and padding (responsive)
        "spacing": {
            "small": {"margin": 8, "padding": 12, "item_spacing": 8},
            "medium": {"margin": 12, "padding": 16, "item_spacing": 12},
            "large": {"margin": 16, "padding": 20, "item_spacing": 16},
            "xlarge": {"margin": 20, "padding": 24, "item_spacing": 20}
        }
    },
    
    # Annotations panel responsive settings
    "annotations_panel": {
        # Panel width as percentage of total window width
        "width_ratio": {
            "small": 0.35,      # 35% for small screens
            "medium": 0.30,     # 30% for medium screens  
            "large": 0.25,      # 25% for large screens
            "xlarge": 0.20      # 20% for very large screens
        },
        # Minimum and maximum absolute widths (in pixels)
        "min_width": 280,
        "max_width": 500,
        
        # Spacing and padding (responsive)
        "spacing": {
            "small": {"margin": 8, "padding": 12, "item_spacing": 8},
            "medium": {"margin": 12, "padding": 16, "item_spacing": 12},
            "large": {"margin": 16, "padding": 20, "item_spacing": 16},
            "xlarge": {"margin": 20, "padding": 24, "item_spacing": 20}
        }
    },
    
    # Font sizes (responsive)
    "fonts": {
        "small": {"title": 14, "body": 11, "caption": 9},
        "medium": {"title": 16, "body": 13, "caption": 10},
        "large": {"title": 18, "body": 14, "caption": 11},
        "xlarge": {"title": 20, "body": 15, "caption": 12}
    }
}

# --- AI Chat Configuration ---
AI_CHAT = {
    "panel_title": "💬 AI Chat",
    "input_placeholder": {
        "responsive_content": {
            "small": "Ask AI...",
            "medium": "Ask AI anything...",
            "large": "Ask AI anything about the document...",
            "xlarge": "Ask AI anything about the document or general questions..."
        }
    },
    "empty_state": {
        # Responsive empty state content based on screen size
        "responsive_content": {
            "small": {
                "icon": "🤖",
                "title": "AI Chat",
                "description": "Start a conversation with AI!"
            },
            "medium": {
                "icon": "🤖",
                "title": "AI Chat Assistant",
                "description": "Ask questions about the document or anything else.\nYour conversation will appear here!"
            },
            "large": {
                "icon": "🤖",
                "title": "AI Chat Assistant",
                "description": "Ask questions about the document or anything else.\nYour conversation will appear here!\n\nTip: Try asking for summaries, explanations, or general knowledge."
            },
            "xlarge": {
                "icon": "🤖",
                "title": "Welcome to AI Chat",
                "description": "Start a conversation with your AI assistant!\nAsk questions about the document or anything else.\n\nTip: Try asking for summaries, explanations, or general knowledge.\nAll your conversations will be saved in this panel."
            }
        },
        # Fallback for older code compatibility
        "icon": "🤖",
        "title": "AI Chat Assistant",
        "description": "Start a conversation with your AI assistant!"
    },
    "colors": {
        # Material Design inspired color palette for chat
        "user_message": {
            "background": "#0078d4",
            "text": "#ffffff",
            "border": "#106ebe"
        },
        "ai_message": {
            "background": "#f5f5f5",
            "text": "#333333", 
            "border": "#e0e0e0"
        },
        "primary": "#0078d4",
        "secondary": "#106ebe",
        "success": "#00a86b",
        "warning": "#ffaa44",
        "error": "#d83b01"
    }
}

# --- AI Annotations Configuration ---
AI_ANNOTATIONS = {
    "panel_title": "✨ AI Annotations",
    "empty_state": {
        # Responsive empty state content based on screen size
        "responsive_content": {
            "small": {
                "icon": "🚀",
                "title": "Start AI Chat",
                "description": "Select text → Ask AI questions!"
            },
            "medium": {
                "icon": "🚀",
                "title": "Start Your AI Journey",
                "description": "Select any text in the PDF and ask AI questions to create intelligent annotations!"
            },
            "large": {
                "icon": "🚀",
                "title": "Start Your AI Journey",
                "description": "Select any text in the PDF and ask AI questions to create your first intelligent annotation!\n\nTip: Try asking about explanations, summaries, or deeper insights."
            },
            "xlarge": {
                "icon": "🚀",
                "title": "Welcome to AI-Enhanced PDF Learning",
                "description": "Select any text in the PDF and ask AI questions to create your first intelligent annotation!\n\nTip: Try asking about explanations, summaries, or deeper insights.\nYour annotations will appear here with beautiful formatting."
            }
        },
        # Fallback for older code compatibility
        "icon": "🚀",
        "title": "Start Your AI Journey",
        "description": "Select any text in the PDF and ask AI questions to create your first intelligent annotation!"
    },
    "colors": {
        # Material Design inspired color palette
        "backgrounds": [
            "#E3F2FD", "#F3E5F5", "#E8F5E8", "#FFF3E0",
            "#F9FBE7", "#FCE4EC", "#E0F2F1", "#FFF8E1"
        ],
        "accents": [
            "#1976D2", "#7B1FA2", "#388E3C", "#F57C00",
            "#689F38", "#C2185B", "#00796B", "#FFA000"
        ],
        "primary": "#0078d4",
        "secondary": "#106ebe"
    }
}

# --- PDF Selection Colors Configuration ---
PDF_SELECTION = {
    "text_selection": {
        "fill_color": (100, 150, 255, 60),  # Soft blue-purple, RGBA
        "border_color": None,  # No border for text selection
        "border_width": 0,
        "corner_radius": 3
    },
    "screenshot_selection": {
        "fill_color": (0, 120, 215, 30),    # Light blue fill, RGBA
        "border_color": (0, 120, 215, 160), # Blue border, RGBA  
        "border_width": 2,
        "corner_radius": 1
    }
}

# --- PDF Viewer Configuration ---
# Settings related to PDF rendering and interaction.
PDF_VIEWER_SETTINGS = {
    # Dots Per Inch (DPI) for rendering PDF pages. Higher values result in better quality.
    "rendering_dpi": 150,
}

# --- File and Path Configuration ---
# Defines default paths used by the application.
# It's good practice to use a dedicated directory for application data in the user's home directory.
APP_DATA_PATH = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower().replace(' ', '_')}")
os.makedirs(APP_DATA_PATH, exist_ok=True)  # Ensure the directory exists

FILE_SETTINGS = {
    # Path to the settings file where user preferences (like window size) are stored.
    "settings_file_path": os.path.join(APP_DATA_PATH, "settings.ini"),
    # Path for storing application logs.
    "log_file_path": os.path.join(APP_DATA_PATH, "app.log"),
    # Maximum number of recent files to remember and display.
    "max_recent_files": 10,
}

# --- Logging Configuration ---
# Basic configuration for application-wide logging.
LOGGING_CONFIG = {
    "level": "INFO",  # Logging level, e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# --- AI Feature Configuration ---
# Configuration for any AI-powered features, such as summarization or analysis.
AI_FEATURE_SETTINGS = {
    # Environment variable name where API key should be stored (for development/testing).
    # In production, users configure their API keys through the Settings dialog.
    "api_key_env_variable": "GEMINI_API_KEY",
    # Default model for processing text.
    "model": "gemini-2.5-flash",
    # Timeout in seconds for API requests.
    "timeout": 60,
} 