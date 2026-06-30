# Search Page and Header Title Cleanup Design Spec

## Goal
Simplify the Fast Search interface and clean up the page headers by removing redundant descriptive text. The focus is to make the search bar the primary visual element on the Fast Search page and remove the system descriptor from the global header.

## Proposed Changes

### Global Header Subtitle Removal
We will remove the description paragraph under the title in the header component on all main templates.

**Files:**
- [search.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/search.html)
- [dumpbox.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/dumpbox.html)
- [maintenance.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/maintenance.html)
- [staging.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/staging.html)

**Code Edit:**
Locate:
```html
<div>
    <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
    <p class="text-xs text-slate-500">Local-First Knowledge & Maintenance Queue</p>
</div>
```
Replace with:
```html
<div>
    <h1 class="text-lg font-semibold tracking-tight text-slate-900">SupportHub</h1>
</div>
```

### Search Page Hero Text Removal
On the search page, we will remove the hero text element.

**Files:**
- [search.html](file:///c:/Users/sande/Documents/SupportHub/app/templates/search.html)

**Code Edit:**
Locate:
```html
<div class="text-center transition-all duration-500 flex flex-col justify-center min-h-[65vh]" id="searchHero">
    <div class="mb-8">
        <h2 class="text-4xl font-extrabold text-slate-900 tracking-tight mb-4">Support Knowledge Base</h2>
        <p class="text-base text-slate-500 max-w-lg mx-auto">Query tickets, clients, symptoms, or master steps instantly.</p>
    </div>
    
    <form id="searchForm" class="flex flex-col sm:flex-row gap-4 max-w-4xl mx-auto w-full items-center">
```
Replace with:
```html
<div class="text-center transition-all duration-500 flex flex-col justify-center min-h-[65vh]" id="searchHero">
    <form id="searchForm" class="flex flex-col sm:flex-row gap-4 max-w-4xl mx-auto w-full items-center">
```

## Verification Plan
1. Start the local server if running, or run the existing UI tests.
2. Manually verify in the browser that:
   - The subtitle "Local-First Knowledge & Maintenance Queue" is removed from the header on all pages.
   - The title "Support Knowledge Base" and its subtitle are removed from the search page.
   - The search form remains centered vertically on the search page.
