document.addEventListener('DOMContentLoaded', () => {
    const maintenanceQueue = document.getElementById('maintenanceQueue');
    const statusText = document.getElementById('statusText');
    const statusIndicator = document.getElementById('statusIndicator');

    // Lightbox modal elements
    const lightboxModal = document.getElementById('lightboxModal');
    const lightboxImage = document.getElementById('lightboxImage');
    const closeLightboxBtn = document.getElementById('closeLightboxBtn');

    // Scroll Queue button & container handling
    const scrollQueueBtn = document.getElementById('scrollQueueBtn');
    const mainElement = document.querySelector('main');
    const scrollQueueIcon = document.getElementById('scrollQueueIcon');

    if (scrollQueueBtn && mainElement) {
        scrollQueueBtn.addEventListener('click', () => {
            const isAtBottom = mainElement.scrollHeight - mainElement.scrollTop <= mainElement.clientHeight + 50;
            if (isAtBottom) {
                mainElement.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                mainElement.scrollTo({ top: mainElement.scrollHeight, behavior: 'smooth' });
            }
        });

        mainElement.addEventListener('scroll', () => {
            const isAtBottom = mainElement.scrollHeight - mainElement.scrollTop <= mainElement.clientHeight + 50;
            const btnText = scrollQueueBtn.querySelector('span');
            if (isAtBottom) {
                if (btnText) btnText.textContent = 'Scroll Top';
                if (scrollQueueIcon) scrollQueueIcon.style.transform = 'rotate(180deg)';
            } else {
                if (btnText) btnText.textContent = 'Scroll Down';
                if (scrollQueueIcon) scrollQueueIcon.style.transform = 'rotate(0deg)';
            }
        });
    }

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
                await fetchQueue();
            } else {
                showToast('Failed to link image to step', 'error');
            }
        } catch (err) {
            console.error(err);
            showToast('Error uploading step image', 'error');
        }
    }

    // Fetch maintenance queue
    async function fetchQueue() {
        try {
            const response = await fetch('/api/maintenance/queue');
            if (!response.ok) {
                throw new Error('Failed to load queue.');
            }
            const data = await response.json();
            renderQueue(data);
        } catch (error) {
            console.error(error);
            showToast('Failed to fetch the maintenance queue.', 'error');
            statusText.textContent = 'Error loading queue';
            statusIndicator.className = 'relative inline-flex rounded-full h-2 w-2 bg-rose-500';
        }
    }

    // Render queue items
    function renderQueue(items) {
        maintenanceQueue.innerHTML = '';

        if (scrollQueueBtn) {
            if (items.length > 0) {
                scrollQueueBtn.classList.remove('hidden');
            } else {
                scrollQueueBtn.classList.add('hidden');
            }
        }

        if (items.length === 0) {
            // Status bar update
            statusText.textContent = 'System Healthy';
            statusIndicator.className = 'relative inline-flex rounded-full h-2 w-2 bg-emerald-500';

            // Operational empty state
            maintenanceQueue.innerHTML = `
                <div class="text-center py-12 border border-dashed border-slate-200 rounded-xl bg-white text-slate-400 space-y-3 shadow-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 mx-auto text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <p class="text-sm font-semibold text-slate-700">No broken steps in queue. Procedures are operational.</p>
                    <p class="text-xs text-slate-400">Flag steps inside Fast Search to populate this maintenance list.</p>
                </div>
            `;
            return;
        }

        // Update status bar with issue count
        statusText.textContent = `${items.length} issue${items.length === 1 ? '' : 's'} pending`;
        statusIndicator.className = 'relative inline-flex rounded-full h-2 w-2 bg-amber-500';

        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'bg-white border border-slate-200 hover:border-slate-350 rounded-xl p-5 transition duration-150 space-y-4 shadow-sm w-full overflow-hidden min-w-0';

            let imagesHtml = '';
            if (item.images && item.images.length > 0) {
                imagesHtml = `
                    <div class="flex flex-wrap gap-2 mt-2">
                        ${item.images.map(img => `<img src="${img}" class="w-16 h-16 object-cover border border-slate-200 rounded cursor-pointer hover:opacity-85 transition-opacity maintenance-thumbnail" />`).join('')}
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="space-y-3 w-full min-w-0 overflow-hidden">
                    <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 w-full min-w-0">
                        <div class="flex-1 min-w-0">
                            ${item.command ? `
                            <div class="w-full font-mono text-xs bg-slate-900 text-slate-100 px-3.5 py-2.5 rounded-lg shadow-inner overflow-hidden">
                                <pre class="whitespace-pre-wrap select-all font-mono leading-relaxed">$ ${escapeHtml(item.command)}</pre>
                            </div>
                            ` : `
                            <p class="text-sm text-slate-800 font-semibold leading-relaxed break-words">
                                ${escapeHtml(item.instructions)}
                            </p>
                            `}
                        </div>
                        <span class="bg-rose-50 text-rose-700 border border-rose-100 px-2 py-0.5 rounded text-xs font-semibold self-start flex-shrink-0 ml-2">
                            Impacts ${item.impact_count} Ticket${item.impact_count === 1 ? '' : 's'}
                        </span>
                    </div>

                    ${imagesHtml}

                    <div class="bg-slate-50 border border-slate-100 rounded-lg p-3 text-xs text-slate-500 space-y-1 w-full min-w-0">
                        <span class="font-bold text-rose-600">Reported Issue:</span>
                        <p class="mt-0.5 break-words whitespace-pre-wrap">${escapeHtml(item.breakage_notes || 'No description provided.')}</p>
                        <div class="text-[10px] text-slate-400 pt-1 font-mono">Last Flagged/Updated: ${new Date(item.updated_at).toLocaleString()}</div>
                    </div>
                </div>

                <div class="flex flex-col gap-4 pt-2 border-t border-slate-100 w-full min-w-0">
                    <div class="space-y-4 w-full min-w-0">
                        <!-- Editor 1: Instructions -->
                        <div id="instructions-container-${item.id}" class="flex flex-col gap-1 min-w-0 ${item.command ? 'hidden' : ''}">
                            <label class="text-[10px] font-bold text-slate-400 uppercase tracking-wider pl-1 flex items-center justify-between">
                                <span>Human Instructions</span>
                                ${item.command ? `<button type="button" class="hide-instructions-btn text-[9px] text-blue-500 hover:text-blue-700 underline font-normal normal-case" data-step-id="${item.id}">Hide Instructions</button>` : ''}
                            </label>
                            <input 
                                type="text" 
                                value="${escapeAttribute(item.instructions)}" 
                                id="input-${item.id}"
                                placeholder="Edit step globally..."
                                class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition duration-150"
                            >
                            <span class="text-[10px] text-slate-400 pl-1">Human instructions (e.g. Run database query - do not include <code>-</code> bullet here)</span>
                        </div>
                        
                        <!-- Editor 2: Command / SQL Console -->
                        <div id="command-container-${item.id}" class="flex flex-col gap-1 min-w-0 ${!item.command ? 'hidden' : ''}">
                            <label class="text-[10px] font-bold text-slate-400 uppercase tracking-wider pl-1 flex items-center justify-between">
                                <span>Raw Command / SQL Console</span>
                                <div class="flex items-center space-x-2">
                                    ${item.command ? '' : `<button type="button" class="hide-command-btn text-[9px] text-rose-500 hover:text-rose-700 underline font-normal normal-case" data-step-id="${item.id}">Remove Command</button>`}
                                    <span class="text-[9px] text-slate-455 font-normal normal-case">multiline editor</span>
                                </div>
                            </label>
                            <div class="relative w-full min-w-0 rounded-lg overflow-hidden border border-slate-800 bg-slate-950 focus-within:ring-2 focus-within:ring-emerald-500/20 focus-within:border-emerald-500 transition duration-150 shadow-md">
                                <!-- Console header -->
                                <div class="flex items-center justify-between px-3 py-1.5 bg-slate-900 border-b border-slate-800">
                                    <div class="flex items-center space-x-1.5">
                                        <span class="w-2 h-2 rounded-full bg-rose-500/80"></span>
                                        <span class="w-2 h-2 rounded-full bg-amber-500/80"></span>
                                        <span class="w-2 h-2 rounded-full bg-emerald-500/80"></span>
                                    </div>
                                    <span class="text-[9px] text-slate-500 font-mono">bash / sql</span>
                                </div>
                                <textarea 
                                    id="command-${item.id}"
                                    placeholder="Type terminal command or paste raw SQL query..."
                                    rows="5"
                                    class="w-full bg-slate-950 text-slate-100 px-3 py-2.5 text-xs focus:outline-none font-mono resize-y leading-relaxed placeholder-slate-700 block"
                                >${escapeHtml(item.command || '')}</textarea>
                            </div>
                            <span class="text-[10px] text-slate-400 pl-1">Raw terminal command or SQL query (do not wrap in backticks or start with <code>-</code>)</span>
                        </div>

                        <!-- Add/Customize toggles -->
                        <div class="flex items-center space-x-3 text-xs pl-1">
                            ${item.command ? `
                            <button type="button" id="toggle-instructions-btn-${item.id}" class="text-blue-500 hover:text-blue-700 underline font-medium">
                                ${item.instructions.startsWith('`') && item.instructions.endsWith('`') && item.instructions.slice(1, -1).trim() === (item.command || '').trim() ? 'Customize Instruction Text' : 'Edit Instruction Text'}
                            </button>
                            ` : `
                            <button type="button" id="toggle-command-btn-${item.id}" class="text-emerald-600 hover:text-emerald-700 underline font-medium">
                                Add Command / SQL Query
                            </button>
                            `}
                        </div>
                    </div>
                    
                    <div class="flex flex-wrap gap-2 justify-end pt-2 border-t border-slate-100">
                        <label class="cursor-pointer inline-flex items-center justify-center px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-sm font-medium transition duration-150">
                            Add Image
                            <input type="file" class="hidden maintenance-image-input" data-step-id="${item.id}" accept="image/*" />
                        </label>
                        <button 
                            data-step-id="${item.id}"
                            class="update-btn px-4 py-2 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-lg text-sm font-medium transition duration-150 shadow-md shadow-blue-500/10"
                        >
                            Global Update
                        </button>
                        <button 
                            data-step-id="${item.id}"
                            class="delete-btn px-4 py-2 border border-rose-200 hover:bg-rose-50 text-rose-600 rounded-lg text-sm font-medium transition duration-150"
                        >
                            Global Delete Step
                        </button>
                    </div>
                </div>
            `;

            // Attach event listeners to buttons
            card.querySelector('.update-btn').addEventListener('click', (e) => handleUpdate(e.target.dataset.stepId));
            card.querySelector('.delete-btn').addEventListener('click', (e) => handleDelete(e.target.dataset.stepId));

            // Setup references to toggles and containers
            const textInput = card.querySelector(`#input-${item.id}`);
            const cmdInput = card.querySelector(`#command-${item.id}`);
            const instructionsContainer = card.querySelector(`#instructions-container-${item.id}`);
            const commandContainer = card.querySelector(`#command-container-${item.id}`);
            const toggleInstructionsBtn = card.querySelector(`#toggle-instructions-btn-${item.id}`);
            const toggleCommandBtn = card.querySelector(`#toggle-command-btn-${item.id}`);

            // Toggle show instructions
            if (toggleInstructionsBtn) {
                toggleInstructionsBtn.addEventListener('click', () => {
                    instructionsContainer.classList.remove('hidden');
                    toggleInstructionsBtn.classList.add('hidden');
                });
            }

            // Toggle show command
            if (toggleCommandBtn) {
                toggleCommandBtn.addEventListener('click', () => {
                    commandContainer.classList.remove('hidden');
                    toggleCommandBtn.classList.add('hidden');
                    // auto fill command if instructions has backticks
                    const val = textInput.value.trim();
                    let match = val.match(/`([^`]+)`/);
                    if (match) {
                        cmdInput.value = match[1].trim();
                    }
                });
            }

            // Hide instruction button inside instructions label
            const hideInstructionsBtn = card.querySelector('.hide-instructions-btn');
            if (hideInstructionsBtn) {
                hideInstructionsBtn.addEventListener('click', () => {
                    instructionsContainer.classList.add('hidden');
                    if (toggleInstructionsBtn) toggleInstructionsBtn.classList.remove('hidden');
                });
            }

            // Remove/hide command button
            const hideCommandBtn = card.querySelector('.hide-command-btn');
            if (hideCommandBtn) {
                hideCommandBtn.addEventListener('click', () => {
                    commandContainer.classList.add('hidden');
                    cmdInput.value = '';
                    if (toggleCommandBtn) toggleCommandBtn.classList.remove('hidden');
                });
            }

            // Sync inputs and keep in track
            if (textInput && cmdInput) {
                // Sync instructions -> command if instructions edited
                textInput.addEventListener('input', () => {
                    const val = textInput.value.trim();
                    let match = val.match(/`([^`]+)`/);
                    if (match) {
                        cmdInput.value = match[1].trim();
                        return;
                    }
                    match = val.match(/\*\*([^*]+)\*\*/);
                    if (match) {
                        cmdInput.value = match[1].trim();
                        return;
                    }
                    match = val.match(/(?:^|\s)(?:\$|#|Run:)\s*([a-zA-Z0-9_\-\.\/]+(?:\s+[^\n]+)?)/i);
                    if (match) {
                        cmdInput.value = match[1].trim();
                        return;
                    }
                });

                // Sync command -> instructions (wrap in backticks) if command edited
                cmdInput.addEventListener('input', () => {
                    const cmdVal = cmdInput.value.trim();
                    const textVal = textInput.value.trim();
                    
                    // If instructions is empty, or is already a wrapped version of command (meaning not customized)
                    const isDefaultInstructions = !textVal || (textVal.startsWith('`') && textVal.endsWith('`')) || textVal === '`' + cmdVal + '`';
                    if (isDefaultInstructions) {
                        textInput.value = cmdVal ? '`' + cmdVal + '`' : '';
                    }
                });
            }

            // Attach step image upload listeners
            const imageInput = card.querySelector('.maintenance-image-input');
            imageInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                const stepId = imageInput.getAttribute('data-step-id');
                if (file && stepId) {
                    uploadStepImage(stepId, file);
                }
            });

            // Attach click listeners to thumbnails for the lightbox modal
            const thumbnails = card.querySelectorAll('.maintenance-thumbnail');
            thumbnails.forEach(thumb => {
                thumb.addEventListener('click', () => {
                    openLightbox(thumb.src);
                });
            });

            maintenanceQueue.appendChild(card);
        });
    }

    // Helper to escape HTML characters
    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeAttribute(str) {
        if (!str) return '';
        return escapeHtml(str).replace(/\r?\n/g, "&#10;");
    }

    // Handle Global Update logic
    async function handleUpdate(stepId) {
        const inputField = document.getElementById(`input-${stepId}`);
        const commandField = document.getElementById(`command-${stepId}`);
        const updatedText = inputField.value.trim();
        const updatedCommand = commandField ? commandField.value.trim() : '';

        if (!updatedText) {
            showToast('Step text cannot be empty.', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/maintenance/resolve/${stepId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: 'update',
                    text: updatedText,
                    command: updatedCommand
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to update step.');
            }

            showToast('Step updated globally and cleared from queue.');
            await fetchQueue();
        } catch (error) {
            console.error(error);
            showToast(error.message || 'Error occurred during update.', 'error');
        }
    }

    // Handle Global Delete logic
    async function handleDelete(stepId) {
        const confirmed = await window.showConfirm(
            "Delete Step Globally",
            "Are you sure you want to delete this step globally? This will remove the step from all linked tickets and re-sequence remaining steps."
        );
        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch(`/api/maintenance/resolve/${stepId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: 'delete'
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to delete step.');
            }

            showToast('Step deleted globally and cascade reordered.');
            await fetchQueue();
        } catch (error) {
            console.error(error);
            showToast(error.message || 'Error occurred during delete.', 'error');
        }
    }

    // Initial load
    fetchQueue();
});
