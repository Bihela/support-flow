# Workspace Rules

- **Database Preservation**: DO NOT delete, reset, or drop the SQLite database (`support_hub.db`) or run test scripts that delete it. The database contains critical production data and knowledge guides. Use migrations, alter statements, or conditional table creation (`CREATE TABLE IF NOT EXISTS`) to modify database structure without destroying existing records.
- **No Browser Popups**: DO NOT use native browser popups like `alert()` or `confirm()`. For confirmation dialogs, always use `await window.showConfirm(title, message, options)` which returns a Promise resolving to a boolean.

