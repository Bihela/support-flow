import pytest
import sqlite3
import json
import os
from fastapi.testclient import TestClient

# Override database.DB_FILE for testing
from app import database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub_alerts_sound_toggle.db")

from app.main import app
from app.database import init_db, get_db_connection

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    init_db()
    yield
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)

@pytest.fixture
def client():
    return TestClient(app)

def test_is_sound_enabled_default_value(client):
    # Get settings, check default is_sound_enabled is 1
    response = client.get("/api/alerts/settings")
    assert response.status_code == 200
    settings = response.json()
    assert settings["is_sound_enabled"] == 1

def test_toggle_sound_settings(client):
    # Set to 0
    update_payload = {
        "is_sound_enabled": 0
    }
    response_update = client.put("/api/alerts/settings", json=update_payload)
    assert response_update.status_code == 200
    assert response_update.json() == {"status": "success"}

    # Get settings to verify it's 0
    response_get = client.get("/api/alerts/settings")
    assert response_get.status_code == 200
    settings = response_get.json()
    assert settings["is_sound_enabled"] == 0

    # Set to 1
    update_payload_2 = {
        "is_sound_enabled": 1
    }
    response_update_2 = client.put("/api/alerts/settings", json=update_payload_2)
    assert response_update_2.status_code == 200
    assert response_update_2.json() == {"status": "success"}

    # Get settings to verify it's 1
    response_get_2 = client.get("/api/alerts/settings")
    assert response_get_2.status_code == 200
    settings_2 = response_get_2.json()
    assert settings_2["is_sound_enabled"] == 1
