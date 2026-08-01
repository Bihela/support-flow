import pytest
import sqlite3
import json
import os
from fastapi.testclient import TestClient

# Use a test database file or in-memory
# To match the app/database.py imports, we override database.DB_FILE for testing.
from app import database
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub.db")

from app.main import app
from app.database import init_db, get_db_connection

@pytest.fixture(autouse=True)
def setup_db():
    # Remove database if exists
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    init_db()
    yield
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)

@pytest.fixture
def client():
    return TestClient(app)

def test_staging_drafts_flow(client):
    # 1. Insert a draft
    payload = {
        "title": "Database connection failing",
        "client": "Client A",
        "symptom": "OperationalError database is locked",
        "steps": ["Check database locking settings", "Increase timeout duration"],
        "raw_markdown": "# Database connection failing\n@ Client A\n> OperationalError database is locked\n- Check database locking settings\n- Increase timeout duration"
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 2. Get drafts
    resp = client.get("/api/staging/drafts")
    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft["parsed_title"] == "Database connection failing"
    assert draft["parsed_client"] == "Client A"
    assert draft["parsed_steps"] == ["Check database locking settings", "Increase timeout duration"]
    draft_id = draft["id"]

    # 3. Compare draft (collisions)
    resp = client.get(f"/api/staging/compare/{draft_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft"]["id"] == draft_id
    assert len(data["collisions"]) == 0

    # 4. Approve draft
    resp = client.post(f"/api/staging/approve/{draft_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    ticket_id = resp.json()["ticket_id"]

    # Verify ticket was added in live DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = c.fetchone()
    assert ticket is not None
    assert ticket["title"] == "Database connection failing"

    # Verify steps were created in master_steps & ticket_steps
    c.execute("SELECT ms.instructions, ts.step_order FROM ticket_steps ts JOIN master_steps ms ON ts.step_id = ms.id WHERE ts.ticket_id = ?", (ticket_id,))
    steps = c.fetchall()
    assert len(steps) == 2
    assert steps[0]["instructions"] == "Check database locking settings"
    assert steps[0]["step_order"] == 1
    assert steps[1]["instructions"] == "Increase timeout duration"
    assert steps[1]["step_order"] == 2

    # Verify draft was deleted
    c.execute("SELECT * FROM staging_inbox WHERE id = ?", (draft_id,))
    assert c.fetchone() is None
    conn.close()

def test_merge_draft(client):
    # Setup live ticket
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Original Ticket", "Client X", "Original Symptom"))
    ticket_id = c.lastrowid
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Step Original",))
    step_id = c.lastrowid
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (ticket_id, step_id, 1))
    conn.commit()
    conn.close()

    # Create draft to merge
    payload = {
        "title": "Original Ticket",
        "client": "Client X",
        "symptom": "Original Symptom",
        "steps": ["Step Original", "Step New To Merge"],
        "raw_markdown": ""
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200
    
    # Get draft ID
    resp = client.get("/api/staging/drafts")
    draft_id = resp.json()[0]["id"]

    # Run merge API
    merge_payload = {
        "draft_id": draft_id,
        "target_live_ticket_id": ticket_id
    }
    resp = client.post("/api/staging/merge", json=merge_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Verify only the new step is added with order 2
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT ms.instructions, ts.step_order FROM ticket_steps ts JOIN master_steps ms ON ts.step_id = ms.id WHERE ts.ticket_id = ? ORDER BY ts.step_order ASC", (ticket_id,))
    steps = c.fetchall()
    assert len(steps) == 2
    assert steps[0]["instructions"] == "Step Original"
    assert steps[0]["step_order"] == 1
    assert steps[1]["instructions"] == "Step New To Merge"
    assert steps[1]["step_order"] == 2

    # Verify draft is deleted
    c.execute("SELECT * FROM staging_inbox WHERE id = ?", (draft_id,))
    assert c.fetchone() is None
    conn.close()

def test_discard_draft(client):
    payload = {
        "title": "Title to discard",
        "client": "",
        "symptom": "",
        "steps": [],
        "raw_markdown": ""
    }
    client.post("/api/staging/draft", json=payload)
    resp = client.get("/api/staging/drafts")
    draft_id = resp.json()[0]["id"]

    resp = client.delete(f"/api/staging/discard/{draft_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM staging_inbox WHERE id = ?", (draft_id,))
    assert c.fetchone() is None
    conn.close()

def test_update_draft(client):
    # 1. Insert initial draft
    payload = {
        "title": "Old Draft Title",
        "client": "Client Old",
        "symptom": "Old Symptom Details",
        "steps": ["Step 1", "Step 2"],
        "raw_markdown": ""
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200

    # Retrieve draft ID
    resp = client.get("/api/staging/drafts")
    draft_id = resp.json()[0]["id"]

    # 2. Update via PUT
    update_payload = {
        "title": "New Updated Title",
        "client": "Client New",
        "symptom": "New Symptom Details",
        "steps": ["Step A", "Step B"]
    }
    resp = client.put(f"/api/staging/update/{draft_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 3. Retrieve draft again and assert update was successful
    resp = client.get("/api/staging/drafts")
    drafts = resp.json()
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft["parsed_title"] == "New Updated Title"
    assert draft["parsed_client"] == "Client New"
    assert draft["parsed_symptom"] == "New Symptom Details"
    assert draft["parsed_steps"] == ["Step A", "Step B"]


def test_api_search_and_fts(client):
    # Insert some live tickets and master steps
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Severe Server Failure", "Client Red", "500 Internal Server Error"))
    t1_id = c.lastrowid
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Database backup timeout", "Client Blue", "Backup failed at midnight"))
    t2_id = c.lastrowid
    
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Reboot the secondary application nodes",))
    s1_id = c.lastrowid
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Verify replica lag and database locks",))
    s2_id = c.lastrowid
    
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t1_id, s1_id, 1))
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t2_id, s2_id, 1))
    
    conn.commit()
    conn.close()
    
    # 1. Test GET /search serves HTML
    resp = client.get("/search")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    
    # 2. Test API search with no query (returns all sorted by created_at DESC)
    resp = client.get("/api/search")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 2
    assert tickets[0]["id"] == t2_id
    assert len(tickets[0]["steps"]) == 1
    assert tickets[0]["steps"][0]["instructions"] == "Verify replica lag and database locks"
    
    # 3. Test API search with query (FTS match)
    resp = client.get("/api/search?q=Server")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 1
    assert tickets[0]["id"] == t1_id
    
    resp = client.get("/api/search?q=replica")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 1
    assert tickets[0]["id"] == t2_id


def test_flagging_and_maintenance(client):
    # Setup step
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Outdated connection config utility",))
    step_id = c.lastrowid
    
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T1", "C1", "S1"))
    t1_id = c.lastrowid
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T2", "C2", "S2"))
    t2_id = c.lastrowid
    
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t1_id, step_id, 1))
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t2_id, step_id, 2))
    
    conn.commit()
    conn.close()
    
    # 1. Flag step
    resp = client.post(f"/api/steps/flag/{step_id}", json={"reason": "Deprecated API endpoint call"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # Verify flag in DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT is_broken, breakage_notes FROM master_steps WHERE id = ?", (step_id,))
    row = c.fetchone()
    assert row["is_broken"] == 1
    assert row["breakage_notes"] == "Deprecated API endpoint call"
    conn.close()
    
    # 2. GET maintenance page HTML
    resp = client.get("/maintenance")
    assert resp.status_code == 200
    
    # 3. GET maintenance queue
    resp = client.get("/api/maintenance/queue")
    assert resp.status_code == 200
    queue = resp.json()
    assert len(queue) == 1
    assert queue[0]["id"] == step_id
    assert queue[0]["impact_count"] == 2
    
    # 4. Resolve via UPDATE
    resp = client.patch(f"/api/maintenance/resolve/{step_id}", json={"action": "update", "text": "Updated API endpoint call"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # Verify updated step in DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT instructions, is_broken, breakage_notes FROM master_steps WHERE id = ?", (step_id,))
    row = c.fetchone()
    assert row["instructions"] == "Updated API endpoint call"
    assert row["is_broken"] == 0
    assert row["breakage_notes"] is None
    conn.close()
    
    # Flag it again to test delete resolution
    client.post(f"/api/steps/flag/{step_id}", json={"reason": "Need removal"})
    
    # Add dummy steps to T1 and T2 to verify reordering on delete
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Step before",))
    sb_id = c.lastrowid
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Step after",))
    sa_id = c.lastrowid
    
    # For T1: step_id is at step_order 1. Insert sb_id at 2.
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t1_id, sb_id, 2))
    
    # For T2: step_id is at step_order 2. Insert sb_id at 1, sa_id at 3.
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t2_id, sb_id, 1))
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (t2_id, sa_id, 3))
    
    conn.commit()
    conn.close()
    
    # 5. Resolve via DELETE
    resp = client.patch(f"/api/maintenance/resolve/{step_id}", json={"action": "delete"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # Verify step was deleted
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM master_steps WHERE id = ?", (step_id,))
    assert c.fetchone() is None
    
    # Check ticket steps ordering:
    # T1 had step_id (1) and sb_id (2). After delete of step_id, sb_id should be reordered to 1.
    c.execute("SELECT step_id, step_order FROM ticket_steps WHERE ticket_id = ? ORDER BY step_order ASC", (t1_id,))
    t1_steps = c.fetchall()
    assert len(t1_steps) == 1
    assert t1_steps[0]["step_id"] == sb_id
    assert t1_steps[0]["step_order"] == 1
    
    # T2 had sb_id (1), step_id (2), sa_id (3). After delete of step_id, sb_id stays 1, sa_id becomes 2.
    c.execute("SELECT step_id, step_order FROM ticket_steps WHERE ticket_id = ? ORDER BY step_order ASC", (t2_id,))
    t2_steps = c.fetchall()
    assert len(t2_steps) == 2
    assert t2_steps[0]["step_id"] == sb_id
    assert t2_steps[0]["step_order"] == 1
    assert t2_steps[1]["step_id"] == sa_id
    assert t2_steps[1]["step_order"] == 2
    
    conn.close()


def test_api_companies(client):
    # Setup tickets with some clients
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T1", "Company A", "S1"))
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T2", "Company B", "S2"))
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T3", "", "S3"))
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T4", None, "S4"))
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("T5", "Company A", "S5"))
    conn.commit()
    conn.close()

    resp = client.get("/api/companies")
    assert resp.status_code == 200
    companies = resp.json()
    assert len(companies) == 2
    assert "Company A" in companies
    assert "Company B" in companies


def test_api_search_with_boost(client):
    # Setup tickets with various clients and titles to test BM25 + boost
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Severe Server Failure", "Client Red", "500 Internal Server Error"))
    t1_id = c.lastrowid
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Server maintenance schedule", "Client Blue", "Backup failed at midnight"))
    t2_id = c.lastrowid
    conn.commit()
    conn.close()

    # Search with company boost for Client Blue - "Server" matches both, but Client Blue gets +10 boost
    resp = client.get("/api/search?q=Server&company=Client Blue")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 2
    assert tickets[0]["id"] == t2_id
    assert tickets[1]["id"] == t1_id

    # Search with company boost for Client Red - Client Red gets +10 boost
    resp = client.get("/api/search?q=Server&company=Client Red")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 2
    assert tickets[0]["id"] == t1_id
    assert tickets[1]["id"] == t2_id

    # Search without query but with company parameter - should order company first
    resp = client.get("/api/search?company=Client Blue")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 2
    assert tickets[0]["id"] == t2_id
    assert tickets[1]["id"] == t1_id

def test_extract_xml_endpoint(client, monkeypatch):
    mock_data = {
        "client": "SINGERFINANCE",
        "title": "Outbound Calls Disconnected Issue",
        "symptom": "SewwandS is experiencing disconnected outbound calls.",
        "steps": ["Requested Charaka to send outbound number", "Investigate using captures"]
    }
    
    # Mock extract_ticket_data in app.main / app.llm_extractor
    monkeypatch.setattr("app.main.extract_ticket_data", lambda *args, **kwargs: mock_data)
    
    xml_payload = """<rss version="0.92">
<channel>
<item>
<title>[DST-6613] SINGERFINANCE|Outbound Calls Disconnected Issue:Agent – SewwandS</title>
<description><p>SewwandS is experiencing outbound call drops.</p></description>
<comments>
<comment id="1">Pls check on this</comment>
<comment id="2">Investigate using captures</comment>
</comments>
</item>
</channel>
</rss>"""
    
    resp = client.post("/api/extract/xml", json={"xml_payload": xml_payload})
    assert resp.status_code == 200
    assert resp.json() == mock_data

def test_delete_ticket(client):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Delete Me", "Client X", "Symptom X"))
    ticket_id = c.lastrowid
    conn.commit()
    conn.close()
    
    resp = client.delete(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200
    assert resp.json() == {"status": "success"}
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    assert c.fetchone() is None
    conn.close()

def test_extract_command_from_instruction():
    from app.main import extract_command_from_instruction
    assert extract_command_from_instruction("Run `ping 8.8.8.8` to test connection") == "ping 8.8.8.8"
    assert extract_command_from_instruction("Execute: $ sudo apt update") == "sudo apt update"
    assert extract_command_from_instruction("Run **ping 8.8.8.8** to test connection") == "ping 8.8.8.8"
    assert extract_command_from_instruction("No command here") is None

def test_approve_draft_with_duplicate_steps(client):
    payload = {
        "title": "Duplicate steps test",
        "client": "Client Dup",
        "symptom": "Testing duplicate steps",
        "steps": ["Repeat step", "Repeat step", "Other step"],
        "raw_markdown": "# Duplicate steps test\n@ Client Dup\n> Testing duplicate steps\n- Repeat step\n- Repeat step\n- Other step"
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200
    
    resp = client.get("/api/staging/drafts")
    drafts = resp.json()
    draft_id = drafts[0]["id"]
    
    # Approve draft containing duplicates
    resp = client.post(f"/api/staging/approve/{draft_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    ticket_id = resp.json()["ticket_id"]
    
    # Verify steps in DB (should preserve step orders even with duplicate step IDs)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT step_id, step_order FROM ticket_steps WHERE ticket_id = ? ORDER BY step_order ASC", (ticket_id,))
    rows = c.fetchall()
    assert len(rows) == 3
    assert rows[0]["step_order"] == 1
    assert rows[1]["step_order"] == 2
    assert rows[2]["step_order"] == 3
    assert rows[0]["step_id"] == rows[1]["step_id"] # Must map to same master step
    conn.close()

def test_company_canonicalization(client):
    # Insert a draft with "Singer SL"
    payload = {
        "title": "Query test",
        "client": "Singer SL",
        "symptom": "some symptom",
        "steps": ["step 1"],
        "raw_markdown": "# Query test\n@ Singer SL\n> some symptom\n- step 1"
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200
    
    # Post another draft with "SINGERSL" (no space, different case)
    payload2 = {
        "title": "Query test 2",
        "client": "SINGERSL",
        "symptom": "some symptom 2",
        "steps": ["step 2"],
        "raw_markdown": "# Query test 2\n@ SINGERSL\n> some symptom 2\n- step 2"
    }
    resp2 = client.post("/api/staging/draft", json=payload2)
    assert resp2.status_code == 200
    
    # Fetch drafts and verify client name is canonicalized to "Singer SL"
    resp3 = client.get("/api/staging/drafts")
    drafts = resp3.json()
    clients = [d["parsed_client"] for d in drafts]
    assert "Singer SL" in clients
    assert "SINGERSL" not in clients # Should be canonicalized to Singer SL

def test_similar_commands_not_collapsed(client):
    # 1. Create a live ticket with root command 'sudo passwd -l root'
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Disable root", "Singer SL", "Lock root account"))
    ticket_id = c.lastrowid
    c.execute("INSERT INTO master_steps (instructions, command) VALUES (?, ?)", ("sudo passwd -l root", "sudo passwd -l root"))
    step_id = c.lastrowid
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (ticket_id, step_id, 1))
    conn.commit()
    conn.close()

    # 2. Insert a draft with a very similar command 'sudo passwd -S root'
    payload = {
        "title": "Check root status",
        "client": "Singer SL",
        "symptom": "Verify root status",
        "steps": ["sudo passwd -S root"],
        "raw_markdown": "# Check root status\n@ Singer SL\n> Verify root status\n- sudo passwd -S root"
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200

    resp_drafts = client.get("/api/staging/drafts")
    draft_id = resp_drafts.json()[0]["id"]

    # 3. Approve the draft
    resp_approve = client.post(f"/api/staging/approve/{draft_id}")
    assert resp_approve.status_code == 200
    new_ticket_id = resp_approve.json()["ticket_id"]

    # 4. Verify that a separate master step was created for 'sudo passwd -S root' and they were not collapsed
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, instructions FROM master_steps WHERE instructions = ?", ("sudo passwd -S root",))
    step_s = c.fetchone()
    assert step_s is not None

    c.execute("SELECT id, instructions FROM master_steps WHERE instructions = ?", ("sudo passwd -l root",))
    step_l = c.fetchone()
    assert step_l is not None
    assert step_s["id"] != step_l["id"]
    conn.close()

def test_maintenance_command_sync(client):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO master_steps (instructions, command, is_broken) VALUES (?, ?, ?)", ("Old instruction", "old_command", 1))
    step_id = c.lastrowid
    conn.commit()
    conn.close()

    # Resolve via UPDATE with a command block in the instruction text but keeping the command input unchanged or empty
    resp = client.patch(f"/api/maintenance/resolve/{step_id}", json={"action": "update", "text": "**new_command_value**"})
    assert resp.status_code == 200

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT command FROM master_steps WHERE id = ?", (step_id,))
    row = c.fetchone()
    conn.close()
    assert row["command"] == "new_command_value"

def test_pre_ticked_checklist_flow(client):
    # 1. Create a draft with checked and unchecked checklist items
    draft_payload = {
        "title": "Admin User Creation",
        "client": "Singer SL",
        "type": "ticket",
        "symptom": "Verify admin permissions",
        "steps": ["Create user in DB"],
        "checklist": ["[x] Database record created", "[ ] User role set to admin"]
    }
    resp = client.post("/api/staging/draft", json=draft_payload)
    assert resp.status_code == 200

    # Get the draft
    resp = client.get("/api/staging/drafts")
    assert resp.status_code == 200
    draft_id = resp.json()[0]["id"]

    # Approve to create ticket
    resp = client.post(f"/api/staging/approve/{draft_id}")
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]

    # Verify checklist was saved with prefixes
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT checklist FROM tickets WHERE id = ?", (ticket_id,))
    row = c.fetchone()
    conn.close()
    
    checklist = json.loads(row["checklist"])
    assert len(checklist) == 2
    assert checklist[0] == "[x] Database record created"
    assert checklist[1] == "[ ] User role set to admin"

    # Update checklist state using PUT
    update_payload = {
        "title": "Admin User Creation",
        "client": "Singer SL",
        "type": "ticket",
        "symptom": "Verify admin permissions",
        "steps": ["Create user in DB"],
        "checklist": ["[x] Database record created", "[x] User role set to admin"]
    }
    resp = client.put(f"/api/tickets/{ticket_id}", json=update_payload)
    assert resp.status_code == 200

    # Verify updated checklist
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT checklist FROM tickets WHERE id = ?", (ticket_id,))
    row = c.fetchone()
    conn.close()
    
    checklist_updated = json.loads(row["checklist"])
    assert checklist_updated[1] == "[x] User role set to admin"






