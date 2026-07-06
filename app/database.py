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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

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
                SELECT group_concat(s.instructions, ' ')
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
            SELECT group_concat(s.instructions, ' ')
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
            SELECT group_concat(s.instructions, ' ')
            FROM ticket_steps ts
            JOIN master_steps s ON ts.step_id = s.id
            WHERE ts.ticket_id = OLD.ticket_id
        ), '')
        WHERE ticket_id = OLD.ticket_id;
    END;
    """)

    # Trigger F: After Update on master_steps
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_master_steps_after_update
    AFTER UPDATE OF instructions ON master_steps
    BEGIN
        UPDATE tickets_fts
        SET steps_content = COALESCE((
            SELECT group_concat(s.instructions, ' ')
            FROM ticket_steps ts
            JOIN master_steps s ON ts.step_id = s.id
            WHERE ts.ticket_id = tickets_fts.ticket_id
        ), '')
        WHERE ticket_id IN (SELECT ticket_id FROM ticket_steps WHERE step_id = NEW.id);
    END;
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
