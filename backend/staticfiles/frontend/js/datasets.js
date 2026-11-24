/* DataMind Dataset Management
 * Uses the existing confirmed endpoints only:
 * GET  /api/datasets/
 * POST /api/datasets/upload/
 * GET  /api/datasets/<id>/preview/
 * GET  /api/datasets/<id>/profile/
 *
 * Rename/delete/export endpoints are not assumed to exist.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const API = "/api/datasets/";
    const MAX_FILE_SIZE = 20 * 1024 * 1024;
    const PAGE_SIZE = 10;

    const $ = id => document.getElementById(id);
    const fileInput = $("datasetFile");
    const dropZone = $("dropZone");
    const uploadButton = $("uploadButton");
    const refreshButton = $("refreshButton");
    const selectedFileLabel = $("selectedFile");
    const uploadMessage = $("uploadMessage");
    const uploadProgress = $("uploadProgress");
    const progressBar = $("progressBar");
    const progressName = $("progressName");
    const progressPercent = $("progressPercent");
    const tableBody = $("datasetTableBody");
    const searchInput = $("searchDataset");
    const sourceFilter = $("datasetFilter");
    const pagination = $("datasetPagination");
    const previewModal = $("previewModal");
    const profileModal = $("profileModal");

    if (!fileInput || !dropZone || !uploadButton || !tableBody) return;

    let selectedFile = null;
    let datasets = [];
    let currentPage = 1;

    const formatNumber = value => Number(value || 0).toLocaleString("en-IN");

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        })[char]);
    }

    function csrfToken() {
        const item = document.cookie.split(";").map(v => v.trim())
            .find(v => v.startsWith("csrftoken="));
        return item ? decodeURIComponent(item.slice("csrftoken=".length)) : "";
    }

    async function responseError(response) {
        try {
            const body = await response.json();
            if (typeof body.error === "string") return body.error;
            if (typeof body.detail === "string") return body.detail;
            return JSON.stringify(body);
        } catch {
            return `Request failed (${response.status}).`;
        }
    }

    function message(text, type = "") {
        if (!uploadMessage) return;
        uploadMessage.textContent = text;
        uploadMessage.className = `upload-message ${type}`.trim();
    }

    function validateFile(file) {
        if (!file) return "Please select a file.";
        const ext = file.name.split(".").pop().toLowerCase();
        if (!["csv", "xlsx"].includes(ext)) return "Only CSV and XLSX files are supported.";
        if (file.size === 0) return "The selected file is empty.";
        if (file.size > MAX_FILE_SIZE) return "Maximum file size is 20 MB.";
        return "";
    }

    function selectFile(file) {
        const error = validateFile(file);
        if (error) {
            selectedFile = null;
            fileInput.value = "";
            selectedFileLabel.textContent = "";
            uploadButton.disabled = true;
            message(error, "error");
            return;
        }

        selectedFile = file;
        selectedFileLabel.textContent =
            `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
        uploadButton.disabled = false;
        message("");
    }

    fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files[0]) selectFile(fileInput.files[0]);
    });

    ["dragenter", "dragover"].forEach(name => dropZone.addEventListener(name, event => {
        event.preventDefault();
        dropZone.classList.add("dragover");
    }));

    ["dragleave", "drop"].forEach(name => dropZone.addEventListener(name, event => {
        event.preventDefault();
        dropZone.classList.remove("dragover");
    }));

    dropZone.addEventListener("drop", event => {
        const file = event.dataTransfer?.files?.[0];
        if (!file) return;
        try {
            const transfer = new DataTransfer();
            transfer.items.add(file);
            fileInput.files = transfer.files;
        } catch (_) { /* selectedFile is retained in memory */ }
        selectFile(file);
    });

    dropZone.addEventListener("click", event => {
        if (event.target.closest("label, button, input")) return;
        fileInput.click();
    });

    dropZone.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInput.click();
        }
    });

    uploadButton.addEventListener("click", uploadDataset);

    function uploadDataset() {
        if (!selectedFile) {
            message("Please select a dataset first.", "error");
            return;
        }

        const fileBeingUploaded = selectedFile;
        const body = new FormData();
        body.append("file", fileBeingUploaded);

        uploadButton.disabled = true;
        uploadProgress.hidden = false;
        progressName.textContent = fileBeingUploaded.name;
        progressPercent.textContent = "0%";
        progressBar.style.width = "0%";
        message("Uploading dataset…", "info");

        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API}upload/`);
        xhr.withCredentials = true;
        const csrf = csrfToken();
        if (csrf) xhr.setRequestHeader("X-CSRFToken", csrf);

        xhr.upload.addEventListener("progress", event => {
            if (!event.lengthComputable) return;
            const pct = Math.round(event.loaded / event.total * 100);
            progressBar.style.width = `${pct}%`;
            progressPercent.textContent = `${pct}%`;
        });

        xhr.onload = async () => {
            let result = {};
            try { result = JSON.parse(xhr.responseText); } catch (_) {}

            if (xhr.status >= 200 && xhr.status < 300) {
                progressBar.style.width = "100%";
                progressPercent.textContent = "100%";
                message(result.message || "Dataset uploaded successfully.", "success");
                selectedFile = null;
                fileInput.value = "";
                selectedFileLabel.textContent = "";
                uploadButton.disabled = true;
                await loadDatasets();

                if (result.preview && result.dataset) {
                    showPreview(result.dataset.name || "Dataset Preview", result.preview);
                }
            } else {
                message(
                    result.error || result.detail || `Upload failed (${xhr.status}).`,
                    "error"
                );
                uploadButton.disabled = !selectedFile;
            }
        };

        xhr.onerror = () => {
            message("Network error. Check your connection and try again.", "error");
            uploadButton.disabled = !selectedFile;
        };

        xhr.send(body);
    }

    async function loadDatasets() {
        tableBody.innerHTML =
            '<tr><td colspan="6" class="table-empty">Loading datasets…</td></tr>';
        if (refreshButton) refreshButton.disabled = true;

        try {
            const response = await fetch(API, {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            });
            if (!response.ok) throw new Error(await responseError(response));

            const payload = await response.json();
            datasets = Array.isArray(payload)
                ? payload
                : (Array.isArray(payload.results) ? payload.results : []);

            currentPage = 1;
            updateSummary();
            renderFiltered();
        } catch (error) {
            tableBody.innerHTML =
                `<tr><td colspan="6" class="table-empty">${escapeHTML(error.message)}</td></tr>`;
            updateSummary();
        } finally {
            if (refreshButton) refreshButton.disabled = false;
        }
    }

    function updateSummary() {
        $("totalDatasets").textContent = formatNumber(datasets.length);
        $("totalRows").textContent = formatNumber(
            datasets.reduce((sum, item) => sum + (Number(item.row_count) || 0), 0)
        );
        $("totalColumns").textContent = formatNumber(
            datasets.reduce((sum, item) => sum + (Number(item.column_count) || 0), 0)
        );
    }

    function filteredItems() {
        const query = (searchInput?.value || "").trim().toLowerCase();
        const source = (sourceFilter?.value || "all").toLowerCase();

        return datasets.filter(item => {
            const name = String(item.name || "").toLowerCase();
            const type = String(item.source_type || "").toLowerCase();
            const matchesSearch = !query || name.includes(query) || type.includes(query);

            let matchesSource = source === "all";
            if (source === "csv") matchesSource = type.includes("csv");
            if (source === "excel") matchesSource = type.includes("excel") || type.includes("xlsx");
            if (source === "mysql") matchesSource = type.includes("mysql");

            return matchesSearch && matchesSource;
        });
    }

    function renderFiltered() {
        const items = filteredItems();
        const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
        currentPage = Math.min(currentPage, pages);
        const start = (currentPage - 1) * PAGE_SIZE;
        renderTable(items.slice(start, start + PAGE_SIZE));
        renderPagination(items.length, pages, start);
    }

    function renderTable(items) {
        if (!items.length) {
            tableBody.innerHTML =
                '<tr><td colspan="6" class="table-empty">No datasets found. Upload a dataset or change your filters.</td></tr>';
            return;
        }

        tableBody.innerHTML = items.map(item => {
            const id = Number(item.id);
            const created = item.created_at
                ? new Date(item.created_at).toLocaleDateString("en-IN") : "—";
            const source = String(item.source_type || "Unknown").toLowerCase();

            return `
                <tr>
                    <td><strong>${escapeHTML(item.name || "Untitled dataset")}</strong></td>
                    <td><span class="file-type">${escapeHTML(source)}</span></td>
                    <td>${formatNumber(item.row_count)}</td>
                    <td>${formatNumber(item.column_count)}</td>
                    <td>${escapeHTML(created)}</td>
                    <td>
                        <button type="button" class="action-button"
                            data-action="preview" data-id="${Number.isInteger(id) ? id : ""}">
                            Preview
                        </button>
                        <button type="button" class="action-button"
                            data-action="profile" data-id="${Number.isInteger(id) ? id : ""}">
                            Profile
                        </button>
                    </td>
                </tr>`;
        }).join("");
    }

    function renderPagination(total, pages, start) {
        if (!pagination) return;
        const info = $("paginationInfo");
        const controls = pagination.querySelector(".pagination-buttons");
        if (info) {
            const first = total ? start + 1 : 0;
            const last = Math.min(start + PAGE_SIZE, total);
            info.textContent = `Showing ${first}–${last} of ${total} datasets`;
        }
        if (controls) {
            controls.innerHTML = `
                <button type="button" data-page="prev" ${currentPage <= 1 ? "disabled" : ""}>Previous</button>
                <button type="button" class="page-number" disabled>${currentPage} / ${pages}</button>
                <button type="button" data-page="next" ${currentPage >= pages ? "disabled" : ""}>Next</button>`;
        }
    }

    searchInput?.addEventListener("input", () => {
        currentPage = 1;
        renderFiltered();
    });

    sourceFilter?.addEventListener("change", () => {
        currentPage = 1;
        renderFiltered();
    });

    pagination?.addEventListener("click", event => {
        const button = event.target.closest("button[data-page]");
        if (!button || button.disabled) return;
        currentPage += button.dataset.page === "next" ? 1 : -1;
        renderFiltered();
    });

    tableBody.addEventListener("click", async event => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const id = Number(button.dataset.id);
        if (!Number.isInteger(id) || id < 1) return;

        button.disabled = true;
        try {
            if (button.dataset.action === "preview") await fetchPreview(id);
            if (button.dataset.action === "profile") await fetchProfile(id);
        } catch (error) {
            window.alert(error.message);
        } finally {
            button.disabled = false;
        }
    });

    async function fetchPreview(id) {
        const response = await fetch(`${API}${id}/preview/`, {
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = await response.json();
        const dataset = datasets.find(item => Number(item.id) === id);
        showPreview(dataset?.name || "Dataset Preview", payload);
    }

    function showPreview(name, payload) {
        if (!previewModal) return;
        $("previewTitle").textContent = name;
        const columns = Array.isArray(payload.columns) ? payload.columns : [];
        const rows = Array.isArray(payload.rows) ? payload.rows : [];
        $("previewDescription").textContent = `Preview · ${rows.length} records`;

        const target = $("previewTable");
        if (!columns.length) {
            target.textContent = "No preview data is available.";
        } else {
            target.innerHTML = `
                <table>
                    <thead><tr>${columns.map(col => `<th>${escapeHTML(col)}</th>`).join("")}</tr></thead>
                    <tbody>${rows.map(row => `<tr>${columns.map(col =>
                        `<td>${escapeHTML(row?.[col])}</td>`).join("")}</tr>`).join("")}</tbody>
                </table>`;
        }
        previewModal.hidden = false;
    }

    async function fetchProfile(id) {
        const response = await fetch(`${API}${id}/profile/`, {
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = await response.json();
        $("profileContent").textContent = JSON.stringify(payload, null, 2);
        profileModal.hidden = false;
    }

    function closeModal(modal) {
        if (modal) modal.hidden = true;
    }

    $("closePreview")?.addEventListener("click", () => closeModal(previewModal));
    $("closeProfile")?.addEventListener("click", () => closeModal(profileModal));

    [previewModal, profileModal].forEach(modal => {
        modal?.addEventListener("click", event => {
            if (event.target === modal) closeModal(modal);
        });
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            closeModal(previewModal);
            closeModal(profileModal);
        }
    });

    refreshButton?.addEventListener("click", loadDatasets);

    window.DataMindDatasets = {
        refresh: loadDatasets,
        getItems: () => [...datasets]
    };

    loadDatasets();
});
