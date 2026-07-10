# Project Memory: Support Hub & Maintenance Queue

## Current Architecture & Constraints
- **Application Type**: Local-first, zero-build Support Hub.
- **Backend**: FastAPI (Python) serving a lightweight SQLite database and static assets.
- **Database**: SQLite with FTS5 enabled for fast searching. 
  - **Rules**: The SQLite `.db` file is strictly ignored via `.gitignore` to prevent any local support tickets/company data from being committed to the repo.
- **Frontend**: Single Page Application (SPA) using HTML, Vanilla CSS, and standard JS. Styled with **Tailwind CSS via CDN**. No Node.js build pipeline or packaging step is required.
- **Auto-Collision Engine**: Powered by `RapidFuzz` in the backend to calculate text similarity between incoming staging drafts and the Live DB.
- **AI & LLM Integration**: Uses an Ephemeral On-Demand Micro-LLM Architecture for extracting ticket payloads to minimize resource footprint. The model is only loaded when processing an extraction request and is immediately unloaded from memory via `del llm` and `gc.collect()`.
- **Model Requirements**: `llama-cpp-python`, `huggingface-hub`, and model `Qwen/Qwen2.5-1.5B-Instruct-GGUF` (specifically `qwen2.5-1.5b-instruct-q4_k_m.gguf`).
- **Confirmation Logic Constraint**: Strictly DO NOT use native browser popups like `alert()` or `confirm()`. For confirmation dialogs, always use `await window.showConfirm(title, message, options)` which returns a Promise resolving to a boolean.



## Core Technical Skills & Patterns
- **Database Relations**: Master-detail with Many-to-Many linking for reusable steps. Editing a step updates it across all linked tickets.
- **FTS5 Integration**: Virtual tables in SQLite mapped to `tickets` and compiled `steps` for high-performance substring/token match search.
- **Staging Area Pattern**: Temporary inbox (`staging_drafts`) to preview support cards, perform fuzzy duplicate checks, and decide actions before final database insertion.
- **Markdown & XML Parser**: Standard JS parser in the browser supporting shorthand characters (`#`, `@`, `>`, `-`). For Jira XML exports, the payload is parsed via python's `xml.etree.ElementTree` in the backend and processed via the Ephemeral On-Demand Micro-LLM pipeline.
- **On-Demand LLM Execution & Reclamation**: Instantiates the quantized local model dynamically, executes structured chat completion, and performs strict RAM/GPU memory reclamation using python's garbage collector.
- **Universal Hardware AI Override & Throttling**:
  - To prevent illegal instruction crashes on CPUs without AVX2/AVX/FMA/F16C support, reinstall `llama-cpp-python` using:
    `CMAKE_ARGS="-DLLAMA_AVX2=OFF -DLLAMA_AVX=OFF -DLLAMA_FMA=OFF -DLLAMA_F16C=OFF" pip install --upgrade --force-reinstall --no-cache-dir llama-cpp-python`
  - If the host lacks C++ compiler tools, fall back to installing precompiled CPU-only wheels (`--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary`) or a pure-Python transformers implementation.
  - To prevent device strain, prioritize the extraction process to `psutil.BELOW_NORMAL_PRIORITY_CLASS` (on Windows) or nice level `10` (on Unix/Linux), and strictly cap the thread count to `n_threads=2` in the `Llama` constructor. Never exceed 2 threads.
- **Step Deduplication & Auto-Linking Engine**:
  - When approving or merging staging drafts, draft troubleshooting steps are fuzzy matched against all existing rows in `master_steps` using `rapidfuzz.fuzz.token_sort_ratio`.
  - A threshold of `90%` match is enforced. If a match is >= 90%, the ticket links to the existing master step ID rather than inserting a duplicate.
  - If a match is < 90%, a new row is created in `master_steps`, automatically extracting terminal command strings if present.

