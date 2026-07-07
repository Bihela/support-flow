from fastapi import FastAPI, Request, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from datetime import datetime, timezone
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import uuid
import shutil
import re
from app.database import (
    get_db_connection,
    init_db,
    get_alert_settings,
    update_alert_settings,
    add_alert,
    get_unseen_alerts,
    mark_alert_seen,
)
from app.collision import check_collisions
from app.llm_extractor import extract_ticket_data
from rapidfuzz import fuzz
import sqlite3

def extract_command_from_instruction(instr: str) -> Optional[str]:
    # Pattern 1: wrapped in backticks
    match = re.search(r'`([^`]+)`', instr)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: wrapped in double asterisks
    match = re.search(r'\*\*([^*]+)\*\*', instr)
    if match:
        return match.group(1).strip()
    
    # Pattern 3: starts with a command prompt sign like $ or # or Run: 
    match = re.search(r'(?:^|\s)(?:\$|#|Run:)\s*([a-zA-Z0-9_\-\.\/]+(?:\s+[^\n]+)?)', instr, re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    return None

def find_matching_step_id(step_instr: str, existing_master_steps: List[Dict[str, Any]]) -> Optional[int]:
    """
    Checks if step_instr matches any existing master steps.
    To avoid dangerous collisions on commands and options, we enforce a strict policy:
    1. Exact case-insensitive match (after stripping whitespace).
    2. If there are option flags (e.g. -S, -l) or if it's a command, do NOT allow fuzzy matching.
    3. For text-only instructions, allow fuzzy matching with a high threshold (e.g. >= 95.0 token_sort_ratio),
       but ONLY if neither instruction contains command-like syntax (backticks, prompt indicators, or hyphens).
    """
    cleaned_instr = step_instr.strip().lower()
    
    # Check for exact match first
    for ms in existing_master_steps:
        if ms["instructions"].strip().lower() == cleaned_instr:
            return ms["id"]
            
    # Helper to check if string contains command indicators or options/arguments
    def has_command_or_flags(text: str) -> bool:
        if "`" in text or "$" in text or "#" in text:
            return True
        if " -" in text or text.startswith("-"):
            return True
        return False

    if has_command_or_flags(step_instr):
        return None

    # For pure text instructions, fallback to fuzzy match with >= 95% threshold
    best_match_id = None
    best_match_score = 0.0
    for ms in existing_master_steps:
        if has_command_or_flags(ms["instructions"]):
            continue
        score = fuzz.token_sort_ratio(step_instr.lower(), ms["instructions"].lower())
        if score > best_match_score:
            best_match_score = score
            best_match_id = ms["id"]
            
    if best_match_score >= 95.0:
        return best_match_id
        
    return None

app = FastAPI(title="Support Engineer Knowledge Hub")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
UPLOAD_URL_PREFIX = "/static/uploads"

class XMLExtractPayload(BaseModel):
    xml_payload: str

class TemplateCreate(BaseModel):
    title: str
    category: Optional[str] = "general"
    body: str
    linked_ticket_id: Optional[int] = None

class NoteCreate(BaseModel):
    title: str
    body: Optional[str] = ""
    color: Optional[str] = "blue"
    is_pinned: Optional[int] = 0
    reminder_date: Optional[str] = None


import asyncio
import threading
import imaplib
import email
from email.header import decode_header
import xml.etree.ElementTree as ET
import logging
import tempfile

logger = logging.getLogger("support_hub_monitors")

# Ensure DB is initialized on startup
monitors_running = True
background_threads = []

def parse_xml_payload(xml_str: str):
    """
    Parses WhatsApp notification XML toast payload.
    Format: <binding template="ToastText02"><text id="1">SenderName</text><text id="2">MessageText</text></binding>
    """
    try:
        root = ET.fromstring(xml_str)
        texts = root.findall(".//text")
        sender = ""
        content = ""
        for t in texts:
            text_id = t.get("id")
            if text_id == "1":
                sender = t.text or ""
            elif text_id == "2":
                content = t.text or ""
        return sender.strip(), content.strip()
    except Exception as e:
        logger.warning(f"Failed to parse XML notification payload: {e}")
        return "", ""

def run_async_coro(coro):
    """Helper to run async coroutines in a background thread with its own event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()

async def broadcast_alert(alert_data: dict):
    await alert_manager.broadcast(alert_data)

def poll_emails():
    while monitors_running:
        try:
            conn = get_db_connection()
            try:
                settings = get_alert_settings(conn)
            finally:
                conn.close()

            if not settings or not settings.get("is_on_shift"):
                # Not on shift, wait and try again
                asyncio.run(asyncio.sleep(5))
                continue

            imap_host = settings.get("imap_host")
            imap_port = settings.get("imap_port") or 993
            imap_user = settings.get("imap_user")
            imap_password = settings.get("imap_password")
            keywords_str = settings.get("target_email_keywords") or ""
            keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]

            if not imap_host or not imap_user or not imap_password:
                # Missing credentials, sleep and continue
                asyncio.run(asyncio.sleep(5))
                continue

            mail = None
            try:
                mail = imaplib.IMAP4_SSL(imap_host, int(imap_port))
                mail.login(imap_user, imap_password)
                mail.select("inbox")

                status, messages = mail.search(None, "UNSEEN")
                if status == "OK":
                    for num in messages[0].split():
                        status, data = mail.fetch(num, "(RFC822)")
                        if status != "OK":
                            continue
                        
                        raw_email = data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Decode subject
                        subject = ""
                        if msg["Subject"]:
                            decoded_subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(decoded_subject, bytes):
                                subject = decoded_subject.decode(encoding or "utf-8", errors="ignore")
                            else:
                                subject = decoded_subject
                        
                        # Decode sender
                        sender = ""
                        if msg["From"]:
                            decoded_sender, encoding = decode_header(msg["From"])[0]
                            if isinstance(decoded_sender, bytes):
                                sender = decoded_sender.decode(encoding or "utf-8", errors="ignore")
                            else:
                                sender = decoded_sender

                        # Find matching keywords
                        subject_lower = subject.lower()
                        sender_lower = sender.lower()
                        matched = False
                        
                        # If no keywords are defined, match everything. Otherwise check match.
                        if not keywords:
                            matched = True
                        else:
                            for kw in keywords:
                                if kw in subject_lower or kw in sender_lower:
                                    matched = True
                                    break
                        
                        if matched:
                            message_id = msg.get("Message-ID", "")
                            # Clean message_id for Gmail URL, stripping angle brackets
                            clean_mid = message_id.strip("<>")
                            link = f"https://mail.google.com/mail/u/0/#inbox/{clean_mid}" if clean_mid else f"https://mail.google.com/mail/u/0/#search/{sender}"
                            
                            # Check if alert already exists in DB
                            db_conn = get_db_connection()
                            try:
                                cursor = db_conn.cursor()
                                cursor.execute("SELECT id FROM received_alerts WHERE link = ?", (link,))
                                existing = cursor.fetchone()
                                if not existing:
                                    alert_id = add_alert(db_conn, "email", sender, subject, link)
                                    # Broadcast alert
                                    cursor.execute("SELECT * FROM received_alerts WHERE id = ?", (alert_id,))
                                    row = cursor.fetchone()
                                    if row:
                                        # Use a thread-safe helper to run the broadcast
                                        asyncio.run(broadcast_alert(dict(row)))
                            finally:
                                db_conn.close()
            except Exception as e:
                logger.warning(f"Error during IMAP polling: {e}")
            finally:
                if mail:
                    try:
                        mail.close()
                    except Exception:
                        pass
                    try:
                        mail.logout()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"General error in poll_emails loop: {e}")
        
        # Sleep for a bit
        asyncio.run(asyncio.sleep(5))

def poll_whatsapp():
    while monitors_running:
        try:
            conn = get_db_connection()
            try:
                settings = get_alert_settings(conn)
            finally:
                conn.close()

            if not settings or not settings.get("is_on_shift"):
                asyncio.run(asyncio.sleep(5))
                continue

            target_names_str = settings.get("target_whatsapp_names") or ""
            target_names = [n.strip().lower() for n in target_names_str.split(",") if n.strip()]

            # Locate Windows Action Center db
            wpn_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")
            if not os.path.exists(wpn_path):
                # Safe fallback if file doesn't exist (e.g. non-Windows OS or no notifications)
                logger.warning(f"Windows notifications database not found at {wpn_path}. WhatsApp monitoring is suspended.")
                asyncio.run(asyncio.sleep(5))
                continue

            # Since Windows locks the file, copy to a temp location
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
                temp_path = tf.name
            
            try:
                shutil.copy2(wpn_path, temp_path)
                
                # Query notifications
                temp_conn = sqlite3.connect(temp_path)
                temp_conn.row_factory = sqlite3.Row
                try:
                    cursor = temp_conn.cursor()
                    cursor.execute("""
                        SELECT Notification.Id, Notification.Payload, Notification.ExpiryTime 
                        FROM Notification 
                        JOIN NotificationHandler ON Notification.HandlerId = NotificationHandler.RecordId 
                        WHERE NotificationHandler.PrimaryId LIKE '%WhatsApp%'
                    """)
                    rows = cursor.fetchall()
                finally:
                    temp_conn.close()

                # Process matching notifications
                for row in rows:
                    payload_xml = row["Payload"]
                    if not payload_xml:
                        continue
                    
                    if isinstance(payload_xml, bytes):
                        try:
                            payload_xml = payload_xml.decode("utf-8", errors="ignore")
                        except Exception:
                            continue
                            
                    sender, text = parse_xml_payload(payload_xml)
                    if not sender:
                        continue
                    
                    # Filter by target names (if specified)
                    matched = False
                    if not target_names:
                        matched = True
                    else:
                        sender_lower = sender.lower()
                        for tn in target_names:
                            if tn in sender_lower:
                                matched = True
                                break
                    
                    if matched:
                        # Check if already in received_alerts by sender and content
                        db_conn = get_db_connection()
                        try:
                            cursor = db_conn.cursor()
                            cursor.execute(
                                "SELECT id FROM received_alerts WHERE type = 'whatsapp' AND sender = ? AND content = ?",
                                (sender, text)
                            )
                            existing = cursor.fetchone()
                            if not existing:
                                alert_id = add_alert(db_conn, "whatsapp", sender, text, None)
                                # Broadcast
                                cursor.execute("SELECT * FROM received_alerts WHERE id = ?", (alert_id,))
                                alert_row = cursor.fetchone()
                                if alert_row:
                                    asyncio.run(broadcast_alert(dict(alert_row)))
                        finally:
                            db_conn.close()
            except Exception as e:
                logger.warning(f"Error querying Windows notification database: {e}")
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"General error in poll_whatsapp loop: {e}")

        asyncio.run(asyncio.sleep(5))

@app.on_event("startup")
def startup_event():
    global monitors_running, background_threads
    init_db()
    
    monitors_running = True
    
    # Start email monitor thread
    email_thread = threading.Thread(target=poll_emails, daemon=True, name="EmailMonitor")
    email_thread.start()
    background_threads.append(email_thread)

    # Start WhatsApp monitor thread
    whatsapp_thread = threading.Thread(target=poll_whatsapp, daemon=True, name="WhatsAppMonitor")
    whatsapp_thread.start()
    background_threads.append(whatsapp_thread)

@app.on_event("shutdown")
def shutdown_event():
    global monitors_running
    monitors_running = False
    for t in background_threads:
        t.join(timeout=1.0)


# Ensure directories exist
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

class DraftPayload(BaseModel):
    title: str
    client: Optional[str] = ""
    symptom: Optional[str] = ""
    steps: List[str]
    raw_markdown: Optional[str] = ""
    images: Optional[List[str]] = []
    type: Optional[str] = "ticket"
    checklist: Optional[List[str]] = []

class UpdateDraftPayload(BaseModel):
    title: str
    client: Optional[str] = ""
    symptom: Optional[str] = ""
    steps: List[str]
    images: Optional[List[str]] = []
    type: Optional[str] = "ticket"
    checklist: Optional[List[str]] = []

class MergePayload(BaseModel):
    draft_id: int
    target_live_ticket_id: int

class StepImagePayload(BaseModel):
    file_path: str

class TicketImagePayload(BaseModel):
    file_path: str

def cleanup_orphaned_images(cursor):
    try:
        # Select all unique file_path values from ticket_images and step_images
        cursor.execute("SELECT DISTINCT file_path FROM ticket_images")
        ticket_imgs = {row["file_path"] for row in cursor.fetchall()}
        
        cursor.execute("SELECT DISTINCT file_path FROM step_images")
        step_imgs = {row["file_path"] for row in cursor.fetchall()}
        
        # Select all unique images in staging inbox
        cursor.execute("SELECT parsed_images FROM staging_inbox")
        staging_imgs = set()
        for row in cursor.fetchall():
            if row["parsed_images"]:
                try:
                    imgs = json.loads(row["parsed_images"])
                    for img in imgs:
                        staging_imgs.add(img)
                except Exception:
                    pass
        
        db_paths = ticket_imgs.union(step_imgs).union(staging_imgs)
        
        # Read the list of files in the configured upload directory
        upload_dir = UPLOAD_DIR
        if not os.path.exists(upload_dir):
            return
            
        for filename in os.listdir(upload_dir):
            relative_path = f"{UPLOAD_URL_PREFIX}/{filename}"
            if relative_path not in db_paths:
                file_to_delete = os.path.join(upload_dir, filename)
                if os.path.isfile(file_to_delete):
                    os.remove(file_to_delete)
    except Exception as e:
        print(f"Error in cleanup_orphaned_images: {e}")

# Serve the search homepage directly from templates
@app.get("/", response_class=HTMLResponse)
def get_search_homepage():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "search.html")
    if not os.path.exists(template_path):
         raise HTTPException(status_code=404, detail="Template search.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Serve the Dump Box HTML page directly from templates
@app.get("/dumpbox", response_class=HTMLResponse)
def get_dumpbox():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dumpbox.html")
    if not os.path.exists(template_path):
         raise HTTPException(status_code=404, detail="Template dumpbox.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    try:
        upload_dir = UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        _, ext = os.path.splitext(file.filename)
        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"file_path": f"{UPLOAD_URL_PREFIX}/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/steps/{step_id}/image")
def add_step_image(step_id: int, payload: StepImagePayload):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM master_steps WHERE id = ?", (step_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Step not found")
        cursor.execute(
            "INSERT INTO step_images (step_id, file_path) VALUES (?, ?)",
            (step_id, payload.file_path)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/tickets/{ticket_id}/image")
def add_ticket_image(ticket_id: int, payload: TicketImagePayload):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")
        cursor.execute(
            "INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)",
            (ticket_id, payload.file_path)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/tickets/{ticket_id}/image")
def remove_ticket_image(ticket_id: int, payload: TicketImagePayload):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")
        cursor.execute(
            "DELETE FROM ticket_images WHERE ticket_id = ? AND file_path = ?",
            (ticket_id, payload.file_path)
        )
        cleanup_orphaned_images(cursor)
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def canonicalize_client_name(client: Optional[str]) -> Optional[str]:
    if not client:
        return client
    stripped = client.strip()
    if not stripped:
        return stripped
    
    def normalize(name: str) -> str:
        return "".join(c for c in name.lower() if c.isalnum())
        
    norm_stripped = normalize(stripped)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT client FROM tickets WHERE client IS NOT NULL AND client != ''")
        existing_clients = [r["client"] for r in cursor.fetchall()]
        for ec in existing_clients:
            if normalize(ec) == norm_stripped:
                return ec
        cursor.execute("SELECT DISTINCT parsed_client FROM staging_inbox WHERE parsed_client IS NOT NULL AND parsed_client != ''")
        existing_staging = [r["parsed_client"] for r in cursor.fetchall()]
        for ec in existing_staging:
            if normalize(ec) == norm_stripped:
                return ec
    except Exception:
        pass
    finally:
        conn.close()
    return stripped

@app.post("/api/staging/draft")
def save_staging_draft(payload: DraftPayload):
    try:
        client_name = canonicalize_client_name(payload.client)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO staging_inbox (raw_markdown, parsed_title, parsed_client, parsed_symptom, parsed_steps, parsed_images, parsed_type, parsed_checklist)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.raw_markdown,
                payload.title,
                client_name,
                payload.symptom,
                json.dumps(payload.steps),
                json.dumps(payload.images or []),
                payload.type,
                json.dumps(payload.checklist or [])
            )
        )
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Draft saved to staging inbox."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 1. GET /staging: Serve the HTML template staging.html
@app.get("/staging", response_class=HTMLResponse)
def get_staging():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "staging.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template staging.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# 2. GET /api/staging/drafts: Fetch all drafts ordered by created_at DESC
@app.get("/api/staging/drafts")
def get_staging_drafts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staging_inbox ORDER BY created_at DESC")
        rows = cursor.fetchall()
        drafts = []
        for r in rows:
            drafts.append({
                "id": r["id"],
                "raw_markdown": r["raw_markdown"],
                "parsed_title": r["parsed_title"],
                "parsed_client": r["parsed_client"],
                "parsed_symptom": r["parsed_symptom"],
                "parsed_steps": json.loads(r["parsed_steps"]) if r["parsed_steps"] else [],
                "parsed_images": json.loads(r["parsed_images"]) if r["parsed_images"] else [],
                "type": r["parsed_type"] if "parsed_type" in r.keys() and r["parsed_type"] else "ticket",
                "checklist": json.loads(r["parsed_checklist"]) if "parsed_checklist" in r.keys() and r["parsed_checklist"] else [],
                "created_at": r["created_at"]
            })
        conn.close()
        return drafts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. GET /api/staging/compare/{draft_id}
@app.get("/api/staging/compare/{draft_id}")
def compare_draft(draft_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staging_inbox WHERE id = ?", (draft_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Draft not found")
        
        draft = {
            "id": row["id"],
            "raw_markdown": row["raw_markdown"],
            "parsed_title": row["parsed_title"],
            "parsed_client": row["parsed_client"],
            "parsed_symptom": row["parsed_symptom"],
            "parsed_steps": json.loads(row["parsed_steps"]) if row["parsed_steps"] else [],
            "parsed_images": json.loads(row["parsed_images"]) if row["parsed_images"] else [],
            "type": row["parsed_type"] if "parsed_type" in row.keys() and row["parsed_type"] else "ticket",
            "checklist": json.loads(row["parsed_checklist"]) if "parsed_checklist" in row.keys() and row["parsed_checklist"] else []
        }
        
        cursor.execute("SELECT id, title, client, symptom FROM tickets")
        live_rows = cursor.fetchall()
        live_tickets = [dict(lr) for lr in live_rows]
        conn.close()
        
        collisions = check_collisions(draft["parsed_title"], draft["parsed_symptom"], live_tickets)
        return {
            "draft": draft,
            "collisions": collisions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. POST /api/staging/approve/{draft_id}
@app.post("/api/staging/approve/{draft_id}")
def approve_draft(draft_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Fetch the draft
        cursor.execute("SELECT * FROM staging_inbox WHERE id = ?", (draft_id,))
        draft_row = cursor.fetchone()
        if not draft_row:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        title = draft_row["parsed_title"]
        client = canonicalize_client_name(draft_row["parsed_client"])
        symptom = draft_row["parsed_symptom"]
        steps = json.loads(draft_row["parsed_steps"]) if draft_row["parsed_steps"] else []
        parsed_images = json.loads(draft_row["parsed_images"]) if draft_row["parsed_images"] else []
        draft_type = draft_row["parsed_type"] if "parsed_type" in draft_row.keys() and draft_row["parsed_type"] else "ticket"
        draft_checklist = draft_row["parsed_checklist"] if "parsed_checklist" in draft_row.keys() and draft_row["parsed_checklist"] else "[]"
        
        # Insert into tickets
        cursor.execute(
            "INSERT INTO tickets (title, client, symptom, type, checklist) VALUES (?, ?, ?, ?, ?)",
            (title, client, symptom, draft_type, draft_checklist)
        )
        new_ticket_id = cursor.lastrowid
        
        # Process steps with fuzzy deduplication
        cursor.execute("SELECT id, instructions FROM master_steps")
        existing_master_steps = [dict(r) for r in cursor.fetchall()]
        
        for step_order, step_instr in enumerate(steps, start=1):
            step_id = find_matching_step_id(step_instr, existing_master_steps)
            if not step_id:
                cmd_val = extract_command_from_instruction(step_instr)
                cursor.execute("INSERT INTO master_steps (instructions, command) VALUES (?, ?)", (step_instr, cmd_val))
                step_id = cursor.lastrowid
                existing_master_steps.append({"id": step_id, "instructions": step_instr})
            
            # Insert relationship
            cursor.execute(
                "INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)",
                (new_ticket_id, step_id, step_order)
            )
            
        # Insert images
        for img_path in parsed_images:
            cursor.execute(
                "INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)",
                (new_ticket_id, img_path)
            )
        
        # Delete from staging inbox
        cursor.execute("DELETE FROM staging_inbox WHERE id = ?", (draft_id,))
        
        # Cleanup orphaned files
        cleanup_orphaned_images(cursor)
        
        # Commit everything atomically
        conn.commit()
        return {"status": "success", "ticket_id": new_ticket_id}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# 5. POST /api/staging/merge
@app.post("/api/staging/merge")
def merge_draft(payload: MergePayload):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Fetch draft
        cursor.execute("SELECT * FROM staging_inbox WHERE id = ?", (payload.draft_id,))
        draft_row = cursor.fetchone()
        if not draft_row:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        # Fetch live ticket to verify existence
        cursor.execute("SELECT id, type, checklist FROM tickets WHERE id = ?", (payload.target_live_ticket_id,))
        ticket_row = cursor.fetchone()
        if not ticket_row:
            raise HTTPException(status_code=404, detail="Target live ticket not found")
        
        target_type = ticket_row["type"] if ticket_row["type"] else "ticket"
        target_checklist_str = ticket_row["checklist"]
        
        draft_type = draft_row["parsed_type"] if "parsed_type" in draft_row.keys() and draft_row["parsed_type"] else "ticket"
        draft_checklist_str = draft_row["parsed_checklist"]

        final_type = target_type
        if draft_type == "guide" or target_type == "guide":
            final_type = "guide"
            
        # Combine checklists
        target_chk = json.loads(target_checklist_str) if target_checklist_str else []
        draft_chk = json.loads(draft_checklist_str) if draft_checklist_str else []
        combined_chk = list(target_chk)
        for item in draft_chk:
            if item not in combined_chk:
                combined_chk.append(item)
                
        cursor.execute(
            "UPDATE tickets SET type = ?, checklist = ? WHERE id = ?",
            (final_type, json.dumps(combined_chk), payload.target_live_ticket_id)
        )
        
        # Get existing steps order/mapping for target ticket
        cursor.execute(
            """
            SELECT ts.step_id, ms.instructions, ts.step_order 
            FROM ticket_steps ts
            JOIN master_steps ms ON ts.step_id = ms.id
            WHERE ts.ticket_id = ?
            ORDER BY ts.step_order ASC
            """,
            (payload.target_live_ticket_id,)
        )
        existing_steps = cursor.fetchall()
        existing_instructions = {es["instructions"] for es in existing_steps}
        
        max_existing_order = 0
        if existing_steps:
            max_existing_order = max(es["step_order"] for es in existing_steps)
            
        draft_steps = json.loads(draft_row["parsed_steps"]) if draft_row["parsed_steps"] else []
        parsed_images = json.loads(draft_row["parsed_images"]) if draft_row["parsed_images"] else []
        
        # Select all master steps to allow fuzzy matching
        cursor.execute("SELECT id, instructions FROM master_steps")
        existing_master_steps = [dict(r) for r in cursor.fetchall()]
 
        for step_instr in draft_steps:
            step_id = find_matching_step_id(step_instr, existing_master_steps)
            if not step_id:
                cmd_val = extract_command_from_instruction(step_instr)
                cursor.execute("INSERT INTO master_steps (instructions, command) VALUES (?, ?)", (step_instr, cmd_val))
                step_id = cursor.lastrowid
                existing_master_steps.append({"id": step_id, "instructions": step_instr})
 
            # Check if this relationship already exists for this ticket
            cursor.execute("SELECT 1 FROM ticket_steps WHERE ticket_id = ? AND step_id = ?", (payload.target_live_ticket_id, step_id))
            if cursor.fetchone():
                continue
 
            max_existing_order += 1
            cursor.execute(
                "INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)",
                (payload.target_live_ticket_id, step_id, max_existing_order)
            )
            
        # Copy draft-level images into ticket_images linked to the target live ticket
        for img_path in parsed_images:
            cursor.execute(
                "SELECT id FROM ticket_images WHERE ticket_id = ? AND file_path = ?",
                (payload.target_live_ticket_id, img_path)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)",
                    (payload.target_live_ticket_id, img_path)
                )
            
        # Delete draft from staging inbox
        cursor.execute("DELETE FROM staging_inbox WHERE id = ?", (payload.draft_id,))
        
        # Cleanup orphaned files
        cleanup_orphaned_images(cursor)
        
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# 6. DELETE /api/staging/discard/{draft_id}
@app.delete("/api/staging/discard/{draft_id}")
def discard_draft(draft_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Verify it exists
        cursor.execute("SELECT id FROM staging_inbox WHERE id = ?", (draft_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Draft not found")
        
        cursor.execute("DELETE FROM staging_inbox WHERE id = ?", (draft_id,))
        
        # Cleanup orphaned files
        cleanup_orphaned_images(cursor)
        
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# DELETE /api/tickets/{ticket_id}
@app.delete("/api/tickets/{ticket_id}")
def delete_ticket(ticket_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Verify it exists
        cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        cursor.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        
        # Cleanup orphaned files
        cleanup_orphaned_images(cursor)
        
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

class UpdateTicketPayload(BaseModel):
    title: str
    client: Optional[str] = ""
    symptom: Optional[str] = ""
    type: Optional[str] = "ticket"
    checklist: List[str]
    steps: List[str]

# PUT /api/tickets/{ticket_id}
@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: int, payload: UpdateTicketPayload):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Verify it exists
        cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        client_name = canonicalize_client_name(payload.client)
        
        # Update tickets
        cursor.execute(
            """
            UPDATE tickets
            SET title = ?,
                client = ?,
                symptom = ?,
                type = ?,
                checklist = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.title,
                client_name,
                payload.symptom,
                payload.type,
                json.dumps(payload.checklist),
                ticket_id
            )
        )
        
        # Re-link ticket steps
        cursor.execute("DELETE FROM ticket_steps WHERE ticket_id = ?", (ticket_id,))
        
        # Fuzzy match and map steps
        cursor.execute("SELECT id, instructions FROM master_steps")
        existing_master_steps = [dict(r) for r in cursor.fetchall()]
        
        for step_order, step_instr in enumerate(payload.steps, start=1):
            step_id = find_matching_step_id(step_instr, existing_master_steps)
            if not step_id:
                cmd_val = extract_command_from_instruction(step_instr)
                cursor.execute("INSERT INTO master_steps (instructions, command) VALUES (?, ?)", (step_instr, cmd_val))
                step_id = cursor.lastrowid
                existing_master_steps.append({"id": step_id, "instructions": step_instr})
                
            cursor.execute(
                "INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)",
                (ticket_id, step_id, step_order)
            )
            
        # Clean up any master steps that are now orphaned (not referenced by any ticket_steps)
        cursor.execute(
            """
            DELETE FROM master_steps 
            WHERE id NOT IN (SELECT DISTINCT step_id FROM ticket_steps)
            """
        )
        
        # Cleanup orphaned files
        cleanup_orphaned_images(cursor)
        
        conn.commit()
        return {"status": "success", "message": "Ticket updated successfully"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# 7. PUT /api/staging/update/{draft_id}
@app.put("/api/staging/update/{draft_id}")
def update_draft(draft_id: int, payload: UpdateDraftPayload):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Verify it exists
        cursor.execute("SELECT id FROM staging_inbox WHERE id = ?", (draft_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Draft not found")
        
        client_name = canonicalize_client_name(payload.client)
        # Build raw markdown based on new fields to keep raw_markdown in sync
        raw_markdown = f"# {payload.title}\n"
        if client_name:
            raw_markdown += f"@ {client_name}\n"
        if payload.symptom:
            raw_markdown += f"> {payload.symptom}\n"
        for step in payload.steps:
            raw_markdown += f"- {step}\n"

        cursor.execute(
            """
            UPDATE staging_inbox
            SET parsed_title = ?,
                parsed_client = ?,
                parsed_symptom = ?,
                parsed_steps = ?,
                parsed_images = ?,
                raw_markdown = ?,
                parsed_type = ?,
                parsed_checklist = ?
            WHERE id = ?
            """,
            (
                payload.title,
                client_name,
                payload.symptom,
                json.dumps(payload.steps),
                json.dumps(payload.images or []),
                raw_markdown,
                payload.type,
                json.dumps(payload.checklist or []),
                draft_id
            )
        )
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Draft updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET /search: Serves app/templates/search.html
@app.get("/search", response_class=HTMLResponse)
def get_search_page():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "search.html")
    if not os.path.exists(template_path):
         raise HTTPException(status_code=404, detail="Template search.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# GET /maintenance: Serves app/templates/maintenance.html
@app.get("/maintenance", response_class=HTMLResponse)
def get_maintenance_page():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "maintenance.html")
    if not os.path.exists(template_path):
         raise HTTPException(status_code=404, detail="Template maintenance.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# GET /api/companies
@app.get("/api/companies", response_model=List[str])
def get_companies():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT client 
            FROM tickets 
            WHERE client IS NOT NULL AND client != ''
            """
        )
        rows = cursor.fetchall()
        companies = [r["client"] for r in rows]
        conn.close()
        return companies
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET /api/search
@app.get("/api/search")
def api_search(q: Optional[str] = None, company: Optional[str] = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        ticket_ids = []
        if q and q.strip():
            query_str = q.strip()
            
            if query_str.isdigit():
                ticket_ids = [int(query_str)]
            # Special handling for "guide" or "guides" query to return all guides
            elif query_str.lower() in ("guide", "guides"):
                cursor.execute(
                    """
                    SELECT id 
                    FROM tickets 
                    WHERE type = 'guide'
                    ORDER BY created_at DESC, id DESC
                    """
                )
                rows = cursor.fetchall()
                ticket_ids = [r["id"] for r in rows]
            else:
                try:
                    # Query the SQLite FTS5 index. Use the bm25 scoring function to rank results.
                    # Calculate a hybrid sorting score: final_score = (-bm25(tickets_fts)) + boost.
                    cursor.execute(
                        """
                        SELECT tf.ticket_id, 
                               -bm25(tickets_fts) as base_score,
                               CASE WHEN t.client = ? THEN 10.0 ELSE 0.0 END as client_boost
                        FROM tickets_fts tf
                        JOIN tickets t ON tf.ticket_id = t.id
                        WHERE tickets_fts MATCH ?
                        ORDER BY (base_score + client_boost) DESC, t.created_at DESC, t.id DESC
                        """,
                        (company, query_str)
                    )
                    rows = cursor.fetchall()
                    ticket_ids = [r["ticket_id"] for r in rows]
                except Exception:
                    like_str = f"%{query_str}%"
                    cursor.execute(
                        """
                        SELECT t.id,
                               CASE WHEN t.client = ? THEN 1.0 ELSE 0.0 END as client_boost
                        FROM tickets t
                        WHERE t.title LIKE ? OR t.client LIKE ? OR t.symptom LIKE ?
                        ORDER BY client_boost DESC, t.created_at DESC, t.id DESC
                        """,
                        (company, like_str, like_str, like_str)
                    )
                    rows = cursor.fetchall()
                    ticket_ids = [r["id"] for r in rows]
        else:
            # Query all tickets sorting by client match first (soft filter) and then by created_at DESC, id DESC
            cursor.execute(
                """
                SELECT t.id,
                       CASE WHEN t.client = ? THEN 1.0 ELSE 0.0 END as client_boost
                FROM tickets t
                ORDER BY client_boost DESC, t.created_at DESC, t.id DESC
                """,
                (company,)
            )
            rows = cursor.fetchall()
            ticket_ids = [r["id"] for r in rows]
            
        tickets = []
        for tid in ticket_ids:
            # Fetch ticket info
            cursor.execute("SELECT id, title, client, symptom, type, checklist, created_at, updated_at FROM tickets WHERE id = ?", (tid,))
            t_row = cursor.fetchone()
            if not t_row:
                continue
            
            # Fetch steps ordered by step_order ASC
            cursor.execute(
                """
                SELECT ms.id, ms.instructions, ms.command, ms.is_broken, ms.breakage_notes, ts.step_order
                FROM ticket_steps ts
                JOIN master_steps ms ON ts.step_id = ms.id
                WHERE ts.ticket_id = ?
                ORDER BY ts.step_order ASC
                """,
                (tid,)
            )
            steps_rows = cursor.fetchall()
            steps = []
            for sr in steps_rows:
                # Fetch step images
                cursor.execute("SELECT file_path FROM step_images WHERE step_id = ?", (sr["id"],))
                step_imgs = [ir["file_path"] for ir in cursor.fetchall()]
                steps.append({
                    "id": sr["id"],
                    "instructions": sr["instructions"],
                    "command": sr["command"],
                    "is_broken": bool(sr["is_broken"]),
                    "breakage_notes": sr["breakage_notes"],
                    "images": step_imgs
                })
            
            # Fetch ticket images
            cursor.execute("SELECT file_path FROM ticket_images WHERE ticket_id = ?", (tid,))
            ticket_imgs = [ir["file_path"] for ir in cursor.fetchall()]
            
            tickets.append({
                "id": t_row["id"],
                "title": t_row["title"],
                "client": t_row["client"],
                "symptom": t_row["symptom"],
                "type": t_row["type"] if "type" in t_row.keys() and t_row["type"] else "ticket",
                "checklist": json.loads(t_row["checklist"]) if "checklist" in t_row.keys() and t_row["checklist"] else [],
                "created_at": t_row["created_at"],
                "updated_at": t_row["updated_at"],
                "steps": steps,
                "images": ticket_imgs
            })
            
        conn.close()
        return tickets
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class FlagPayload(BaseModel):
    reason: str

# POST /api/steps/flag/{step_id}
@app.post("/api/steps/flag/{step_id}")
def flag_step(step_id: int, payload: FlagPayload):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Verify step exists
        cursor.execute("SELECT id FROM master_steps WHERE id = ?", (step_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Step not found")
            
        cursor.execute(
            """
            UPDATE master_steps 
            SET is_broken = 1, breakage_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.reason, step_id)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# GET /api/maintenance/queue
@app.get("/api/maintenance/queue")
def get_maintenance_queue():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, instructions, command, breakage_notes, updated_at FROM master_steps WHERE is_broken = 1")
        broken_steps = cursor.fetchall()
        
        queue = []
        for bs in broken_steps:
            cursor.execute("SELECT COUNT(*) as count FROM ticket_steps WHERE step_id = ?", (bs["id"],))
            cnt_row = cursor.fetchone()
            impact_count = cnt_row["count"] if cnt_row else 0
            
            # Fetch step images
            cursor.execute("SELECT file_path FROM step_images WHERE step_id = ?", (bs["id"],))
            step_imgs = [ir["file_path"] for ir in cursor.fetchall()]
            
            queue.append({
                "id": bs["id"],
                "instructions": bs["instructions"],
                "command": bs["command"],
                "breakage_notes": bs["breakage_notes"],
                "updated_at": bs["updated_at"],
                "impact_count": impact_count,
                "images": step_imgs
            })
            
        conn.close()
        return queue
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ResolvePayload(BaseModel):
    action: str
    text: Optional[str] = ""
    command: Optional[str] = ""

# PATCH /api/maintenance/resolve/{step_id}
@app.patch("/api/maintenance/resolve/{step_id}")
def resolve_step(step_id: int, payload: ResolvePayload):
    if payload.action not in ("update", "delete"):
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'update' or 'delete'.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM master_steps WHERE id = ?", (step_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Step not found")
            
        if payload.action == "update":
            # Explicitly update instructions, command and timestamps
            cursor.execute(
                """
                UPDATE master_steps
                SET instructions = ?, command = ?, is_broken = 0, breakage_notes = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (payload.text, payload.command, step_id)
            )
        elif payload.action == "delete":
            # Retrieve all ticket_ids that reference this step_id
            cursor.execute("SELECT DISTINCT ticket_id FROM ticket_steps WHERE step_id = ?", (step_id,))
            affected_tickets = [r["ticket_id"] for r in cursor.fetchall()]
            
            # Delete from master_steps (ON DELETE CASCADE deletes from ticket_steps and step_images)
            cursor.execute("DELETE FROM master_steps WHERE id = ?", (step_id,))
            
            # Re-order steps for affected tickets
            for tid in affected_tickets:
                cursor.execute(
                    "SELECT step_id FROM ticket_steps WHERE ticket_id = ? ORDER BY step_order ASC",
                    (tid,)
                )
                ts_rows = cursor.fetchall()
                for new_order, ts_row in enumerate(ts_rows, start=1):
                    cursor.execute(
                        "UPDATE ticket_steps SET step_order = ? WHERE ticket_id = ? AND step_id = ?",
                        (new_order, tid, ts_row["step_id"])
                    )
            
            # Cleanup orphaned files
            cleanup_orphaned_images(cursor)
                    
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/extract/xml")
def extract_xml_endpoint(payload: XMLExtractPayload):
    import re
    from html import unescape
    from html.parser import HTMLParser
    
    class JiraXMLHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_item = False
            self.current_tag = None
            self.title = ""
            self.description = ""
            self.comments = []
            self.temp_data = []
            
            # For custom fields tracking
            self.custom_fields = []
            self.in_customfield = False
            self.current_customfield_name = ""
            self.current_customfield_values = []
            self.in_customfieldname = False
            self.in_customfieldvalue = False

        def handle_starttag(self, tag, attrs):
            if tag == "item":
                self.in_item = True
            if self.in_item:
                if tag in ["title", "description", "comment"]:
                    self.current_tag = tag
                    self.temp_data = []
                elif tag == "customfield":
                    self.in_customfield = True
                    self.current_customfield_name = ""
                    self.current_customfield_values = []
                elif tag == "customfieldname" and self.in_customfield:
                    self.in_customfieldname = True
                    self.temp_data = []
                elif tag == "customfieldvalue" and self.in_customfield:
                    self.in_customfieldvalue = True
                    self.temp_data = []

        def handle_endtag(self, tag):
            if tag == "item":
                self.in_item = False
            if self.in_item:
                if self.current_tag == tag:
                    text_content = "".join(self.temp_data).strip()
                    if tag == "title":
                        self.title = text_content
                    elif tag == "description":
                        self.description = text_content
                    elif tag == "comment":
                        self.comments.append(text_content)
                    self.current_tag = None
                elif tag == "customfield":
                    self.in_customfield = False
                    self.custom_fields.append({
                        "name": self.current_customfield_name,
                        "values": self.current_customfield_values
                    })
                elif tag == "customfieldname" and self.in_customfield:
                    self.current_customfield_name = "".join(self.temp_data).strip()
                    self.in_customfieldname = False
                elif tag == "customfieldvalue" and self.in_customfield:
                    self.current_customfield_values.append("".join(self.temp_data).strip())
                    self.in_customfieldvalue = False

        def handle_data(self, data):
            if self.in_item:
                if self.current_tag:
                    self.temp_data.append(data)
                elif self.in_customfieldname or self.in_customfieldvalue:
                    self.temp_data.append(data)

    def extract_heuristics(title_text: str, desc_text: str, comments: list, custom_fields: list) -> dict:
        cleaned_title = re.sub(r'^\[[a-zA-Z0-9]+-\d+\]\s*', '', title_text).strip()
        client = ""
        title = cleaned_title
        
        delimiters = [cleaned_title.find('|'), cleaned_title.find(':'), cleaned_title.find(' - ')]
        valid_delimiters = [(idx, len_delim) for idx, len_delim in zip(delimiters, [1, 1, 3]) if idx != -1]
        
        if valid_delimiters:
            valid_delimiters.sort(key=lambda x: x[0])
            split_idx, delim_len = valid_delimiters[0]
            client = cleaned_title[:split_idx].strip()
            title = cleaned_title[split_idx+delim_len:].strip()
            
        if not client:
            for field in custom_fields:
                fname = field["name"].lower()
                if "client" in fname or "company" in fname or "account" in fname or "organization" in fname:
                    if field["values"]:
                        client = field["values"][0]
                        break
            
        clean_desc = unescape(desc_text)
        clean_desc = re.sub(r'<(table|span|style|script)[^>]*>.*?</\1>', '', clean_desc, flags=re.DOTALL | re.IGNORECASE)
        clean_desc = re.sub(r'<[^>]+>', '', clean_desc)
        
        # Strip greetings and leading punctuation in fallback path
        clean_desc = re.sub(r'^(Hi|Hello|Dear|Hi all|Hello team)[\s\w]+,?\s*', '', clean_desc, flags=re.IGNORECASE).strip()
        clean_desc = clean_desc.lstrip(",.?!:; \t\n")
        
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_desc) if s.strip()]
        symptom = " ".join(sentences[:3]).strip()
        
        steps = []
        
        def extract_steps_from_text(text):
            decoded = unescape(text)
            li_matches = re.findall(r'<li[^>]*>(.*?)</li>', decoded, flags=re.DOTALL | re.IGNORECASE)
            if li_matches:
                for item in li_matches:
                    cleaned = re.sub(r'<[^>]+>', '', item).strip()
                    cleaned = re.sub(r'^(?:\d+\.|\*|-)\s*', '', cleaned).strip()
                    if cleaned:
                        steps.append(cleaned)
            else:
                lines = decoded.splitlines()
                for line in lines:
                    line_str = line.strip()
                    line_str = re.sub(r'<[^>]+>', '', line_str).strip()
                    if re.match(r'^(?:\d+\.|\*|-)\s+', line_str) or re.match(r'^(?:\d+\.|\*|-)$', line_str):
                        cleaned = re.sub(r'^(?:\d+\.|\*|-)\s*', '', line_str).strip()
                        if cleaned:
                            steps.append(cleaned)
                        
        extract_steps_from_text(desc_text)
        for comment in comments:
            extract_steps_from_text(comment)
            
        return {
            "client": client,
            "title": title,
            "symptom": symptom,
            "steps": steps
        }

    try:
        parser = JiraXMLHTMLParser()
        parser.feed(payload.xml_payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse payload: {str(e)}")
        
    if not parser.title and not parser.description:
        raise HTTPException(status_code=400, detail="XML does not contain valid JIRA <item> data.")
        
    # Format unified text block
    unified_text = f"Title: {parser.title}\nDescription: {parser.description}\nComments:\n"
    for comment in parser.comments:
        unified_text += f"- {comment}\n"
        
    try:
        result = extract_ticket_data(parser.title, parser.description, parser.comments)
        heuristics = extract_heuristics(parser.title, parser.description, parser.comments, parser.custom_fields)
        if not result.get("client") or not result["client"].strip():
            result["client"] = heuristics.get("client")
        if not result.get("title") or not result["title"].strip():
            result["title"] = heuristics.get("title")
        return result
    except Exception as e:
        # Graceful fallback to backend XML heuristic parser
        print(f"LLM Extraction failed ({e}). Falling back to backend XML heuristic parser.")
        return extract_heuristics(parser.title, parser.description, parser.comments, parser.custom_fields)


# ───────────────────────── Admin Page & API ─────────────────────────

@app.get("/admin", response_class=HTMLResponse)
def get_admin_page():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template admin.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/admin/stats")
def get_admin_stats():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM tickets")
        total_tickets = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM master_steps")
        total_steps = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM ticket_images")
        ticket_img_count = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(*) as cnt FROM step_images")
        step_img_count = cursor.fetchone()["cnt"]
        total_images = ticket_img_count + step_img_count

        from app.database import DB_FILE
        db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0

        cursor.execute("SELECT COALESCE(type, 'ticket') as t, COUNT(*) as cnt FROM tickets GROUP BY t ORDER BY cnt DESC")
        type_rows = cursor.fetchall()
        types = [{"type": r["t"], "count": r["cnt"]} for r in type_rows]

        return {
            "total_tickets": total_tickets,
            "total_steps": total_steps,
            "total_images": total_images,
            "db_size_bytes": db_size,
            "types": types,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/admin/export/db")
def export_db():
    from app.database import DB_FILE
    if not os.path.exists(DB_FILE):
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(
        path=DB_FILE,
        filename="support_hub_export.db",
        media_type="application/octet-stream",
    )


@app.post("/api/admin/import/db")
async def import_db(file: UploadFile = File(...)):
    from app.database import DB_FILE
    backup_path = DB_FILE + ".backup"
    try:
        # Create backup
        if os.path.exists(DB_FILE):
            shutil.copy2(DB_FILE, backup_path)

        # Write uploaded file
        contents = await file.read()
        with open(DB_FILE, "wb") as f:
            f.write(contents)

        # Ensure schema is up to date
        init_db()
        return {"status": "success", "message": "Database imported successfully. Backup saved."}
    except Exception as e:
        # Restore from backup on error
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, DB_FILE)
        raise HTTPException(status_code=500, detail=f"Import failed, backup restored: {str(e)}")


@app.get("/api/admin/export/json")
def export_json():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, client, symptom, type, checklist FROM tickets ORDER BY id ASC")
        ticket_rows = cursor.fetchall()

        tickets_out = []
        for t in ticket_rows:
            # Steps
            cursor.execute(
                """
                SELECT ms.instructions, ms.command, ts.step_order
                FROM ticket_steps ts
                JOIN master_steps ms ON ts.step_id = ms.id
                WHERE ts.ticket_id = ?
                ORDER BY ts.step_order ASC
                """,
                (t["id"],),
            )
            steps = [
                {"instructions": s["instructions"], "command": s["command"], "step_order": s["step_order"]}
                for s in cursor.fetchall()
            ]

            # Ticket images
            cursor.execute("SELECT file_path FROM ticket_images WHERE ticket_id = ?", (t["id"],))
            images = [r["file_path"] for r in cursor.fetchall()]

            checklist = None
            if t["checklist"]:
                try:
                    checklist = json.loads(t["checklist"])
                except Exception:
                    checklist = None

            tickets_out.append({
                "title": t["title"],
                "client": t["client"],
                "symptom": t["symptom"],
                "type": t["type"] or "ticket",
                "checklist": checklist,
                "images": images,
                "steps": steps,
            })

        # Export templates
        cursor.execute("SELECT title, category, body, linked_ticket_id FROM email_templates")
        templates_out = [dict(r) for r in cursor.fetchall()]

        # Export notes
        cursor.execute("SELECT title, body, color, is_pinned, reminder_date FROM notes")
        notes_out = [dict(r) for r in cursor.fetchall()]

        export_data = {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tickets": tickets_out,
            "email_templates": templates_out,
            "notes": notes_out,
        }

        from fastapi.responses import Response
        json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="support_hub_export.json"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/admin/import/json")
async def import_json(file: UploadFile = File(...)):
    conn = get_db_connection()
    try:
        contents = await file.read()
        data = json.loads(contents.decode("utf-8"))
        tickets = data.get("tickets", [])

        cursor = conn.cursor()
        imported = 0
        skipped = 0

        # Cache existing master steps for dedup
        cursor.execute("SELECT id, instructions FROM master_steps")
        existing_master_steps = [dict(r) for r in cursor.fetchall()]

        for ticket in tickets:
            title = ticket.get("title", "")
            client = ticket.get("client", "")
            t_type = ticket.get("type", "ticket")

            # Check for duplicate
            cursor.execute(
                "SELECT id FROM tickets WHERE title = ? AND client = ? AND COALESCE(type, 'ticket') = ?",
                (title, client, t_type),
            )
            if cursor.fetchone():
                skipped += 1
                continue

            symptom = ticket.get("symptom", "")
            checklist = ticket.get("checklist")
            checklist_str = json.dumps(checklist) if checklist else None

            cursor.execute(
                "INSERT INTO tickets (title, client, symptom, type, checklist) VALUES (?, ?, ?, ?, ?)",
                (title, client, symptom, t_type, checklist_str),
            )
            new_ticket_id = cursor.lastrowid

            for step in ticket.get("steps", []):
                instr = step.get("instructions", "")
                cmd = step.get("command")
                order = step.get("step_order", 1)

                # Reuse or create master step
                step_id = find_matching_step_id(instr, existing_master_steps)
                if not step_id:
                    # Exact match only for JSON import
                    cursor.execute("INSERT INTO master_steps (instructions, command) VALUES (?, ?)", (instr, cmd))
                    step_id = cursor.lastrowid
                    existing_master_steps.append({"id": step_id, "instructions": instr})

                cursor.execute(
                    "INSERT INTO ticket_steps (ticket_id, step_id, step_order) VALUES (?, ?, ?)",
                    (new_ticket_id, step_id, order),
                )

            imported += 1

        # Import templates
        templates = data.get("email_templates", [])
        for temp in templates:
            t_title = temp.get("title", "")
            t_category = temp.get("category", "general")
            t_body = temp.get("body", "")
            t_linked = temp.get("linked_ticket_id")
            
            cursor.execute("SELECT id FROM email_templates WHERE title = ? AND body = ?", (t_title, t_body))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO email_templates (title, category, body, linked_ticket_id) VALUES (?, ?, ?, ?)",
                    (t_title, t_category, t_body, t_linked)
                )

        # Import notes
        notes_list = data.get("notes", [])
        for note in notes_list:
            n_title = note.get("title", "")
            n_body = note.get("body", "")
            n_color = note.get("color", "blue")
            n_pinned = note.get("is_pinned", 0)
            n_reminder = note.get("reminder_date")

            cursor.execute("SELECT id FROM notes WHERE title = ? AND body = ?", (n_title, n_body))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO notes (title, body, color, is_pinned, reminder_date) VALUES (?, ?, ?, ?, ?)",
                    (n_title, n_body, n_color, n_pinned, n_reminder)
                )

        conn.commit()
        return {"status": "success", "imported": imported, "skipped": skipped}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/workspace", response_class=HTMLResponse)
def get_workspace_page():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "workspace.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template workspace.html not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/templates")
def get_email_templates(category: Optional[str] = None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if category and category.lower() != 'all':
            cursor.execute("SELECT * FROM email_templates WHERE category = ? ORDER BY id DESC", (category,))
        else:
            cursor.execute("SELECT * FROM email_templates ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/templates")
def create_email_template(payload: TemplateCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO email_templates (title, category, body, linked_ticket_id) VALUES (?, ?, ?, ?)",
            (payload.title, payload.category, payload.body, payload.linked_ticket_id)
        )
        conn.commit()
        new_id = cursor.lastrowid
        return {"status": "success", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.put("/api/templates/{id}")
def update_email_template(id: int, payload: TemplateCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE email_templates SET title = ?, category = ?, body = ?, linked_ticket_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload.title, payload.category, payload.body, payload.linked_ticket_id, id)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/templates/{id}")
def delete_email_template(id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM email_templates WHERE id = ?", (id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/notes")
def get_notes():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes ORDER BY is_pinned DESC, updated_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/notes")
def create_note(payload: NoteCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO notes (title, body, color, is_pinned, reminder_date) VALUES (?, ?, ?, ?, ?)",
            (payload.title, payload.body, payload.color, payload.is_pinned, payload.reminder_date)
        )
        conn.commit()
        new_id = cursor.lastrowid
        return {"status": "success", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.put("/api/notes/{id}")
def update_note(id: int, payload: NoteCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notes SET title = ?, body = ?, color = ?, is_pinned = ?, reminder_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload.title, payload.body, payload.color, payload.is_pinned, payload.reminder_date, id)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/notes/{id}")
def delete_note(id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


class AlertTriggerPayload(BaseModel):
    type: str
    sender: str
    content: str
    link: Optional[str] = None


class AlertSettingsPayload(BaseModel):
    is_on_shift: Optional[int] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None
    target_email_keywords: Optional[str] = None
    target_whatsapp_names: Optional[str] = None
    alarm_volume: Optional[float] = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                pass


alert_manager = ConnectionManager()


@app.get("/api/alerts")
def get_alerts_endpoint():
    conn = get_db_connection()
    try:
        alerts = get_unseen_alerts(conn)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/alerts/{id}/seen")
def mark_alert_seen_endpoint(id: int):
    conn = get_db_connection()
    try:
        mark_alert_seen(conn, id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/alerts/settings")
def get_alert_settings_endpoint():
    conn = get_db_connection()
    try:
        settings = get_alert_settings(conn)
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        return settings
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.put("/api/alerts/settings")
def update_alert_settings_endpoint(payload: AlertSettingsPayload):
    conn = get_db_connection()
    try:
        settings_dict = {k: v for k, v in payload.dict().items() if v is not None}
        update_alert_settings(conn, settings_dict)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/alerts/trigger")
async def trigger_alert_endpoint(payload: AlertTriggerPayload):
    conn = get_db_connection()
    try:
        alert_id = add_alert(
            conn,
            type_=payload.type,
            sender=payload.sender,
            content=payload.content,
            link=payload.link
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM received_alerts WHERE id = ?", (alert_id,))
        row = cursor.fetchone()
        alert_data = dict(row) if row else {}
        
        await alert_manager.broadcast(alert_data)
        
        return {"status": "triggered", "alert_id": alert_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.websocket("/api/alerts/ws")
async def websocket_alerts_endpoint(websocket: WebSocket):
    await alert_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)
    except Exception:
        alert_manager.disconnect(websocket)
