import pytest
import sqlite3
import json
import os
import io
import uuid
from fastapi.testclient import TestClient
from app import database

# Override database file for testing
database.DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_support_hub.db")

# Force app to use test_uploads directory to avoid deleting production uploads during tests
import app.main as main_module
main_module.UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "test_uploads")
main_module.UPLOAD_URL_PREFIX = "/static/test_uploads"

from app.main import app
from app.database import init_db, get_db_connection

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    init_db()
    # Create static/test_uploads if not exists
    upload_dir = main_module.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    
    # Track files that existed before the test run
    pre_existing_files = set(os.listdir(upload_dir))
    
    yield
    # Clean up test DB
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)
    # Clean up ONLY the files created during this test run
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            if f not in pre_existing_files:
                try:
                    os.remove(os.path.join(upload_dir, f))
                except Exception:
                    pass
        # Clean up directory itself if empty
        try:
            if not os.listdir(upload_dir):
                os.rmdir(upload_dir)
        except Exception:
            pass

@pytest.fixture
def client():
    return TestClient(app)

def test_file_upload(client):
    # Perform a multipart upload
    file_data = b"fake image data"
    file_name = "test_image.png"
    
    response = client.post(
        "/api/upload",
        files={"file": (file_name, io.BytesIO(file_data), "image/png")}
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert "file_path" in res_data
    assert res_data["file_path"].startswith(main_module.UPLOAD_URL_PREFIX + "/")
    
    # Check that file exists on disk
    filename = res_data["file_path"].split("/")[-1]
    disk_path = os.path.join(main_module.UPLOAD_DIR, filename)
    assert os.path.exists(disk_path)
    with open(disk_path, "rb") as f:
        assert f.read() == file_data

def test_add_step_image_association(client):
    # Setup a step first
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO master_steps (instructions) VALUES (?)", ("Test instructions",))
    step_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Post association
    img_path = f"{main_module.UPLOAD_URL_PREFIX}/some_image.png"
    payload = {"file_path": img_path}
    response = client.post(f"/api/steps/{step_id}/image", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Query database to check if record exists
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM step_images WHERE step_id = ?", (step_id,))
    row = c.fetchone()
    assert row is not None
    assert row["file_path"] == img_path
    conn.close()

def test_draft_with_images_flow(client):
    # 1. Post staging draft with images
    img1 = f"{main_module.UPLOAD_URL_PREFIX}/img1.png"
    img2 = f"{main_module.UPLOAD_URL_PREFIX}/img2.png"
    img_updated = f"{main_module.UPLOAD_URL_PREFIX}/img_updated.png"
    
    payload = {
        "title": "Staging Draft with Images",
        "client": "Client Imaginary",
        "symptom": "Images test",
        "steps": ["Step with image 1"],
        "images": [img1, img2]
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200
    
    # 2. Get staging drafts and check images
    resp = client.get("/api/staging/drafts")
    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 1
    assert drafts[0]["parsed_images"] == [img1, img2]
    draft_id = drafts[0]["id"]
    
    # 3. Compare draft should return images
    resp = client.get(f"/api/staging/compare/{draft_id}")
    assert resp.status_code == 200
    compare_data = resp.json()
    assert compare_data["draft"]["parsed_images"] == [img1, img2]
    
    # 4. Update draft with images
    update_payload = {
        "title": "Updated Draft Title",
        "client": "Client Imaginary",
        "symptom": "Updated Images test",
        "steps": ["Step with image 1"],
        "images": [img_updated]
    }
    resp = client.put(f"/api/staging/update/{draft_id}", json=update_payload)
    assert resp.status_code == 200
    
    # Verify updated
    resp = client.get("/api/staging/drafts")
    assert resp.json()[0]["parsed_images"] == [img_updated]

def test_approve_draft_with_images(client):
    # Upload some mock images to simulate files on disk
    upload_dir = main_module.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    
    img1_filename = "mock_img1.png"
    img2_filename = "mock_img2.png"
    img3_filename = "mock_img3.png" # Will be orphaned
    
    with open(os.path.join(upload_dir, img1_filename), "wb") as f:
        f.write(b"img1")
    with open(os.path.join(upload_dir, img2_filename), "wb") as f:
        f.write(b"img2")
    with open(os.path.join(upload_dir, img3_filename), "wb") as f:
        f.write(b"img3")
        
    img1_path = f"{main_module.UPLOAD_URL_PREFIX}/{img1_filename}"
    img2_path = f"{main_module.UPLOAD_URL_PREFIX}/{img2_filename}"
    img3_path = f"{main_module.UPLOAD_URL_PREFIX}/{img3_filename}"
    
    # Post draft
    payload = {
        "title": "Approval test with images",
        "client": "Client Z",
        "symptom": "Testing image mapping",
        "steps": ["Step 1"],
        "images": [img1_path, img2_path]
    }
    resp = client.post("/api/staging/draft", json=payload)
    assert resp.status_code == 200
    
    # Get draft ID
    resp = client.get("/api/staging/drafts")
    draft_id = resp.json()[0]["id"]
    
    # Approve draft
    resp = client.post(f"/api/staging/approve/{draft_id}")
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]
    
    # Verify ticket_images has the rows
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM ticket_images WHERE ticket_id = ?", (ticket_id,))
    rows = c.fetchall()
    assert len(rows) == 2
    paths = {r["file_path"] for r in rows}
    assert paths == {img1_path, img2_path}
    conn.close()
    
    # Verify disk cleanup deleted img3 but kept img1 and img2
    assert os.path.exists(os.path.join(upload_dir, img1_filename))
    assert os.path.exists(os.path.join(upload_dir, img2_filename))
    assert not os.path.exists(os.path.join(upload_dir, img3_filename))

def test_merge_draft_with_images(client):
    upload_dir = main_module.UPLOAD_DIR
    img_filename = "merge_img.png"
    img_path = f"{main_module.UPLOAD_URL_PREFIX}/{img_filename}"
    
    with open(os.path.join(upload_dir, img_filename), "wb") as f:
        f.write(b"merge")
        
    # Setup live ticket
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Live Ticket", "Client M", "Symptom M"))
    ticket_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Create draft
    payload = {
        "title": "Live Ticket",
        "client": "Client M",
        "symptom": "Symptom M",
        "steps": ["Step 2"],
        "images": [img_path]
    }
    client.post("/api/staging/draft", json=payload)
    draft_id = client.get("/api/staging/drafts").json()[0]["id"]
    
    # Merge
    merge_payload = {
        "draft_id": draft_id,
        "target_live_ticket_id": ticket_id
    }
    resp = client.post("/api/staging/merge", json=merge_payload)
    assert resp.status_code == 200
    
    # Check ticket_images
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM ticket_images WHERE ticket_id = ?", (ticket_id,))
    rows = c.fetchall()
    assert len(rows) == 1
    assert rows[0]["file_path"] == img_path
    conn.close()
    assert os.path.exists(os.path.join(upload_dir, img_filename))

def test_maintenance_resolve_delete_cleanup(client):
    upload_dir = main_module.UPLOAD_DIR
    img_filename = "step_broken_img.png"
    img_path = f"{main_module.UPLOAD_URL_PREFIX}/{img_filename}"
    
    with open(os.path.join(upload_dir, img_filename), "wb") as f:
        f.write(b"broken")
        
    # Setup step and associate image
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO master_steps (instructions, is_broken) VALUES (?, ?)", ("Broken step instructions", 1))
    step_id = c.lastrowid
    c.execute("INSERT INTO step_images (step_id, file_path) VALUES (?, ?)", (step_id, img_path))
    conn.commit()
    conn.close()
    
    assert os.path.exists(os.path.join(upload_dir, img_filename))
    
    # Resolve delete
    resp = client.patch(f"/api/maintenance/resolve/{step_id}", json={"action": "delete"})
    assert resp.status_code == 200
    
    # Check file is deleted from disk due to cleanup
    assert not os.path.exists(os.path.join(upload_dir, img_filename))

def test_search_and_maintenance_return_images(client):
    conn = get_db_connection()
    c = conn.cursor()
    
    timg = f"{main_module.UPLOAD_URL_PREFIX}/timg.png"
    simg = f"{main_module.UPLOAD_URL_PREFIX}/simg.png"

    # Insert ticket
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Ticket Search Test", "Client Search", "Symptom Search"))
    ticket_id = c.lastrowid
    c.execute("INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)", (ticket_id, timg))
    
    # Insert step
    c.execute("INSERT INTO master_steps (instructions, is_broken) VALUES (?, ?)", ("Step search test", 1))
    step_id = c.lastrowid
    c.execute("INSERT INTO step_images (step_id, file_path) VALUES (?, ?)", (step_id, simg))
    
    # Link ticket to step
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (ticket_id, step_id, 1))
    
    conn.commit()
    conn.close()
    
    # Test GET /api/search
    resp = client.get("/api/search")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 1
    assert tickets[0]["images"] == [timg]
    assert tickets[0]["steps"][0]["images"] == [simg]
    
    # Test GET /api/maintenance/queue
    resp = client.get("/api/maintenance/queue")
    assert resp.status_code == 200
    queue = resp.json()
    assert len(queue) == 1
    assert queue[0]["images"] == [simg]

def test_add_ticket_image_association(client):
    # Setup a ticket first
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Test Ticket", "Test Client", "Test Symptom"))
    ticket_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Post association
    img_path = f"{main_module.UPLOAD_URL_PREFIX}/some_ticket_image.png"
    payload = {"file_path": img_path}
    response = client.post(f"/api/tickets/{ticket_id}/image", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Query database to check if record exists
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM ticket_images WHERE ticket_id = ?", (ticket_id,))
    row = c.fetchone()
    assert row is not None
    assert row["file_path"] == img_path
    conn.close()

def test_remove_ticket_image_association(client):
    # Setup a ticket first
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom) VALUES (?, ?, ?)", ("Test Ticket 2", "Test Client 2", "Test Symptom 2"))
    ticket_id = c.lastrowid
    img_path = f"{main_module.UPLOAD_URL_PREFIX}/remove_me.png"
    c.execute("INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)", (ticket_id, img_path))
    conn.commit()
    conn.close()
    
    # Send DELETE request
    payload = {"file_path": img_path}
    response = client.request("DELETE", f"/api/tickets/{ticket_id}/image", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Query database to check if record was removed
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM ticket_images WHERE ticket_id = ? AND file_path = ?", (ticket_id, img_path))
    row = c.fetchone()
    assert row is None
    conn.close()

def test_update_ticket(client):
    # Setup live ticket and steps
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (title, client, symptom, type) VALUES (?, ?, ?, ?)", ("Original Ticket", "Company A", "Original Symptom", "ticket"))
    ticket_id = c.lastrowid
    c.execute("INSERT INTO master_steps (instructions, command) VALUES (?, ?)", ("Step 1 instructions", "echo step1"))
    step1_id = c.lastrowid
    c.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)", (ticket_id, step1_id, 1))
    conn.commit()
    conn.close()

    # Call PUT endpoint to edit the ticket
    payload = {
        "title": "Updated Ticket Title",
        "client": "Company B",
        "symptom": "Updated Symptom Description",
        "type": "guide",
        "checklist": ["Verify login works", "Verify DB connection"],
        "steps": ["Step 1 instructions", "New step instructions"]
    }
    response = client.put(f"/api/tickets/{ticket_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Query DB to check updates
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT title, client, symptom, type, checklist FROM tickets WHERE id = ?", (ticket_id,))
    ticket = c.fetchone()
    assert ticket["title"] == "Updated Ticket Title"
    assert ticket["client"] == "Company B"
    assert ticket["symptom"] == "Updated Symptom Description"
    assert ticket["type"] == "guide"
    assert json.loads(ticket["checklist"]) == ["Verify login works", "Verify DB connection"]

    # Verify steps have been correctly linked
    c.execute(
        """
        SELECT ms.instructions, ts.step_order 
        FROM ticket_steps ts 
        JOIN master_steps ms ON ts.step_id = ms.id 
        WHERE ts.ticket_id = ? 
        ORDER BY ts.step_order ASC
        """,
        (ticket_id,)
    )
    steps = c.fetchall()
    assert len(steps) == 2
    assert steps[0]["instructions"] == "Step 1 instructions"
    assert steps[0]["step_order"] == 1
    assert steps[1]["instructions"] == "New step instructions"
    assert steps[1]["step_order"] == 2
    conn.close()
