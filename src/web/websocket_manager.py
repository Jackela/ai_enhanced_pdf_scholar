"""
WebSocket Manager - Real-time Communication

This module manages WebSocket connections for real-time updates
between the web frontend and backend controllers.
"""

import logging
import json
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    {
        "name": "WebSocketManager", 
        "version": "1.0.0",
        "description": "Manages WebSocket connections for real-time updates.",
        "dependencies": ["FastAPI"],
        "interface": {
            "inputs": ["WebSocket connections", "broadcast messages"],
            "outputs": "Real-time updates to connected clients"
        }
    }
    
    Manages WebSocket connections and broadcasts real-time updates
    from Controller signals to connected web clients.
    """
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: List[WebSocket] = []
        logger.info("WebSocketManager initialized")
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected WebSocket clients."""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
        
        logger.debug(f"Broadcasted message to {len(self.active_connections)} clients")
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections) 