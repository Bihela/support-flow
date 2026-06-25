# SupportFlow

SupportFlow is a local-first, zero-build Support Hub and Maintenance Queue system. It is designed to run locally, serving a lightweight sqlite3 database with FastAPI and a modern single-page-app (SPA) frontend.

## Key Features

- **Local-First & Fast:** Runs on your local machine using SQLite FTS5 full-text search with BM25 ranking for ultra-fast support ticket querying.
- **Auto-Collision Engine:** Leverages `RapidFuzz` to compute text similarity, identifying potential duplicates or relevant solutions when drafting or merging tickets.
- **Ephemeral AI/LLM Integration:** Quantized micro-LLM extraction using llama-cpp-python (`Qwen2.5-1.5B-Instruct-GGUF`). The model is loaded on-demand for payload parsing and instantly reclaimed from RAM/GPU memory to keep a small footprint.
- **Master Steps & Auto-Linking:** Troubleshooting steps are automatically linked to tickets. Editing a troubleshooting step updates it globally across all referencing tickets.
- **Maintenance Queue:** Instantly flag broken, outdated, or failing troubleshooting steps to keep your documentation high quality.

## Prerequisites

- **Python:** 3.10 or higher.
- **C++ Compiler (Recommended for AI Acceleration):** Necessary for building native bindings for `llama-cpp-python`. If you do not have C++ tools, you can fall back to the pre-compiled CPU wheels.

## Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/support-flow.git
   cd support-flow
   ```

2. **Initialize the Virtual Environment & Install Dependencies:**
   On Windows:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
   *Note: If installing `llama-cpp-python` fails due to compilation issues, run:*
   ```bash
   pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary llama-cpp-python
   ```

3. **Database Initialization:**
   The SQLite database structure can be initialized from `schema.sql`:
   ```bash
   sqlite3 support_hub.db < schema.sql
   ```

4. **Run the Application:**
   Double click `start.bat` (Windows) or execute `start.sh` (macOS/Linux).
   Alternatively, run:
   ```bash
   uvicorn app.main:app --reload
   ```
   Open your browser and navigate to `http://127.0.0.1:8000`.

## Running Tests

To run the automated test suite, make sure pytest is installed:
```bash
pytest test_staging_api.py test_image_endpoints.py -v
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
