document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('searchForm');
    const searchQuery = document.getElementById('searchQuery');
    const searchResults = document.getElementById('searchResults');
    const resultsCount = document.getElementById('resultsCount');
    
    const companyFilter = document.getElementById('companyFilter');
    
    // Modal elements
    const flagModal = document.getElementById('flagModal');
    const modalBackdrop = document.getElementById('modalBackdrop');
    const flagReason = document.getElementById('flagReason');
    const cancelFlagBtn = document.getElementById('cancelFlagBtn');
    const submitFlagBtn = document.getElementById('submitFlagBtn');
    const toastContainer = document.getElementById('toastContainer');

    let currentStepIdToFlag = null;

    // Lightbox modal elements
    const lightboxModal = document.getElementById('lightboxModal');
    const lightboxImage = document.getElementById('lightboxImage');
    const closeLightboxBtn = document.getElementById('closeLightboxBtn');

    if (lightboxModal) {
        lightboxModal.addEventListener('click', (e) => {
            if (e.target === lightboxModal || e.target === closeLightboxBtn || e.target.closest('#closeLightboxBtn')) {
                lightboxModal.classList.add('hidden');
                lightboxImage.src = '';
            }
        });
    }

    function openLightbox(src) {
        if (lightboxImage && lightboxModal) {
            lightboxImage.src = src;
            lightboxModal.classList.remove('hidden');
        }
    }

    // Standard JS debounce helper function
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Toast utility
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `px-4 py-3 rounded-lg text-sm font-medium shadow-lg border transition-all duration-300 transform translate-y-2 opacity-0 flex items-center space-x-2`;
        
        if (type === 'success') {
            toast.className += ' bg-emerald-50 border-emerald-250 text-emerald-800';
            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>${message}</span>
            `;
        } else {
            toast.className += ' bg-rose-50 border-rose-250 text-rose-800';
            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>${message}</span>
            `;
        }
        
        toastContainer.appendChild(toast);
        
        // Trigger reflow to animate
        setTimeout(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
        }, 10);

        // Remove toast
        setTimeout(() => {
            toast.classList.add('translate-y-2', 'opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Modal Visibility Controllers
    function openModal(stepId) {
        currentStepIdToFlag = stepId;
        flagReason.value = '';
        flagModal.classList.remove('hidden');
        flagReason.focus();
    }

    // Populate company options
    async function loadCompanies() {
        try {
            const currentSelected = companyFilter.value;
            const response = await fetch('/api/companies');
            if (!response.ok) {
                throw new Error('Failed to fetch companies');
            }
            const companies = await response.json();
            
            // Keep default option
            companyFilter.innerHTML = '<option value="">-- Select Company (Soft Filter) --</option>';
            companies.forEach(company => {
                const opt = document.createElement('option');
                opt.value = company;
                opt.textContent = company;
                companyFilter.appendChild(opt);
            });

            // Re-select if it was previously selected and still exists
            if (companies.includes(currentSelected)) {
                companyFilter.value = currentSelected;
            }
        } catch (error) {
            console.error('Failed to load companies dropdown:', error);
        }
    }

    function closeModal() {
        flagModal.classList.add('hidden');
        currentStepIdToFlag = null;
    }

    async function uploadStepImage(stepId, file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const uploadRes = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            if (!uploadRes.ok) throw new Error('Upload failed');
            const uploadData = await uploadRes.json();
            
            const linkRes = await fetch(`/api/steps/${stepId}/image`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: uploadData.file_path })
            });

            if (linkRes.ok) {
                showToast('Step image added successfully!');
                executeSearch(searchQuery.value, companyFilter.value);
            } else {
                showToast('Failed to link image to step', 'error');
            }
        } catch (err) {
            console.error(err);
            showToast('Error uploading step image', 'error');
        }
    }

    async function uploadTicketImage(ticketId, file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const uploadRes = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            if (!uploadRes.ok) throw new Error('Upload failed');
            const uploadData = await uploadRes.json();
            
            const linkRes = await fetch(`/api/tickets/${ticketId}/image`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: uploadData.file_path })
            });

            if (linkRes.ok) {
                showToast('Ticket image added successfully!');
                executeSearch(searchQuery.value, companyFilter.value);
            } else {
                showToast('Failed to link image to ticket', 'error');
            }
        } catch (err) {
            console.error(err);
            showToast('Error uploading ticket image', 'error');
        }
    }

    async function removeTicketImage(ticketId, filePath) {
        if (!confirm('Are you sure you want to remove this image from the ticket?')) return;
        try {
            const res = await fetch(`/api/tickets/${ticketId}/image`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath })
            });

            if (res.ok) {
                showToast('Ticket image removed successfully!');
                executeSearch(searchQuery.value, companyFilter.value);
            } else {
                showToast('Failed to remove image from ticket', 'error');
            }
        } catch (err) {
            console.error(err);
            showToast('Error removing ticket image', 'error');
        }
    }

    cancelFlagBtn.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', closeModal);

    const searchHero = document.getElementById('searchHero');
    const resultsSection = document.getElementById('resultsSection');

    // Fetch and render tickets
    async function executeSearch(query = '', company = '') {
        const trimmedQuery = query.trim();
        if (!trimmedQuery && !company) {
            // Restore minimalist centered view
            if (searchHero) {
                searchHero.classList.remove('min-h-[20vh]', 'py-4', 'border-b', 'border-slate-200/50');
                searchHero.classList.add('min-h-[65vh]', 'justify-center');
            }
            if (resultsSection) {
                resultsSection.classList.add('hidden', 'opacity-0');
                resultsSection.classList.remove('opacity-100');
            }
            return;
        }

        // Transition to top layout
        if (searchHero) {
            searchHero.classList.remove('min-h-[65vh]', 'justify-center');
            searchHero.classList.add('min-h-[20vh]', 'py-4', 'border-b', 'border-slate-200/50');
        }
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
            setTimeout(() => {
                resultsSection.classList.remove('opacity-0');
                resultsSection.classList.add('opacity-100');
            }, 50);
        }

        try {
            resultsCount.textContent = 'Searching...';
            let url = `/api/search?q=${encodeURIComponent(trimmedQuery)}&company=${encodeURIComponent(company)}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Search failed to complete.');
            }
            const tickets = await response.json();
            renderResults(tickets);
        } catch (error) {
            console.error(error);
            showToast('Failed to retrieve search results.', 'error');
            resultsCount.textContent = 'Error';
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatTicketRefs(text) {
        if (!text) return '';
        let escaped = escapeHtml(text);
        escaped = escaped.replace(/\[([^\]]+)\]\(ticket:\/\/(\d+)\)/gi, (match, label, id) => {
            return `<a href="#" class="ticket-ref text-blue-600 font-semibold hover:underline" data-id="${id}">${label}</a>`;
        });
        escaped = escaped.replace(/(ticket|query)\s+#?(\d+)/gi, (match, type, id) => {
            return `<a href="#" class="ticket-ref text-blue-600 font-semibold hover:underline" data-id="${id}">${match}</a>`;
        });
        return escaped;
    }

    function cleanInstructions(instructions, command) {
        if (!command) return instructions;
        
        const normInstr = instructions.replace(/\r\n/g, '\n').trim();
        const normCmd = command.replace(/\r\n/g, '\n').trim();
        
        const wrapPatterns = [
            `**${normCmd}**`,
            `**\n${normCmd}\n**`,
            `**\n${normCmd}**`,
            `**${normCmd}\n**`,
            `\`${normCmd}\``,
            `\`\n${normCmd}\n\``,
            `\`\n${normCmd}\``,
            `\`${normCmd}\n\``
        ];
        
        for (const pattern of wrapPatterns) {
            if (normInstr.includes(pattern)) {
                return normInstr.replace(pattern, '').trim();
            }
        }
        
        const escapedCmd = normCmd.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regexDoubleAsterisk = new RegExp('\\*\\*\\s*' + escapedCmd + '\\s*\\*\\*', 'i');
        if (regexDoubleAsterisk.test(normInstr)) {
            return normInstr.replace(regexDoubleAsterisk, '').trim();
        }
        
        const regexBacktick = new RegExp('`\\s*' + escapedCmd + '\\s*`', 'i');
        if (regexBacktick.test(normInstr)) {
            return normInstr.replace(regexBacktick, '').trim();
        }
        
        if (normInstr === normCmd || normInstr === '$ ' + normCmd || normInstr === '$' + normCmd) {
            return '';
        }
        
        return instructions;
    }

    function renderResults(tickets) {
        const query = searchQuery.value.trim();
        const company = companyFilter.value;

        // If company filter is selected:
        // - If there is a search query, allow matching company tickets OR general guides.
        // - If there is no search query, strictly show only company tickets.
        const filteredTickets = company
            ? tickets.filter(t => t.client === company || (query && t.type === 'guide'))
            : tickets;

        resultsCount.textContent = `${filteredTickets.length} ticket${filteredTickets.length === 1 ? '' : 's'} found`;
        searchResults.innerHTML = '';

        if (filteredTickets.length === 0) {
            searchResults.innerHTML = `
                <div class="text-center py-12 border border-dashed border-slate-200 rounded-xl bg-white text-slate-500">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 mx-auto text-slate-455 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p class="text-sm">No tickets found matching your query.</p>
                </div>
            `;
            return;
        }

        filteredTickets.forEach(ticket => {
            const hasBrokenStep = ticket.steps && ticket.steps.some(step => step.is_broken);
            const card = document.createElement('div');
            if (hasBrokenStep) {
                card.className = 'bg-rose-50/20 border border-rose-200 rounded-xl p-6 shadow-sm transition duration-150 space-y-4 w-full min-w-0 overflow-hidden';
            } else {
                card.className = 'bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md transition duration-150 space-y-4 w-full min-w-0 overflow-hidden';
            }
            
            // Client pill markup
            const clientPill = ticket.client 
                ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-205">${ticket.client}</span>`
                : '';

            // Broken steps indicator label
            const brokenWarning = hasBrokenStep
                ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-600 border border-rose-100">⚠️ CONTAINS FLAG PROCEDURES</span>`
                : '';

            // Ticket images markup
            let ticketImagesHtml = '';
            if (ticket.images && ticket.images.length > 0) {
                ticketImagesHtml = `
                    <div class="mt-3 flex flex-wrap gap-3">
                        ${ticket.images.map(img => `
                            <div class="relative group/img w-20 h-20">
                                <img src="${img}" class="w-20 h-20 object-cover border border-slate-200 rounded cursor-pointer hover:opacity-80 transition-opacity search-thumbnail" />
                                <button 
                                    class="remove-ticket-image-btn absolute -top-1.5 -right-1.5 bg-rose-500 hover:bg-rose-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shadow-md opacity-0 group-hover/img:opacity-100 transition-opacity focus:outline-none"
                                    data-ticket-id="${ticket.id}"
                                    data-img-src="${img}"
                                    title="Remove image from ticket"
                                >
                                    &times;
                                </button>
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            // Steps list items
            let stepsHtml = '';
            if (ticket.steps && ticket.steps.length > 0) {
                stepsHtml = `
                    <div class="space-y-2 w-full min-w-0">
                        <h4 class="text-xs font-semibold text-slate-500 tracking-wider uppercase">Troubleshooting Steps</h4>
                        <ol class="list-decimal list-inside space-y-3.5 text-sm text-slate-700 pl-1 w-full min-w-0">
                            ${ticket.steps.map(step => {
                                let stepImagesHtml = '';
                                if (step.images && step.images.length > 0) {
                                    stepImagesHtml = `
                                        <div class="mt-1 flex flex-wrap gap-2 pl-6">
                                            ${step.images.map(img => `<img src="${img}" class="w-16 h-16 object-cover border border-slate-200 rounded cursor-pointer hover:opacity-80 transition-opacity search-thumbnail" />`).join('')}
                                        </div>
                                    `;
                                }
                                
                                let stepCommandHtml = '';
                                if (step.command) {
                                    stepCommandHtml = `
                                        <div class="mt-2 pl-6 flex items-start space-x-2 w-full min-w-0">
                                            <div class="flex-1 min-w-0 font-mono text-xs bg-slate-900 text-slate-100 px-3 py-2 rounded flex items-start justify-between shadow-inner overflow-hidden">
                                                <pre class="whitespace-pre-wrap break-all select-all flex-1 min-w-0 pr-2 font-mono">$ ${escapeHtml(step.command)}</pre>
                                                <button 
                                                    class="copy-cmd-btn ml-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 hover:text-white border border-slate-700 rounded px-2 py-1 text-[10px] transition duration-150 flex-shrink-0"
                                                    data-cmd="${escapeHtml(step.command)}"
                                                >
                                                    Copy
                                                </button>
                                            </div>
                                        </div>
                                    `;
                                }

                                const cleanedInstr = formatTicketRefs(cleanInstructions(step.instructions, step.command));

                                if (step.is_broken) {
                                    return `
                                        <li class="border border-rose-200/50 bg-rose-50/50 rounded-lg p-2.5 text-rose-800 w-full min-w-0 overflow-hidden">
                                            <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-1.5 w-full min-w-0">
                                                <span class="whitespace-pre-wrap break-words flex-1 min-w-0">${cleanedInstr || "Run command:"}</span>
                                                <span class="inline-flex items-center self-start text-[11px] font-medium bg-rose-100 text-rose-700 border border-rose-200/60 px-2 py-0.5 rounded flex-shrink-0">
                                                    ⚠️ Flagged: ${step.breakage_notes || 'Outdated'}
                                                 </span>
                                            </div>
                                            ${stepImagesHtml}
                                            ${stepCommandHtml}
                                        </li>
                                    `;
                                } else {
                                    return `
                                        <li class="group/step py-1 flex flex-col gap-2 w-full min-w-0 overflow-hidden">
                                            <div class="flex items-start justify-between gap-4 w-full min-w-0">
                                                <span class="leading-relaxed flex-1 whitespace-pre-wrap break-words min-w-0">${cleanedInstr || "Run command:"}</span>
                                                <div class="flex items-center space-x-3 flex-shrink-0">
                                                    <label class="cursor-pointer inline-flex items-center space-x-1 text-xs text-slate-400 hover:text-blue-600 transition duration-150" title="Attach image to step">
                                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                        </svg>
                                                        <span>Attach</span>
                                                        <input type="file" class="hidden step-image-input" data-step-id="${step.id}" accept="image/*" />
                                                    </label>
                                                    <button 
                                                        data-step-id="${step.id}"
                                                        class="flag-btn inline-flex items-center space-x-1 text-xs text-slate-400 hover:text-rose-600 transition duration-150"
                                                        title="Flag this step as broken"
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                                                        </svg>
                                                        <span>Flag</span>
                                                    </button>
                                                </div>
                                            </div>
                                            ${stepImagesHtml}
                                            ${stepCommandHtml}
                                        </li>
                                    `;
                                }
                            }).join('')}
                        </ol>
                    </div>
                `;
            } else {
                stepsHtml = `<p class="text-xs text-slate-400 italic">No troubleshooting steps recorded for this ticket.</p>`;
            }

            // Checklist markup
            let checklistHtml = '';
            if (ticket.checklist && ticket.checklist.length > 0) {
                checklistHtml = `
                    <div class="mt-4 pt-3 border-t border-slate-100 space-y-2">
                        <h4 class="text-xs font-semibold text-slate-500 tracking-wider uppercase">Verification Checklist</h4>
                        <ul class="space-y-1.5 text-sm text-slate-700">
                            ${ticket.checklist.map((item, idx) => `
                                <li class="flex items-center space-x-2">
                                    <input type="checkbox" id="chk-${ticket.id}-${idx}" class="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer">
                                    <label for="chk-${ticket.id}-${idx}" class="cursor-pointer select-none">${escapeHtml(item)}</label>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                `;
            }

            let typeBadge = '';
            if (ticket.type === 'guide') {
                typeBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">Guide</span>`;
            } else if (ticket.type === 'dailychecklist' || ticket.type === 'daily_checklist') {
                typeBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">Daily Checklist</span>`;
            }

            card.innerHTML = `
                <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 w-full min-w-0">
                    <h3 class="text-base font-bold text-slate-900 flex-1 min-w-0 truncate">${ticket.title}</h3>
                    <div class="flex items-center space-x-2 flex-shrink-0">
                        ${brokenWarning}
                        ${typeBadge}
                        ${clientPill}
                        <label class="cursor-pointer inline-flex items-center space-x-1 text-xs text-slate-500 hover:text-blue-600 border border-slate-205 px-2 py-0.5 rounded transition duration-150" title="Attach image to ticket">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <span>Attach Image</span>
                            <input type="file" class="hidden ticket-image-input" data-ticket-id="${ticket.id}" accept="image/*" />
                        </label>
                        <button 
                            data-ticket-id="${ticket.id}" 
                            class="edit-ticket-btn text-xs text-blue-550 hover:text-blue-750 hover:bg-blue-50 border border-transparent hover:border-blue-200 px-2 py-0.5 rounded transition duration-150 mr-1"
                            title="Edit this ticket"
                        >
                            Edit
                        </button>
                        <button 
                            data-ticket-id="${ticket.id}" 
                            class="delete-ticket-btn text-xs text-rose-500 hover:text-rose-700 hover:bg-rose-50 border border-transparent hover:border-rose-250 px-2 py-0.5 rounded transition duration-150"
                            title="Delete this ticket"
                        >
                            Delete
                        </button>
                    </div>
                </div>
                ${ticket.symptom ? `
                    <div class="bg-slate-50 border border-slate-100 px-4 py-2.5 rounded-lg text-sm text-slate-700 w-full min-w-0 overflow-hidden">
                        <span class="block text-[10px] font-bold text-slate-400 tracking-wider uppercase mb-1">${ticket.type === 'guide' ? 'Description / Objective' : 'Symptom'}</span>
                        <p class="italic leading-relaxed break-words whitespace-pre-wrap">"${formatTicketRefs(ticket.symptom)}"</p>
                    </div>
                ` : ''}
                ${ticketImagesHtml}
                ${stepsHtml}
                ${checklistHtml}
            `;

            searchResults.appendChild(card);
        });

        // Attach event listeners to all flag buttons
        const flagButtons = searchResults.querySelectorAll('.flag-btn');
        flagButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const stepId = btn.getAttribute('data-step-id');
                if (stepId) {
                    openModal(parseInt(stepId, 10));
                }
            });
        });

        // Attach event listeners to step image inputs
        const stepImageInputs = searchResults.querySelectorAll('.step-image-input');
        stepImageInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                const file = e.target.files[0];
                const stepId = input.getAttribute('data-step-id');
                if (file && stepId) {
                    uploadStepImage(stepId, file);
                }
            });
        });

        // Attach event listeners to ticket image inputs
        const ticketImageInputs = searchResults.querySelectorAll('.ticket-image-input');
        ticketImageInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                const file = e.target.files[0];
                const ticketId = input.getAttribute('data-ticket-id');
                if (file && ticketId) {
                    uploadTicketImage(ticketId, file);
                }
            });
        });

        // Attach event listeners to remove ticket image buttons
        const removeImageButtons = searchResults.querySelectorAll('.remove-ticket-image-btn');
        removeImageButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const ticketId = btn.getAttribute('data-ticket-id');
                const imgSrc = btn.getAttribute('data-img-src');
                if (ticketId && imgSrc) {
                    removeTicketImage(parseInt(ticketId, 10), imgSrc);
                }
            });
        });

        // Attach click listeners to all search thumbnails for the lightbox modal
        const thumbnails = searchResults.querySelectorAll('.search-thumbnail');
        thumbnails.forEach(thumb => {
            thumb.addEventListener('click', () => {
                openLightbox(thumb.src);
            });
        });

        // Attach event listeners to edit ticket buttons
        const editButtons = searchResults.querySelectorAll('.edit-ticket-btn');
        editButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const ticketId = parseInt(btn.getAttribute('data-ticket-id'), 10);
                const ticket = tickets.find(t => t.id === ticketId);
                if (ticket) {
                    openEditModal(ticket);
                }
            });
        });

        // Attach event listeners to delete ticket buttons
        const deleteButtons = searchResults.querySelectorAll('.delete-ticket-btn');
        deleteButtons.forEach(btn => {
            btn.addEventListener('click', async () => {
                const ticketId = btn.getAttribute('data-ticket-id');
                if (ticketId && confirm('Are you sure you want to delete this ticket? This will remove all its mappings and cannot be undone.')) {
                    try {
                        const res = await fetch(`/api/tickets/${ticketId}`, { method: 'DELETE' });
                        if (res.ok) {
                            showToast('Ticket deleted successfully.');
                            await loadCompanies();
                            executeSearch(searchQuery.value, companyFilter.value);
                        } else {
                            showToast('Failed to delete ticket.', 'error');
                        }
                    } catch (err) {
                        console.error(err);
                        showToast('Network error while deleting ticket.', 'error');
                    }
                }
            });
        });

        // Attach event listeners to copy command buttons
        const copyButtons = searchResults.querySelectorAll('.copy-cmd-btn');
        copyButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const cmd = btn.getAttribute('data-cmd');
                if (cmd) {
                    navigator.clipboard.writeText(cmd).then(() => {
                        showToast('Command copied to clipboard!');
                    }).catch(err => {
                        console.error('Failed to copy command:', err);
                        showToast('Failed to copy command.', 'error');
                    });
                }
            });
        });
    }

    // Debounced keystroke search
    const performDebouncedSearch = debounce(() => {
        executeSearch(searchQuery.value, companyFilter.value);
    }, 200);

    searchQuery.addEventListener('input', performDebouncedSearch);

    // Filter change listener
    companyFilter.addEventListener('change', () => {
        executeSearch(searchQuery.value, companyFilter.value);
    });

    // Form search submission
    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        executeSearch(searchQuery.value, companyFilter.value);
    });

    // Modal submit flag execution
    submitFlagBtn.addEventListener('click', async () => {
        const reason = flagReason.value.trim();
        if (!reason) {
            showToast('Please provide a reason for flagging this step.', 'error');
            return;
        }

        if (!currentStepIdToFlag) {
            showToast('No active step selected for flagging.', 'error');
            closeModal();
            return;
        }

        try {
            submitFlagBtn.disabled = true;
            submitFlagBtn.textContent = 'Flagging...';

            const response = await fetch(`/api/steps/flag/${currentStepIdToFlag}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason })
            });

            if (!response.ok) {
                throw new Error('Flagging API request failed.');
            }

            showToast('Step successfully flagged as broken.');
            closeModal();
            
            // Reload search with the active query and company
            executeSearch(searchQuery.value, companyFilter.value);
        } catch (error) {
            console.error(error);
            showToast('Failed to flag step.', 'error');
        } finally {
            submitFlagBtn.disabled = false;
            submitFlagBtn.textContent = 'Flag Step';
        }
    });

    // Edit Ticket Modal Elements
    const editTicketModal = document.getElementById('editTicketModal');
    const editModalBackdrop = document.getElementById('editModalBackdrop');
    const cancelEditBtn = document.getElementById('cancelEditBtn');
    const saveEditBtn = document.getElementById('saveEditBtn');

    const editTicketId = document.getElementById('editTicketId');
    const editTicketTitle = document.getElementById('editTicketTitle');
    const editTicketClient = document.getElementById('editTicketClient');
    const editTicketType = document.getElementById('editTicketType');
    const editTicketSymptom = document.getElementById('editTicketSymptom');
    const editTicketSteps = document.getElementById('editTicketSteps');
    const editTicketChecklist = document.getElementById('editTicketChecklist');

    function openEditModal(ticket) {
        if (!editTicketModal) return;
        editTicketId.value = ticket.id;
        editTicketTitle.value = ticket.title || '';
        editTicketClient.value = ticket.client || '';
        editTicketType.value = ticket.type || 'ticket';
        editTicketSymptom.value = ticket.symptom || '';
        
        // Format steps as a markdown list
        const stepsText = ticket.steps 
            ? ticket.steps.map(s => `- ${s.instructions}`).join('\n') 
            : '';
        editTicketSteps.value = stepsText;

        // Format checklist as a markdown list
        const checklistText = ticket.checklist 
            ? ticket.checklist.map(c => `- ${c}`).join('\n') 
            : '';
        editTicketChecklist.value = checklistText;

        editTicketModal.classList.remove('hidden');
    }

    function closeEditModal() {
        if (editTicketModal) {
            editTicketModal.classList.add('hidden');
        }
    }

    if (cancelEditBtn) cancelEditBtn.addEventListener('click', closeEditModal);
    if (editModalBackdrop) editModalBackdrop.addEventListener('click', closeEditModal);

    if (saveEditBtn) {
        saveEditBtn.addEventListener('click', async () => {
            const ticketId = editTicketId.value;
            const title = editTicketTitle.value.trim();
            const client = editTicketClient.value.trim();
            const type = editTicketType.value;
            const symptom = editTicketSymptom.value.trim();

            if (!title) {
                showToast('Title is required.', 'error');
                return;
            }

            // Parse steps text back into string array (trimming lists)
            const steps = editTicketSteps.value.split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0)
                .map(line => line.replace(/^([-*+]|\d+\.)\s*/, '').trim())
                .filter(line => line.length > 0);

            // Parse checklist text back into string array
            const checklist = editTicketChecklist.value.split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0)
                .map(line => line.replace(/^([-*+]?\s*\[[ xX]\]|[-*+?])\s*/, '').trim())
                .filter(line => line.length > 0);

            try {
                saveEditBtn.disabled = true;
                saveEditBtn.textContent = 'Saving...';

                const response = await fetch(`/api/tickets/${ticketId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        title,
                        client,
                        type,
                        symptom,
                        steps,
                        checklist
                    })
                });

                if (!response.ok) {
                    throw new Error('Update failed');
                }

                showToast('Ticket updated successfully!');
                closeEditModal();
                await loadCompanies();
                executeSearch(searchQuery.value, companyFilter.value);
            } catch (err) {
                console.error(err);
                showToast('Failed to update ticket.', 'error');
            } finally {
                saveEditBtn.disabled = false;
                saveEditBtn.textContent = 'Save Changes';
            }
        });
    }

    // Intercept clicks on ticket/query references
    document.addEventListener('click', (e) => {
        const ref = e.target.closest('.ticket-ref');
        if (ref) {
            e.preventDefault();
            const ticketId = ref.getAttribute('data-id');
            searchQuery.value = ticketId;
            executeSearch(ticketId, companyFilter.value);
        }
    });

    // Initial load
    loadCompanies().then(() => {
        executeSearch();
    });
});
