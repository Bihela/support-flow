# Strict Company Filtering & Image Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement strict company filtering in the search API and ensure images attached to staging drafts are preserved during garbage collection cleanup.

**Architecture:** Modify `api_search` in `app/main.py` to filter strictly using SQL `WHERE client = ?` if a company filter is specified. Modify `cleanup_orphaned_images` to fetch all files in `staging_inbox.parsed_images` to prevent premature file deletion.

**Tech Stack:** FastAPI, SQLite3.

## Global Constraints
- Database `support_hub.db` MUST NOT be reset or deleted.

---

### Task 1: Preserve Staging Inbox Images

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: Database schema from previous tasks.
- Produces: Updated `cleanup_orphaned_images` function.

- [ ] **Step 1: Update cleanup_orphaned_images in main.py**
  Modify `cleanup_orphaned_images` to fetch and parse the `parsed_images` column from the `staging_inbox` table and add them to the list of preserved image paths.

---

### Task 2: Strict Search Filter Implementation

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: None
- Produces: Updated `api_search` SQL queries.

- [ ] **Step 1: Update FTS5 search logic**
  Update the FTS5 execution block to apply `t.client = ?` as a strict SQL filter if a company filter is provided.

- [ ] **Step 2: Update Fallback search logic**
  Update the `LIKE` fallback execution block to filter by `t.client = ?` if a company filter is provided.

- [ ] **Step 3: Update Browse search logic**
  Update the browse execution block (when `q` is empty) to strictly query `t.client = ?`.
