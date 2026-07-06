document.addEventListener("DOMContentLoaded", () => {
    const statTickets = document.getElementById("statTickets");
    const statSteps = document.getElementById("statSteps");
    const statImages = document.getElementById("statImages");
    const statDbSize = document.getElementById("statDbSize");
    const typeBreakdown = document.getElementById("typeBreakdown");
    const typeList = document.getElementById("typeList");

    const dbFileInput = document.getElementById("dbFileInput");
    const jsonFileInput = document.getElementById("jsonFileInput");
    const importResults = document.getElementById("importResults");
    const resultImported = document.getElementById("resultImported");
    const resultSkipped = document.getElementById("resultSkipped");

    const toastContainer = document.getElementById("toastContainer");

    // Toast Utility
    function showToast(message, type = "success") {
        const toast = document.createElement("div");
        toast.className = `px-4 py-3 rounded-lg text-sm font-medium shadow-lg border transition-all duration-300 transform translate-y-2 opacity-0 flex items-center space-x-2 bg-white`;
        
        if (type === "success") {
            toast.className += " bg-emerald-50 border-emerald-250 text-emerald-800";
            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>${message}</span>
            `;
        } else {
            toast.className += " bg-rose-50 border-rose-250 text-rose-800";
            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>${message}</span>
            `;
        }
        
        toastContainer.appendChild(toast);
        setTimeout(() => toast.classList.remove("translate-y-2", "opacity-0"), 10);
        setTimeout(() => {
            toast.classList.add("translate-y-2", "opacity-0");
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function formatBytes(bytes) {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    async function loadStats() {
        try {
            const response = await fetch("/api/admin/stats");
            if (!response.ok) throw new Error("Failed to load statistics");
            const data = await response.json();

            statTickets.textContent = data.total_tickets;
            statSteps.textContent = data.total_steps;
            statImages.textContent = data.total_images;
            statDbSize.textContent = formatBytes(data.db_size_bytes);

            if (data.types && data.types.length > 0) {
                typeList.innerHTML = "";
                data.types.forEach(t => {
                    const badge = document.createElement("span");
                    let badgeClass = "bg-slate-100 text-slate-700 border-slate-200";
                    if (t.type === "guide") badgeClass = "bg-blue-50 text-blue-700 border-blue-200";
                    else if (t.type === "dailychecklist") badgeClass = "bg-purple-50 text-purple-700 border-purple-200";
                    else if (t.type === "query") badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-200";

                    badge.className = `inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${badgeClass}`;
                    badge.textContent = `${t.type}: ${t.count}`;
                    typeList.appendChild(badge);
                });
                typeBreakdown.classList.remove("hidden");
            } else {
                typeBreakdown.classList.add("hidden");
            }
        } catch (err) {
            console.error(err);
            showToast("Error loading stats", "error");
        }
    }

    window.exportDb = function() {
        window.location.href = "/api/admin/export/db";
    };

    window.exportJson = function() {
        window.location.href = "/api/admin/export/json";
    };

    window.importDb = async function() {
        const file = dbFileInput.files[0];
        if (!file) {
            showToast("Please select a database file first.", "error");
            return;
        }

        const confirm = window.confirm("WARNING: This will replace your entire database with the uploaded file. A backup will be created. Are you sure you want to continue?");
        if (!confirm) return;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/admin/import/db", {
                method: "POST",
                body: formData
            });
            if (response.ok) {
                showToast("Database file imported successfully!");
                dbFileInput.value = "";
                loadStats();
            } else {
                const data = await response.json();
                showToast(data.detail || "Import failed", "error");
            }
        } catch (err) {
            console.error(err);
            showToast("Network error importing database", "error");
        }
    };

    window.importJson = async function() {
        const file = jsonFileInput.files[0];
        if (!file) {
            showToast("Please select a JSON file first.", "error");
            return;
        }

        const confirm = window.confirm("Are you sure you want to merge tickets from the selected JSON file?");
        if (!confirm) return;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/admin/import/json", {
                method: "POST",
                body: formData
            });
            if (response.ok) {
                const data = await response.json();
                showToast(`JSON Import completed!`);
                resultImported.textContent = data.imported;
                resultSkipped.textContent = data.skipped;
                importResults.classList.remove("hidden");
                jsonFileInput.value = "";
                loadStats();
            } else {
                const data = await response.json();
                showToast(data.detail || "JSON Import failed", "error");
            }
        } catch (err) {
            console.error(err);
            showToast("Network error during JSON import", "error");
        }
    };

    // Initial Load
    loadStats();
});
