import pytest
import os
import sqlite3
from datetime import datetime, timedelta
from app import database

# Configure test database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub_alerts.db")

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    database.init_db()
    yield
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)

def test_alert_tables_and_functions():
    conn = database.get_db_connection()
    try:
        # Check if tables exist
        cursor = conn.cursor()
        
        # Test alert_settings exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_settings';")
        assert cursor.fetchone() is not None, "alert_settings table should exist"
        
        # Test received_alerts exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='received_alerts';")
        assert cursor.fetchone() is not None, "received_alerts table should exist"
        
        # Test default configurations are inserted
        settings = database.get_alert_settings(conn)
        assert settings is not None
        assert settings["is_on_shift"] == 0
        assert settings["imap_host"] == "imap.gmail.com"
        assert settings["imap_port"] == 993
        assert settings["alarm_volume"] == 1.0
        assert settings["target_email_keywords"] == ""
        assert settings["target_whatsapp_names"] == ""
        
        # Test update_alert_settings
        new_settings = {
            "is_on_shift": 1,
            "imap_host": "imap.mail.yahoo.com",
            "imap_port": 995,
            "imap_user": "user@yahoo.com",
            "imap_password": "password123",
            "target_email_keywords": "CRITICAL,ERROR",
            "target_whatsapp_names": "Support Group",
            "alarm_volume": 0.8
        }
        database.update_alert_settings(conn, new_settings)
        
        updated = database.get_alert_settings(conn)
        for k, v in new_settings.items():
            assert updated[k] == v
            
        # Test add_alert
        alert_id = database.add_alert(
            conn, 
            type_="email", 
            sender="client@corp.com", 
            content="Server is down!", 
            link="http://localhost:3000/tickets/1"
        )
        assert isinstance(alert_id, int)
        
        # Test get_unseen_alerts
        unseen = database.get_unseen_alerts(conn)
        assert len(unseen) == 1
        assert unseen[0]["sender"] == "client@corp.com"
        assert unseen[0]["content"] == "Server is down!"
        assert unseen[0]["type"] == "email"
        assert unseen[0]["status"] == "unseen"
        
        # Test mark_alert_seen
        database.mark_alert_seen(conn, alert_id)
        unseen_after = database.get_unseen_alerts(conn)
        assert len(unseen_after) == 0
        
        # Test get_unseen_alerts only returns last 24h
        old_alert_id = database.add_alert(
            conn,
            type_="whatsapp",
            sender="Manager",
            content="Old alert"
        )
        from datetime import timezone
        past_time = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE received_alerts SET timestamp = ? WHERE id = ?", (past_time, old_alert_id))
        conn.commit()
        
        unseen_last_24h = database.get_unseen_alerts(conn)
        assert len(unseen_last_24h) == 0
        
    finally:
        conn.close()