## Project Folder Structure Layout
```text
SupportHub/
├── .gitignore
├── project_memory.md
├── requirements.txt
├── schema.sql
├── start.bat               <-- Windows local execution script
├── start.sh                <-- Linux/macOS local execution script
├── models/                 <-- Local directory for GGUF model files
├── app/
│   ├── __init__.py
│   ├── main.py            <-- FastAPI Application
│   ├── database.py        <-- SQLite/SQLAlchemy connections and models
│   ├── parser.py          <-- Backup/Validation parser helper (if needed)
│   ├── collision.py       <-- RapidFuzz text similarity checking logic
│   ├── llm_extractor.py   <-- Ephemeral micro-LLM extraction module
│   └── templates/
│       └── index.html     <-- Frontend Single Page App UI
```

## Implementation Status

### Phase 1: Foundation & Setup
- [x] Create `.gitignore` to exclude database files and virtual environments.
- [x] Define database schema (`schema.sql`) including Many-to-Many Ticket-to-Step join tables and SQLite FTS5 configuration.
- [x] Create `requirements.txt` with necessary backend packages.
- [x] Pre-populate `project_memory.md` with system architecture and constraints.

### Phase 2: Backend Development & Ingestion Engine
- [x] Initialize Python Virtual Environment and install packages.
- [x] Implement `app/database.py` with sqlite3 tables and FTS5 triggers.
- [x] Build `app/main.py` FastAPI app providing staging API route `/api/staging/draft`.
- [x] Create frontend Dump Box view (`app/templates/dumpbox.html`) and live-parser (`app/static/parser.js`).
- [x] Add startup scripts (`start.bat` & `start.sh`) for single-click execution.

### Phase 3: Staging Inbox, Auto-Collision (RapidFuzz), & Search
- [x] Implement `app/collision.py` matching rules against Live DB.
- [x] Create search and staging queue endpoints `/api/search` and `/api/staging`.
- [x] Develop the /staging inbox view showing duplicates side-by-side with [Approve as New], [Discard Duplicate], or [Merge] actions.

### Phase 4: Master Steps & Maintenance Queue
- [x] Link master steps editing across multiple tickets.
- [x] Add the flag/unflag broken troubleshooting steps logic.
- [x] Implement the Maintenance Queue view.

### Phase 5: Soft-Filter Search Engine & Discovery Dashboard
- [x] Implement FTS5 BM25 search ranking and company boosts in the API.
- [x] Create search input debouncing (200ms) and dynamic company selection filters.
- [x] Add visual warning indicators on ticket cards containing flagged steps.

### Phase 6: Image Attachments & Maintenance
- [x] Add `ticket_images` and `step_images` tables.
- [x] Implement `/api/upload` endpoint and upload attachment maps.
- [x] Integrate frontend upload selectors, thumbnails, and modal lightbox viewers.
- [x] Implement automated disk file cleanup to remove orphaned uploads when tickets/steps are deleted.

## Lessons Learned
- **FTS5 SQLite Triggers**: Created a robust multi-trigger schema that updates `tickets_fts` when `tickets`, `ticket_steps` or `master_steps` updates. This enforces that database integrity and search sync are completely decoupled from python code, allowing pure SQL transactions to preserve indexing.
- **IT-Specific Fuzzy Normalization**: Standard `RapidFuzz` string matching scores are degraded by common technical contractions (e.g. "auth" vs "authentication", "fail" vs "error"). Introducing a lightweight IT/support terminology normalizer (which translates synonyms prior to computing the token set ratio) raised the match confidence on the duplicate test cases from 53% to 100%.
- **FTS5 Soft-Filtering with BM25**: We solved the problem of cross-company knowledge discovery using a weighted SQL score. Instead of strictly filtering queries using a `WHERE client = :client` clause (which isolates company data), we compute `-bm25(tickets_fts)` and conditionally add a boost value of `+10.0` if the ticket's client matches the targeted company parameter. This ensures exact technical matches from different companies float to the top of results when targeted company matches are thin.
- **Orphaned File Garbage Collection**: Uploading images in local-first apps creates a risk of disk bloat when tickets/steps are deleted. By running a database-driven garbage collector (`cleanup_orphaned_images`) that cross-references active attachments against physical files on disk during database deletions, we maintain a self-cleaning, low-footprint local asset uploads directory.


