# Design Spec: Publishing SupportFlow to GitHub

Designing the migration of the SupportHub project (to be named `SupportFlow` or `support-flow`) to a public GitHub repository, setting up CI/CD, configuring open-source documentation, and adding automated testing configurations.

## Exclusions & Security (Critical)
* `project_memory.md` must be added to `.gitignore` so it is never pushed.
* `support_hub.db` and any SQLite database files must remain in `.gitignore`.
* `app/static/uploads/` must remain in `.gitignore`.
* Any GGUF model files in `models/` must not be pushed to GitHub.

## Documentation & Repository Metadata
* **README.md:** Standard open-source README detailing:
  * Application purpose (local-first support hub with SQLite FTS5 search and ephemeral micro-LLM extraction).
  * System requirements (Python 3.10+, llama-cpp-python dependencies).
  * Setup & Quickstart (running `start.bat` / `start.sh`).
  * Running tests locally.
* **LICENSE:** MIT License file.
* **Repository Settings:** Set the repository description, tags (e.g. `fastapi`, `sqlite-fts5`, `local-llm`, `helpdesk`), and homepage.

## CI/CD Pipeline
* **GitHub Actions Workflow (`.github/workflows/ci.yml`):**
  * Runs on `push` and `pull_request` targeting `main`.
  * Installs dependencies (using mock/CPU-only installation instructions for pytest to avoid heavy GPU compiler setups on Ubuntu runners).
  * Runs `pytest` to execute all unit/integration tests.

## Testing Setup
* Create or modify test cases to run against a temporary SQLite database (using a pytest fixture) so they don't overwrite or read the local `support_hub.db`.
* Mock out LLM inference steps in automated tests to ensure tests run fast and don't fail in GitHub Actions due to missing GGUF weights.
