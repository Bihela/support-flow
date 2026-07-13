document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements - Templates
    const templatesList = document.getElementById("templatesList");
    const searchTemplate = document.getElementById("searchTemplate");
    const categoryFilter = document.getElementById("categoryFilter");
    const btnNewTemplate = document.getElementById("btnNewTemplate");
    const templateModal = document.getElementById("templateModal");
    const templateForm = document.getElementById("templateForm");
    const btnCancelTemplate = document.getElementById("btnCancelTemplate");
    const templateModalTitle = document.getElementById("templateModalTitle");
    const editTemplateId = document.getElementById("editTemplateId");

    // DOM Elements - Notes
    const notesList = document.getElementById("notesList");
    const pinnedNotesSection = document.getElementById("pinnedNotesSection");
    const pinnedNotesList = document.getElementById("pinnedNotesList");
    const btnNewNote = document.getElementById("btnNewNote");
    const noteModal = document.getElementById("noteModal");
    const noteForm = document.getElementById("noteForm");
    const btnCancelNote = document.getElementById("btnCancelNote");
    const noteModalTitle = document.getElementById("noteModalTitle");
    const editNoteId = document.getElementById("editNoteId");



    let allTemplates = [];
    let currentCategory = "all";



    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Wrap placeholders {{var}} in a beautifully styled mark badge
    function formatBodyWithPlaceholders(body) {
        const escaped = escapeHtml(body);
        return escaped.replace(/\{\{([^}]+)\}\}/g, (match, p1) => {
            return `<mark class="bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 px-1 py-0.5 rounded font-mono text-xs font-semibold border border-amber-200 select-all">${p1}</mark>`;
        });
    }

    // --- TEMPLATES LOGIC ---
    async function loadTemplates() {
        try {
            const url = currentCategory === "all" ? "/api/templates" : `/api/templates?category=${currentCategory}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error("Failed to load templates");
            allTemplates = await res.json();
            renderTemplates();
        } catch (err) {
            console.error(err);
            showToast("Failed to load email templates", "error");
        }
    }

    function renderTemplates() {
        const query = searchTemplate.value.toLowerCase().trim();
        const filtered = allTemplates.filter(t => {
            const matchTitle = t.title.toLowerCase().includes(query);
            const matchBody = t.body.toLowerCase().includes(query);
            return matchTitle || matchBody;
        });

        templatesList.innerHTML = "";

        if (filtered.length === 0) {
            templatesList.innerHTML = `
                <div class="text-center text-slate-400 py-12 border border-dashed border-slate-200 rounded-xl bg-white shadow-xs">
                    <p class="text-sm">No templates match your search.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(t => {
            const card = document.createElement("div");
            card.className = "bg-white border border-slate-200 hover:border-slate-300 rounded-xl p-5 shadow-sm space-y-3 transition duration-150";
            
            let catClass = "bg-slate-50 text-slate-700 border-slate-200";
            if (t.category === "escalation") catClass = "bg-red-50 text-red-700 border-red-200";
            else if (t.category === "resolution") catClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
            else if (t.category === "follow-up") catClass = "bg-blue-50 text-blue-700 border-blue-200";
            else if (t.category === "handover") catClass = "bg-purple-50 text-purple-700 border-purple-200";

            card.innerHTML = `
                <div class="flex items-start justify-between gap-2">
                    <div>
                        <h4 class="text-sm font-bold text-slate-900">${escapeHtml(t.title)}</h4>
                        <span class="inline-flex items-center px-2 py-0.5 mt-1 rounded-full text-[10px] font-semibold border ${catClass}">${t.category}</span>
                        ${t.linked_ticket_id ? `<span class="inline-flex items-center px-2 py-0.5 mt-1 ml-1 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">Ticket #${t.linked_ticket_id}</span>` : ""}
                    </div>
                    <div class="flex space-x-1.5 flex-shrink-0">
                        <button onclick="editTemplate(${t.id})" class="p-1 text-slate-400 hover:text-slate-600 transition" title="Edit Template">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                        </button>
                        <button onclick="deleteTemplate(${t.id})" class="p-1 text-slate-400 hover:text-red-650 transition" title="Delete Template">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="bg-slate-50 border border-slate-150 rounded-lg p-3 text-xs leading-relaxed max-h-48 overflow-y-auto w-full min-w-0">
                    <pre class="whitespace-pre-wrap font-sans select-text break-words">${formatBodyWithPlaceholders(t.body)}</pre>
                </div>
                <button onclick="copyToClipboard(this)" class="w-full py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition flex items-center justify-center space-x-1.5">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                    </svg>
                    <span>Copy to Clipboard</span>
                </button>
            `;
            templatesList.appendChild(card);
        });
    }

    window.copyToClipboard = function(btn) {
        const textPre = btn.previousElementSibling.querySelector("pre");
        // Copy body content
        navigator.clipboard.writeText(textPre.textContent).then(() => {
            const originalHtml = btn.innerHTML;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                <span class="text-emerald-700">Copied!</span>
            `;
            showToast("Copied email template to clipboard");
            setTimeout(() => {
                btn.innerHTML = originalHtml;
            }, 2000);
        }).catch(err => {
            console.error(err);
            showToast("Failed to copy template", "error");
        });
    };

    // Category selection pills
    categoryFilter.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        categoryFilter.querySelectorAll("button").forEach(b => {
            b.className = "px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200 transition";
        });
        btn.className = "px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100 transition";
        currentCategory = btn.dataset.cat;
        loadTemplates();
    });

    searchTemplate.addEventListener("input", renderTemplates);

    // Template Modal Handlers
    btnNewTemplate.addEventListener("click", () => {
        templateModalTitle.textContent = "Create Email Template";
        editTemplateId.value = "";
        templateForm.reset();
        templateModal.classList.remove("hidden");
    });

    btnCancelTemplate.addEventListener("click", () => {
        templateModal.classList.add("hidden");
    });

    templateForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = editTemplateId.value;
        const payload = {
            title: document.getElementById("templateTitle").value,
            category: document.getElementById("templateCategory").value,
            body: document.getElementById("templateBody").value,
            linked_ticket_id: document.getElementById("templateLinkedTicket").value ? parseInt(document.getElementById("templateLinkedTicket").value) : null
        };

        const method = id ? "PUT" : "POST";
        const url = id ? `/api/templates/${id}` : "/api/templates";

        try {
            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error("Request failed");
            showToast(id ? "Template updated successfully!" : "Template created successfully!");
            templateModal.classList.add("hidden");
            loadTemplates();
        } catch (err) {
            console.error(err);
            showToast("Failed to save template", "error");
        }
    });

    window.editTemplate = function(id) {
        const t = allTemplates.find(temp => temp.id === id);
        if (!t) return;
        templateModalTitle.textContent = "Edit Email Template";
        editTemplateId.value = t.id;
        document.getElementById("templateTitle").value = t.title;
        document.getElementById("templateCategory").value = t.category;
        document.getElementById("templateBody").value = t.body;
        document.getElementById("templateLinkedTicket").value = t.linked_ticket_id || "";
        templateModal.classList.remove("hidden");
    };

    window.deleteTemplate = async function(id) {
        const confirmed = await window.showConfirm(
            "Delete Template",
            "Are you sure you want to delete this email template?"
        );
        if (!confirmed) return;
        try {
            const res = await fetch(`/api/templates/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Delete failed");
            showToast("Template deleted successfully");
            loadTemplates();
        } catch (err) {
            console.error(err);
            showToast("Failed to delete template", "error");
        }
    };


    // --- NOTES LOGIC ---
    let allNotes = [];

    async function loadNotes() {
        try {
            const res = await fetch("/api/notes");
            if (!res.ok) throw new Error("Failed to load notes");
            allNotes = await res.json();
            renderNotes();
        } catch (err) {
            console.error(err);
            showToast("Failed to load notes", "error");
        }
    }

    function checkOverdue(dateStr) {
        if (!dateStr) return false;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const reminderDate = new Date(dateStr);
        reminderDate.setHours(0, 0, 0, 0);
        return reminderDate <= today;
    }

    function renderNotes() {
        pinnedNotesList.innerHTML = "";
        notesList.innerHTML = "";

        const pinned = allNotes.filter(n => n.is_pinned === 1);
        const normal = allNotes.filter(n => n.is_pinned === 0);

        if (pinned.length > 0) {
            pinnedNotesSection.classList.remove("hidden");
            pinned.forEach(n => appendNoteCard(pinnedNotesList, n));
        } else {
            pinnedNotesSection.classList.add("hidden");
        }

        if (normal.length === 0) {
            notesList.innerHTML = `
                <div class="text-center text-slate-400 py-12 border border-dashed border-slate-200 rounded-xl bg-white shadow-xs">
                    <p class="text-sm">No active scratch notes.</p>
                </div>
            `;
        } else {
            normal.forEach(n => appendNoteCard(notesList, n));
        }
    }

    function appendNoteCard(container, n) {
        const card = document.createElement("div");
        
        let borderClass = "border-l-blue-500";
        if (n.color === "yellow") borderClass = "border-l-yellow-500";
        else if (n.color === "green") borderClass = "border-l-emerald-500";
        else if (n.color === "red") borderClass = "border-l-rose-500";

        const isOverdue = checkOverdue(n.reminder_date);
        let reminderBadge = "";
        if (n.reminder_date) {
            const badgeBg = isOverdue ? "bg-rose-50 text-rose-700 border-rose-250 animate-pulse" : "bg-slate-100 text-slate-650 border-slate-200";
            reminderBadge = `
                <div class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${badgeBg} gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                    <span>${n.reminder_date}</span>
                </div>
            `;
        }

        card.className = `bg-white border border-slate-200 hover:border-slate-350 border-l-4 ${borderClass} rounded-xl p-5 shadow-sm space-y-2.5 transition duration-150`;
        card.innerHTML = `
            <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                    <h4 class="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                        ${n.is_pinned ? "📌 " : ""}${escapeHtml(n.title)}
                    </h4>
                    <div class="mt-1 flex flex-wrap gap-1.5">
                        ${reminderBadge}
                    </div>
                </div>
                <div class="flex space-x-1 flex-shrink-0">
                    <button onclick="togglePinNote(${n.id})" class="p-1 text-slate-400 hover:text-slate-600 transition" title="${n.is_pinned ? "Unpin note" : "Pin note"}">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                        </svg>
                    </button>
                    <button onclick="editNote(${n.id})" class="p-1 text-slate-400 hover:text-slate-600 transition" title="Edit Note">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                    </button>
                    <button onclick="deleteNote(${n.id})" class="p-1 text-slate-400 hover:text-red-650 transition" title="Delete Note">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </div>
            </div>
            ${n.body ? `
            <div class="text-xs text-slate-600 break-words leading-relaxed whitespace-pre-wrap select-text">
                ${escapeHtml(n.body)}
            </div>
            ` : ""}
        `;
        container.appendChild(card);
    }

    // Note Modal Handlers
    btnNewNote.addEventListener("click", () => {
        noteModalTitle.textContent = "Create Reminder Note";
        editNoteId.value = "";
        noteForm.reset();
        noteModal.classList.remove("hidden");
    });

    btnCancelNote.addEventListener("click", () => {
        noteModal.classList.add("hidden");
    });

    noteForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = editNoteId.value;
        const payload = {
            title: document.getElementById("noteTitle").value,
            body: document.getElementById("noteBody").value,
            color: document.getElementById("noteColor").value,
            is_pinned: document.getElementById("noteIsPinned").checked ? 1 : 0,
            reminder_date: document.getElementById("noteReminderDate").value || null
        };

        const method = id ? "PUT" : "POST";
        const url = id ? `/api/notes/${id}` : "/api/notes";

        try {
            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error("Request failed");
            showToast(id ? "Note updated successfully!" : "Note created successfully!");
            noteModal.classList.add("hidden");
            loadNotes();
        } catch (err) {
            console.error(err);
            showToast("Failed to save note", "error");
        }
    });

    window.editNote = function(id) {
        const n = allNotes.find(note => note.id === id);
        if (!n) return;
        noteModalTitle.textContent = "Edit Reminder Note";
        editNoteId.value = n.id;
        document.getElementById("noteTitle").value = n.title;
        document.getElementById("noteBody").value = n.body || "";
        document.getElementById("noteColor").value = n.color;
        document.getElementById("noteIsPinned").checked = n.is_pinned === 1;
        document.getElementById("noteReminderDate").value = n.reminder_date || "";
        noteModal.classList.remove("hidden");
    };

    window.togglePinNote = async function(id) {
        const n = allNotes.find(note => note.id === id);
        if (!n) return;
        const payload = {
            title: n.title,
            body: n.body,
            color: n.color,
            is_pinned: n.is_pinned === 1 ? 0 : 1,
            reminder_date: n.reminder_date
        };
        try {
            const res = await fetch(`/api/notes/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error("Update failed");
            loadNotes();
        } catch (err) {
            console.error(err);
            showToast("Failed to pin note", "error");
        }
    };

    window.deleteNote = async function(id) {
        const confirmed = await window.showConfirm(
            "Delete Note",
            "Are you sure you want to delete this note?"
        );
        if (!confirmed) return;
        try {
            const res = await fetch(`/api/notes/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Delete failed");
            showToast("Note deleted successfully");
            loadNotes();
        } catch (err) {
            console.error(err);
            showToast("Failed to delete note", "error");
        }
    };

    // Initial Load
    loadTemplates();
    loadNotes();
});
