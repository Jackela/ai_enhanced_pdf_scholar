"""
FastAPI Server - REST API Interface for Controllers

This module provides a FastAPI-based REST API server that exposes
the existing Controller interfaces as web endpoints.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.controllers.application_controller import ApplicationController
from src.web.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


# Pydantic Models
class ChatMessageRequest(BaseModel):
    message: str
    use_rag: bool = False

class APIResponse(BaseModel):
    success: bool
    data: Any = None
    error: str = None


class APIServer:
    """FastAPI server exposing Controller interfaces as REST APIs."""
    
    def __init__(self, app_controller: ApplicationController, host: str = "localhost", port: int = 8000):
        self.app_controller = app_controller
        self.host = host
        self.port = port
        
        self.app = FastAPI(
            title="AI Enhanced PDF Scholar API",
            description="REST API for AI-powered PDF analysis",
            version="1.0.0"
        )
        
        self.ws_manager = WebSocketManager()
        self._setup_middleware()
        self._setup_routes()
        
        logger.info(f"APIServer initialized on {host}:{port}")
    
    def _setup_middleware(self):
        """Setup CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/")
        async def root():
            # Serve static HTML file
            from pathlib import Path
            static_dir = Path(__file__).parent / "static"
            html_file = static_dir / "index.html"
            if html_file.exists():
                return FileResponse(html_file)
            return {"message": "AI Enhanced PDF Scholar Web API", "status": "running"}
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "service": "AI Enhanced PDF Scholar"}
        
        @self.app.get("/api/status")
        async def get_status():
            try:
                status = self.app_controller.get_application_status()
                return APIResponse(success=True, data=status)
            except Exception as e:
                logger.error(f"Error getting status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/chat")
        async def send_chat_message(request: ChatMessageRequest):
            try:
                chat_controller = self.app_controller.get_chat_controller()
                if not chat_controller:
                    raise HTTPException(status_code=503, detail="Chat service not available")
                
                chat_controller.handle_user_message(request.message)
                return APIResponse(success=True, data={"message": "Message received", "response": "Processing..."})
            except Exception as e:
                logger.error(f"Error sending chat message: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/chat/message")
        async def send_chat_message_alt(request: ChatMessageRequest):
            """Alternative endpoint for chat messages."""
            return await send_chat_message(request)
        
        @self.app.post("/api/pdf/upload")
        async def upload_pdf(file: UploadFile = File(...)):
            try:
                if not file.filename.endswith('.pdf'):
                    raise HTTPException(status_code=400, detail="Only PDF files are allowed")
                
                pdf_controller = self.app_controller.get_pdf_controller()
                if not pdf_controller:
                    raise HTTPException(status_code=503, detail="PDF service not available")
                
                # For testing, just return success without actually processing
                return APIResponse(success=True, data={
                    "filename": file.filename,
                    "size": file.size,
                    "message": "PDF upload endpoint is working"
                })
            except Exception as e:
                logger.error(f"Error uploading PDF: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await websocket.send_text(f"Echo: {data}")
            except WebSocketDisconnect:
                self.ws_manager.disconnect(websocket)
    
    async def start_server(self):
        """Start the FastAPI server."""
        import uvicorn
        
        logger.info(f"Starting API server on {self.host}:{self.port}")
        
        if not self.app_controller.is_initialized():
            success = self.app_controller.initialize_application()
            if not success:
                raise RuntimeError("Failed to initialize application controller")
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self):
        """Run the server."""
        import asyncio
        asyncio.run(self.start_server()) 