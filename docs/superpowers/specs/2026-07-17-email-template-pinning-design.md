# Email Template Pinning Design

Add a feature to pin important email templates to the top of the templates list in the workspace.

## User Review Required

No critical items or breaking changes. We will perform a safe database migration by adding `is_pinned` column to `email_templates` table if it does not already exist.

## Proposed Changes

### Database & Backend

#### [MODIFY] [database.py](file:///c:/Users/sande/Documents/SupportHub/app/database.py)
- Update the table creation query for `email_templates` to include `is_pinned INTEGER DEFAULT 0`.
- In `init_db()`, execute a safe migration check to `ALTER TABLE email_templates ADD COLUMN is_pinned INTEGER DEFAULT 0` under a try-catch block to handle existing tables gracefully.

#### [MODIFY] [main.py](file:///c:/Users/sande/Documents/SupportHub/app/main.py)
- Update `get_email_templates` (`GET /api/templates`) to sort by `is_pinned DESC, id DESC`.
- Add a new route `PUT /api/templates/{id}/pin` which toggles the `is_pinned` value for the template.

### Frontend UI

#### [MODIFY] [workspace.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/workspace.html)
- No direct HTML updates are needed for the template card itself since cards are rendered dynamically in Javascript, but ensure UI styling supports the pin buttons.

#### [MODIFY] [workspace.js](file:///c:/Users/sande/Documents/SupportHub/app/static/workspace.js)
- Update `renderTemplates` to display a pin toggle button next to the edit/delete buttons.
- Render an amber `📌 Pinned` badge next to the category badge when `t.is_pinned === 1`.
- implement `togglePinTemplate(id)` to hit `PUT /api/templates/{id}/pin`, then call `loadTemplates()` to reload and update the UI.

## Verification Plan

### Automated Tests
- Run backend tests to verify existing features are not broken.
- Add a test or verify with quick assertions that the new endpoint works.

### Manual Verification
- Launch the application and load the workspace page.
- Create a template, click the pin button, verify it bubbles to the top and shows the "Pinned" badge.
- Click the pin button again, verify it is unpinned.
