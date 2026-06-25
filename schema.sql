-- Support Engineer Knowledge Hub & Maintenance Queue
-- Database Schema (SQLite)

-- 1. Master Tickets Table
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    client TEXT,
    symptom TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Master Steps Table
-- Steps are standalone entities. Editing a step updates it across all linked tickets.
-- If is_broken = 1, it enters the Maintenance Queue.
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instructions TEXT NOT NULL,
    is_broken INTEGER DEFAULT 0 CHECK(is_broken IN (0, 1)),
    breakage_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Ticket-to-Step Relationship (Many-to-Many Join Table with Ordering)
CREATE TABLE IF NOT EXISTS ticket_steps (
    ticket_id INTEGER,
    step_id INTEGER,
    step_order INTEGER NOT NULL,
    PRIMARY KEY (ticket_id, step_id),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES steps(id) ON DELETE CASCADE
);

-- 4. Staging Inbox Table
-- Holds shorthand markdown entry drafts before merging/approving into Live DB
CREATE TABLE IF NOT EXISTS staging_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_markdown TEXT NOT NULL,
    parsed_title TEXT,
    parsed_client TEXT,
    parsed_symptom TEXT,
    parsed_steps TEXT, -- JSON array of steps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. SQLite FTS5 Virtual Table for Fast Search
-- This table indexes tickets and their compiled steps for blazing fast search.
CREATE VIRTUAL TABLE IF NOT EXISTS tickets_fts USING fts5(
    ticket_id UNINDEXED,
    title,
    client,
    symptom,
    steps_content
);

-- Triggers to auto-delete from FTS index when a ticket is deleted
CREATE TRIGGER IF NOT EXISTS trg_tickets_after_delete
AFTER DELETE ON tickets
BEGIN
    DELETE FROM tickets_fts WHERE ticket_id = OLD.id;
END;
