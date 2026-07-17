document.addEventListener("DOMContentLoaded", () => {
    let currentDraftId = null;
    let selectedLiveTicketId = null;
    let drafts = [];

    const draftList = document.getElementById("draftList");
    const draftCount = document.getElementById("draftCount");
    const workArea = document.getElementById("workArea");
    const emptyState = document.getElementById("emptyState");
    const workspace = document.getElementById("workspace");

    // Inputs/controls in editor
    const editTitle = document.getElementById("editTitle");
    const editClient = document.getElementById("editClient");
    const editType = document.getElementById("editType");
    const editSymptom = document.getElementById("editSymptom");
    const editSteps = document.getElementById("editSteps");
    const editChecklist = document.getElementById("editChecklist");
    const saveDraftBtn = document.getElementById("saveDraftBtn");
    const draftImageUpload = document.getElementById("draftImageUpload");
    const editImagesList = document.getElementById("editImagesList");
    let currentDraftImages = [];

    // Collision components
    const matchStatus = document.getElementById("matchStatus");
    const collisionContainer = document.getElementById("collisionContainer");

    // Actions
    const discardBtn = document.getElementById("discardBtn");
    const mergeBtn = document.getElementById("mergeBtn");
    const approveBtn = document.getElementById("approveBtn");


    function renderDraftImages() {
        editImagesList.innerHTML = "";
        currentDraftImages.forEach((img, idx) => {
            const wrapper = document.createElement("div");
            wrapper.className = "relative inline-block w-16 h-16 border border-slate-200 rounded overflow-hidden group";
            wrapper.innerHTML = `
                <img src="${img}" class="w-full h-full object-cover" />
                <button type="button" class="absolute top-0 right-0 bg-red-600 text-white rounded-full w-4 h-4 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity" data-index="${idx}">
                    &times;
                </button>
            `;
            wrapper.querySelector("button").addEventListener("click", () => {
                currentDraftImages.splice(idx, 1);
                renderDraftImages();
            });
            editImagesList.appendChild(wrapper);
        });
    }

    if (draftImageUpload) {
        draftImageUpload.addEventListener("change", async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append("file", file);

            try {
                const response = await fetch("/api/upload", {
                    method: "POST",
                    body: formData
                });
                if (response.ok) {
                    const data = await response.json();
                    currentDraftImages.push(data.file_path);
                    renderDraftImages();
                } else {
                    showToast("Failed to upload image", "error");
                }
            } catch (err) {
                console.error(err);
                showToast("Network error uploading image", "error");
            } finally {
                draftImageUpload.value = "";
            }
        });
    }



    async function loadDrafts() {
        try {
            const res = await fetch("/api/staging/drafts");
            drafts = await res.json();
            draftCount.textContent = drafts.length;
            renderSidebar();
        } catch (err) {
            showToast("Failed to load staging drafts", "error");
            console.error(err);
        }
    }

    function renderSidebar() {
        if (drafts.length === 0) {
            draftList.innerHTML = `<div class="text-xs text-slate-400 text-center py-8">No pending drafts found.</div>`;
            return;
        }

        draftList.innerHTML = drafts.map(d => {
            const isCurrent = d.id === currentDraftId;
            return `
                <div data-id="${d.id}" class="p-3 rounded-lg cursor-pointer transition duration-150 border ${
                    isCurrent 
                        ? "bg-blue-50 border-blue-200 text-slate-900" 
                        : "bg-white border-slate-150 hover:bg-slate-50 text-slate-650 hover:text-slate-900 shadow-sm"
                }">
                    <div class="flex items-center justify-between space-x-2">
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200 max-w-[120px] truncate">
                            ${d.parsed_client || "No Client"}
                        </span>
                        <span class="text-[10px] text-slate-400 font-mono">ID: ${d.id}</span>
                    </div>
                    <h4 class="text-sm font-bold text-slate-800 mt-1 truncate">${d.parsed_title || "Untitled"}</h4>
                    <p class="text-xs text-slate-400 line-clamp-1 mt-1">${d.parsed_symptom || "No symptom details..."}</p>
                </div>
            `;
        }).join("");

        // Attach click listeners to sidebar cards
        draftList.querySelectorAll("[data-id]").forEach(card => {
            card.addEventListener("click", () => {
                const id = parseInt(card.getAttribute("data-id"));
                selectDraft(id);
            });
        });
    }

    async function selectDraft(draftId) {
        currentDraftId = draftId;
        selectedLiveTicketId = null; // reset selected collision target
        
        // Disable merge button initially
        mergeBtn.disabled = true;
        mergeBtn.className = "px-4 py-2 bg-blue-105 text-blue-600 border border-blue-200 rounded text-sm font-medium transition duration-150 cursor-not-allowed opacity-50";

        // Refresh sidebar view to reflect selection border
        renderSidebar();

        try {
            const res = await fetch(`/api/staging/compare/${draftId}`);
            if (!res.ok) throw new Error("Could not fetch compare data");
            const data = await res.json();
            
            // Show Workspace, Hide Empty State
            emptyState.classList.add("hidden");
            workspace.classList.remove("hidden");

            // Fill editor
            editTitle.value = data.draft.parsed_title || "";
            editClient.value = data.draft.parsed_client || "";
            editType.value = data.draft.type || "ticket";
            editSymptom.value = data.draft.parsed_symptom || "";
            if (data.draft.type === "query") {
                editSteps.value = data.draft.parsed_steps ? data.draft.parsed_steps.join("\n") : "";
            } else {
                editSteps.value = data.draft.parsed_steps ? data.draft.parsed_steps.map(s => `- ${s}`).join("\n") : "";
            }
            editChecklist.value = data.draft.checklist ? data.draft.checklist.map(item => `- [ ] ${item}`).join("\n") : "";
            currentDraftImages = data.draft.parsed_images || [];
            renderDraftImages();

            // Handle Collision UI
            renderCollisions(data.collisions);

        } catch (err) {
            showToast("Failed to load draft details", "error");
            console.error(err);
        }
    }

    function renderCollisions(collisions) {
        collisionContainer.innerHTML = "";
        
        if (!collisions || collisions.length === 0) {
            matchStatus.textContent = "Safe: No Collisions";
            matchStatus.className = "text-[10px] px-2 py-0.5 rounded font-medium bg-emerald-50 text-emerald-600 border border-emerald-100";
            collisionContainer.innerHTML = `
                <div class="h-full flex flex-col items-center justify-center text-center text-slate-400 py-12 border border-dashed border-slate-200 rounded-lg bg-slate-50/50">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-emerald-450 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <p class="text-xs">No matching live tickets found in DB.</p>
                </div>
            `;
            return;
        }

        const highestScore = collisions[0].score;
        if (highestScore >= 85) {
            matchStatus.textContent = `Collision Warning: ${highestScore.toFixed(0)}%`;
            matchStatus.className = "text-[10px] px-2 py-0.5 rounded font-medium bg-rose-50 text-rose-600 border border-rose-100 animate-pulse";
        } else {
            matchStatus.textContent = `Potential Duplicates: ${highestScore.toFixed(0)}%`;
            matchStatus.className = "text-[10px] px-2 py-0.5 rounded font-medium bg-amber-55 text-amber-700 border border-amber-200";
        }

        collisionContainer.innerHTML = collisions.map(c => {
            const isSelected = c.id === selectedLiveTicketId;
            let collisionImagesHtml = "";
            if (c.images && c.images.length > 0) {
                collisionImagesHtml = `
                    <div class="mt-2 flex flex-wrap gap-1">
                        ${c.images.map(img => `<img src="${img}" class="w-12 h-12 object-cover border border-slate-200 rounded" />`).join("")}
                    </div>
                `;
            }
            return `
                <div data-live-id="${c.id}" class="p-4 rounded-lg border cursor-pointer transition duration-150 ${
                    isSelected
                        ? "bg-blue-50 border-blue-400 text-slate-900 shadow-sm" 
                        : "bg-white border-slate-200 hover:border-slate-350 hover:bg-slate-50 text-slate-700 shadow-xs"
                }">
                    <div class="flex items-center justify-between">
                        <span class="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                            c.score >= 85 ? "bg-rose-50 text-rose-600 border border-rose-100" : "bg-slate-105 text-slate-600 border border-slate-200"
                        }">
                            Match: ${c.score.toFixed(0)}%
                        </span>
                        <span class="text-[10px] text-slate-400 font-mono">Live ID: ${c.id}</span>
                    </div>
                    <h4 class="text-sm font-bold text-slate-900 mt-2">${c.title || "Untitled"}</h4>
                    <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200 mt-1">
                        ${c.client || "No Client Specified"}
                    </span>
                    ${c.symptom ? `<p class="text-xs text-slate-500 mt-2 bg-slate-50 p-2 rounded border border-slate-100 whitespace-pre-wrap">${c.symptom}</p>` : ""}
                    ${collisionImagesHtml}
                </div>
            `;
        }).join("");

        // Attach select event listener to collision tickets
        collisionContainer.querySelectorAll("[data-live-id]").forEach(card => {
            card.addEventListener("click", () => {
                const liveId = parseInt(card.getAttribute("data-live-id"));
                
                // Toggle selection
                if (selectedLiveTicketId === liveId) {
                    selectedLiveTicketId = null;
                } else {
                    selectedLiveTicketId = liveId;
                }

                // Re-render collisions to show updated highlight
                renderCollisions(collisions);

                // Enable/disable merge button
                if (selectedLiveTicketId) {
                    mergeBtn.removeAttribute("disabled");
                    mergeBtn.className = "px-4 py-2 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-sm font-medium transition duration-150 cursor-pointer shadow-md shadow-blue-500/10 hover:shadow-blue-500/25";
                } else {
                    mergeBtn.setAttribute("disabled", "true");
                    mergeBtn.className = "px-4 py-2 bg-blue-105 text-blue-600 border border-blue-200 rounded text-sm font-medium transition duration-150 cursor-not-allowed opacity-50";
                }
            });
        });
    }

    function parseStepsFromInput(text) {
        const rawSteps = text.split("\n");
        const steps = [];
        let currentStep = "";
        let inMultiLineBlock = false;
        const listBulletRegex = /^([-*+]|\d+\.)(\s+|(?=[`*]))/;

        for (const line of rawSteps) {
            const trimmed = line.trim();
            
            if (inMultiLineBlock && currentStep !== null) {
                let lineContent = line;
                if (listBulletRegex.test(trimmed)) {
                    lineContent = line.replace(listBulletRegex, '');
                }
                currentStep += "\n" + lineContent;
                
                const boldCount = (currentStep.match(/\*\*/g) || []).length;
                const tripleCodeCount = (currentStep.match(/```/g) || []).length;
                const singleCodeCount = (currentStep.match(/`/g) || []).length - (tripleCodeCount * 3);
                if (boldCount % 2 === 0 && tripleCodeCount % 2 === 0 && singleCodeCount % 2 === 0) {
                    inMultiLineBlock = false;
                    steps.push(currentStep.trim());
                    currentStep = "";
                }
            } else if (listBulletRegex.test(trimmed)) {
                if (currentStep) {
                    steps.push(currentStep.trim());
                }
                const stepContent = trimmed.replace(listBulletRegex, '').trim();
                const boldCount = (stepContent.match(/\*\*/g) || []).length;
                const tripleCodeCount = (stepContent.match(/```/g) || []).length;
                const singleCodeCount = (stepContent.match(/`/g) || []).length - (tripleCodeCount * 3);
                
                if (boldCount % 2 !== 0 || tripleCodeCount % 2 !== 0 || singleCodeCount % 2 !== 0) {
                    inMultiLineBlock = true;
                    currentStep = stepContent;
                } else {
                    steps.push(stepContent);
                    currentStep = "";
                }
            } else {
                if (currentStep) {
                    currentStep += "\n" + line; // Keep original indentation
                } else if (trimmed) {
                    currentStep = trimmed;
                }
            }
        }
        if (currentStep) {
            steps.push(currentStep.trim());
        }
        return steps.filter(s => s.length > 0);
    }

    // Helper: Parse checklist string array
    function parseChecklistFromInput(text) {
        return text.split("\n")
            .map(line => line.trim())
            .filter(line => line.length > 0)
            .map(line => {
                // remove leading markdown checkbox signs: - [ ] , * [ ] , ? etc
                return line.replace(/^([-*+]?\s*\[[ xX]\]|[-*+?])\s*/, "").trim();
            })
            .filter(line => line.length > 0);
    }

    // Save Draft Updates
    async function performSave() {
        if (!currentDraftId) return false;

        let stepsArray = [];
        if (editType.value === "query") {
            const queryText = editSteps.value.trim();
            if (queryText) {
                const listBulletRegex = /^([-*+]|\d+\.)(\s+|(?=[`*]))/;
                const cleanQuery = queryText.replace(listBulletRegex, '').trim();
                if (cleanQuery.startsWith('`') && cleanQuery.endsWith('`')) {
                    stepsArray.push(cleanQuery);
                } else {
                    stepsArray.push('`' + cleanQuery + '`');
                }
            }
        } else {
            stepsArray = parseStepsFromInput(editSteps.value);
        }
        const checklistArray = parseChecklistFromInput(editChecklist.value);
        const payload = {
            title: editTitle.value.trim(),
            client: editClient.value.trim(),
            symptom: editSymptom.value.trim(),
            steps: stepsArray,
            images: currentDraftImages,
            type: editType.value,
            checklist: checklistArray
        };

        if (!payload.title) {
            showToast("Draft Title cannot be empty", "error");
            return false;
        }

        try {
            const res = await fetch(`/api/staging/update/${currentDraftId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                // Refresh local drafts object and update sidebar text immediately
                const draft = drafts.find(d => d.id === currentDraftId);
                if (draft) {
                    draft.parsed_title = payload.title;
                    draft.parsed_client = payload.client;
                    draft.parsed_symptom = payload.symptom;
                    draft.parsed_steps = payload.steps;
                    draft.parsed_images = payload.images;
                    draft.type = payload.type;
                    draft.checklist = payload.checklist;
                }
                renderSidebar();
                
                // Re-evaluate collisions in the UI (or let compare re-trigger)
                const compRes = await fetch(`/api/staging/compare/${currentDraftId}`);
                if (compRes.ok) {
                    const compData = await compRes.json();
                    renderCollisions(compData.collisions);
                }
                
                return true;
            } else {
                const errData = await res.json();
                showToast(errData.detail || "Failed to save draft details", "error");
                return false;
            }
        } catch (err) {
            showToast("Network error trying to update draft", "error");
            console.error(err);
            return false;
        }
    }

    saveDraftBtn.addEventListener("click", async () => {
        saveDraftBtn.disabled = true;
        const success = await performSave();
        if (success) {
            showToast("Draft updates saved locally.");
        }
        saveDraftBtn.disabled = false;
    });

    async function handleDiscardDraft(draftId) {
        const confirmed = await window.showConfirm(
            "Discard Draft",
            "Are you sure you want to discard this draft? This cannot be undone."
        );
        if (!confirmed) return;

        try {
            discardBtn.disabled = true;
            const res = await fetch(`/api/staging/discard/${draftId}`, {
                method: "DELETE"
            });

            if (res.ok) {
                showToast("Draft successfully discarded.");
                resetWorkspace();
                await loadDrafts();
            } else {
                showToast("Failed to discard draft.", "error");
            }
        } catch (err) {
            showToast("Network error while discarding draft.", "error");
            console.error(err);
        } finally {
            discardBtn.disabled = false;
        }
    }

    // Discard draft
    discardBtn.addEventListener("click", async () => {
        if (!currentDraftId) return;
        await handleDiscardDraft(currentDraftId);
    });

    // Approve as New
    approveBtn.addEventListener("click", async () => {
        if (!currentDraftId) return;

        // Auto-save changes first to capture last edits
        approveBtn.textContent = "Saving & Approving...";
        approveBtn.disabled = true;
        const saved = await performSave();
        if (!saved) {
            approveBtn.textContent = "Approve as New";
            approveBtn.disabled = false;
            return;
        }

        try {
            const res = await fetch(`/api/staging/approve/${currentDraftId}`, {
                method: "POST"
            });

            if (res.ok) {
                showToast("Approved as a new Support Ticket!");
                resetWorkspace();
                await loadDrafts();
            } else {
                const errData = await res.json();
                showToast(errData.detail || "Failed to approve ticket", "error");
            }
        } catch (err) {
            showToast("Network error approving ticket", "error");
            console.error(err);
        } finally {
            approveBtn.textContent = "Approve as New";
            approveBtn.disabled = false;
        }
    });

    // Merge notes
    mergeBtn.addEventListener("click", async () => {
        if (!currentDraftId || !selectedLiveTicketId) return;

        mergeBtn.textContent = "Merging...";
        mergeBtn.disabled = true;

        // Auto-save changes first to capture last edits
        const saved = await performSave();
        if (!saved) {
            mergeBtn.textContent = "Merge Notes";
            mergeBtn.disabled = false;
            return;
        }

        try {
            const res = await fetch("/api/staging/merge", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    draft_id: currentDraftId,
                    target_live_ticket_id: selectedLiveTicketId
                })
            });

            if (res.ok) {
                showToast("Merged draft steps into target live ticket.");
                resetWorkspace();
                await loadDrafts();
            } else {
                const errData = await res.json();
                showToast(errData.detail || "Failed to merge draft", "error");
            }
        } catch (err) {
            showToast("Network error merging draft", "error");
            console.error(err);
        } finally {
            mergeBtn.textContent = "Merge Notes";
            mergeBtn.disabled = false;
        }
    });

    function resetWorkspace() {
        currentDraftId = null;
        selectedLiveTicketId = null;
        workspace.classList.add("hidden");
        emptyState.classList.remove("hidden");
    }

    // Load initial drafts
    loadDrafts();
});
