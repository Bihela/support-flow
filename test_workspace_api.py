import pytest
import os
from fastapi.testclient import TestClient
from app import database

# Configure test database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub_workspace.db")

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

def test_templates_crud(client):
    # Create template
    payload = {
        "title": "Escalation to Tier 3",
        "category": "escalation",
        "body": "Hello {{engineer}},\nWe are escalating ticket #{{ticket_id}} to Tier 3.",
        "linked_ticket_id": 88
    }
    res = client.post("/api/templates", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    template_id = res.json()["id"]

    # Get templates
    res = client.get("/api/templates")
    assert res.status_code == 200
    templates = res.json()
    assert len(templates) == 1
    assert templates[0]["title"] == "Escalation to Tier 3"
    assert templates[0]["linked_ticket_id"] == 88

    # Update template
    updated_payload = {
        "title": "Escalation to Tier 3 Revised",
        "category": "escalation",
        "body": "Hello {{engineer}},\nWe are escalating ticket #{{ticket_id}} to Tier 3 immediately.",
        "linked_ticket_id": None
    }
    res = client.put(f"/api/templates/{template_id}", json=updated_payload)
    assert res.status_code == 200

    # Verify update
    res = client.get("/api/templates")
    templates = res.json()
    assert templates[0]["title"] == "Escalation to Tier 3 Revised"
    assert templates[0]["linked_ticket_id"] is None

    # Delete template
    res = client.delete(f"/api/templates/{template_id}")
    assert res.status_code == 200

    # Verify delete
    res = client.get("/api/templates")
    assert len(res.json()) == 0


def test_notes_crud(client):
    # Create note
    payload = {
        "title": "Daily Standup Reminder",
        "body": "Prepare updates for Hutch CDR tickets",
        "color": "yellow",
        "is_pinned": 1,
        "reminder_date": "2026-07-06"
    }
    res = client.post("/api/notes", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    note_id = res.json()["id"]

    # Get notes
    res = client.get("/api/notes")
    assert res.status_code == 200
    notes = res.json()
    assert len(notes) == 1
    assert notes[0]["title"] == "Daily Standup Reminder"
    assert notes[0]["is_pinned"] == 1
    assert notes[0]["reminder_date"] == "2026-07-06"

    # Update note (unpin it)
    updated_payload = {
        "title": "Daily Standup Reminder",
        "body": "Prepare updates for Hutch CDR tickets",
        "color": "blue",
        "is_pinned": 0,
        "reminder_date": None
    }
    res = client.put(f"/api/notes/{note_id}", json=updated_payload)
    assert res.status_code == 200

    # Verify update
    res = client.get("/api/notes")
    notes = res.json()
    assert notes[0]["color"] == "blue"
    assert notes[0]["is_pinned"] == 0
    assert notes[0]["reminder_date"] is None

    # Delete note
    res = client.delete(f"/api/notes/{note_id}")
    assert res.status_code == 200

    # Verify delete
    res = client.get("/api/notes")
    assert len(res.json()) == 0
