# Task 3 Completion Report - Background Monitors for IMAP and Windows Notifications

I have successfully implemented Task 3: Background Monitors for IMAP and Windows Notifications.

## Implementation Details

### 1. Background Polling Tasks (`app/main.py`)
- **Email Poller (`poll_emails`)**: 
  - Runs in a background daemon thread (`EmailMonitor`) managed by FastAPI's startup/shutdown lifecycle hooks.
  - Queries `alert_settings` continuously (every 5 seconds) to check shift status.
  - When `is_on_shift` is enabled, establishes a secure SSL connection using `imaplib.IMAP4_SSL`.
  - Searches for `UNSEEN` messages, decodes sender headers and subjects safely, and filters matching elements against custom keywords configured in settings.
  - Prevents duplicate alerts by checking constructed unique Gmail links (`https://mail.google.com/mail/u/0/#inbox/{message_id}`) against the database.
  - Persists new alerts to the `received_alerts` table and broadcasts the payload to connected WebSockets.
- **WhatsApp Notification Poller (`poll_whatsapp`)**:
  - Runs in a background daemon thread (`WhatsAppMonitor`).
  - Safely copies the locked Windows Action Center database (`wpndatabase.db`) to a temporary path via `shutil.copy2` to read contents without file access locks.
  - Connects to the copied SQLite database and filters messages belonging to `WhatsApp`.
  - Parses the XML payloads to extract sender names and text bodies.
  - Compares names against target settings filters. If matching, inserts unique alerts into the database and broadcasts them to clients.
  - Includes a safe OS-level fallback mechanism: if the database file is missing (e.g. non-Windows OS, notifications deactivated), it logs a warning, sleeps, and cleanly continues without blocking or crashing the loop.

### 2. Startup/Shutdown Hooks (`app/main.py`)
- Registered startup events to initiate the monitor threads daemonized.
- Configured shutdown events to set the running flag to false and gracefully join the thread execution objects.

## Testing & Verification (`test_alerts_monitors.py`)
- Created `test_alerts_monitors.py` covering:
  - XML payload extraction parser accuracy.
  - Mocked IMAP email polling with matching/non-matching keywords.
  - Mocked Windows Notification center DB parsing, temporary copy routing, and schema filtering.
  - Seamless database insertion validation.
- All tests in the test suite pass:
  - `test_alerts_db.py` (Passed)
  - `test_alerts_api.py` (Passed)
  - `test_alerts_monitors.py` (Passed)

---
Verified successfully on: Windows 11.

## Review Fix Report (July 2026)

### 1. Native `asyncio` Background Tasks on Main Event Loop
- **Issue**: Background monitors ran on separate daemon threads, resulting in event loop conflict and `RuntimeError` during WebSocket broadcasts.
- **Solution**: 
  - Converted `poll_emails` and `poll_whatsapp` loops into async task loops (`email_monitor_loop` and `whatsapp_monitor_loop`) run natively on the main asyncio event loop via `asyncio.create_task`.
  - Moved blocking synchronous operations (IMAP networking and Action Center SQLite file copies/reads) to separate thread-pool executors using `asyncio.to_thread` (`poll_emails_sync` and `poll_whatsapp_sync`).
  - Added backward-compatible synchronous wrappers (`poll_emails` and `poll_whatsapp`) checking for running event loops and scheduling broadcasts safely so tests continue to pass without modifications.

### 2. Lifespan Event Handlers Migration
- **Issue**: `@app.on_event("startup")` and `@app.on_event("shutdown")` are deprecated in modern FastAPI.
- **Solution**:
  - Replaced the deprecated event hooks in [main.py](file:///c:/Users/sande/Documents/SupportHub/app/main.py) with the modern `lifespan` async context manager.
  - Background task creation is handled at startup and cancelled cleanly at shutdown using task cancellation and `asyncio.gather`.

