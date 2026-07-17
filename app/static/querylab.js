/**
 * Query Lab — Interactive SQL query workbench for SupportHub.
 * 
 * Loads auto-learned schema from stored query-type tickets,
 * provides a SQL editor with validation, and a template library.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── State ─────────────────────────────────────────────────
    let currentCompany = null;
    let schemaCache = {};       // { client: { tables: {...} } }
    let currentTemplates = [];
    let allTemplates = [];
    let validationTimeout = null;

    // ── DOM refs ──────────────────────────────────────────────
    const companySelect = document.getElementById('companySelect');
    const companyBadge = document.getElementById('companyBadge');
    const schemaPanel = document.getElementById('schemaPanel');
    const schemaFilter = document.getElementById('schemaFilter');
    const schemaTree = document.getElementById('schemaTree');
    const queryEditor = document.getElementById('queryEditor');
    const lineNumbers = document.getElementById('lineNumbers');
    const editorStatus = document.getElementById('editorStatus');
    const validationResults = document.getElementById('validationResults');
    const validationStatus = document.getElementById('validationStatus');
    const templatePanel = document.getElementById('templatePanel');
    const templateFilter = document.getElementById('templateFilter');
    const templateList = document.getElementById('templateList');
    const allCompaniesToggle = document.getElementById('allCompaniesToggle');
    const copyBtn = document.getElementById('copyBtn');
    const resetBtn = document.getElementById('resetBtn');
    const saveTemplateBtn = document.getElementById('saveTemplateBtn');
    const toggleSchemaBtn = document.getElementById('toggleSchemaBtn');
    const toggleTemplateBtn = document.getElementById('toggleTemplateBtn');
    const closeSchemaBtn = document.getElementById('closeSchemaBtn');
    const closeTemplateBtn = document.getElementById('closeTemplateBtn');

    // ── Init ──────────────────────────────────────────────────
    loadCompanies();
    setupEditor();
    setupEventListeners();

    // ── API Calls ─────────────────────────────────────────────

    async function loadCompanies() {
        try {
            const res = await fetch('/api/querylab/companies');
            const data = await res.json();
            companySelect.innerHTML = '<option value="">-- Select Company --</option>';
            for (const c of data.companies) {
                const opt = document.createElement('option');
                opt.value = c.name;
                opt.textContent = `${c.name} (${c.table_count} tables, ${c.query_count} queries)`;
                companySelect.appendChild(opt);
            }
        } catch (e) {
            console.error('Failed to load companies:', e);
        }
    }

    async function loadSchema(client) {
        if (schemaCache[client]) {
            renderSchemaTree(schemaCache[client]);
            return;
        }
        try {
            schemaTree.innerHTML = '<div class="text-xs text-slate-400 text-center py-4">Loading schema...</div>';
            const res = await fetch(`/api/querylab/schema/${encodeURIComponent(client)}`);
            const data = await res.json();
            schemaCache[client] = data;
            renderSchemaTree(data);
        } catch (e) {
            schemaTree.innerHTML = '<div class="text-xs text-red-400 text-center py-4">Failed to load schema</div>';
            console.error('Failed to load schema:', e);
        }
    }

    async function loadTemplates(client) {
        try {
            templateList.innerHTML = '<div class="text-xs text-slate-400 text-center py-4">Loading templates...</div>';
            const url = client ? `/api/querylab/templates?client=${encodeURIComponent(client)}` : '/api/querylab/templates';
            const res = await fetch(url);
            const data = await res.json();
            if (client) {
                currentTemplates = data.templates;
            } else {
                allTemplates = data.templates;
            }
            renderTemplateList(client ? currentTemplates : allTemplates);
        } catch (e) {
            templateList.innerHTML = '<div class="text-xs text-red-400 text-center py-4">Failed to load templates</div>';
            console.error('Failed to load templates:', e);
        }
    }

    async function loadTemplateDetail(ticketId) {
        try {
            const res = await fetch(`/api/querylab/templates/${ticketId}`);
            const data = await res.json();
            if (data.sql) {
                queryEditor.value = data.sql;
                updateLineNumbers();
                triggerValidation();
                window.showToast(`Loaded template: ${data.title}`, 'success');
            } else {
                window.showToast('No SQL found in this template', 'warning');
            }
        } catch (e) {
            window.showToast('Failed to load template', 'error');
            console.error('Failed to load template detail:', e);
        }
    }

    async function runValidation() {
        const sql = queryEditor.value.trim();
        if (!sql) {
            validationResults.innerHTML = '<p class="text-xs text-slate-400">Write a query to see validation results</p>';
            validationStatus.textContent = '';
            return;
        }
        if (!currentCompany) {
            validationResults.innerHTML = '<p class="text-xs text-amber-500">⚠️ Select a company to validate against its schema</p>';
            validationStatus.textContent = '';
            return;
        }

        validationStatus.textContent = 'Validating...';
        try {
            const res = await fetch('/api/querylab/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql, client: currentCompany }),
            });
            const data = await res.json();
            renderValidationResults(data);
        } catch (e) {
            validationResults.innerHTML = '<p class="text-xs text-red-400">❌ Validation failed</p>';
            validationStatus.textContent = 'Error';
            console.error('Validation failed:', e);
        }
    }

    // ── Schema Explorer ───────────────────────────────────────

    function renderSchemaTree(data) {
        const tables = data.tables || {};
        const tableNames = Object.keys(tables);

        if (tableNames.length === 0) {
            schemaTree.innerHTML = '<div class="text-xs text-slate-400 text-center py-8 px-4">No schema found for this company. Add query-type tickets to build the schema map.</div>';
            return;
        }

        let html = '';
        for (const tableName of tableNames.sort()) {
            const tableInfo = tables[tableName];
            const columns = tableInfo.columns || [];
            const sourceCount = (tableInfo.source_tickets || []).length;
            const tooltip = sourceCount > 0 ? `title="Learned from ${sourceCount} ticket${sourceCount > 1 ? 's' : ''}"` : '';

            html += `
                <div class="ql-tree-table mb-1" data-table="${escapeHtml(tableName)}">
                    <div class="ql-tree-toggle ql-tree-item font-medium text-slate-800" ${tooltip}
                         onclick="this.classList.toggle('expanded')">
                        <span class="ql-table-name" data-insert='"${escapeHtml(tableName)}"'>${escapeHtml(tableName)}</span>
                        <span class="text-[10px] text-slate-400 ml-1">(${columns.length})</span>
                    </div>
                    <div class="ql-tree-children">
            `;
            for (const col of columns) {
                html += `<div class="ql-tree-item ql-tree-col text-slate-600" data-insert='"${escapeHtml(col)}"'>${escapeHtml(col)}</div>`;
            }
            html += `</div></div>`;
        }

        schemaTree.innerHTML = html;

        // Click-to-insert handlers
        schemaTree.querySelectorAll('[data-insert]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                insertAtCursor(el.dataset.insert);
            });
        });
    }

    function filterSchema() {
        const term = schemaFilter.value.trim().toLowerCase();
        const tables = schemaTree.querySelectorAll('.ql-tree-table');
        tables.forEach(tableEl => {
            const tableName = (tableEl.dataset.table || '').toLowerCase();
            const columns = tableEl.querySelectorAll('.ql-tree-col');
            let tableMatch = tableName.includes(term);
            let anyColMatch = false;

            columns.forEach(col => {
                const colText = col.textContent.toLowerCase();
                const match = colText.includes(term);
                col.style.display = (!term || match || tableMatch) ? '' : 'none';
                if (match) anyColMatch = true;
            });

            tableEl.style.display = (!term || tableMatch || anyColMatch) ? '' : 'none';

            // Auto-expand if filtering and has matches
            if (term && (tableMatch || anyColMatch)) {
                const toggle = tableEl.querySelector('.ql-tree-toggle');
                if (toggle && !toggle.classList.contains('expanded')) {
                    toggle.classList.add('expanded');
                }
            }
        });
    }

    // ── Editor ────────────────────────────────────────────────

    function setupEditor() {
        queryEditor.addEventListener('input', () => {
            updateLineNumbers();
            triggerValidation();
            updateEditorStatus();
        });

        queryEditor.addEventListener('scroll', () => {
            lineNumbers.scrollTop = queryEditor.scrollTop;
        });

        // Tab key inserts spaces instead of changing focus
        queryEditor.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = queryEditor.selectionStart;
                const end = queryEditor.selectionEnd;
                queryEditor.value = queryEditor.value.substring(0, start) + '    ' + queryEditor.value.substring(end);
                queryEditor.selectionStart = queryEditor.selectionEnd = start + 4;
                updateLineNumbers();
            }
        });

        updateLineNumbers();
    }

    function updateLineNumbers() {
        const lines = queryEditor.value.split('\n');
        const count = Math.max(lines.length, 1);
        let html = '';
        for (let i = 1; i <= count; i++) {
            html += `<span>${i}</span>`;
        }
        lineNumbers.innerHTML = html;
    }

    function updateEditorStatus() {
        const text = queryEditor.value;
        const lines = text.split('\n').length;
        const chars = text.length;
        editorStatus.textContent = `${lines} line${lines !== 1 ? 's' : ''}, ${chars} char${chars !== 1 ? 's' : ''}`;
    }

    function insertAtCursor(text) {
        queryEditor.focus();
        const start = queryEditor.selectionStart;
        const end = queryEditor.selectionEnd;
        const before = queryEditor.value.substring(0, start);
        const after = queryEditor.value.substring(end);

        // Add a space before if the char before cursor isn't whitespace or empty
        const needsSpace = before.length > 0 && !/[\s(,]$/.test(before);
        const insertion = (needsSpace ? ' ' : '') + text;

        queryEditor.value = before + insertion + after;
        queryEditor.selectionStart = queryEditor.selectionEnd = start + insertion.length;
        updateLineNumbers();
        triggerValidation();
        updateEditorStatus();
    }

    function triggerValidation() {
        if (validationTimeout) clearTimeout(validationTimeout);
        validationTimeout = setTimeout(runValidation, 500);
    }

    // ── Validation Display ────────────────────────────────────

    function renderValidationResults(data) {
        let html = '';

        // SELECT-only check
        if (data.is_select_only) {
            html += `<div class="flex items-center gap-2 text-xs"><span class="text-emerald-500 font-bold">✅</span> <span class="text-slate-600">Read-only query (SELECT only)</span></div>`;
        } else {
            html += `<div class="flex items-center gap-2 text-xs"><span class="text-red-500 font-bold">❌</span> <span class="text-red-600 font-medium">Contains write operations — only SELECT queries are allowed</span></div>`;
        }

        // Tables check
        if (data.tables_found && data.tables_found.length > 0) {
            const tableErrors = (data.errors || []).filter(e => e.includes('table') || e.includes('Table'));
            if (tableErrors.length === 0) {
                html += `<div class="flex items-center gap-2 text-xs"><span class="text-emerald-500 font-bold">✅</span> <span class="text-slate-600">All tables found in schema: ${data.tables_found.map(t => `<code class="text-xs bg-slate-100 px-1 rounded">${escapeHtml(t)}</code>`).join(', ')}</span></div>`;
            } else {
                for (const err of tableErrors) {
                    html += `<div class="flex items-center gap-2 text-xs"><span class="text-red-500 font-bold">❌</span> <span class="text-red-600">${escapeHtml(err)}</span></div>`;
                }
            }
        }

        // Column warnings
        const colWarnings = (data.warnings || []).filter(w => w.includes('column') || w.includes('Column'));
        for (const warn of colWarnings) {
            html += `<div class="flex items-center gap-2 text-xs"><span class="text-amber-500 font-bold">⚠️</span> <span class="text-amber-600">${escapeHtml(warn)}</span></div>`;
        }

        // Other errors
        const otherErrors = (data.errors || []).filter(e => !e.includes('table') && !e.includes('Table') && !e.includes('read-only') && !e.includes('write'));
        for (const err of otherErrors) {
            html += `<div class="flex items-center gap-2 text-xs"><span class="text-red-500 font-bold">❌</span> <span class="text-red-600">${escapeHtml(err)}</span></div>`;
        }

        // Overall verdict
        if (data.valid) {
            html += `<div class="mt-2 pt-2 border-t border-slate-100 flex items-center gap-2 text-xs"><span class="text-emerald-600 font-semibold">✅ Query is valid and safe to run</span></div>`;
            validationStatus.textContent = 'Valid';
            validationStatus.className = 'text-[10px] font-mono text-emerald-600';
        } else {
            html += `<div class="mt-2 pt-2 border-t border-slate-100 flex items-center gap-2 text-xs"><span class="text-red-600 font-semibold">❌ Query has issues — review errors above</span></div>`;
            validationStatus.textContent = 'Issues found';
            validationStatus.className = 'text-[10px] font-mono text-red-500';
        }

        validationResults.innerHTML = html;
    }

    // ── Template Library ──────────────────────────────────────

    function renderTemplateList(templates) {
        if (!templates || templates.length === 0) {
            templateList.innerHTML = '<div class="text-xs text-slate-400 text-center py-8 px-4">No query templates found for this company</div>';
            return;
        }

        let html = '';
        for (const t of templates) {
            const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString() : '';
            const symptomSnippet = t.symptom ? (t.symptom.length > 60 ? t.symptom.substring(0, 60) + '...' : t.symptom) : '';

            html += `
                <div class="ql-template-card bg-slate-50 border border-slate-200 rounded-lg p-3 cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition duration-150 mb-2" data-ticket-id="${t.id}">
                    <div class="flex items-start justify-between gap-2 mb-1">
                        <h4 class="text-xs font-semibold text-slate-800 leading-tight">${escapeHtml(t.title || 'Untitled')}</h4>
                    </div>
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">${escapeHtml(t.client || 'Unknown')}</span>
                        <span class="text-[10px] text-slate-400">${dateStr}</span>
                    </div>
                    ${symptomSnippet ? `<p class="text-[11px] text-slate-500 leading-snug">${escapeHtml(symptomSnippet)}</p>` : ''}
                </div>
            `;
        }

        templateList.innerHTML = html;

        // Click handlers
        templateList.querySelectorAll('.ql-template-card').forEach(card => {
            card.addEventListener('click', () => {
                const ticketId = card.dataset.ticketId;
                loadTemplateDetail(parseInt(ticketId));
            });
        });
    }

    function filterTemplates() {
        const term = templateFilter.value.trim().toLowerCase();
        const source = allCompaniesToggle.checked ? allTemplates : currentTemplates;
        if (!term) {
            renderTemplateList(source);
            return;
        }
        const filtered = source.filter(t =>
            (t.title || '').toLowerCase().includes(term) ||
            (t.symptom || '').toLowerCase().includes(term) ||
            (t.client || '').toLowerCase().includes(term)
        );
        renderTemplateList(filtered);
    }

    // ── Actions ───────────────────────────────────────────────

    async function copyToClipboard() {
        const sql = queryEditor.value.trim();
        if (!sql) {
            window.showToast('Nothing to copy — write a query first', 'warning');
            return;
        }
        try {
            await navigator.clipboard.writeText(sql);
            window.showToast('Query copied to clipboard', 'success');
        } catch (e) {
            // Fallback for non-HTTPS
            const textarea = document.createElement('textarea');
            textarea.value = sql;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            window.showToast('Query copied to clipboard', 'success');
        }
    }

    function resetEditor() {
        queryEditor.value = '';
        updateLineNumbers();
        updateEditorStatus();
        validationResults.innerHTML = '<p class="text-xs text-slate-400">Write a query to see validation results</p>';
        validationStatus.textContent = '';
        validationStatus.className = 'text-[10px] text-slate-400 font-mono';
    }

    function saveAsTemplate() {
        const sql = queryEditor.value.trim();
        if (!sql) {
            window.showToast('Write a query before saving as template', 'warning');
            return;
        }
        // Store SQL in sessionStorage and redirect to dump box
        sessionStorage.setItem('querylab_sql', sql);
        sessionStorage.setItem('querylab_client', currentCompany || '');
        window.location.href = '/dumpbox';
    }

    // ── Event Listeners ───────────────────────────────────────

    function setupEventListeners() {
        // Company selection
        companySelect.addEventListener('change', async () => {
            currentCompany = companySelect.value || null;
            if (currentCompany) {
                companyBadge.textContent = currentCompany;
                companyBadge.classList.remove('hidden');
                await Promise.all([loadSchema(currentCompany), loadTemplates(currentCompany)]);
                // Also preload all templates for toggle
                if (allTemplates.length === 0) {
                    const res = await fetch('/api/querylab/templates');
                    const data = await res.json();
                    allTemplates = data.templates;
                }
                triggerValidation();
            } else {
                companyBadge.classList.add('hidden');
                schemaTree.innerHTML = '<div class="text-xs text-slate-400 text-center py-8 px-4">Select a company to explore its auto-learned schema</div>';
                templateList.innerHTML = '<div class="text-xs text-slate-400 text-center py-8 px-4">Select a company to view query templates</div>';
            }
        });

        // Schema filter
        schemaFilter.addEventListener('input', filterSchema);

        // Template filter
        templateFilter.addEventListener('input', filterTemplates);

        // All companies toggle
        allCompaniesToggle.addEventListener('change', () => {
            if (allCompaniesToggle.checked) {
                if (allTemplates.length === 0) {
                    loadTemplates(null);
                } else {
                    renderTemplateList(allTemplates);
                }
            } else {
                renderTemplateList(currentTemplates);
            }
        });

        // Action buttons
        copyBtn.addEventListener('click', copyToClipboard);
        resetBtn.addEventListener('click', resetEditor);
        saveTemplateBtn.addEventListener('click', saveAsTemplate);

        // Responsive panel toggles
        toggleSchemaBtn.addEventListener('click', () => {
            const isVisible = schemaPanel.classList.contains('flex');
            if (isVisible && !schemaPanel.classList.contains('xl:flex')) {
                schemaPanel.classList.remove('flex');
                schemaPanel.classList.add('hidden');
            } else {
                schemaPanel.classList.remove('hidden');
                schemaPanel.classList.add('flex');
            }
        });

        toggleTemplateBtn.addEventListener('click', () => {
            const isVisible = templatePanel.classList.contains('flex');
            if (isVisible && !templatePanel.classList.contains('lg:flex')) {
                templatePanel.classList.remove('flex');
                templatePanel.classList.add('hidden');
            } else {
                templatePanel.classList.remove('hidden');
                templatePanel.classList.add('flex');
            }
        });

        closeSchemaBtn.addEventListener('click', () => {
            schemaPanel.classList.remove('flex');
            schemaPanel.classList.add('hidden');
        });

        closeTemplateBtn.addEventListener('click', () => {
            templatePanel.classList.remove('flex');
            templatePanel.classList.add('hidden');
        });
    }

    // ── Utilities ─────────────────────────────────────────────

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(text || ''));
        return div.innerHTML;
    }
});
