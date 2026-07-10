# Custom Confirmation Modals Design Spec

## Goal
Replace native browser `confirm()` popups across all pages in the Support Hub with a unified, premium-styled Tailwind modal confirmation system, and document rules to prevent native browser popups from being introduced in the future.

## Proposed Changes

### 1. Global Confirmation Helper
In [theme.js](file:///c:/Users/sande/Documents/SupportHub/app/static/theme.js):
- Add `window.showConfirm(title, message, options)` as a global async function.
- It will dynamically build a Tailwind-styled modal with:
  - Overlay with blur (`backdrop-blur-sm bg-slate-900/60`).
  - Slide/fade animations.
  - Dark mode support using Tailwind's `dark:` utility classes.
  - Buttons for Cancel and Confirm, returning a Promise resolving to `true` or `false`.
  - Safety default where "Cancel" is pre-focused, and pressing Escape cancels the action.
  - Custom icons depending on whether the action is destructive or informative.

### 2. Refactoring Confirmation Call Sites
We will replace all 8 synchronous `window.confirm` / `confirm` calls with `await window.showConfirm(...)`. Since these exist inside event handlers or form submit actions, those functions will be marked as `async`.

The call sites are:
- [admin.js](file:///c:/Users/sande/Documents/SupportHub/app/static/admin.js#L105)
- [admin.js](file:///c:/Users/sande/Documents/SupportHub/app/static/admin.js#L137)
- [maintenance.js](file:///c:/Users/sande/Documents/SupportHub/app/static/maintenance.js#L327)
- [search.js](file:///c:/Users/sande/Documents/SupportHub/app/static/search.js#L188)
- [search.js](file:///c:/Users/sande/Documents/SupportHub/app/static/search.js#L618)
- [staging.js](file:///c:/Users/sande/Documents/SupportHub/app/static/staging.js#L439)
- [workspace.js](file:///c:/Users/sande/Documents/SupportHub/app/static/workspace.js#L243)
- [workspace.js](file:///c:/Users/sande/Documents/SupportHub/app/static/workspace.js#L445)

### 3. Guidelines & Rules updates
To ensure future agents don't re-introduce native browser popups:
- Add a rule to [.agents/AGENTS.md](file:///c:/Users/sande/Documents/SupportHub/.agents/AGENTS.md).
- Update the documentation in [project_memory.md](file:///c:/Users/sande/Documents/SupportHub/project_memory.md).

## Verification Plan
- Run play/test actions for delete, remove, and overwrite across all views.
- Verify modals look premium, adapt to light/dark themes, and close properly via backdrop, Escape, and buttons.
