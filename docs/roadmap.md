# SupportFlow Roadmap & Labeled Issue Ideas

This document outlines future enhancements and feature ideas for SupportFlow. Maintainers can copy these ideas directly into GitHub Issues and tag them to attract contributors.

---

## Labeled Issue Ideas

### Issue 1: Add a Dark/Light Theme Toggle
* **Difficulty:** Easy / Good First Issue
* **Labels:** `good first issue`, `enhancement`, `frontend`
* **Title:** `feat: Add a theme toggle (Dark/Light mode) in UI`
* **Description:**
  ```markdown
  **Describe the Enhancement**
  Add a button/toggle in the header to switch between Dark Mode and Light Mode.

  **Suggested Implementation:**
  - Standardize Tailwind class variables or custom CSS variables for light/dark colors.
  - Store user preference in browser `localStorage` so it persists between page refreshes.
  - Update `index.html` header to include a sun/moon icon toggle.
  ```

---

### Issue 2: Support Ticket and Master Steps Exporter
* **Difficulty:** Medium / Help Wanted
* **Labels:** `help wanted`, `enhancement`, `backend`
* **Title:** `feat: Export support tickets and master steps to Markdown or PDF`
* **Description:**
  ```markdown
  **Describe the Enhancement**
  We want to export resolved support tickets or compiled master steps into shareable formats like Markdown (.md) or PDF (.pdf).

  **Suggested Implementation:**
  - Add an `/api/export/ticket/{id}` endpoint in `app/main.py` that generates a formatted markdown file download.
  - Integrate a frontend export button on the ticket detail cards.
  - (Optional) Use a lightweight library like `reportlab` or similar to support PDF export.
  ```

---

### Issue 3: Model Configuration Selector in UI
* **Difficulty:** Medium / Advanced
* **Labels:** `help wanted`, `enhancement`, `AI`
* **Title:** `feat: Add model configuration and weight selector in Settings`
* **Description:**
  ```markdown
  **Describe the Enhancement**
  Currently, the micro-LLM extraction parameters and Hugging Face weights are hardcoded. We want a settings interface in the UI to change which GGUF model/repo is downloaded.

  **Suggested Implementation:**
  - Create a lightweight `/api/settings` endpoint to retrieve and update model parameters (repo ID, filename, thread cap).
  - Persist settings in a new `settings` table in SQLite.
  - Update `llm_extractor.py` to dynamically load values from the database instead of hardcoding Qwen2.5.
  ```

---

### Issue 4: Text Extraction from Uploaded Document Attachments
* **Difficulty:** Hard
* **Labels:** `enhancement`, `backend`, `document-parsing`
* **Title:** `feat: Parse text content from uploaded text/PDF attachments`
* **Description:**
  ```markdown
  **Describe the Enhancement**
  Support parsing and index searching of text inside PDF, TXT, or JSON file attachments.

  **Suggested Implementation:**
  - Add backend document parsers (e.g. `pypdf` or standard text reading helper).
  - When files are attached, extract their textual contents and insert them into a virtual search index.
  ```
