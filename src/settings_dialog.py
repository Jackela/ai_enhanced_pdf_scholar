from PyQt6.QtWidgets import QDialog, QLineEdit, QPushButton, QFormLayout, QMessageBox
from PyQt6.QtCore import QSettings
import config
import logging

# Configure logging for debugging
logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """
    A dialog for users to configure LLM API key and model name.
    Settings are saved and loaded using QSettings.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 150)
        self.settings = QSettings(config.APP_NAME, "Settings")
        
        logger.info(f"SettingsDialog initialized with QSettings organization: '{self.settings.organizationName()}', application: '{self.settings.applicationName()}'")
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QFormLayout(self)
        self.api_key_input = QLineEdit(self)
        self.api_key_input.setPlaceholderText("Enter your Gemini API Key")
        layout.addRow("Gemini API Key:", self.api_key_input)
        self.model_name_input = QLineEdit(self)
        self.model_name_input.setPlaceholderText(f"e.g., {config.AI_FEATURE_SETTINGS['model']}")
        layout.addRow("Gemini Model Name:", self.model_name_input)
        save_button = QPushButton("Save", self)
        save_button.clicked.connect(self.save_settings)
        layout.addRow(save_button)

    def load_settings(self):
        api_key = self.settings.value("llm/api_key", "")
        model_name = self.settings.value("llm/model_name", config.AI_FEATURE_SETTINGS['model'])
        
        # Log loaded settings (safely)
        api_key_preview = f"{api_key[:8]}..." if len(api_key) > 8 else "***EMPTY***" if not api_key else f"{api_key[:4]}***"
        logger.info(f"Loading settings - API Key: {api_key_preview} (length: {len(api_key)}), Model: {model_name}")
        
        all_keys = self.settings.allKeys()
        logger.info(f"All available keys in QSettings: {all_keys}")
        
        self.api_key_input.setText(api_key)
        self.model_name_input.setText(model_name)

    def save_settings(self):
        api_key = self.api_key_input.text().strip()
        model_name = self.model_name_input.text().strip()
        
        # Log what we're about to save (safely)
        api_key_preview = f"{api_key[:8]}..." if len(api_key) > 8 else "***EMPTY***" if not api_key else f"{api_key[:4]}***"
        logger.info(f"Saving settings - API Key: {api_key_preview} (length: {len(api_key)}), Model: {model_name}")
        
        self.settings.setValue("llm/api_key", api_key)
        self.settings.setValue("llm/model_name", model_name)
        
        # Force sync to ensure settings are written immediately
        self.settings.sync()
        
        # Verify the save by reading back
        saved_api_key = self.settings.value("llm/api_key", "")
        saved_model_name = self.settings.value("llm/model_name", "")
        logger.info(f"Verification - saved API key length: {len(saved_api_key)}, model: {saved_model_name}")
        
        QMessageBox.information(self, "Settings Saved", "LLM settings have been saved successfully.")
        self.accept()

    def get_settings(self):
        return self.api_key_input.text().strip(), self.model_name_input.text().strip()
