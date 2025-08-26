"""
Application Configuration

This file contains the configuration settings for the AI Enhanced PDF Scholar application.
It follows a modular approach to keep settings organized and easy to manage.
"""

import os

from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# --- Application Metadata ---
# Used for display purposes, like in the 'About' dialog.
APP_NAME = "AI Enhanced PDF Scholar"
APP_VERSION = "0.1.0"

# --- Web UI Configuration ---
# Default settings for the web interface layout and styling.
UI_SETTINGS = {
    "default_page_title": f"{APP_NAME} v{APP_VERSION}",
    "default_viewport_width": 1200,
    "default_viewport_height": 800,
    "min_viewport_width": 800,
    "min_viewport_height": 600,
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
    "ui_text": {
        "send_button": "Send",
        "sending_button": "Sending...",
        "input_instruction": "(Enter to send)"
    },
    "input_settings": {
        "max_lines": 5,
        "button_size": {"width": 70, "height": 32},
        "font_family": "Segoe UI, Arial, sans-serif"
    },
    "suggestions": {
        "label": "💡 Quick Start:",
        "buttons": [
            "📋 Summarize this document",
            "🔍 Explain key concepts",
            "💡 Help with research",
            "❓ General questions"
        ]
    },
    "empty_state": {
        # Responsive empty state content based on screen size
        "responsive_content": {
            "small": {
                "icon": "🤖",
                "title": "AI Assistant Ready",
                "description": "Start chatting! Try asking:\n• \"Summarize this document\"\n• \"Explain key concepts\"\n• Any general questions"
            },
            "medium": {
                "icon": "🤖",
                "title": "AI Assistant Ready",
                "description": "Start chatting! Try asking:\n• \"Summarize this document\"\n• \"Explain key concepts\"\n• \"Help with research\"\n• Any general questions\n\nYour conversation will appear here!"
            },
            "large": {
                "icon": "🤖",
                "title": "AI Assistant Ready",
                "description": "Welcome! I can help you with:\n\n📄 Document Analysis\n• Summarize content\n• Explain complex concepts\n• Answer specific questions\n\n🧠 General Knowledge\n• Research assistance\n• Explanations on any topic\n• Writing and analysis help\n\nJust type your question below!"
            },
            "xlarge": {
                "icon": "🤖",
                "title": "AI Assistant Ready",
                "description": "Welcome! I'm here to help you with:\n\n📄 Document Analysis\n• Summarize content and key points\n• Explain complex concepts in simple terms\n• Answer specific questions about the text\n• Cross-reference information\n\n🧠 General Knowledge & Research\n• Research assistance on any topic\n• Detailed explanations and analysis\n• Writing and editing help\n• Academic and professional support\n\nYour conversation history will be saved here.\nJust type your question below to get started!"
            }
        },
        # Fallback for older code compatibility
        "icon": "🤖",
        "title": "AI Assistant Ready",
        "description": "Start chatting! Ask about the document or any general questions."
    },
    "colors": {
        # Modern Material Design 3 inspired color palette
        "user_message": {
            "background": "#0078d4",
            "text": "#ffffff",
            "border": "#106ebe"
        },
        "ai_message": {
            "background": "#f8faff",
            "text": "#1a1a1a",
            "border": "#e3ecf7"
        },
        "primary": "#0078d4",
        "secondary": "#106ebe",
        "success": "#00a86b",
        "warning": "#ffaa44",
        "error": "#d83b01",
        # New modern color scheme
        "header": {
            "gradient_start": "#667eea",
            "gradient_end": "#764ba2",
            "text": "#ffffff",
            "accent": "rgba(255, 255, 255, 0.2)"
        },
        "container": {
            "background": "#ffffff",
            "border": "#e8eaed",
            "shadow": "rgba(60, 64, 67, 0.15)",
            "hover": "#f8f9fa"
        },
        "suggestion": {
            "background": "rgba(103, 126, 234, 0.08)",
            "border": "rgba(103, 126, 234, 0.2)",
            "text": "#3c4043",
            "hover_bg": "rgba(103, 126, 234, 0.12)",
            "hover_border": "#667eea",
            "active_bg": "rgba(103, 126, 234, 0.16)"
        },
        "empty_state": {
            "icon_bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "text_primary": "#202124",
            "text_secondary": "#5f6368"
        }
    },
    # New visual design configuration
    "design": {
        "border_radius": {
            "small": 8,
            "medium": 12,
            "large": 16
        },
        "shadows": {
            "light": "0 2px 8px rgba(60, 64, 67, 0.1)",
            "medium": "0 4px 16px rgba(60, 64, 67, 0.15)",
            "heavy": "0 8px 32px rgba(60, 64, 67, 0.2)"
        },
        "animations": {
            "duration": 250,  # milliseconds
            "easing": "ease-out"
        },
        "spacing": {
            "tight": 4,
            "normal": 8,
            "comfortable": 12,
            "spacious": 16
        }
    },
    # Enhanced responsive breakpoints for design elements
    "responsive_design": {
        "small": {
            "header_height": 60,
            "suggestion_columns": 1,
            "max_suggestions": 3
        },
        "medium": {
            "header_height": 70,
            "suggestion_columns": 2,
            "max_suggestions": 4
        },
        "large": {
            "header_height": 80,
            "suggestion_columns": 2,
            "max_suggestions": 4
        },
        "xlarge": {
            "header_height": 90,
            "suggestion_columns": 2,
            "max_suggestions": 4
        }
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

class Config:
    @staticmethod
    def get_gemini_api_key():
        """
        Get Gemini API key from multiple sources (按优先级):
        1. 环境变量 GEMINI_API_KEY
        2. .env文件中的 GEMINI_API_KEY
        3. Web应用设置文件中存储的用户配置

        @returns {string|None} API key or None if not found
        """
        import json
        from pathlib import Path

        # 1. 环境变量
        env_key = os.getenv('GEMINI_API_KEY')
        if env_key and env_key.strip():
            return env_key.strip()

        # 2. 配置文件 (Web UI设置)
        try:
            config_file = Path.home() / ".ai_pdf_scholar" / "settings.json"
            if config_file.exists():
                with open(config_file, encoding='utf-8') as f:
                    settings = json.load(f)
                    api_key = settings.get('gemini_api_key', '')
                    if api_key and api_key.strip():
                        return api_key.strip()
        except Exception:
            pass  # 配置文件不存在或损坏，使用默认值

        return None

    @staticmethod
    def is_api_key_configured():
        """
        Check if API key is configured from any source.

        @returns {boolean} True if API key is available
        """
        return Config.get_gemini_api_key() is not None
