import pytest
import os
import sqlite3
import imaplib
import email
from email.message import EmailMessage
import shutil
import tempfile
import asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Override database file
from app import database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub_monitors_bg.db")

from app.main import app, poll_emails, poll_whatsapp, monitors_running, parse_xml_payload
from app.database import init_db, get_db_connection, update_alert_settings, get_alert_settings

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    init_db()
    # Ensure shift is off by default
    conn = get_db_connection()
    try:
        update_alert_settings(conn, {"is_on_shift": 0})
    finally:
        conn.close()
    yield
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)

def test_parse_xml_payload():
    xml_str = '<binding template="ToastText02"><text id="1">Alice</text><text id="2">Hello Support!</text></binding>'
    sender, content = parse_xml_payload(xml_str)
    assert sender == "Alice"
    assert content == "Hello Support!"

    xml_generic = '<binding template="ToastGeneric"><text>Bob</text><text>Emergency issue</text></binding>'
    sender2, content2 = parse_xml_payload(xml_generic)
    assert sender2 == "Bob"
    assert content2 == "Emergency issue"

@patch("imaplib.IMAP4_SSL")
def test_poll_emails_matches_keywords(mock_imap_class):
    # Setup mock IMAP
    mock_imap = MagicMock()
    mock_imap_class.return_value = mock_imap
    mock_imap.search.return_value = ("OK", [b"1"])
    
    # Create a mock raw email
    msg = EmailMessage()
    msg["Subject"] = "Urgent: Server Down!"
    msg["From"] = "client@example.com"
    msg["Message-ID"] = "<test-msg-id-123>"
    raw_email = msg.as_bytes()
    mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822)", raw_email)])

    # Setup settings to turn shift ON and have matching keywords
    conn = get_db_connection()
    try:
        update_alert_settings(conn, {
            "is_on_shift": 1,
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_user": "test@example.com",
            "imap_password": "password",
            "target_email_keywords": "Urgent,Error"
        })
    finally:
        conn.close()

    # We patch monitors_running to run only once
    global monitors_running
    # Use patch to loop once and raise an exception or control it
    # Let's run a modified wrapper or patch sleep to raise an exception to exit loop
    with patch("app.main.monitors_running", new_callable=MagicMock) as mock_running:
        # Loop once
        mock_running.__bool__.side_effect = [True, False]
        # We also mock broadcast_alert to avoid actual network/ws broadcast issues in raw test
        with patch("app.main.broadcast_alert", new_callable=MagicMock) as mock_broadcast:
            poll_emails()
            
    # Verify alert was inserted into DB
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM received_alerts WHERE type = 'email'")
        row = cursor.fetchone()
        assert row is not None
        assert row["sender"] == "client@example.com"
        assert row["content"] == "Urgent: Server Down!"
        assert "test-msg-id-123" in row["link"]
    finally:
        conn.close()

@patch("shutil.copy2")
@patch("os.path.exists")
def test_poll_whatsapp_matches(mock_exists, mock_copy):
    mock_exists.return_value = True
    
    # Setup conditional mock for sqlite3.connect
    # Setup mock sqlite for wpndatabase
    mock_temp_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_temp_conn.cursor.return_value = mock_cursor
    
    payload_xml = '<binding template="ToastText02"><text id="1">Bob</text><text id="2">WhatsApp Message content</text></binding>'
    
    # Mock return rows from Notification table (mock row objects with string key access)
    row_mock = MagicMock()
    row_mock.__getitem__.side_effect = lambda key: {"Id": 1, "Payload": payload_xml, "ExpiryTime": 1000}[key]
    mock_cursor.fetchall.return_value = [row_mock]

    # Setup conditional mock for sqlite3.connect
    real_connect = sqlite3.connect
    def side_effect_connect(database_path, *args, **kwargs):
        if "wpndatabase" in database_path or "tmp" in database_path or "temp" in database_path:
            return mock_temp_conn
        return real_connect(database_path, *args, **kwargs)
        
    mock_sqlite_connect = MagicMock(side_effect=side_effect_connect)
    
    with patch("sqlite3.connect", mock_sqlite_connect), \
         patch("app.main.sqlite3.connect", mock_sqlite_connect):
    
        # Setup settings to turn shift ON and have matching keywords/names
        conn = get_db_connection()
        try:
            update_alert_settings(conn, {
                "is_on_shift": 1,
                "target_whatsapp_names": "Bob,Charlie"
            })
        finally:
            conn.close()

        with patch("app.main.monitors_running", new_callable=MagicMock) as mock_running:
            mock_running.__bool__.side_effect = [True, False]
            with patch("app.main.broadcast_alert", new_callable=MagicMock) as mock_broadcast:
                poll_whatsapp()

        # Verify alert was inserted into DB
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM received_alerts WHERE type = 'whatsapp'")
            row = cursor.fetchone()
            assert row is not None
            assert row["sender"] == "Bob"
            assert row["content"] == "WhatsApp Message content"
        finally:
            conn.close()

@patch("imaplib.IMAP4_SSL")
def test_poll_emails_ignores_old_emails(mock_imap_class):
    # Setup mock IMAP
    mock_imap = MagicMock()
    mock_imap_class.return_value = mock_imap
    mock_imap.search.return_value = ("OK", [b"1"])
    
    # Create a mock raw email dated 5 hours ago
    from datetime import datetime, timezone, timedelta
    old_time = datetime.now(timezone.utc) - timedelta(hours=5)
    email_date_str = old_time.strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    msg = EmailMessage()
    msg["Subject"] = "Urgent: Old Alert!"
    msg["From"] = "client@example.com"
    msg["Message-ID"] = "<old-msg-id-123>"
    msg["Date"] = email_date_str
    raw_email = msg.as_bytes()
    mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822)", raw_email)])

    # Setup settings to turn shift ON and have matching keywords
    conn = get_db_connection()
    try:
        update_alert_settings(conn, {
            "is_on_shift": 1,
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_user": "test@example.com",
            "imap_password": "password",
            "target_email_keywords": "" # match everything
        })
    finally:
        conn.close()

    with patch("app.main.monitors_running", new_callable=MagicMock) as mock_running:
        mock_running.__bool__.side_effect = [True, False]
        with patch("app.main.broadcast_alert", new_callable=MagicMock) as mock_broadcast:
            poll_emails()
            
    # Verify no alert was inserted into DB (since it was skipped as old)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM received_alerts WHERE type = 'email' AND content = 'Urgent: Old Alert!'")
        row = cursor.fetchone()
        assert row is None
    finally:
        conn.close()
