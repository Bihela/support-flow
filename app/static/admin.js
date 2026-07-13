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

        const confirmed = await window.showConfirm("Restore Database", "WARNING: This will replace your entire database with the uploaded file. A backup will be created. Are you sure you want to continue?");
        if (!confirmed) return;

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

        const confirmed = await window.showConfirm("Merge Tickets", "Are you sure you want to merge tickets from the selected JSON file?", { isDestructive: false });
        if (!confirmed) return;

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
