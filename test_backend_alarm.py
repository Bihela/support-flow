import pytest
import os
from fastapi.testclient import TestClient

# Override database.DB_FILE for testing
from app import database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub_backend_alarm.db")

from app.main import app
from app.database import init_db

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

def test_silence_endpoint(client):
    response = client.post("/api/alerts/silence")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

def test_trigger_alert_with_sound_enabled(client):
    # Enable shift and enable sound
    settings_payload = {
        "is_on_shift": 1,
        "is_sound_enabled": 1
    }
    client.put("/api/alerts/settings", json=settings_payload)

    # Trigger alert
    payload = {
        "type": "email",
        "sender": "alert@system.com",
        "content": "Server down",
        "link": "http://localhost/tickets/server"
    }
    response = client.post("/api/alerts/trigger", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "triggered"

def test_trigger_alert_with_sound_disabled(client):
    # Enable shift but disable sound
    settings_payload = {
        "is_on_shift": 1,
        "is_sound_enabled": 0
    }
    client.put("/api/alerts/settings", json=settings_payload)

    # Trigger alert
    payload = {
        "type": "whatsapp",
        "sender": "12345",
        "content": "Whatsapp sound disabled test",
        "link": "http://localhost/whatsapp"
    }
    response = client.post("/api/alerts/trigger", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "triggered"
