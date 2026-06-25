# Design Spec: Strict Company Filtering & Staging Inbox Image Preservation

This specification addresses two issues:
1. **Strict Company Filtering**: When a company filter is selected, the search results should strictly show only that company's data. Soft/fuzzy matching across other companies should only occur when searching without a strict company filter.
2. **Staging Inbox Image Preservation**: The database image garbage collector (`cleanup_orphaned_images`) currently deletes images in the uploads folder if they are not linked to live tickets or steps, which inadvertently deletes files associated with pending drafts in the staging inbox.

## Proposed Changes

### 1. Backend Search Logic
Update the `/api/search` endpoint in [app/main.py](file:///c:/Users/sande/Documents/SupportHub/app/main.py) to:
- Apply a strict `WHERE client = ?` filter when a company dropdown option is chosen. This applies to FTS5 matches, LIKE fallbacks, and browse (no query text) calls.

### 2. Image Garbage Collection Logic
Update `cleanup_orphaned_images` in [app/main.py](file:///c:/Users/sande/Documents/SupportHub/app/main.py) to:
- Retrieve all images referenced in `staging_inbox.parsed_images`.
- Add those paths to the preserved/active list so they are not deleted when clearing orphans.

## Verification Plan

### Automated Tests
- Run `pytest test_image_endpoints.py` to ensure upload/linking tests continue passing.

### Manual Verification
1. Upload an image to a staging draft.
2. Approve a different staging draft (triggering the image cleanup).
3. Verify that the image in the first draft is still visible and not deleted on disk.
4. Select a company filter on the Fast Search page. Verify only that company's cards are listed.
