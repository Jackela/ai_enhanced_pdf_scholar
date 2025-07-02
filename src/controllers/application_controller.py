"""
Application Controller - Top-Level Controller for Application Coordination

This controller serves as the main coordinator for the entire application,
managing the lifecycle of all other controllers and services, and handling
cross-cutting concerns like dependency injection and application state.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from PyQt6.QtWidgets import QApplication

from src.core.config_manager import ConfigManager
from src.core.state_manager import StateManager
from src.core.style_manager import StyleManager

from src.services.chat_service import ChatService
from src.services.annotation_service import AnnotationService
from src.services.pdf_service import PDFService

from src.controllers.chat_controller import ChatController
from src.controllers.annotation_controller import AnnotationController
from src.controllers.pdf_controller import PDFController

# LLMService imported locally to avoid circular imports
from src.rag_service import RAGService

logger = logging.getLogger(__name__)


class ApplicationController(QObject):
    """
    {
        "name": "ApplicationController",
        "version": "1.0.0",
        "description": "Top-level application controller for dependency injection and coordination.",
        "dependencies": ["All Services", "All Controllers", "SSOT Infrastructure"],
        "interface": {
            "inputs": ["application_events", "lifecycle_events"],
            "outputs": "Coordinated application behavior"
        }
    }
    
    Main application controller that:
    - Manages dependency injection for all services and controllers
    - Coordinates cross-cutting concerns between controllers
    - Handles application lifecycle events
    - Provides centralized error handling and logging
    """
    
    # Application-level signals
    application_ready = pyqtSignal()
    application_error = pyqtSignal(str)  # error_message
    services_initialized = pyqtSignal()
    controllers_initialized = pyqtSignal()
    
    def __init__(self, settings: QSettings):
        """
        Initialize application controller with Qt settings.
        
        Args:
            settings: Qt application settings
        """
        super().__init__()
        
        self._settings = settings
        
        # SSOT Infrastructure
        self._config_manager: Optional[ConfigManager] = None
        self._state_manager: Optional[StateManager] = None  
        self._style_manager: Optional[StyleManager] = None
        
        # Services
        self._llm_service: Optional[LLMService] = None
        self._rag_service: Optional[RAGService] = None
        self._chat_service: Optional[ChatService] = None
        self._annotation_service: Optional[AnnotationService] = None
        self._pdf_service: Optional[PDFService] = None
        
        # Controllers
        self._chat_controller: Optional[ChatController] = None
        self._annotation_controller: Optional[AnnotationController] = None
        self._pdf_controller: Optional[PDFController] = None
        
        # Application state
        self._initialized = False
        self._services_ready = False
        self._controllers_ready = False
        
        logger.info("ApplicationController created")
    
    def initialize_application(self) -> bool:
        """
        Initialize the entire application stack.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Starting application initialization")
            
            # Step 1: Initialize SSOT Infrastructure
            if not self._initialize_ssot_infrastructure():
                return False
            
            # Step 2: Initialize Services
            if not self._initialize_services():
                return False
            
            # Step 3: Initialize Controllers
            if not self._initialize_controllers():
                return False
            
            # Step 4: Setup cross-controller coordination
            self._setup_controller_coordination()
            
            # Step 5: Load initial application state
            self._load_initial_state()
            
            self._initialized = True
            self.application_ready.emit()
            
            logger.info("Application initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Application initialization failed: {e}")
            self.application_error.emit(f"Initialization failed: {e}")
            return False
    
    def _initialize_ssot_infrastructure(self) -> bool:
        """Initialize SSOT infrastructure components."""
        try:
            logger.info("Initializing SSOT infrastructure")
            
            # Initialize ConfigManager
            self._config_manager = ConfigManager()
            
            # Initialize StateManager
            self._state_manager = StateManager()
            
            # Initialize StyleManager
            self._style_manager = StyleManager(self._config_manager)
            
            logger.info("SSOT infrastructure initialized")
            return True
            
        except Exception as e:
            logger.error(f"SSOT infrastructure initialization failed: {e}")
            return False
    
    def _initialize_services(self) -> bool:
        """Initialize all business logic services."""
        try:
            logger.info("Initializing services")
            
            # Initialize LLMService
            from src.llm_service import GeminiLLMService
            self._llm_service = GeminiLLMService(self._settings)
            
            # Initialize RAGService
            api_key = self._config_manager.get('rag.api_key', '')
            cache_dir = self._config_manager.get('rag.cache_dir', './rag_cache')
            
            if api_key:
                self._rag_service = RAGService(api_key, cache_dir)
            else:
                logger.warning("RAG service not initialized - no API key")
                self._rag_service = None
            
            # Initialize ChatService
            self._chat_service = ChatService(
                llm_service=self._llm_service,
                state_manager=self._state_manager,
                rag_service=self._rag_service
            )
            
            # Initialize AnnotationService
            self._annotation_service = AnnotationService(
                state_manager=self._state_manager
            )
            
            # Initialize PDFService
            self._pdf_service = PDFService(
                state_manager=self._state_manager
            )
            
            self._services_ready = True
            self.services_initialized.emit()
            
            logger.info("Services initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            return False
    
    def _initialize_controllers(self) -> bool:
        """Initialize all UI-Service coordination controllers."""
        try:
            logger.info("Initializing controllers")
            
            # Initialize ChatController
            self._chat_controller = ChatController(
                chat_service=self._chat_service,
                state_manager=self._state_manager,
                config_manager=self._config_manager
            )
            
            # Initialize AnnotationController
            self._annotation_controller = AnnotationController(
                annotation_service=self._annotation_service,
                state_manager=self._state_manager,
                config_manager=self._config_manager
            )
            
            # Initialize PDFController
            self._pdf_controller = PDFController(
                pdf_service=self._pdf_service,
                state_manager=self._state_manager,
                config_manager=self._config_manager
            )
            
            self._controllers_ready = True
            self.controllers_initialized.emit()
            
            logger.info("Controllers initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Controller initialization failed: {e}")
            return False
    
    def _setup_controller_coordination(self) -> None:
        """Setup coordination between controllers for cross-cutting concerns."""
        try:
            logger.info("Setting up controller coordination")
            
            # PDF text selection -> Annotation creation
            self._pdf_controller.text_selected.connect(
                self._annotation_controller.handle_annotation_highlight_request
            )
            
            # Chat AI response -> Annotation enhancement
            self._chat_controller.ai_response_completed.connect(
                self._on_ai_response_for_annotation
            )
            
            # Document loading -> RAG index building
            self._pdf_controller.document_loaded.connect(
                self._on_document_loaded_for_rag
            )
            
            logger.info("Controller coordination setup completed")
            
        except Exception as e:
            logger.error(f"Controller coordination setup failed: {e}")
    
    def _load_initial_state(self) -> None:
        """Load initial application state from persistence."""
        try:
            logger.info("Loading initial application state")
            
            # Load recent documents
            recent_docs = self._settings.value('recent_documents', [])
            self._state_manager.set_state('app.recent_documents', recent_docs)
            
            # Load RAG mode preference
            rag_mode = self._settings.value('rag_mode', False, type=bool)
            self._state_manager.set_state('app.rag_mode', rag_mode)
            
            # Load window geometry if available
            geometry = self._settings.value('window_geometry')
            if geometry:
                self._state_manager.set_state('app.window_geometry', geometry)
            
            logger.info("Initial application state loaded")
            
        except Exception as e:
            logger.error(f"Failed to load initial state: {e}")
    
    def _on_ai_response_for_annotation(self, ai_response: str) -> None:
        """
        Handle AI response that might enhance current annotation.
        
        Args:
            ai_response: AI response text
        """
        # Get current text selection
        selection = self._state_manager.get_state('pdf.selected_text')
        
        if selection and selection.get('text'):
            # Check if we have a pending annotation for this text
            # This is a simplified coordination - in practice, you might want
            # more sophisticated logic to match AI responses to annotations
            logger.debug("AI response available for annotation enhancement")
    
    def _on_document_loaded_for_rag(self, file_path: str, page_count: int) -> None:
        """
        Handle document loading for RAG index building.
        
        Args:
            file_path: Path to loaded document
            page_count: Number of pages in document
        """
        if self._rag_service and self._state_manager.get_state('app.rag_mode', False):
            try:
                logger.info(f"Building RAG index for document: {file_path}")
                # Note: In real implementation, this should be async
                # self._rag_service.build_index(file_path)
                logger.info("RAG index building initiated")
            except Exception as e:
                logger.error(f"Failed to build RAG index: {e}")
    
    # Public API for Main Window
    
    def get_chat_controller(self) -> Optional[ChatController]:
        """Get chat controller instance."""
        return self._chat_controller
    
    def get_annotation_controller(self) -> Optional[AnnotationController]:
        """Get annotation controller instance."""
        return self._annotation_controller
    
    def get_pdf_controller(self) -> Optional[PDFController]:
        """Get PDF controller instance."""
        return self._pdf_controller
    
    def get_config_manager(self) -> Optional[ConfigManager]:
        """Get configuration manager instance."""
        return self._config_manager
    
    def get_state_manager(self) -> Optional[StateManager]:
        """Get state manager instance."""
        return self._state_manager
    
    def get_style_manager(self) -> Optional[StyleManager]:
        """Get style manager instance."""
        return self._style_manager
    
    # Application Lifecycle Management
    
    def handle_application_shutdown(self) -> None:
        """Handle application shutdown cleanup."""
        try:
            logger.info("Starting application shutdown")
            
            # Save application state
            self._save_application_state()
            
            # Cleanup controllers
            if self._chat_controller:
                self._chat_controller.cleanup()
            
            # Cleanup services
            if self._chat_service:
                # Chat service cleanup if needed
                pass
            
            # Cleanup SSOT infrastructure
            if self._state_manager:
                # State manager cleanup if needed
                pass
            
            logger.info("Application shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
    
    def _save_application_state(self) -> None:
        """Save current application state to persistence."""
        try:
            # Save recent documents
            recent_docs = self._state_manager.get_state('app.recent_documents', [])
            self._settings.setValue('recent_documents', recent_docs)
            
            # Save RAG mode
            rag_mode = self._state_manager.get_state('app.rag_mode', False)
            self._settings.setValue('rag_mode', rag_mode)
            
            # Save window geometry
            geometry = self._state_manager.get_state('app.window_geometry')
            if geometry:
                self._settings.setValue('window_geometry', geometry)
            
            self._settings.sync()
            
            logger.info("Application state saved")
            
        except Exception as e:
            logger.error(f"Failed to save application state: {e}")
    
    # Status and Utility Methods
    
    def is_initialized(self) -> bool:
        """Check if application is fully initialized."""
        return self._initialized
    
    def are_services_ready(self) -> bool:
        """Check if all services are ready."""
        return self._services_ready
    
    def are_controllers_ready(self) -> bool:
        """Check if all controllers are ready."""
        return self._controllers_ready
    
    def get_application_status(self) -> Dict[str, Any]:
        """Get current application status."""
        return {
            'initialized': self._initialized,
            'services_ready': self._services_ready,
            'controllers_ready': self._controllers_ready,
            'config_loaded': bool(self._config_manager),
            'state_available': bool(self._state_manager),
            'style_manager_ready': bool(self._style_manager),
            'llm_configured': bool(self._llm_service and self._llm_service.is_configured()),
            'rag_available': bool(self._rag_service)
        } 