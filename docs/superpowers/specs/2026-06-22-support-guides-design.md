# Design Spec: Support Guides, Playbooks & Landing Page Search Clean-up

We want to allow users to store support playbooks/guides (like "User Creation") with steps and a verification checklist. These guides will be created via the **Dump Box**, go through the **Staging Inbox**, and be fully searchable using the existing global search bar.

Additionally, the Fast Search landing page should load with only the search bar visible, displaying no results until the user initiates a search.

## Proposed Changes

### 1. Database Schema
Update [app/database.py](file:///c:/Users/sande/Documents/SupportHub/app/database.py) to:
- Safely add `type` (TEXT, defaults to `'ticket'`) and `checklist` (TEXT, JSON string) to the `tickets` table.
- Safely add `parsed_type` and `parsed_checklist` to `staging_inbox`.
- Update FTS5 sync triggers so that `checklist` content is concatenated into `steps_content` in `tickets_fts` for indexing.

### 2. Dump Box UI & Shorthand Parser
- **Dropdown Selector**: Add a `<select id="typeSelect">` dropdown on the Dump Box page (`app/templates/dumpbox.html`) next to the Submit button. The user can explicitly choose between "Troubleshooting Ticket" and "Support Guide".
- **Shorthand Checklist Parsing**:
  - In [app/static/parser.js](file:///c:/Users/sande/Documents/SupportHub/app/static/parser.js), parse lines starting with `- [ ] ` or `* [ ] ` or `? ` as checklist items.
  - Set the draft type explicitly based on the dropdown selection.
- Update the Dump Box preview card to render the parsed checklist if it exists.

### 3. Backend Endpoints
Update [app/main.py](file:///c:/Users/sande/Documents/SupportHub/app/main.py):
- Update `DraftPayload` and `UpdateDraftPayload` models to include `type` and `checklist`.
- Update `/api/staging/draft` and draft approval/merge endpoints to handle type and checklist.
- When a guide is approved, save `type = 'guide'` and the `checklist` (JSON serialized list of strings) to the `tickets` table.

### 4. Staging Editor Update
Modify [app/templates/staging.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/staging.html) and [app/static/staging.js](file:///c:/Users/sande/Documents/SupportHub/app/static/staging.js):
- Add a text area for the verification checklist (one item per line) and a dropdown to select between "ticket" and "guide".
- Update the save, merge, and approve actions to send the type and checklist.

### 5. Search Interface UI Updates
- **Search Results Card**: If a search result is a `'guide'`, display its checklist at the bottom of the card with checkable boxes so the support engineer can verify their steps.
- **Landing Page (Fast Search)**: Modify [app/templates/search.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/search.html) and its JS to load without displaying initial results. Results will only render once the user enters a search query or selects a company filter.
