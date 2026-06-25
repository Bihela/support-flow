# Support Guides & Search Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Support Guides/Playbooks with custom checklists, integrated into Dump Box, Staging, and Fast Search, and hide initial results on the landing page until a query is run.

**Architecture:** Extend the `tickets` and `staging_inbox` tables with `type` and `checklist` columns. Update FTS5 triggers to index checklists. Update frontend parser to parse checklist items (`- [ ]`) and support type dropdowns. Update Fast Search to only show results after search action.

**Tech Stack:** FastAPI, SQLite3, HTML, Vanilla CSS, Vanilla JS.

## Global Constraints
- Database `support_hub.db` MUST NOT be reset or deleted.

---

### Task 1: Database Migration & FTS5 Trigger Updates

**Files:**
- Modify: `app/database.py`

**Interfaces:**
- Consumes: None
- Produces: SQLite tables with `type` and `checklist` columns, updated triggers.

- [ ] **Step 1: Safely add new columns in init_db**
  Add try/except alter statements in `app/database.py` for:
  - `staging_inbox.parsed_type` (TEXT, default 'ticket')
  - `staging_inbox.parsed_checklist` (TEXT)
  - `tickets.type` (TEXT, default 'ticket')
  - `tickets.checklist` (TEXT)

- [ ] **Step 2: Update triggers in init_db**
  Update `trg_tickets_after_insert` and `trg_tickets_after_update` triggers to append `COALESCE(NEW.checklist, '')` into `steps_content` inside `tickets_fts`.

- [ ] **Step 3: Run database init**
  Run `venv\Scripts\python.exe app/database.py` to apply schema updates.

---

### Task 2: Backend Models & API Endpoints

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: Database updates from Task 1.
- Produces: Updated FastAPI endpoints `/api/staging/draft`, `/api/staging/approve/{draft_id}`, `/api/staging/merge`, `/api/staging/compare/{draft_id}`, etc.

- [ ] **Step 1: Update Pydantic Models**
  Add `type` and `checklist` fields to `DraftPayload` and `UpdateDraftPayload` in `app/main.py`.

- [ ] **Step 2: Update API Endpoint Handlers**
  Modify endpoint handlers to save/load type and checklist to/from `staging_inbox` and `tickets` tables. Ensure approval/merge endpoints write `type` and `checklist` to `tickets` table and link steps correctly.

---

### Task 3: Shorthand Parser & Dump Box Dropdown

**Files:**
- Modify: `app/templates/dumpbox.html`
- Modify: `app/static/parser.js`

**Interfaces:**
- Consumes: `/api/staging/draft` payload updates.
- Produces: Explicit type dropdown selector and checklist parsing in the Dump Box UI.

- [ ] **Step 1: Add Dropdown Selector in dumpbox.html**
  Add type select element near the Submit button in `app/templates/dumpbox.html`.

- [ ] **Step 2: Parse Checklists and Types in parser.js**
  - Update `parseShorthand` to extract lines starting with `- [ ] `, `* [ ] ` or `? ` as checklist items.
  - Send `type` and `checklist` fields in payload.
  - Update rendering in `updatePreview` to show the checklist preview card if present.

---

### Task 4: Staging Editor Integration

**Files:**
- Modify: `app/templates/staging.html`
- Modify: `app/static/staging.js`

**Interfaces:**
- Consumes: Backend staging payload.
- Produces: Edit controls for type and checklist in the Staging Inbox workspace.

- [ ] **Step 1: Add input fields in staging.html**
  Add a dropdown for ticket type and a textarea for the verification checklist in the edit panel.

- [ ] **Step 2: Populate and Save checklist in staging.js**
  Update Javascript to populate the edit fields and send them during draft save, approval, and merge actions.

---

### Task 5: Fast Search Results Checklist & Search Landing Page Cleanup

**Files:**
- Modify: `app/templates/search.html`
- Modify: `app/static/search.js` (or inline script inside search.html if applicable)

**Interfaces:**
- Consumes: Search result objects from `/api/search`.
- Produces: Interactive checklist checkboxes on search card results and empty landing page view.

- [ ] **Step 1: Hide initial results**
  Ensure results container is hidden or shows a helper message when the search page first loads. Only render results once the user submits a query or selects a company filter.

- [ ] **Step 2: Render checklist items on guide cards**
  If a ticket in search results has `type == 'guide'`, display checklist checkboxes that support interactive checking/unchecking.
