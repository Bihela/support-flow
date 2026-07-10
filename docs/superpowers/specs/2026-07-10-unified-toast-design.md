# Unified Global Toast System Design Spec

## Goal
Replace native browser `alert()` fallbacks and consolidate 6 duplicate local `showToast` implementations across the Support Hub with a single, premium-styled global `window.showToast` component in `theme.js`.

## Proposed Changes

### 1. Global Toast Helper
In [theme.js](file:///c:/Users/sande/Documents/SupportHub/app/static/theme.js):
- Implement `window.showToast(message, type = 'success')`.
- It will dynamically build a toast container `#toastContainer` on `document.body` if not present.
- Create slide-up animated notifications using Tailwind classes (`bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl rounded-lg`).
- Support automatic dismissal after 4 seconds with fade-out transitions.

### 2. Cleanup local showToast definitions
Remove duplicate definitions and direct calls to the new global helper `window.showToast` in:
- `admin.js`
- `maintenance.js`
- `parser.js`
- `search.js`
- `staging.js`
- `workspace.js`
- `workspace.html` (replace `triggerToast` with calls directly to `window.showToast`).

### 3. Guidelines & Rules updates
Ensure guidelines/memory files reflect that both native `confirm()` and `alert()` are prohibited.
- [.agents/AGENTS.md](file:///c:/Users/sande/Documents/SupportHub/.agents/AGENTS.md)
- [project_memory.md](file:///c:/Users/sande/Documents/SupportHub/project_memory.md)

## Verification Plan
- Trigger alert mark-as-seen updates in Workspace and verify a premium non-blocking toast displays without browser alerts.
- Test alerts/notifications in staging, search, maintenance, and admin views to verify no regressions in toast styling or delivery.
