(() => {
    "use strict";

    const API_BASE = "/api/connectors/mysql/";
    const state = { connections: [], selectedConnectionId: null, selectedTable: null };
    const $ = (id) => document.getElementById(id);

    function csrfToken() {
        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        if (match) return decodeURIComponent(match[1]);
        const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]");
        return tokenInput ? tokenInput.value : "";
    }

    async function api(path = "", options = {}) {
        const headers = { "Accept": "application/json", ...(options.headers || {}) };
        if (options.body) headers["Content-Type"] = "application/json";
        if (options.method && options.method.toUpperCase() !== "GET") headers["X-CSRFToken"] = csrfToken();
        const response = await fetch(API_BASE + path, {
            ...options,
            headers,
            credentials: "same-origin"
        });
        let data;
        try { data = await response.json(); }
        catch (_) { data = { detail: `Server returned HTTP ${response.status}.` }; }
        if (!response.ok || data.success === false) {
            const message = data.error || data.detail || data.message || `Request failed (HTTP ${response.status}).`;
            throw new Error(typeof message === "string" ? message : JSON.stringify(message));
        }
        return data;
    }

    function showNotice(message, type = "success") {
        const box = $("connectionMessage");
        box.textContent = message;
        box.className = `notice show ${type}`;
    }

    function setPageMessage(message = "", type = "") {
        const box = $("pageMessage");
        box.textContent = message;
        box.className = `page-message ${type}`.trim();
    }

    function setBusy(button, busy, busyText = "Please wait...") {
        if (!button) return;
        if (busy) {
            button.dataset.originalText = button.textContent;
            button.textContent = busyText;
            button.disabled = true;
        } else {
            button.textContent = button.dataset.originalText || button.textContent;
            button.disabled = false;
        }
    }

    function renderConnections() {
        const list = $("connectionList");
        $("connectionCount").textContent = state.connections.length;
        list.replaceChildren();
        if (!state.connections.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "No saved connections yet. Add your first MySQL database using the form.";
            list.append(empty);
            return;
        }
        state.connections.forEach((connection) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "connection-item" + (connection.id === state.selectedConnectionId ? " selected" : "");
            const icon = document.createElement("span");
            icon.className = "db-icon";
            icon.textContent = "▤";
            const meta = document.createElement("span");
            meta.className = "connection-meta";
            const name = document.createElement("strong");
            name.textContent = connection.name;
            const detail = document.createElement("small");
            detail.textContent = `${connection.username}@${connection.host}:${connection.port} · ${connection.database_name}`;
            meta.append(name, detail);
            const arrow = document.createElement("span");
            arrow.className = "connection-arrow";
            arrow.textContent = "›";
            button.append(icon, meta, arrow);
            button.addEventListener("click", () => selectConnection(connection.id));
            list.append(button);
        });
    }

    async function loadConnections() {
        const refresh = $("refreshConnections");
        setBusy(refresh, true, "Refreshing...");
        try {
            const data = await api();
            state.connections = Array.isArray(data.connections) ? data.connections : [];
            renderConnections();
            if (state.selectedConnectionId && !state.connections.some(c => c.id === state.selectedConnectionId)) {
                resetExplorer();
            }
            setPageMessage(`${state.connections.length} saved connection${state.connections.length === 1 ? "" : "s"} loaded.`, "success");
        } catch (error) {
            setPageMessage(error.message, "error");
            $("connectionList").textContent = "Could not load connections. Check that you are signed in and the API is running.";
        } finally {
            setBusy(refresh, false);
        }
    }

    function resetExplorer() {
        state.selectedConnectionId = null;
        state.selectedTable = null;
        $("explorerTitle").textContent = "Choose a connection";
        $("explorerSubtitle").textContent = "Your database tables will appear here after you select a saved connection.";
        $("selectedConnectionStatus").textContent = "Not connected";
        $("selectedConnectionStatus").classList.remove("active");
        $("tableCount").textContent = "0 tables";
        $("tableList").textContent = "No tables loaded.";
        $("tablePreview").textContent = "Select a table to preview its records.";
        $("selectedTableTitle").textContent = "Table details";
        $("previewButton").disabled = true;
        $("edaButton").disabled = true;
        $("aiQuestion").disabled = true;
        $("askAiButton").disabled = true;
        $("analysisResult").hidden = true;
        $("edaResult").hidden = true;
        renderConnections();
    }

    async function selectConnection(id) {
        const connection = state.connections.find(item => item.id === id);
        if (!connection) return;
        state.selectedConnectionId = id;
        state.selectedTable = null;
        renderConnections();
        $("explorerTitle").textContent = connection.name;
        $("explorerSubtitle").textContent = `${connection.database_name} · ${connection.host}:${connection.port}`;
        $("selectedConnectionStatus").textContent = "Loading tables...";
        $("selectedConnectionStatus").classList.add("active");
        $("tableList").textContent = "Loading tables...";
        $("tablePreview").textContent = "Select a table to preview its records.";
        $("selectedTableTitle").textContent = "Table details";
        disableTableActions();
        try {
            const data = await api(`${id}/tables/`);
            renderTables(data.tables || []);
            $("selectedConnectionStatus").textContent = "Connection ready";
            $("tableCount").textContent = `${(data.tables || []).length} table${(data.tables || []).length === 1 ? "" : "s"}`;
        } catch (error) {
            $("selectedConnectionStatus").textContent = "Connection error";
            $("tableList").textContent = error.message;
        }
    }

    function disableTableActions() {
        $("previewButton").disabled = true;
        $("edaButton").disabled = true;
        $("aiQuestion").disabled = true;
        $("askAiButton").disabled = true;
        $("analysisResult").hidden = true;
        $("edaResult").hidden = true;
    }

    function renderTables(tables) {
        const list = $("tableList");
        list.replaceChildren();
        if (!tables.length) {
            list.textContent = "No tables found in this database.";
            return;
        }
        tables.forEach((table) => {
            const tableName = typeof table === "string" ? table : (table.name || table.table_name || String(table));
            const button = document.createElement("button");
            button.type = "button";
            button.className = "table-item";
            const icon = document.createElement("span");
            icon.textContent = "▦";
            const label = document.createElement("span");
            label.textContent = tableName;
            button.append(icon, label);
            button.addEventListener("click", () => selectTable(tableName, button));
            list.append(button);
        });
    }

    async function selectTable(tableName, button) {
        state.selectedTable = tableName;
        document.querySelectorAll(".table-item").forEach(item => item.classList.remove("selected"));
        button.classList.add("selected");
        $("selectedTableTitle").textContent = tableName;
        $("tablePreview").textContent = "Loading table preview...";
        $("previewButton").disabled = false;
        $("edaButton").disabled = false;
        $("aiQuestion").disabled = false;
        $("askAiButton").disabled = false;
        $("analysisResult").hidden = true;
        $("edaResult").hidden = true;
        await loadPreview();
    }

    function displayValue(value) {
        if (value === null || value === undefined) return "—";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
    }

    async function loadPreview() {
        if (!state.selectedConnectionId || !state.selectedTable) return;
        setBusy($("previewButton"), true, "Loading...");
        try {
            const tablePath = encodeURIComponent(state.selectedTable);
            const data = await api(`${state.selectedConnectionId}/tables/${tablePath}/preview/`);
            renderPreview(data);
        } catch (error) {
            $("tablePreview").textContent = error.message;
        } finally {
            setBusy($("previewButton"), false);
        }
    }

    function renderPreview(data) {
        const container = $("tablePreview");
        container.replaceChildren();
        const caption = document.createElement("div");
        caption.className = "table-caption";
        caption.textContent = `${data.database || "Database"}.${data.table || state.selectedTable} · ${data.total_rows_returned ?? (data.rows || []).length} rows returned`;
        container.append(caption);
        const columns = data.columns || [];
        const rows = data.rows || [];
        if (!columns.length) {
            const empty = document.createElement("div");
            empty.className = "preview-placeholder";
            empty.textContent = "This table has no previewable columns or records.";
            container.append(empty);
            return;
        }
        const table = document.createElement("table");
        table.className = "data-table";
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        columns.forEach(column => {
            const th = document.createElement("th");
            th.textContent = typeof column === "string" ? column : (column.name || column.column_name || JSON.stringify(column));
            headerRow.append(th);
        });
        thead.append(headerRow);
        const tbody = document.createElement("tbody");
        rows.forEach(row => {
            const tr = document.createElement("tr");
            columns.forEach((column, index) => {
                const key = typeof column === "string" ? column : (column.name || column.column_name);
                const td = document.createElement("td");
                td.textContent = Array.isArray(row) ? displayValue(row[index]) : displayValue(row && row[key]);
                tr.append(td);
            });
            tbody.append(tr);
        });
        table.append(thead, tbody);
        container.append(table);
    }

    async function runEda() {
        if (!state.selectedConnectionId || !state.selectedTable) return;
        const button = $("edaButton");
        setBusy(button, true, "Analyzing...");
        const result = $("edaResult");
        result.hidden = false;
        result.textContent = "Generating exploratory data analysis...";
        try {
            const tablePath = encodeURIComponent(state.selectedTable);
            const data = await api(`${state.selectedConnectionId}/tables/${tablePath}/eda/`);
            result.textContent = JSON.stringify(data.eda ?? data, null, 2);
        } catch (error) {
            result.textContent = `EDA failed: ${error.message}`;
        } finally {
            setBusy(button, false);
        }
    }

    async function askAi() {
        if (!state.selectedConnectionId || !state.selectedTable) return;
        const question = $("aiQuestion").value.trim();
        if (!question) {
            $("aiQuestion").focus();
            return;
        }
        const button = $("askAiButton");
        setBusy(button, true, "Thinking...");
        const result = $("analysisResult");
        result.hidden = false;
        result.textContent = "Analyzing your question...";
        try {
            const tablePath = encodeURIComponent(state.selectedTable);
            const data = await api(`${state.selectedConnectionId}/tables/${tablePath}/ask/`, {
                method: "POST",
                body: JSON.stringify({ question })
            });
            result.textContent = typeof data.analysis === "string" ? data.analysis : JSON.stringify(data.analysis, null, 2);
        } catch (error) {
            result.textContent = `AI analysis failed: ${error.message}`;
        } finally {
            setBusy(button, false);
        }
    }

    async function createConnection(event) {
        event.preventDefault();
        const form = $("connectionForm");
        const button = $("connectButton");
        const payload = Object.fromEntries(new FormData(form).entries());
        payload.port = Number(payload.port);
        setBusy(button, true, "Connecting...");
        showNotice("Checking database credentials and saving the connection...", "success");
        try {
            const data = await api("", { method: "POST", body: JSON.stringify(payload) });
            showNotice(data.message || "MySQL connected and saved successfully.", "success");
            form.reset();
            $("port").value = "3306";
            await loadConnections();
            if (data.connection && data.connection.id) await selectConnection(data.connection.id);
            if (Array.isArray(data.tables)) {
                $("tableCount").textContent = `${data.tables.length} table${data.tables.length === 1 ? "" : "s"}`;
            }
        } catch (error) {
            showNotice(error.message, "error");
        } finally {
            setBusy(button, false);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        $("connectionForm").addEventListener("submit", createConnection);
        $("refreshConnections").addEventListener("click", loadConnections);
        $("previewButton").addEventListener("click", loadPreview);
        $("edaButton").addEventListener("click", runEda);
        $("askAiButton").addEventListener("click", askAi);
        $("aiQuestion").addEventListener("keydown", event => {
            if (event.key === "Enter") { event.preventDefault(); askAi(); }
        });
        document.querySelectorAll("[data-coming-soon]").forEach(link => {
            link.addEventListener("click", event => {
                event.preventDefault();
                setPageMessage(`${link.dataset.comingSoon} is not connected yet.`, "");
            });
        });
        loadConnections();
    });
})();
