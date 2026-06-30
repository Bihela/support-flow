# Search Page and Header Title Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up descriptive headers on all pages and remove the hero titles from the Fast Search page.

**Architecture:** Edit frontend templates in the `app/templates` directory. Remove target subtitle components and header wrappers using simple text replacement.

**Tech Stack:** HTML, Tailwind CSS, Jinja templates.

## Global Constraints
- Database Preservation: DO NOT delete, reset, or drop the SQLite database (`support_hub.db`) or run test scripts that delete it.
- Maintain existing styles and responsive layout structures.

---

### Task 1: Clean Up Header Subtitle Across Templates

**Files:**
- Modify: [search.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/search.html)
- Modify: [dumpbox.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/dumpbox.html)
- Modify: [maintenance.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/maintenance.html)
- Modify: [staging.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/staging.html)

- [ ] **Step 1: Edit app/templates/search.html**
  Remove the `<p class="text-xs text-slate-500">Local-First Knowledge & Maintenance Queue</p>` paragraph in the header block.
  Replace:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
                  <p class="text-xs text-slate-500">Local-First Knowledge & Maintenance Queue</p>
              </div>
  ```
  With:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
              </div>
  ```

- [ ] **Step 2: Edit app/templates/dumpbox.html**
  Remove the subtitle paragraph from the header block.
  Replace:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
                  <p class="text-xs text-slate-500">Local-First Knowledge & Maintenance Queue</p>
              </div>
  ```
  With:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
              </div>
  ```

- [ ] **Step 3: Edit app/templates/maintenance.html**
  Remove the subtitle paragraph from the header block.
  Replace:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
                  <p class="text-xs text-slate-500">Local-First Knowledge & Maintenance Queue</p>
              </div>
  ```
  With:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
              </div>
  ```

- [ ] **Step 4: Edit app/templates/staging.html**
  Remove the subtitle paragraph from the header block.
  Replace:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
                  <p class="text-xs text-slate-500">Local-First Knowledge & Maintenance Queue</p>
              </div>
  ```
  With:
  ```html
              <div>
                  <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
              </div>
  ```

- [ ] **Step 5: Commit changes**
  Run: `git commit -am "chore: remove Local-First subtitle from all page headers"`

---

### Task 2: Remove Fast Search Page Hero Text

**Files:**
- Modify: [search.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/search.html)

- [ ] **Step 1: Edit app/templates/search.html**
  Remove the hero title text block inside the search form container.
  Replace:
  ```html
              <!-- Center Hero Search Container -->
              <div class="text-center transition-all duration-500 flex flex-col justify-center min-h-[65vh]" id="searchHero">
                  <div class="mb-8">
                      <h2 class="text-4xl font-extrabold text-slate-900 tracking-tight mb-4">Support Knowledge Base</h2>
                      <p class="text-base text-slate-500 max-w-lg mx-auto">Query tickets, clients, symptoms, or master steps instantly.</p>
                  </div>
                  
                  <form id="searchForm" class="flex flex-col sm:flex-row gap-4 max-w-4xl mx-auto w-full items-center">
  ```
  With:
  ```html
              <!-- Center Hero Search Container -->
              <div class="text-center transition-all duration-500 flex flex-col justify-center min-h-[65vh]" id="searchHero">
                  <form id="searchForm" class="flex flex-col sm:flex-row gap-4 max-w-4xl mx-auto w-full items-center">
  ```

- [ ] **Step 2: Commit changes**
  Run: `git commit -am "feat: remove hero title and subtitle from Fast Search page"`
