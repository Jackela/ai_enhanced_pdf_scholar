import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget, QMessageBox, QDialog
from PyQt6.QtCore import QSettings

from src.settings_dialog import SettingsDialog
import config

@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app
    app.quit()

@pytest.fixture
def dummy_parent_widget(qapp):
    return QWidget()

@pytest.fixture(autouse=True)
def mock_qsettings():
    with patch('src.settings_dialog.QSettings') as mock_settings_class:
        mock_settings_instance = MagicMock()
        mock_settings_class.return_value = mock_settings_instance
        # Configure the mock_settings_instance.value to return actual strings
        mock_settings_instance.value.side_effect = lambda key, default: {
            "llm/api_key": "mock_api_key_from_qsettings",
            "llm/model_name": "mock_model_name_from_qsettings"
        }.get(key, default)
        yield mock_settings_instance

class TestSettingsDialog:

    def test_init_ui(self, qapp, dummy_parent_widget, mock_qsettings):
        dialog = SettingsDialog(parent=dummy_parent_widget)
        assert dialog.windowTitle() == "Settings"
        assert dialog.api_key_input is not None
        assert dialog.model_name_input is not None
        assert dialog.api_key_input.placeholderText() == "Enter your Gemini API Key"
        assert dialog.model_name_input.placeholderText() == f"e.g., {config.AI_FEATURE_SETTINGS['model']}"

    def test_load_settings(self, qapp, dummy_parent_widget, mock_qsettings):
        mock_qsettings.value.side_effect = ["mock_api_key", "mock_model_name"]
        dialog = SettingsDialog(parent=dummy_parent_widget)
        assert dialog.api_key_input.text() == "mock_api_key"
        assert dialog.model_name_input.text() == "mock_model_name"
        mock_qsettings.value.assert_any_call("llm/api_key", "")
        mock_qsettings.value.assert_any_call("llm/model_name", config.AI_FEATURE_SETTINGS['model'])

    def test_save_settings(self, qapp, dummy_parent_widget, mock_qsettings, mocker):
        dialog = SettingsDialog(parent=dummy_parent_widget)
        dialog.api_key_input.setText("new_api_key")
        dialog.model_name_input.setText("new_model_name")
        mocker.patch('PyQt6.QtWidgets.QMessageBox.information')
        dialog.save_settings()
        mock_qsettings.setValue.assert_any_call("llm/api_key", "new_api_key")
        mock_qsettings.setValue.assert_any_call("llm/model_name", "new_model_name")
        QMessageBox.information.assert_called_once_with(dialog, "Settings Saved", "LLM settings have been saved successfully.")
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_get_settings(self, qapp, dummy_parent_widget, mock_qsettings):
        dialog = SettingsDialog(parent=dummy_parent_widget)
        dialog.api_key_input.setText("retrieved_api_key")
        dialog.model_name_input.setText("retrieved_model_name")
        api_key, model_name = dialog.get_settings()
        assert api_key == "retrieved_api_key"
        assert model_name == "retrieved_model_name"
