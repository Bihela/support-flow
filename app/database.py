import sqlite3
import os
import json

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "support_hub.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Master Tickets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        client TEXT,
        symptom TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Master Steps Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS master_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instructions TEXT NOT NULL,
        command TEXT,
        is_broken INTEGER DEFAULT 0 CHECK(is_broken IN (0, 1)),
        breakage_notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Ticket-to-Step Relationship
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticket_steps (
        ticket_id INTEGER,
        step_id INTEGER,
        step_order INTEGER NOT NULL,
        PRIMARY KEY (ticket_id, step_order),
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
        FOREIGN KEY (step_id) REFERENCES master_steps(id) ON DELETE CASCADE
    );
    """)

    # Check and run migration if old constraint exists
    cursor.execute("PRAGMA table_info(ticket_steps)")
    columns = cursor.fetchall()
    pk_cols = [col["name"] for col in columns if col["pk"] > 0]
    if pk_cols and "step_order" not in pk_cols:
        cursor.execute("DROP TRIGGER IF EXISTS trg_ticket_steps_after_insert")
        cursor.execute("DROP TRIGGER IF EXISTS trg_ticket_steps_after_delete")
        cursor.execute("ALTER TABLE ticket_steps RENAME TO ticket_steps_old")
        cursor.execute("""
        CREATE TABLE ticket_steps (
            ticket_id INTEGER,
            step_id INTEGER,
            step_order INTEGER NOT NULL,
            PRIMARY KEY (ticket_id, step_order),
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (step_id) REFERENCES master_steps(id) ON DELETE CASCADE
        );
        """)
        cursor.execute("INSERT INTO ticket_steps (ticket_id, step_id, step_order) SELECT ticket_id, step_id, step_order FROM ticket_steps_old")
        cursor.execute("DROP TABLE ticket_steps_old")

    # 4. Staging Inbox Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staging_inbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_markdown TEXT NOT NULL,
        parsed_title TEXT,
        parsed_client TEXT,
        parsed_symptom TEXT,
        parsed_steps TEXT, -- JSON serialized array of strings
        parsed_images TEXT, -- JSON array of image paths
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Alter staging_inbox in case it already exists without parsed_images column
    try:
        cursor.execute("ALTER TABLE staging_inbox ADD COLUMN parsed_images TEXT;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE staging_inbox ADD COLUMN parsed_type TEXT DEFAULT 'ticket';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE staging_inbox ADD COLUMN parsed_checklist TEXT;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN type TEXT DEFAULT 'ticket';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN checklist TEXT;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE master_steps ADD COLUMN command TEXT;")
    except sqlite3.OperationalError:
        pass

    # 4a. Ticket Images Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticket_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        file_path TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
    );
    """)

    # 4b. Step Images Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS step_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        step_id INTEGER,
        file_path TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (step_id) REFERENCES master_steps(id) ON DELETE CASCADE
    );
    """)

    # 4c. Email Templates Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        body TEXT NOT NULL,
        linked_ticket_id INTEGER,
        is_pinned INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    try:
        cursor.execute("ALTER TABLE email_templates ADD COLUMN is_pinned INTEGER DEFAULT 0;")
    except sqlite3.OperationalError:
        pass

    # 4d. Notes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT,
        color TEXT DEFAULT 'blue',
        is_pinned INTEGER DEFAULT 0,
        reminder_date TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4e. Alert Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        is_on_shift INTEGER DEFAULT 0,
        imap_host TEXT DEFAULT 'imap.gmail.com',
        imap_port INTEGER DEFAULT 993,
        imap_user TEXT,
        imap_password TEXT,
        target_email_keywords TEXT DEFAULT '',
        target_whatsapp_names TEXT DEFAULT '',
        alarm_volume REAL DEFAULT 1.0,
        last_shift_on_time TEXT,
        is_sound_enabled INTEGER DEFAULT 1
    );
    """)

    try:
        cursor.execute("ALTER TABLE alert_settings ADD COLUMN last_shift_on_time TEXT;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE alert_settings ADD COLUMN is_sound_enabled INTEGER DEFAULT 1;")
    except sqlite3.OperationalError:
        pass


    # Insert default settings if empty
    cursor.execute("""
    INSERT INTO alert_settings (id, is_on_shift, imap_host, imap_port, alarm_volume)
    SELECT 1, 0, 'imap.gmail.com', 993, 1.0
    WHERE NOT EXISTS (SELECT 1 FROM alert_settings WHERE id = 1);
    """)

    # 4f. Received Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS received_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        sender TEXT,
        content TEXT,
        link TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'unseen'
    );
    """)

    # 4g. Monitor Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS monitor_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        level TEXT,
        component TEXT,
        message TEXT,
        details TEXT
    );
    """)

    # 5. SQLite FTS5 Virtual Table
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS tickets_fts USING fts5(
        ticket_id UNINDEXED,
        title,
        client,
        symptom,
        steps_content
    );
    """)

    # --- SQLite FTS5 Auto-Sync Triggers ---

    cursor.execute("DROP TRIGGER IF EXISTS trg_tickets_after_insert")
    cursor.execute("DROP TRIGGER IF EXISTS trg_tickets_after_update")
    cursor.execute("DROP TRIGGER IF EXISTS trg_tickets_after_delete")
    cursor.execute("DROP TRIGGER IF EXISTS trg_ticket_steps_after_insert")
    cursor.execute("DROP TRIGGER IF EXISTS trg_ticket_steps_after_delete")
    cursor.execute("DROP TRIGGER IF EXISTS trg_master_steps_after_update")

    # Trigger A: After Insert on tickets
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_tickets_after_insert
    AFTER INSERT ON tickets
    BEGIN
        INSERT INTO tickets_fts(ticket_id, title, client, symptom, steps_content)
        VALUES (NEW.id, NEW.title, NEW.client, NEW.symptom, COALESCE(NEW.checklist, ''));
    END;
    """)

    # Trigger B: After Update on tickets
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_tickets_after_update
    AFTER UPDATE ON tickets
    BEGIN
        UPDATE tickets_fts
        SET title = NEW.title,
            client = NEW.client,
            symptom = NEW.symptom,
            steps_content = COALESCE((
                SELECT group_concat(COALESCE(s.instructions, '') || ' ' || COALESCE(s.command, ''), ' ')
                FROM ticket_steps ts
                JOIN master_steps s ON ts.step_id = s.id
                WHERE ts.ticket_id = NEW.id
            ), '') || ' ' || COALESCE(NEW.checklist, '')
        WHERE ticket_id = NEW.id;
    END;
    """)

    # Trigger C: After Delete on tickets
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_tickets_after_delete
    AFTER DELETE ON tickets
    BEGIN
        DELETE FROM tickets_fts WHERE ticket_id = OLD.id;
    END;
    """)

    # Trigger D: After Insert on ticket_steps (to update steps_content in FTS)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_ticket_steps_after_insert
    AFTER INSERT ON ticket_steps
    BEGIN
        UPDATE tickets_fts
        SET steps_content = COALESCE((
            SELECT group_concat(COALESCE(s.instructions, '') || ' ' || COALESCE(s.command, ''), ' ')
            FROM ticket_steps ts
            JOIN master_steps s ON ts.step_id = s.id
            WHERE ts.ticket_id = NEW.ticket_id
        ), '')
        WHERE ticket_id = NEW.ticket_id;
    END;
    """)

    # Trigger E: After Delete on ticket_steps
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_ticket_steps_after_delete
    AFTER DELETE ON ticket_steps
    BEGIN
        UPDATE tickets_fts
        SET steps_content = COALESCE((
            SELECT group_concat(COALESCE(s.instructions, '') || ' ' || COALESCE(s.command, ''), ' ')
            FROM ticket_steps ts
            JOIN master_steps s ON ts.step_id = s.id
            WHERE ts.ticket_id = OLD.ticket_id
        ), '')
        WHERE ticket_id = OLD.ticket_id;
    END;
    """)

    # Trigger F: After Update on master_steps (instructions or command)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_master_steps_after_update
    AFTER UPDATE OF instructions, command ON master_steps
    BEGIN
        UPDATE tickets_fts
        SET steps_content = COALESCE((
            SELECT group_concat(COALESCE(s.instructions, '') || ' ' || COALESCE(s.command, ''), ' ')
            FROM ticket_steps ts
            JOIN master_steps s ON ts.step_id = s.id
            WHERE ts.ticket_id = tickets_fts.ticket_id
        ), '')
        WHERE ticket_id IN (SELECT ticket_id FROM ticket_steps WHERE step_id = NEW.id);
    END;
    """)

    conn.commit()
    conn.close()

def get_alert_settings(conn: sqlite3.Connection) -> dict:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_settings WHERE id = 1")
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None

def update_alert_settings(conn: sqlite3.Connection, settings: dict) -> None:
    cursor = conn.cursor()
    # If is_on_shift is changing to 1, we set last_shift_on_time = CURRENT_TIMESTAMP
    if settings.get("is_on_shift") == 1:
        cursor.execute("UPDATE alert_settings SET last_shift_on_time = CURRENT_TIMESTAMP WHERE id = 1")

    # Build dynamic update statement based on provided keys
    allowed_keys = {
        "is_on_shift", "imap_host", "imap_port", "imap_user", 
        "imap_password", "target_email_keywords", "target_whatsapp_names", 
        "alarm_volume", "is_sound_enabled"
    }
    update_data = {k: v for k, v in settings.items() if k in allowed_keys}
    if not update_data:
        return
        
    set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
    values = list(update_data.values())
    cursor.execute(f"UPDATE alert_settings SET {set_clause} WHERE id = 1", values)
    conn.commit()

def add_alert(conn: sqlite3.Connection, type_: str, sender: str, content: str, link: str = None, timestamp: str = None) -> int:
    cursor = conn.cursor()
    if timestamp:
        cursor.execute(
            "INSERT INTO received_alerts (type, sender, content, link, timestamp) VALUES (?, ?, ?, ?, ?)",
            (type_, sender, content, link, timestamp)
        )
    else:
        cursor.execute(
            "INSERT INTO received_alerts (type, sender, content, link) VALUES (?, ?, ?, ?)",
            (type_, sender, content, link)
        )
    conn.commit()
    return cursor.lastrowid

def get_unseen_alerts(conn: sqlite3.Connection) -> list:
    cursor = conn.cursor()
    # Get current settings to see if shift is on
    cursor.execute("SELECT is_on_shift FROM alert_settings WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row["is_on_shift"]:
        return []
        
    cursor.execute(
        "SELECT * FROM received_alerts WHERE status = 'unseen' "
        "AND timestamp >= datetime('now', '-24 hours') "
        "ORDER BY timestamp DESC"
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def mark_alert_seen(conn: sqlite3.Connection, alert_id: int) -> None:
    cursor = conn.cursor()
    cursor.execute("UPDATE received_alerts SET status = 'seen' WHERE id = ?", (alert_id,))
    conn.commit()

import random

def add_monitor_log(conn: sqlite3.Connection, level: str, component: str, message: str, details: str = None) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO monitor_logs (level, component, message, details) VALUES (?, ?, ?, ?)",
        (level, component, message, details)
    )
    # Prune logs older than 24 hours probabilistically (~2% of calls) to reduce disk I/O churn
    if random.random() < 0.02:
        cursor.execute("DELETE FROM monitor_logs WHERE timestamp < datetime('now', '-24 hours')")
    conn.commit()
    return cursor.lastrowid

def get_monitor_logs(conn: sqlite3.Connection, limit: int = 200) -> list:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM monitor_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

