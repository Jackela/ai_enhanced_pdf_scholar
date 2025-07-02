"""
Web UI Module - Web Interface for AI Enhanced PDF Scholar

This module provides the web-based user interface for the AI Enhanced PDF Scholar,
built on top of the existing Service and Controller layers for complete UI framework independence.

Architecture:
- FastAPI backend exposing Controller interfaces as REST APIs
- Modern HTML5/CSS3/JavaScript frontend
- Real-time updates via WebSocket
- Responsive design optimized for all devices
"""

from .api_server import APIServer
from .websocket_manager import WebSocketManager

__all__ = [
    'APIServer',
    'WebSocketManager'
] 