import sys
import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog,
    QSizePolicy, QHBoxLayout, QMessageBox, QStatusBar, QToolBar, QScrollArea, QLabel, QFrame
)
from PyQt6.QtCore import QSettings, QRectF, Qt
from PyQt6.QtGui import QImage, QAction, QIcon, QResizeEvent
import fitz
import config

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import refactored and new components
from src.pdf_viewer import PDFViewer, SelectionMode
from src.settings_dialog import SettingsDialog
from src.llm_service import (
    LLMService, GeminiLLMService, LLMServiceError, 
    LLMConfigurationError, LLMAPIError, LLMResponseError
)
from src.llm_worker import LLMWorker
from src.inquiry_popup import InquiryPopup
from src.annotation_manager import AnnotationManager
from src.loading_indicator import LoadingIndicator
from src.responsive_utils import responsive_calc
from src.chat_panel import ChatPanel

class MainWindow(QMainWindow):
    """
    The main application window, acting as the central orchestrator (Controller).
    It initializes all sub-components and connects their signals and slots
    to manage the application's workflow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-Enhanced PDF Scholar")
        
        # Set modern window geometry and center on screen
        self._setup_window_geometry()

        # --- Core Components Initialization ---
        # Use consistent QSettings configuration with settings_dialog.py
        self.settings = QSettings(config.APP_NAME, "Settings")
        logger.info(f"Initialized QSettings with organization: '{self.settings.organizationName()}', application: '{self.settings.applicationName()}'")
        
        self.llm_service: LLMService = GeminiLLMService(self.settings)
        
        self.pdf_viewer = PDFViewer(self)
        
        # Create a single loading indicator instance for the whole application
        self.loading_indicator = LoadingIndicator(self)
        
        # Store the last query position for loading indicator
        self.last_query_position = None
        self.current_selected_text = ""  # Store selected text for annotations
        
        # Query state management for debouncing
        self.is_querying = False
        self.llm_worker = None

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # -- Toolbar --
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        
        # -- UI Components --
        self._setup_ui()
        
        # Initialize annotation manager AFTER UI setup (needs panel components)
        self.annotation_manager = AnnotationManager(
            self.pdf_viewer, 
            self.annotations_layout, 
            self.empty_message
        )
        
        # Connect chat panel signals
        self._connect_chat_signals()
        
        # -- Actions --
        self.setup_actions()
        
        self._connect_signals()

    def _connect_chat_signals(self):
        """Connect chat panel signals to main window handlers."""
        if hasattr(self, 'chat_widget') and self.chat_widget:
            # Connect user message signal to AI processing
            self.chat_widget.ai_response_requested.connect(self.handle_chat_query)
            
            # Connect chat cleared signal
            self.chat_widget.chat_cleared.connect(self.on_chat_cleared)
            
            logger.info("Chat panel signals connected")

    def _setup_window_geometry(self):
        """Setup modern window geometry with screen centering."""
        # Get screen geometry
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            
            # Calculate optimal window size (80% of screen size)
            window_width = min(1400, int(screen_geometry.width() * 0.8))
            window_height = min(900, int(screen_geometry.height() * 0.8))
            
            # Calculate center position
            x = screen_geometry.center().x() - window_width // 2
            y = screen_geometry.center().y() - window_height // 2
            
            # Ensure window stays within screen bounds
            x = max(screen_geometry.left(), min(x, screen_geometry.right() - window_width))
            y = max(screen_geometry.top(), min(y, screen_geometry.bottom() - window_height))
            
            self.setGeometry(x, y, window_width, window_height)
            logger.info(f"Window centered at ({x}, {y}) with size {window_width}x{window_height}")
        else:
            # Fallback if screen detection fails
            self.setGeometry(100, 100, 1400, 900)
            logger.warning("Could not detect screen, using fallback geometry")
        
        # Set minimum size for usability
        self.setMinimumSize(config.UI_SETTINGS["min_width"], config.UI_SETTINGS["min_height"])

    def _setup_ui(self):
        # --- Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Modern Toolbar ---
        toolbar_layout = QHBoxLayout()
        
        # Create modern styled buttons
        btn_open = QPushButton("📂 Open PDF")
        btn_settings = QPushButton("⚙️ Settings")
        
        # Apply modern button styling
        button_style = """
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #106ebe;
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background-color: #005a9e;
                transform: translateY(0px);
            }
        """
        btn_open.setStyleSheet(button_style)
        btn_settings.setStyleSheet(button_style)
        
        toolbar_layout.addWidget(btn_open)
        toolbar_layout.addWidget(btn_settings)
        toolbar_layout.addStretch()
        
        # App title with modern styling
        title_label = QLabel("AI Enhanced PDF Scholar")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #323130;
                margin: 0px 20px;
            }
        """)
        toolbar_layout.addWidget(title_label)
        
        # --- Connections for Toolbar Buttons ---
        btn_open.clicked.connect(self.open_pdf)
        btn_settings.clicked.connect(self.open_settings)

        main_layout.addLayout(toolbar_layout)
        
        # --- Content Area: Chat Panel + PDF Viewer + Annotations Panel ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)
        
        # Chat Panel (left side)
        self.chat_panel = self.create_chat_panel()
        content_layout.addWidget(self.chat_panel, 1)  # 1/5 of the width
        
        # PDF Viewer (center, takes most of the space)
        self.pdf_viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(self.pdf_viewer, 3)  # 3/5 of the width
        
        # Annotations Panel (right side)
        self.annotations_panel = self.create_annotations_panel()
        content_layout.addWidget(self.annotations_panel, 1)  # 1/5 of the width
        
        main_layout.addLayout(content_layout)
        
        # --- Modern Status Bar ---
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
                color: #495057;
                font-size: 11px;
            }
        """)
        self.statusBar().showMessage("Ready. Please open a PDF file to begin AI-enhanced annotation.")

    def create_annotations_panel(self):
        """Create the modern responsive right-side annotations panel."""
        # Main panel frame with responsive styling
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        # Set responsive width based on current window size
        self._update_panel_dimensions(panel)
        
        # Apply responsive styling
        panel.setStyleSheet(responsive_calc.get_panel_style_template())
        
        # Get responsive spacing configuration
        spacing_config = responsive_calc.get_spacing_config()
        
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            spacing_config["padding"], 
            spacing_config["margin"], 
            spacing_config["padding"], 
            spacing_config["margin"]
        )
        
        # Responsive panel title with icon
        title_label = QLabel(responsive_calc.get_panel_title())
        title_style = responsive_calc.create_responsive_style(
            responsive_calc.get_title_style_template()
        )
        title_label.setStyleSheet(title_style)
        panel_layout.addWidget(title_label)
        
        # Scrollable area for annotations with responsive styling
        self.annotations_scroll = QScrollArea()
        self.annotations_scroll.setWidgetResizable(True)
        self.annotations_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.annotations_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.annotations_scroll.setStyleSheet(responsive_calc.get_scroll_area_style_template())
        
        # Container widget for annotations
        self.annotations_container = QWidget()
        self.annotations_layout = QVBoxLayout(self.annotations_container)
        self.annotations_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.annotations_layout.setSpacing(spacing_config["item_spacing"])
        self.annotations_layout.setContentsMargins(
            spacing_config["margin"]//2, 
            spacing_config["margin"]//2, 
            spacing_config["margin"]//2, 
            spacing_config["margin"]//2
        )
        
        # Responsive empty state message - dynamically updated based on screen size
        empty_state_config = responsive_calc.get_empty_state_config()
        empty_text = f"{empty_state_config['icon']} {empty_state_config['title']}\n\n{empty_state_config['description']}"
        
        self.empty_message = QLabel(empty_text)
        self.empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message.setWordWrap(True)  # Enable word wrapping for responsive text
        empty_style = responsive_calc.create_responsive_style(
            responsive_calc.get_empty_state_style_template()
        )
        self.empty_message.setStyleSheet(empty_style)
        self.annotations_layout.addWidget(self.empty_message)
        
        self.annotations_scroll.setWidget(self.annotations_container)
        panel_layout.addWidget(self.annotations_scroll)
        
        # Store panel reference for responsive updates
        self.annotations_panel_widget = panel
        
        return panel

    def create_chat_panel(self):
        """Create the left-side chat panel."""
        # Main panel frame with responsive styling
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        # Set responsive width based on current window size
        self._update_chat_panel_dimensions(panel)
        
        # Apply responsive styling for chat panel
        panel_style = responsive_calc.create_responsive_style(
            responsive_calc.get_chat_panel_style_template()
        )
        panel.setStyleSheet(panel_style)
        
        # Panel layout
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        
        # Create chat panel widget
        self.chat_widget = ChatPanel()
        panel_layout.addWidget(self.chat_widget)
        
        # Store panel reference for responsive updates
        self.chat_panel_widget = panel
        
        return panel

    def _update_chat_panel_dimensions(self, panel=None):
        """Update chat panel dimensions based on current window size."""
        if panel is None:
            panel = getattr(self, 'chat_panel_widget', None)
        
        if panel is not None:
            # Calculate responsive width
            current_width = self.width()
            optimal_width = responsive_calc.get_chat_panel_width(current_width)
            
            # Apply responsive dimensions
            panel_config = responsive_calc.config["chat_panel"]
            panel.setMinimumWidth(panel_config["min_width"])
            panel.setMaximumWidth(panel_config["max_width"])
            panel.setFixedWidth(optimal_width)
            
            logger.debug(f"Updated chat panel width to {optimal_width}px (window: {current_width}px)")

    def _update_panel_dimensions(self, panel=None):
        """Update annotations panel dimensions based on current window size."""
        if panel is None:
            panel = getattr(self, 'annotations_panel_widget', None)
        
        if panel is not None:
            # Calculate responsive width
            current_width = self.width()
            optimal_width = responsive_calc.get_annotations_panel_width(current_width)
            
            # Apply responsive dimensions
            panel_config = responsive_calc.config["annotations_panel"]
            panel.setMinimumWidth(panel_config["min_width"])
            panel.setMaximumWidth(panel_config["max_width"])
            panel.setFixedWidth(optimal_width)
            
            logger.debug(f"Updated panel width to {optimal_width}px (window: {current_width}px)")
    
    def resizeEvent(self, event: QResizeEvent):
        """Handle window resize events to update responsive UI."""
        super().resizeEvent(event)
        
        # Update responsive calculations
        responsive_calc.refresh()
        
        # Update both panel dimensions
        self._update_chat_panel_dimensions()
        self._update_panel_dimensions()
        
        # Update empty state message styling for new responsive values
        self._update_empty_state_styling()
        
        # Log resize event for debugging
        new_size = event.size()
        logger.debug(f"Window resized to {new_size.width()}x{new_size.height()}")

    def _update_empty_state_styling(self):
        """Update empty state message styling and content with current responsive values."""
        if hasattr(self, 'empty_message') and self.empty_message:
            # Update responsive content based on current breakpoint
            empty_state_config = responsive_calc.get_empty_state_config()
            empty_text = f"{empty_state_config['icon']} {empty_state_config['title']}\n\n{empty_state_config['description']}"
            self.empty_message.setText(empty_text)
            
            # Update styling
            empty_style = responsive_calc.create_responsive_style(
                responsive_calc.get_empty_state_style_template()
            )
            self.empty_message.setStyleSheet(empty_style)
            
            logger.debug(f"Updated empty state for breakpoint: {responsive_calc.get_current_breakpoint()}")

    def _connect_signals(self):
        # When the view changes (scroll, resize), update annotation positions
        self.pdf_viewer.view_changed.connect(self.annotation_manager.handle_viewer_changed)
        
        # Connect to the new dual-mode selection signals
        self.pdf_viewer.text_query_requested.connect(self.handle_text_query)
        self.pdf_viewer.image_query_requested.connect(self.handle_image_query)

        # Connect double-click signal to open file dialog
        self.pdf_viewer.open_pdf_requested.connect(self.open_pdf)

        # When the viewer encounters an error
        self.pdf_viewer.error_occurred.connect(lambda msg: self.statusBar().showMessage(msg, 5000))

    def setup_actions(self):
        """Create and configure all QAction objects for the toolbar and menus."""
        # Open PDF Action
        open_action = QAction(QIcon.fromTheme("document-open", QIcon(":/icons/open.png")), "&Open PDF...", self)
        open_action.triggered.connect(self.open_pdf)
        self.toolbar.addAction(open_action)

        # Settings Action
        settings_action = QAction(QIcon.fromTheme("preferences-system", QIcon(":/icons/settings.png")), "&Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        self.toolbar.addAction(settings_action)
        
        self.toolbar.addSeparator()

        # Selection Mode Action
        self.selection_mode_action = QAction("S&witch to Area Selection", self)
        self.selection_mode_action.setCheckable(True)
        self.selection_mode_action.triggered.connect(self.toggle_selection_mode)
        self.toolbar.addAction(self.selection_mode_action)
        # Initialize with text selection mode
        self.toggle_selection_mode(False)

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.annotation_manager.clear_all_annotations()
            self.pdf_viewer.load_pdf(file_path)
            self.statusBar().showMessage(f"Opened {file_path}", 5000)

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.llm_service.refresh_config()
            self.statusBar().showMessage("Settings updated.", 5000)

    def handle_text_query(self, selected_text: str, context_text: str, pdf_rect: fitz.Rect):
        """Handles a query request originating from a text selection."""
        # Prevent multiple concurrent queries (debouncing)
        if self.is_querying:
            logger.warning("Query already in progress, ignoring new query request")
            QMessageBox.information(
                self, 
                "Query in Progress",
                "Please wait for the current AI query to complete before starting a new one."
            )
            return
            
        # Store selected text for later use in annotations
        self.current_selected_text = selected_text
        
        popup = InquiryPopup(
            parent=self.pdf_viewer, 
            selected_text=selected_text,
            context_text=context_text
        )
        popup.annotation_requested.connect(
            lambda prompt: self.start_ai_query(prompt, pdf_rect)
        )
        
        # Position and show the popup
        if self.pdf_viewer.selection_end_pos:
            global_pos = self.pdf_viewer.mapToGlobal(self.pdf_viewer.selection_end_pos.toPoint())
            popup.move(global_pos)
            
            # Store position for loading indicator
            self.last_query_position = global_pos
        
        popup.show()
    
    def handle_image_query(self, image: QImage):
        """Handles a query request originating from a screenshot selection."""
        QMessageBox.information(
            self, 
            "Feature Not Implemented",
            "Querying with image selections is not yet implemented."
        )

    def start_ai_query(self, prompt: str, pdf_rect: fitz.Rect):
        # Additional check for concurrent queries
        if self.is_querying:
            logger.warning("Query already in progress, cannot start new query")
            return
            
        logger.info("Starting AI query with loading indicator")
        self.statusBar().showMessage("Querying AI...", 3000)
        
        # Set query state
        self.is_querying = True
        
        # Clear PDF selection state now that query has started
        self.pdf_viewer.clear_selection()
        
        # Show loading indicator at last known position
        if self.last_query_position:
            self.loading_indicator.show_at_position(self.last_query_position)
        
        self.llm_worker = LLMWorker(self.llm_service, prompt)
        
        self.llm_worker.result_ready.connect(
            lambda response: self.handle_ai_response(response, pdf_rect)
        )
        self.llm_worker.error_occurred.connect(self.handle_ai_error)
        self.llm_worker.start()

    def handle_ai_error(self, error_msg: str):
        # Hide loading indicator
        self.loading_indicator.hide_with_fade()
        
        # Reset query state
        self.is_querying = False
        self.llm_worker = None
        
        # The error message now includes the exception type
        if "LLMConfigurationError" in error_msg:
            QMessageBox.critical(
                self, 
                "LLM Not Configured",
                "The Gemini API key is missing or invalid. Please configure it in the Settings menu."
            )
        elif "LLMAPIError" in error_msg:
            QMessageBox.critical(
                self, 
                "API Error",
                f"An error occurred while communicating with the AI service. Please check your network connection and API key validity.\n\nDetails: {error_msg}"
            )
        elif "LLMResponseError" in error_msg:
            QMessageBox.critical(
                self, 
                "Invalid AI Response",
                f"The AI service returned an unexpected or invalid response.\n\nDetails: {error_msg}"
            )
        else:
            QMessageBox.critical(
                self, 
                "AI Error", 
                f"An unexpected error occurred during the AI query.\n\nDetails: {error_msg}"
            )
        self.statusBar().showMessage("AI query failed.", 5000)

    def handle_ai_response(self, ai_response: str, pdf_rect: fitz.Rect):
        # Hide loading indicator with fade effect
        self.loading_indicator.hide_with_fade()
        
        # Reset query state
        self.is_querying = False
        self.llm_worker = None
        
        self.statusBar().showMessage("AI response received.", 5000)
        page_num = self.pdf_viewer.get_current_page_number()
        if page_num is not None:
            # Pass the selected text to the annotation manager
            self.annotation_manager.add_annotation(
                page_num, 
                pdf_rect, 
                ai_response, 
                self.current_selected_text
            )
            logger.info(f"Added panel annotation to page {page_num}")
            
            # Clear stored selected text
            self.current_selected_text = ""

    def on_query_started(self):
        """Shows the loading indicator when a query starts."""
        if self.last_query_position:
            self.loading_indicator.show_at_position(self.last_query_position)
        else:
            # Fallback to center of the window if position is not available
            self.loading_indicator.show_at_position(self.geometry().center())
        logger.info("Starting AI query with loading indicator")

    def on_query_finished(self, result, selected_rect):
        """Hides the loading indicator and processes the successful query result."""
        self.loading_indicator.hide_with_fade()
        logger.info(f"LLM query finished successfully.")
        
        page_num = self.pdf_viewer.currentPage()
        pdf_coords = self.pdf_viewer.get_pdf_coords(selected_rect)
        if pdf_coords:
            self.annotation_manager.add_annotation(
                page_num=page_num,
                pdf_coords=pdf_coords,
                text=result
            )
            logger.info(f"Added sticky note annotation to page {page_num}")

    def on_query_error(self, error_message):
        """Hides the loading indicator and shows an error message."""
        self.loading_indicator.hide_with_fade()
        QMessageBox.critical(self, "AI Query Error", error_message)
        logger.error(f"LLM query failed: {error_message}")

    def setup_llm_worker(self, inquiry_text, context_text, selected_rect):
        """Initializes and configures the LLM worker thread."""
        if not self.llm_service.is_configured():
            return

        self.llm_worker = LLMWorker(self.llm_service, inquiry_text, context_text, selected_rect)
        
        # Connect signals for this worker
        self.llm_worker.query_started.connect(self.on_query_started)
        self.llm_worker.query_finished.connect(self.on_query_finished)
        self.llm_worker.query_error.connect(self.on_query_error)
        
        self.llm_worker.start()
        logger.info("LLM worker started for query.")

    def toggle_selection_mode(self, is_area_mode):
        """Toggles the selection mode between text and area (screenshot)."""
        if is_area_mode:
            self.pdf_viewer.set_selection_mode(SelectionMode.SCREENSHOT)
            self.selection_mode_action.setText("Switch to &Text Selection")
            self.selection_mode_action.setToolTip("Currently in Area Selection mode")
        else:
            self.pdf_viewer.set_selection_mode(SelectionMode.TEXT)
            self.selection_mode_action.setText("Switch to &Area Selection")
            self.selection_mode_action.setToolTip("Currently in Text Selection mode")

    def handle_chat_query(self, message: str):
        """Handle a chat query from the chat panel."""
        if not message.strip():
            return
        
        logger.info(f"Processing chat query: {len(message)} characters")
        
        # Create LLM worker for chat query
        self.setup_chat_llm_worker(message)

    def setup_chat_llm_worker(self, message: str):
        """Setup LLM worker for chat queries."""
        try:
            # Cancel any existing worker
            if self.llm_worker is not None:
                self.llm_worker.finished.disconnect()
                self.llm_worker.error.disconnect()
                self.llm_worker.terminate()
                self.llm_worker.wait()
                self.llm_worker = None
            
            # Create new worker for chat
            self.llm_worker = LLMWorker(self.llm_service, message)
            
            # Connect signals
            self.llm_worker.result_ready.connect(self.on_chat_query_finished)
            self.llm_worker.error_occurred.connect(self.on_chat_query_error)
            
            # Start worker
            self.llm_worker.start()
            
            logger.info("Chat LLM worker started")
            
        except Exception as e:
            logger.error(f"Error setting up chat LLM worker: {e}")
            self.handle_chat_error(f"Failed to start AI processing: {str(e)}")

    def on_chat_query_finished(self, result):
        """Handle completion of chat LLM query."""
        if hasattr(self, 'chat_widget') and self.chat_widget:
            self.chat_widget.add_ai_response(result)
        
        # Clean up worker
        if self.llm_worker:
            self.llm_worker = None
        
        logger.info("Chat query completed successfully")

    def on_chat_query_error(self, error_message):
        """Handle error in chat LLM query."""
        logger.error(f"Chat query error: {error_message}")
        self.handle_chat_error(error_message)
        
        # Clean up worker
        if self.llm_worker:
            self.llm_worker = None

    def handle_chat_error(self, error_message: str):
        """Handle chat-specific errors."""
        if hasattr(self, 'chat_widget') and self.chat_widget:
            self.chat_widget.handle_ai_error(error_message)

    def on_chat_cleared(self):
        """Handle chat cleared event."""
        logger.info("Chat conversation cleared")
        # Could add additional cleanup or analytics here

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Enable input method support for Chinese/international text input
    # Note: High DPI scaling is enabled by default in Qt6
    
    # Ensure proper text input support
    app.setProperty("inputMethod", True)
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())