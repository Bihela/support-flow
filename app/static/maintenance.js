document.addEventListener('DOMContentLoaded', () => {
    const maintenanceQueue = document.getElementById('maintenanceQueue');
    const toastContainer = document.getElementById('toastContainer');
    const statusText = document.getElementById('statusText');
    const statusIndicator = document.getElementById('statusIndicator');

    // Toast utility
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `px-4 py-3 rounded-lg text-sm font-medium shadow-xl border transition-all duration-300 transform translate-y-2 opacity-0 flex items-center space-x-2`;
        
        if (type === 'success') {
            toast.className += ' bg-white border-emerald-250 text-emerald-700 shadow-emerald-50';
            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>${message}</span>
            `;
        } else {
            toast.className += ' bg-white border-rose-250 text-rose-700 shadow-rose-50';
            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>${message}</span>
            `;
        }
        
        toastContainer.appendChild(toast);
        
        // Trigger reflow
        setTimeout(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
        }, 10);

        // Remove toast
        setTimeout(() => {
            toast.classList.add('translate-y-2', 'opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

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
                <div class="space-y-2 w-full min-w-0 overflow-hidden">
                    <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 w-full min-w-0">
                        <div class="flex-1 min-w-0">
                            ${item.command ? `
                            <div class="w-full font-mono text-xs bg-slate-900 text-slate-100 px-3 py-2 rounded shadow-inner overflow-x-auto">
                                <pre class="whitespace-pre select-all font-mono">$ ${escapeHtml(item.command)}</pre>
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

                <div class="flex flex-col gap-3 pt-1 w-full min-w-0">
                    <div class="flex flex-col sm:flex-row gap-3 w-full min-w-0">
                        <input 
                            type="text" 
                            value="${escapeHtml(item.instructions)}" 
                            id="input-${item.id}"
                            placeholder="Edit step globally..."
                            class="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition duration-150"
                        >
                        <input 
                            type="text" 
                            value="${escapeHtml(item.command || '')}" 
                            id="command-${item.id}"
                            placeholder="Add/edit terminal command..."
                            class="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition duration-150 font-mono"
                        >
                    </div>
                    <div class="flex flex-wrap gap-2 justify-end">
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
        if (!confirm('Are you sure you want to delete this step globally? This will remove the step from all linked tickets and re-sequence remaining steps.')) {
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
