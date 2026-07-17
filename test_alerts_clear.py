import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

# Override database file before importing database and main
from app import database
import os
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub.db")

from app.main import app

@pytest.fixture(autouse=True)
def setup_test_db():
    # Clean and setup test database
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    
    database.init_db()
    
    # Enable shift and sound to default values
    conn = sqlite3.connect(database.DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE alert_settings SET is_on_shift = 1, is_sound_enabled = 1 WHERE id = 1")
    conn.commit()
    conn.close()
    
    yield
    
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)

def test_clear_alerts():
    client = TestClient(app)
    
    # 1. Insert a few alerts
    conn = sqlite3.connect(database.DB_FILE)
    database.add_alert(conn, "email", "test-sender", "test-email-content", "link-1")
    database.add_alert(conn, "email", "test-sender-2", "test-email-content-2", "link-2")
    conn.close()
    
    # Verify they show up as unseen
    res_get = client.get("/api/alerts")
    assert res_get.status_code == 200
    alerts = res_get.json()
    assert len(alerts) == 2
    assert alerts[0]["status"] == "unseen"
    
    # 2. Trigger clear
    res_clear = client.post("/api/alerts/clear")
    assert res_clear.status_code == 200
    assert res_clear.json() == {"status": "success"}
    
    # 3. Verify they are gone from the unseen queue
    res_get_after = client.get("/api/alerts")
    assert res_get_after.status_code == 200
    alerts_after = res_get_after.json()
    assert len(alerts_after) == 0
