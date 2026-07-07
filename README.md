# SupportFlow

SupportFlow is a local-first, zero-build Support Hub and Maintenance Queue system. It is designed to run locally, serving a lightweight sqlite3 database with FastAPI and a modern single-page-app (SPA) frontend.

## Key Features

- **Local-First & Fast:** Runs on your local machine using SQLite FTS5 full-text search with BM25 ranking for ultra-fast support ticket querying.
- **Auto-Collision Engine:** Leverages `RapidFuzz` to compute text similarity, identifying potential duplicates or relevant solutions when drafting or merging tickets.
- **Ephemeral AI/LLM Integration:** Quantized micro-LLM extraction using llama-cpp-python (`Qwen2.5-1.5B-Instruct-GGUF`). The model is loaded on-demand for payload parsing and instantly reclaimed from RAM/GPU memory to keep a small footprint.
- **Master Steps & Auto-Linking:** Troubleshooting steps are automatically linked to tickets. Editing a troubleshooting step updates it globally across all referencing tickets.
- **Maintenance Queue:** Instantly flag broken, outdated, or failing troubleshooting steps to keep your documentation high quality.
- **Workspaces:** Isolate different clients, projects, or environments by switching between multiple workspaces, each keeping its own set of staging drafts and tickets.
- **Admin Panel:** Export/import your entire knowledge base as JSON or SQLite database files for backup and sharing.

## Prerequisites

- **Python:** 3.10 or higher.
- **C++ Compiler (Recommended for AI Acceleration):** Necessary for building native bindings for `llama-cpp-python`. If you do not have C++ tools, the startup scripts will automatically fall back to the pre-compiled CPU wheels.

## Local Setup

The easiest way to get started is with the one-click startup scripts:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/support-flow.git
   cd support-flow
   ```

2. **Double-click the startup script:**
   - **Windows:** Double-click `start.bat`
   - **macOS / Linux:** Run `./start.sh` (you may need to `chmod +x start.sh` first)

   The script will automatically:
   - Check that Python is installed
   - Create a virtual environment (if needed)
   - Install all dependencies (including llama-cpp-python with CPU fallback)
   - Initialize the database
   - Open your browser to `http://localhost:8000`

3. **That's it!** The app will be running at `http://localhost:8000`.

> **Admin Panel:** Access the admin page at [http://localhost:8000/admin](http://localhost:8000/admin) to manage database exports/imports and other settings.

### Manual Setup (Alternative)

If you prefer to set up manually:

```bash
# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# If llama-cpp-python fails to compile:
pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary llama-cpp-python

# Initialize the database
python -m app.database

# Start the server
uvicorn app.main:app --reload
```

## Sharing with Colleagues

Your SupportHub database is **local and private** — it is never committed to the repository and stays on your machine only.

To share your knowledge base with a colleague:

1. **Export your data:**
   - Go to the **Admin** page → click **Export Database** (full `.db` file) or **Export JSON** (portable text format)

2. **Share the exported file privately:**
   - Send via email, Microsoft Teams, USB drive, or any secure file-sharing method
   - ⚠️ Do **not** commit database files to the repository

3. **Colleague imports the data:**
   - Open their **Admin** page → click **Import Database** or **Import from JSON**

4. **Import behavior:**
   | Method | Behavior |
   |---|---|
   | **JSON Import** | Merges non-duplicate tickets into the existing database. Existing entries are preserved. |
   | **Database Import** | Replaces the entire database with the imported file. All current data is overwritten. |

> **Tip:** JSON export/import is recommended for merging knowledge bases across team members without data loss.

## Running Tests

To run the automated test suite, activate your virtual environment and run:
```bash
python -m pytest -v
```

## Contributing

We welcome contributions of all kinds! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
