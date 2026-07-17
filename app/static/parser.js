document.addEventListener("DOMContentLoaded", () => {
    const shorthandBox = document.getElementById("shorthandBox");
    const previewCard = document.getElementById("previewCard");
    const submitBtn = document.getElementById("submitBtn");
    const clearBtn = document.getElementById("clearBtn");
    const typeSelect = document.getElementById("typeSelect");

    const imageUpload = document.getElementById("imageUpload");
    const uploadedImagesList = document.getElementById("uploadedImagesList");
    let attachedImages = [];
    let lastXmlRequest = "";
    let lastXmlParsed = null;
    let isExtractingXml = false;

    const placeholderHtml = `
        <div class="text-center text-slate-400">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 mx-auto text-slate-350 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p class="text-sm">Start typing shorthand markdown on the left to see the support card preview.</p>
        </div>
    `;

    function sanitizeHtmlAndExtractText(htmlString) {
        if (!htmlString) return "";
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = htmlString;
        const tagsToRemove = ["table", "span", "style", "script"];
        tagsToRemove.forEach(tag => {
            const elements = tempDiv.querySelectorAll(tag);
            elements.forEach(el => el.remove());
        });
        return tempDiv.textContent || tempDiv.innerText || "";
    }

    function parseJiraXML(xmlString) {
        try {
            const parser = new DOMParser();
            let xmlDoc = parser.parseFromString(xmlString, "text/xml");
            
            let parserError = xmlDoc.querySelector("parsererror");
            if (parserError) {
                console.warn("XML parse error with text/xml, falling back to text/html:", parserError.textContent);
                xmlDoc = parser.parseFromString(xmlString, "text/html");
            }

            // Title & Client Heuristics
            let rawTitle = "";
            const summaryNode = xmlDoc.querySelector("summary");
            const titleNode = xmlDoc.querySelector("title");
            if (summaryNode) {
                rawTitle = summaryNode.textContent.trim();
            } else if (titleNode) {
                rawTitle = titleNode.textContent.trim();
            }

            const cleanedTitle = rawTitle.replace(/^\[[a-zA-Z0-9]+-\d+\]\s*/, "").trim();
            let client = "";
            let title = cleanedTitle;

            const pipeIndex = cleanedTitle.indexOf("|");
            const colonIndex = cleanedTitle.indexOf(":");
            const dashIndex = cleanedTitle.indexOf(" - ");

            let splitIndex = -1;
            let delimiterLength = 1;

            const indices = [
                { index: pipeIndex, len: 1 },
                { index: colonIndex, len: 1 },
                { index: dashIndex, len: 3 }
            ].filter(item => item.index !== -1);

            if (indices.length > 0) {
                indices.sort((a, b) => a.index - b.index);
                splitIndex = indices[0].index;
                delimiterLength = indices[0].len;
            }

            if (splitIndex !== -1) {
                client = cleanedTitle.substring(0, splitIndex).trim();
                title = cleanedTitle.substring(splitIndex + delimiterLength).trim();
            } else {
                const customfields = xmlDoc.querySelectorAll("customfield");
                for (const field of customfields) {
                    const fieldnameNode = field.querySelector("customfieldname");
                    if (fieldnameNode) {
                        const fieldname = fieldnameNode.textContent.toLowerCase();
                        if (fieldname.includes("client") || fieldname.includes("company") || fieldname.includes("account") || fieldname.includes("organization")) {
                            const valueNode = field.querySelector("customfieldvalue");
                            if (valueNode) {
                                client = valueNode.textContent.trim();
                                break;
                            }
                        }
                    }
                }
            }

            // Description & Comments Sanitization
            let symptom = "";
            const descriptionNode = xmlDoc.querySelector("description");
            if (descriptionNode) {
                const sanitizedDesc = sanitizeHtmlAndExtractText(descriptionNode.textContent);
                const sentences = sanitizedDesc.split(/(?<=[.!?])\s+/).filter(s => s.trim().length > 0);
                symptom = sentences.slice(0, 3).join(" ").trim();
            }

            const steps = [];

            function extractSteps(node) {
                if (!node) return;
                const rawText = node.textContent || "";
                const temp = document.createElement("div");
                temp.innerHTML = rawText;
                const liTags = temp.querySelectorAll("li");
                if (liTags.length > 0) {
                    liTags.forEach(li => {
                        const cleaned = li.textContent.replace(/^(?:\d+\.|\*|-)\s*/, "").trim();
                        if (cleaned) {
                            steps.push(cleaned);
                        }
                    });
                } else {
                    const lines = rawText.split(/\r?\n/);
                    lines.forEach(line => {
                        const trimmed = line.trim();
                        if (/^(?:\d+\.|\*|-)\s+/.test(trimmed)) {
                            const cleaned = trimmed.replace(/^(?:\d+\.|\*|-)\s*/, "").trim();
                            if (cleaned) {
                                steps.push(cleaned);
                            }
                        }
                    });
                }
            }

            if (descriptionNode) {
                extractSteps(descriptionNode);
            }

            const commentNodes = xmlDoc.querySelectorAll("comments comment, comment");
            commentNodes.forEach(node => {
                extractSteps(node);
            });

            return { title, client, symptom, steps, checklist: [] };
        } catch (err) {
            console.error("parseJiraXML exception:", err);
            return { title: "", client: "", symptom: "", steps: [] };
        }
    }

    function parseShorthand(text) {
        const trimmedText = text.trim();
        const isXml = (trimmedText.startsWith("<") && 
                      (trimmedText.includes("<rss") || trimmedText.includes("<item>") || trimmedText.includes("<summary>") || trimmedText.includes("<description>"))) ||
                      trimmedText.startsWith("<?xml");
        if (isXml) {
            const xmlResult = lastXmlParsed || { title: "", client: "", symptom: "", steps: [], type: "ticket", checklist: [] };
            // Ensure checklist is always present from XML results
            if (!xmlResult.checklist) xmlResult.checklist = [];
            if (!xmlResult.type) xmlResult.type = "ticket";
            return xmlResult;
        }

        // Fallback Configuration
        const lines = text.split("\n");
        let title = "";
        let client = "";
        let symptom = "";
        const steps = [];
        const checklist = [];
        
        let type = typeSelect ? typeSelect.value : "ticket";

        if (type === "query") {
            let bodyLines = [];
            for (let line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith("# ")) {
                    title = trimmed.slice(2).trim();
                } else if (trimmed.startsWith("@ ")) {
                    client = trimmed.slice(2).trim();
                } else if (trimmed.startsWith("> ")) {
                    symptom = trimmed.slice(2).trim();
                } else {
                    bodyLines.push(line);
                }
            }
            const queryBody = bodyLines.join("\n").trim();
            if (queryBody) {
                const listBulletRegex = /^([-*+]|\d+\.)(\s+|(?=[`*]))/;
                const cleanQuery = queryBody.replace(listBulletRegex, '').trim();
                if (cleanQuery.startsWith("`") && cleanQuery.endsWith("`")) {
                    steps.push(cleanQuery);
                } else {
                    steps.push("`" + cleanQuery + "`");
                }
            }
            return { title, client, symptom, steps, type, checklist };
        }

        let currentStep = null;
        let inMultiLineBlock = false;

        for (let line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("# ") && !inMultiLineBlock) {
                title = trimmed.slice(2).trim();
            } else if (trimmed.startsWith("@ ") && !inMultiLineBlock) {
                client = trimmed.slice(2).trim();
            } else if (trimmed.startsWith("> ") && !inMultiLineBlock) {
                symptom = trimmed.slice(2).trim();
            } else if ((trimmed.startsWith("- [ ] ") || trimmed.startsWith("- [x] ") || trimmed.startsWith("* [ ] ") || trimmed.startsWith("* [x] ")) && !inMultiLineBlock) {
                checklist.push(trimmed.slice(6).trim());
            } else if (trimmed.startsWith("? ") && !inMultiLineBlock) {
                checklist.push(trimmed.slice(2).trim());
            } else {
                const listBulletRegex = /^([-*+]|\d+\.)(\s+|(?=[`*]))/;
                if (inMultiLineBlock && currentStep !== null) {
                    let lineContent = line;
                    if (listBulletRegex.test(trimmed)) {
                        lineContent = line.replace(listBulletRegex, "");
                    }
                    currentStep += "\n" + lineContent;
                    
                    const boldCount = (currentStep.match(/\*\*/g) || []).length;
                    const tripleCodeCount = (currentStep.match(/```/g) || []).length;
                    const singleCodeCount = (currentStep.match(/`/g) || []).length - (tripleCodeCount * 3);
                    if (boldCount % 2 === 0 && tripleCodeCount % 2 === 0 && singleCodeCount % 2 === 0) {
                        inMultiLineBlock = false;
                        steps.push(currentStep);
                        currentStep = null;
                    }
                } else if (listBulletRegex.test(trimmed)) {
                    const stepContent = trimmed.replace(listBulletRegex, "").trim();
                    const boldCount = (stepContent.match(/\*\*/g) || []).length;
                    const tripleCodeCount = (stepContent.match(/```/g) || []).length;
                    const singleCodeCount = (stepContent.match(/`/g) || []).length - (tripleCodeCount * 3);
                    if (boldCount % 2 !== 0 || tripleCodeCount % 2 !== 0 || singleCodeCount % 2 !== 0) {
                        inMultiLineBlock = true;
                        currentStep = stepContent;
                    } else {
                        steps.push(stepContent);
                    }
                } else if (steps.length > 0 && trimmed.length > 0) {
                    steps[steps.length - 1] += "\n" + line;
                }
            }
        }
        if (inMultiLineBlock && currentStep !== null) {
            steps.push(currentStep);
        }

        type = typeSelect ? typeSelect.value : "ticket";
        if (checklist.length > 0 && typeSelect && typeSelect.value !== "guide") {
            typeSelect.value = "guide";
            type = "guide";
        }

        return { title, client, symptom, steps, type, checklist };
    }

    function renderThumbnails() {
        uploadedImagesList.innerHTML = "";
        attachedImages.forEach((img, idx) => {
            const wrapper = document.createElement("div");
            wrapper.className = "relative inline-block w-20 h-20 border border-slate-200 rounded overflow-hidden group";
            wrapper.innerHTML = `
                <img src="${img}" class="w-full h-full object-cover" />
                <button type="button" class="absolute top-0 right-0 bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity" data-index="${idx}">
                    &times;
                </button>
            `;
            wrapper.querySelector("button").addEventListener("click", () => {
                attachedImages.splice(idx, 1);
                renderThumbnails();
                updatePreview();
            });
            uploadedImagesList.appendChild(wrapper);
        });
    }

    imageUpload.addEventListener("change", async (e) => {
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
                attachedImages.push(data.file_path);
                renderThumbnails();
                updatePreview();
            } else {
                showToast("Failed to upload image", "error");
            }
        } catch (err) {
            console.error(err);
            showToast("Network error uploading image", "error");
        } finally {
            imageUpload.value = ""; // clear input
        }
    });

    async function updatePreview() {
        const text = shorthandBox.value;
        const trimmedText = text.trim();
        const isXml = (trimmedText.startsWith("<") && 
                      (trimmedText.includes("<rss") || trimmedText.includes("<item>") || trimmedText.includes("<summary>") || trimmedText.includes("<description>"))) ||
                      trimmedText.startsWith("<?xml");

        if (isXml) {
            if (trimmedText !== lastXmlRequest) {
                lastXmlRequest = trimmedText;
                lastXmlParsed = null;
                isExtractingXml = true;

                // Disable submit button
                submitBtn.disabled = true;

                // Show loading spinner
                previewCard.className = "flex-1 flex flex-col border border-slate-200 bg-white rounded-lg p-6 shadow-md text-left self-start w-full";
                previewCard.innerHTML = `
                    <div class="flex flex-col items-center justify-center py-12 text-slate-500">
                        <svg class="animate-spin h-8 w-8 text-slate-600 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <p class="text-sm font-medium">AI running in background compatibility mode (approx. 15s). Feel free to switch tabs...</p>
                    </div>
                `;

                try {
                    const response = await fetch("/api/extract/xml", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({ xml_payload: text })
                    });

                    if (response.ok) {
                        const data = await response.json();
                        lastXmlParsed = {
                            title: data.title || "",
                            client: data.client || "",
                            symptom: data.symptom || "",
                            steps: data.steps || [],
                            checklist: data.checklist || [],
                            type: "ticket"
                        };
                    } else {
                        const err = await response.json().catch(() => ({}));
                        showToast(err.detail || "Failed to extract XML from backend", "error");
                        lastXmlParsed = null;
                        lastXmlRequest = "";
                    }
                } catch (err) {
                    console.error("XML extraction error:", err);
                    showToast("Network error extracting XML data", "error");
                    lastXmlParsed = null;
                    lastXmlRequest = "";
                } finally {
                    isExtractingXml = false;
                    submitBtn.disabled = false;
                    updatePreview();
                }
                return;
            } else if (isExtractingXml) {
                // If it is currently extracting and the input is the same, keep spinner and do not re-run
                return;
            }
        }

        const parsed = parseShorthand(text);

        if (!parsed.title && !parsed.client && !parsed.symptom && parsed.steps.length === 0 && (!parsed.checklist || parsed.checklist.length === 0) && attachedImages.length === 0) {
            previewCard.innerHTML = placeholderHtml;
            previewCard.className = "flex-1 flex items-center justify-center border border-dashed border-slate-200 rounded-lg p-6 bg-white shadow-sm";
            return;
        }

        previewCard.className = "flex-1 flex flex-col border border-slate-200 bg-white rounded-lg p-6 shadow-md text-left self-start w-full";

        function escapeHtml(str) {
            if (!str) return "";
            return str
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        let stepsHtml = "";
        if (parsed.steps.length > 0) {
            if (parsed.type === "query") {
                let rawQuery = parsed.steps[0];
                if (rawQuery.startsWith("`") && rawQuery.endsWith("`")) {
                    rawQuery = rawQuery.slice(1, -1);
                }
                stepsHtml = `
                    <div class="mt-6 w-full min-w-0">
                        <h4 class="text-xs font-semibold text-slate-450 uppercase tracking-wider mb-2">Database Query</h4>
                        <div class="font-mono text-xs bg-slate-900 text-slate-100 px-4 py-3 rounded-lg flex items-start justify-between shadow-inner overflow-hidden w-full min-w-0">
                            <pre class="whitespace-pre-wrap break-all select-all flex-1 min-w-0 pr-2 font-mono">${escapeHtml(rawQuery)}</pre>
                            <button 
                                type="button"
                                class="copy-query-btn ml-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 hover:text-white border border-slate-700 rounded px-2.5 py-1 text-[10px] transition duration-150 flex-shrink-0"
                                data-cmd="${escapeHtml(rawQuery)}"
                            >
                                Copy
                            </button>
                        </div>
                    </div>
                `;
            } else {
                stepsHtml = `
                    <div class="mt-6">
                        <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Troubleshooting Steps</h4>
                        <ol class="list-decimal list-inside space-y-2 text-slate-650">
                            ${parsed.steps.map(step => `<li class="font-mono text-sm py-1 border-b border-slate-100 last:border-b-0 whitespace-pre-wrap">${escapeHtml(step)}</li>`).join("")}
                        </ol>
                    </div>
                `;
            }
        }

        let checklistHtml = "";
        if (parsed.checklist && parsed.checklist.length > 0) {
            checklistHtml = `
                <div class="mt-6">
                    <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Verification Checklist</h4>
                    <ul class="space-y-2 text-slate-650">
                        ${parsed.checklist.map(item => `
                            <li class="flex items-center space-x-2 text-sm">
                                <input type="checkbox" disabled class="rounded border-slate-300 text-blue-600 focus:ring-blue-500">
                                <span>${item}</span>
                            </li>
                        `).join("")}
                    </ul>
                </div>
            `;
        }

        let imagesHtml = "";
        if (attachedImages.length > 0) {
            imagesHtml = `
                <div class="mt-6">
                    <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Attachments</h4>
                    <div class="flex flex-wrap gap-2">
                        ${attachedImages.map(img => `<img src="${img}" class="w-20 h-20 object-cover border border-slate-200 rounded cursor-pointer hover:opacity-85 transition-opacity" />`).join("")}
                    </div>
                </div>
            `;
        }

        const typeBadge = parsed.type === "guide" 
            ? `<span class="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">Guide</span>`
            : parsed.type === "query"
                ? `<span class="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">Database Query</span>`
                : "";

        previewCard.innerHTML = `
            <div class="flex items-start justify-between border-b border-slate-150 pb-4 mb-4">
                <div>
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                        ${parsed.client || "No Client Specified"}
                    </span>
                    ${typeBadge}
                    <h3 class="text-lg font-bold text-slate-900 mt-2">${parsed.title || "Untitled Ticket"}</h3>
                </div>
            </div>
            
            ${parsed.symptom ? `
            <div class="bg-slate-50 border border-slate-100 rounded-lg p-4 mb-4">
                <h4 class="text-xs font-semibold text-slate-550 uppercase tracking-wider mb-1">Symptom / Description</h4>
                <p class="text-sm text-slate-650 whitespace-pre-wrap">${parsed.symptom}</p>
            </div>
            ` : ""}

            ${stepsHtml}

            ${checklistHtml}

            ${imagesHtml}
        `;
    }



    shorthandBox.addEventListener("input", updatePreview);
    if (typeSelect) {
        typeSelect.addEventListener("change", updatePreview);
    }

    clearBtn.addEventListener("click", () => {
        shorthandBox.value = "";
        attachedImages = [];
        lastXmlRequest = "";
        lastXmlParsed = null;
        isExtractingXml = false;
        submitBtn.disabled = false;
        if (typeSelect) {
            typeSelect.value = "ticket";
        }
        renderThumbnails();
        updatePreview();
    });

    submitBtn.addEventListener("click", async () => {
        const text = shorthandBox.value.trim();
        if (!text) {
            showToast("Cannot submit empty shorthand content", "error");
            return;
        }

        const parsed = parseShorthand(text);
        if (!parsed.title) {
            showToast("Support Card requires a Title (# Title)", "error");
            return;
        }

        const payload = {
            title: parsed.title,
            client: parsed.client,
            symptom: parsed.symptom,
            steps: parsed.steps,
            raw_markdown: text,
            images: attachedImages,
            type: parsed.type,
            checklist: parsed.checklist
        };

        try {
            submitBtn.disabled = true;
            submitBtn.textContent = "Submitting...";

            const response = await fetch("/api/staging/draft", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.ok && result.status === "success") {
                showToast("Draft Saved to Staging Inbox!");
                shorthandBox.value = "";
                attachedImages = [];
                lastXmlRequest = "";
                lastXmlParsed = null;
                isExtractingXml = false;
                if (typeSelect) {
                    typeSelect.value = "ticket";
                }
                renderThumbnails();
                updatePreview();
            } else {
                showToast(result.detail || "Failed to save draft.", "error");
            }
        } catch (error) {
            showToast("Network error submitting draft.", "error");
            console.error(error);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit to Staging";
        }
    });

    // Initial state setup
    updatePreview();

    if (previewCard) {
        previewCard.addEventListener("click", (e) => {
            const btn = e.target.closest(".copy-query-btn");
            if (btn) {
                const cmd = btn.getAttribute("data-cmd");
                navigator.clipboard.writeText(cmd).then(() => {
                    const originalText = btn.textContent;
                    btn.textContent = "Copied!";
                    btn.classList.add("bg-emerald-600", "text-white");
                    btn.classList.remove("bg-slate-800", "text-slate-300");
                    setTimeout(() => {
                        btn.textContent = originalText;
                        btn.classList.remove("bg-emerald-600", "text-white");
                        btn.classList.add("bg-slate-800", "text-slate-300");
                    }, 1500);
                }).catch(err => {
                    console.error("Failed to copy text: ", err);
                });
            }
        });
    }
});
