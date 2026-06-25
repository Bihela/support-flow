# Publish SupportFlow to GitHub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize a local Git repository, set up `.gitignore` security exclusions, prepare open-source configuration (README/LICENSE), configure a GitHub Actions CI pipeline, and create a public GitHub repository named `support-flow` using the GitHub CLI.

**Architecture:** 
- Initialize Git repository locally.
- Explicitly exclude the database file `support_hub.db` and the metadata file `project_memory.md` in `.gitignore`.
- Set up a standard open-source README and LICENSE.
- Create a `.github/workflows/ci.yml` pipeline that installs dependencies and runs tests on push/PR.
- Use `gh repo create` to publish the repo and push code to GitHub.

**Tech Stack:** Git, GitHub Actions, GitHub CLI (`gh`), FastAPI, pytest, SQLite.

## Global Constraints
- **Database Preservation**: DO NOT delete, reset, or drop the SQLite database (`support_hub.db`) or run test scripts that delete it.
- **Strict Privacy**: Do not push the SQLite database `support_hub.db` or `project_memory.md` under any circumstances.

---

### Task 1: Exclusions & Git Initialization

**Files:**
- Modify: `.gitignore`
- Create: `LICENSE`

- [ ] **Step 1: Update `.gitignore` to explicitly exclude `project_memory.md`**
  Add `project_memory.md` to `.gitignore` so that it is never tracked.

- [ ] **Step 2: Create MIT LICENSE file**
  Create a standard `LICENSE` file containing the MIT License terms.

- [ ] **Step 3: Initialize Git repository**
  Run: `git init`

- [ ] **Step 4: Verify ignored files**
  Verify that `project_memory.md`, `support_hub.db`, and `app/static/uploads/` are properly ignored by Git.
  Run: `git status --ignored` and check that those files are listed as ignored.

- [ ] **Step 5: Create initial commit locally**
  Add all allowed files and make the first local commit.
  Run: `git add .` and `git commit -m "initial commit: local-first support hub foundation"`

---

### Task 2: Open-Source Documentation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create a comprehensive open-source README**
  Create a `README.md` containing features (local-first design, fast SQLite FTS5 search, ephemeral micro-LLM extraction), dependencies, local setup instructions (`start.bat`/`start.sh`), and how to run tests.

- [ ] **Step 2: Commit documentation**
  Run: `git add README.md` and `git commit -m "docs: add README and LICENSE"`

---

### Task 3: CI/CD Pipeline Configuration

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create GitHub Actions workflow file**
  Create `.github/workflows/ci.yml` to run pytest tests on every push and pull request.

- [ ] **Step 2: Commit workflow file**
  Run: `git add .github/workflows/ci.yml` and `git commit -m "ci: add GitHub Actions workflow for tests"`

---

### Task 4: GitHub Repository Creation & Publishing

**Files:**
- None

- [ ] **Step 1: Check GitHub CLI authentication**
  Run: `gh auth status` to ensure `gh` is authenticated.

- [ ] **Step 2: Create the repository on GitHub**
  Run: `gh repo create support-flow --public --source=. --remote=origin --push --description "Local-first Support Hub with SQLite FTS5 Search and Ephemeral micro-LLM Ingestion"`
