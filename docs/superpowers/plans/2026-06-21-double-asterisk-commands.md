# Double Asterisk Commands Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract commands wrapped in double asterisks `**...**` in the staging/draft editor and store them in the database.

**Architecture:** Add a new regex pattern in `extract_command_from_instruction` in `app/main.py`.

**Tech Stack:** FastAPI, Python re module.

## Global Constraints
None.

---

### Task 1: Backend Regex Support & Verification

**Files:**
- Modify: `app/main.py`
- Modify: `test_staging_api.py`

**Interfaces:**
- Consumes: None
- Produces: None

- [ ] **Step 1: Write a failing test in test_staging_api.py**

Let's locate the tests file first to see how it's structured. We'll add a test verifying that `extract_command_from_instruction` parses double asterisks.

- [ ] **Step 2: Run pytest to verify it fails**

- [ ] **Step 3: Modify app/main.py to support double asterisk extraction**

- [ ] **Step 4: Run pytest to verify it passes**
