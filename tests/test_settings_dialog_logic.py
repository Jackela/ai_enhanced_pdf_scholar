"""
Unit tests for SettingsDialog in src/settings_dialog.py.
Covers initialization, load_settings from QSettings, save_settings writing back, and get_settings.
"""
import pytest
from PyQt6.QtWidgets import QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import QCoreApplication
from unittest.mock import MagicMock

import config

import src.settings_dialog as settings_dialog_module

class DummySettings:
    def __init__(self, initial=None):
        # initial dict of values
        self.store = initial or {}
        self.synced = False
    def value(self, key, default=None):
        return self.store.get(key, default)
    def setValue(self, key, value):
        self.store[key] = value
    def sync(self):
        self.synced = True
    def allKeys(self):
        return list(self.store.keys())
    def organizationName(self):
        return "OrgName"
    def applicationName(self):
        return "AppName"

@pytest.fixture(autouse=True)
def qapp(request):
    # Ensure a QCoreApplication exists for widget creation
    app = QCoreApplication.instance() or QCoreApplication([])
    return app

@pytest.fixture
def dummy_settings():
    # Provide initial settings values
    return DummySettings({
        "llm/api_key": "initkey",
        "llm/model_name": "init-model"
    })

@ pytest.fixture(autouse=True)
def patch_qsettings_and_message(monkeypatch, dummy_settings):
    # Monkey-patch QSettings in module to use DummySettings
    monkeypatch.setattr(settings_dialog_module, 'QSettings', lambda a,b: dummy_settings)
    # Monkey-patch QMessageBox.information to no-op
    monkeypatch.setattr(settings_dialog_module.QMessageBox, 'information', lambda *args, **kwargs: None)
    yield


def test_load_settings_initializes_fields(dummy_settings):
    dlg = settings_dialog_module.SettingsDialog(parent=None)
    # After init, input fields should have loaded values
    assert isinstance(dlg.api_key_input, QLineEdit)
    assert dlg.api_key_input.text() == "initkey"
    assert isinstance(dlg.model_name_input, QLineEdit)
    assert dlg.model_name_input.text() == "init-model"


def test_get_settings_strips_whitespace(dummy_settings):
    dlg = settings_dialog_module.SettingsDialog(parent=None)
    # Set some values with whitespace
    dlg.api_key_input.setText("  newkey  ")
    dlg.model_name_input.setText("  new-model  ")
    api, model = dlg.get_settings()
    assert api == "newkey"
    assert model == "new-model"


def test_save_settings_writes_and_accepts(dummy_settings, monkeypatch):
    dlg = settings_dialog_module.SettingsDialog(parent=None)
    # Change input values
    dlg.api_key_input.setText("savedkey")
    dlg.model_name_input.setText("saved-model")
    # Spy on accept()
    accepted = []
    monkeypatch.setattr(dlg, 'accept', lambda: accepted.append(True))
    # Call save
    dlg.save_settings()
    # Settings should be written
    assert dummy_settings.store.get("llm/api_key") == "savedkey"
    assert dummy_settings.store.get("llm/model_name") == "saved-model"
    # sync should have been called
    assert dummy_settings.synced is True
    # accept() called
    assert accepted == [True]
    # QMessageBox.information was no-op, but no exception


def test_save_settings_empty_fields(dummy_settings):
    dlg = settings_dialog_module.SettingsDialog(parent=None)
    # Clear input values
    dlg.api_key_input.setText("")
    dlg.model_name_input.setText("")
    # Call save
    # Should not raise and store empty strings
    dlg.save_settings()
    assert dummy_settings.store.get("llm/api_key") == ""
    assert dummy_settings.store.get("llm/model_name") == "" 