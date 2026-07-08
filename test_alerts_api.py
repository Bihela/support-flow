import pytest
import sqlite3
import json
import os
from fastapi.testclient import TestClient

# Override database.DB_FILE for testing
from app import database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub_alerts_api.db")

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

def test_get_alerts_empty(client):
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert response.json() == []

def test_trigger_and_get_alerts(client):
    # Enable shift first
    client.put("/api/alerts/settings", json={"is_on_shift": 1})
    
    # Trigger email alert
    payload = {
        "type": "email",
        "sender": "alert@system.com",
        "content": "CPU usage is high",
        "link": "http://localhost/tickets/cpu"
    }
    response = client.post("/api/alerts/trigger", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "triggered"
    assert "alert_id" in res_data
    alert_id = res_data["alert_id"]

    # Get unseen alerts (should have the new alert)
    response_get = client.get("/api/alerts")
    assert response_get.status_code == 200
    alerts = response_get.json()
    assert len(alerts) == 1
    assert alerts[0]["id"] == alert_id
    assert alerts[0]["type"] == "email"
    assert alerts[0]["sender"] == "alert@system.com"
    assert alerts[0]["content"] == "CPU usage is high"
    assert alerts[0]["link"] == "http://localhost/tickets/cpu"
    assert alerts[0]["status"] == "unseen"

    # Mark as seen
    response_seen = client.post(f"/api/alerts/{alert_id}/seen")
    assert response_seen.status_code == 200
    assert response_seen.json() == {"status": "success"}

    # Get unseen alerts again (should be empty now)
    response_get_2 = client.get("/api/alerts")
    assert response_get_2.status_code == 200
    assert response_get_2.json() == []

def test_alert_settings(client):
    # Get current settings
    response = client.get("/api/alerts/settings")
    assert response.status_code == 200
    settings = response.json()
    assert settings["is_on_shift"] == 0
    assert settings["imap_host"] == "imap.gmail.com"
    assert settings["imap_port"] == 993

    # Update settings
    update_payload = {
        "is_on_shift": 1,
        "imap_host": "imap.testserver.com",
        "imap_port": 143,
        "imap_user": "test_user",
        "imap_password": "test_password",
        "target_email_keywords": "CRITICAL,URGENT",
        "target_whatsapp_names": "DevOps Alerts",
        "alarm_volume": 0.5
    }
    response_update = client.put("/api/alerts/settings", json=update_payload)
    assert response_update.status_code == 200
    assert response_update.json() == {"status": "success"}

    # Get updated settings to verify
    response_get_updated = client.get("/api/alerts/settings")
    assert response_get_updated.status_code == 200
    updated_settings = response_get_updated.json()
    for k, v in update_payload.items():
        assert updated_settings[k] == v

def test_websocket_broadcast(client):
    payload = {
        "type": "whatsapp",
        "sender": "919999999999",
        "content": "Emergency! Power outage.",
        "link": "http://localhost/tickets/power"
    }
    with client.websocket_connect("/api/alerts/ws") as websocket:
        # Trigger an alert via the endpoint
        response = client.post("/api/alerts/trigger", json=payload)
        assert response.status_code == 200
        alert_id = response.json()["alert_id"]

        # WebSocket should receive the broadcast message
        ws_msg = websocket.receive_json()
        assert ws_msg["id"] == alert_id
        assert ws_msg["type"] == "whatsapp"
        assert ws_msg["sender"] == "919999999999"
        assert ws_msg["content"] == "Emergency! Power outage."
        assert ws_msg["link"] == "http://localhost/tickets/power"
        assert ws_msg["status"] == "unseen"
