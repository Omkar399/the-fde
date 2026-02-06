/**
 * THE FDE - Live Dashboard SSE Client
 * Vanilla JS - no frameworks.
 */

// ── Default Target Fields (loaded from schema) ────
var DEFAULT_TARGET_FIELDS = [
    { name: "customer_id", type: "string" },
    { name: "full_name", type: "string" },
    { name: "subscription_tier", type: "string" },
    { name: "signup_date", type: "date" },
    { name: "email", type: "string" },
    { name: "phone", type: "string" },
    { name: "address", type: "string" },
    { name: "city", type: "string" },
    { name: "state", type: "string" },
    { name: "zip_code", type: "string" },
    { name: "date_of_birth", type: "date" },
    { name: "account_balance", type: "number" },
    { name: "last_login", type: "datetime" },
    { name: "is_active", type: "boolean" }
];

var FIELD_TYPES = ["string", "number", "date", "datetime", "boolean"];

// ── Setup Tab: Add Field ──────────────────────────
function addField(name, type) {
    var list = document.getElementById("field-list");
    var row = document.createElement("div");
    row.className = "field-row";
    row.innerHTML =
        '<input type="text" class="field-name" value="' + _escAttr(name || "") + '" placeholder="field_name">' +
        '<select class="field-type">' +
        FIELD_TYPES.map(function (t) {
            return '<option value="' + t + '"' + (t === (type || "string") ? ' selected' : '') + '>' + t + '</option>';
        }).join("") +
        '</select>' +
        '<button class="btn-field-remove" onclick="removeField(this)" title="Remove field">' +
        '<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>' +
        '</button>';
    list.appendChild(row);
}

// ── Setup Tab: Remove Field ───────────────────────
function removeField(btn) {
    var row = btn.closest(".field-row");
    if (row) row.remove();
}

// ── Setup Tab: Get Config ─────────────────────────
function getSetupConfig() {
    var fields = [];
    document.querySelectorAll("#field-list .field-row").forEach(function (row) {
        var name = row.querySelector(".field-name").value.trim();
        var type = row.querySelector(".field-type").value;
        if (name) {
            fields.push({ name: name, type: type });
        }
    });

    var c1Url = document.getElementById("client-1-url").value.trim();
    var c2Url = document.getElementById("client-2-url").value.trim();

    return {
        target_fields: fields,
        clients: [
            {
                name: "Acme Corp",
                portal_url: c1Url || "",
                username: document.getElementById("client-1-user").value.trim() || "admin",
                password: document.getElementById("client-1-pass").value.trim() || "admin123"
            },
            {
                name: "Globex Inc",
                portal_url: c2Url || "",
                username: document.getElementById("client-2-user").value.trim() || "admin",
                password: document.getElementById("client-2-pass").value.trim() || "admin123"
            }
        ]
    };
}

// ── Setup Tab: Populate Defaults ──────────────────
function populateSetupDefaults() {
    var list = document.getElementById("field-list");
    if (!list) return;
    list.innerHTML = "";
    DEFAULT_TARGET_FIELDS.forEach(function (f) {
        addField(f.name, f.type);
    });
}

function _escAttr(s) {
    return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Global: Start Demo Button Handler ──────────────
function startDemo() {
    var btn = document.getElementById("btn-start");
    btn.disabled = true;
    btn.classList.add("running");
    btn.textContent = "Running...";

    // Switch to Live tab when starting
    switchTab("live");

    var config = getSetupConfig();

    fetch("/demo/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.status === "already_running") {
                btn.textContent = "Running...";
            }
        })
        .catch(function (err) {
            btn.disabled = false;
            btn.classList.remove("running");
            btn.textContent = "Run Pipeline";
            console.error("Failed to start demo:", err);
        });
}

// ── Global: Tab Switching ──────────────────────────
function switchTab(tab) {
    document.querySelectorAll(".center-tab").forEach(function (el) {
        el.classList.toggle("active", el.id === "tab-" + tab);
    });
    document.querySelectorAll(".tab-content").forEach(function (el) {
        el.classList.toggle("active", el.id === "tab-content-" + tab);
    });
}

(function () {
    "use strict";

    // ── State ──────────────────────────────────────────
    const state = {
        connected: false,
        demoRunning: false,
        currentPhase: null,
        activeStep: null,
        phases: {
            1: { client: "Acme Corp", mappings: [], calls: 0, memoryHits: 0, complete: false },
            2: { client: "Globex Inc", mappings: [], calls: 0, memoryHits: 0, complete: false },
        },
        memoryBank: [],  // All stored mappings across phases
        liveVncUrl: null, // AGI browser live session URL
        results: {},      // Per-phase summary from backend
    };

    // ── DOM refs ───────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);

    const dom = {
        liveBadge: $("#live-badge"),
        steps: {
            scrape: $("#step-scrape"),
            analyze: $("#step-analyze"),
            call: $("#step-call"),
            learn: $("#step-learn"),
            deploy: $("#step-deploy"),
        },
        phase1: {
            card: $("#phase-1"),
            mappings: $("#phase-1-mappings"),
            calls: $("#phase-1-calls"),
            memory: $("#phase-1-memory"),
            log: $("#phase-1-log"),
        },
        phase2: {
            card: $("#phase-2"),
            mappings: $("#phase-2-mappings"),
            calls: $("#phase-2-calls"),
            memory: $("#phase-2-memory"),
            log: $("#phase-2-log"),
        },
        // Browser
        browserUrl: $("#browser-url"),
        browserIframe: $("#browser-iframe"),
        browserOverlay: $("#browser-overlay"),
        browserAction: $("#browser-action"),
        // Memory
        memoryItems: $("#memory-items"),
        memoryEmpty: $("#memory-empty"),
        memoryCount: $("#memory-count"),
        // (logs are per-phase now)
    };

    // ── SSE Connection ─────────────────────────────────
    function connect() {
        const evtSource = new EventSource("/dashboard/events");

        evtSource.onopen = function () {
            state.connected = true;
            dom.liveBadge.classList.add("connected");
            dom.liveBadge.querySelector(".live-text").textContent = "LIVE";
            log("Connected to event stream", "info");
        };

        evtSource.onmessage = function (e) {
            try {
                const event = JSON.parse(e.data);
                handleEvent(event);
            } catch (err) {
                console.error("Failed to parse event:", err);
            }
        };

        evtSource.onerror = function () {
            state.connected = false;
            dom.liveBadge.classList.remove("connected");
            dom.liveBadge.querySelector(".live-text").textContent = "DISCONNECTED";
        };
    }

    // ── Event Router ───────────────────────────────────
    function handleEvent(event) {
        const { type, data } = event;

        switch (type) {
            case "phase_start":     onPhaseStart(data); break;
            case "phase_complete":  onPhaseComplete(data); break;
            case "step_start":      onStepStart(data); break;
            case "step_complete":   onStepComplete(data); break;
            case "mapping_result":  onMappingResult(data); break;
            case "phone_call":      onPhoneCall(data); break;
            case "phone_response":  onPhoneResponse(data); break;
            case "memory_store":    onMemoryStore(data); break;
            case "memory_recall":   onMemoryRecall(data); break;
            case "memory_update":   onMemoryUpdate(data); break;
            case "deploy_complete": onDeployComplete(data); break;
            case "browser_navigate": onBrowserNavigate(data); break;
            case "browser_live":    onBrowserLive(data); break;
            case "demo_complete":   onDemoComplete(data); break;
            case "reset":           onReset(); break;
            case "error":
                log("Error: " + (data.message || "Unknown"), "error");
                resetButton();
                break;
            default:
                log(data.message || type, "info");
        }
    }

    // ── Phase Handlers ─────────────────────────────────

    function onPhaseStart(data) {
        state.currentPhase = data.phase;
        state.demoRunning = true;
        resetSteps();
        log("Phase " + data.phase + " started \u2014 " + data.client, "info");

        if (data.phase === 1) {
            dom.phase1.card.style.opacity = "1";
            dom.phase2.card.style.opacity = "0.3";
        } else {
            dom.phase1.card.style.opacity = "0.6";
            dom.phase2.card.style.opacity = "1";
        }
    }

    function onPhaseComplete(data) {
        state.phases[data.phase].complete = true;
        resetSteps();
        log("Phase " + data.phase + " complete!", "success");

        const card = data.phase === 1 ? dom.phase1.card : dom.phase2.card;
        card.classList.add("phase-complete-flash");
        setTimeout(() => card.classList.remove("phase-complete-flash"), 600);

        // Capture summary for Results tab
        if (data.summary) {
            state.results[data.phase] = data.summary;
            renderResults();
        }

        // Hide browser when phase ends
        showBrowserIdle();
    }

    // ── Step Handlers ──────────────────────────────────

    function onStepStart(data) {
        state.activeStep = data.step;
        Object.values(dom.steps).forEach((el) => {
            if (el && !el.classList.contains("complete")) {
                el.classList.remove("active");
            }
        });
        const stepEl = dom.steps[data.step];
        if (stepEl) {
            stepEl.classList.remove("skipped");
            stepEl.classList.add("active");
        }
        log(data.message || "Step: " + data.step, "info");
    }

    function onStepComplete(data) {
        const stepEl = dom.steps[data.step];
        if (stepEl) {
            stepEl.classList.remove("active");
            stepEl.classList.add("complete");
        }
        // Hide browser after scrape completes
        if (data.step === "scrape") {
            showBrowserIdle();
        }
        log(data.message || data.step + " complete", "success");
    }

    // ── Browser Handlers ───────────────────────────────

    function onBrowserLive(data) {
        // AGI Inc provides a VNC URL to watch the browser session live
        if (data.vnc_url) {
            state.liveVncUrl = data.vnc_url;
            dom.browserOverlay.classList.add("hidden");
            dom.browserUrl.textContent = "AGI Browser — Live Session";
            dom.browserUrl.classList.add("active");
            // Load VNC stream in iframe
            dom.browserIframe.src = data.vnc_url;
            // Show "open in new tab" link as action bar
            dom.browserAction.innerHTML =
                esc(data.action || "Watching live") +
                ' &mdash; <a href="' + esc(data.vnc_url) +
                '" target="_blank" style="color:#2563EB;text-decoration:underline">Open full view \u2197</a>';
            dom.browserAction.classList.add("visible");
            log("AGI Browser live session started", "info");
        }
    }

    function onBrowserNavigate(data) {
        // If we have a live VNC session, just update the action text (don't change iframe)
        if (state.liveVncUrl) {
            if (data.action) {
                dom.browserAction.innerHTML =
                    esc(data.action) +
                    ' &mdash; <a href="' + esc(state.liveVncUrl) +
                    '" target="_blank" style="color:#2563EB;text-decoration:underline">Open full view \u2197</a>';
                dom.browserAction.classList.add("visible");
            }
            dom.browserUrl.textContent = data.url || "AGI Browser — Live Session";
            log("Browser: " + (data.action || data.url), "info");
            return;
        }

        // No live session — show portal pages in iframe (mock mode)
        if (data.url) {
            var iframeSrc = data.url;
            try {
                var parsed = new URL(data.url, window.location.origin);
                iframeSrc = parsed.pathname + parsed.search;
            } catch (e) {
                // Already relative, use as-is
            }
            dom.browserOverlay.classList.add("hidden");
            dom.browserUrl.textContent = data.url;
            dom.browserUrl.classList.add("active");
            dom.browserIframe.src = iframeSrc;
        }
        if (data.action) {
            dom.browserAction.textContent = data.action;
            dom.browserAction.classList.add("visible");
        }
        log("Browser: " + (data.action || data.url), "info");
    }

    function showBrowserIdle() {
        state.liveVncUrl = null;
        dom.browserOverlay.classList.remove("hidden");
        dom.browserOverlay.innerHTML =
            '<svg class="browser-idle-icon" width="40" height="40" viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="18" stroke="#CBD5E1" stroke-width="2"/><path d="M20 2C20 2 28 10 28 20C28 30 20 38 20 38" stroke="#CBD5E1" stroke-width="1.5"/><path d="M20 2C20 2 12 10 12 20C12 30 20 38 20 38" stroke="#CBD5E1" stroke-width="1.5"/><path d="M3 15h34M3 25h34" stroke="#CBD5E1" stroke-width="1.5"/></svg>' +
            '<span>AGI Browser \u2014 Idle</span>';
        dom.browserUrl.textContent = "about:blank";
        dom.browserUrl.classList.remove("active");
        dom.browserAction.classList.remove("visible");
        dom.browserIframe.src = "about:blank";
    }

    // ── Mapping Handlers ───────────────────────────────

    function onMappingResult(data) {
        const phase = state.currentPhase || 1;
        const phaseData = state.phases[phase];
        phaseData.mappings.push(data);

        if (data.from_memory) {
            phaseData.memoryHits++;
        }

        renderMappings(phase);
        const badge = data.from_memory ? "memory" : "ai";
        log(data.source + " \u2192 " + data.target + " [" + badge + "]", data.from_memory ? "memory" : "info");
    }

    function onPhoneCall(data) {
        const phase = state.currentPhase || 1;
        state.phases[phase].calls++;
        renderStats(phase);
        log("PHONE RINGING: \"" + data.column + "\" \u2192 \"" + data.mapping + "\"", "phone");
        // Show call banner in browser panel
        dom.browserOverlay.classList.remove("hidden");
        dom.browserOverlay.innerHTML =
            '<div style="font-size:36px">&#128222;</div>' +
            '<span style="color:#EC4899;font-size:14px;font-weight:700">CALLING HUMAN...</span>' +
            '<span style="color:#475569;font-size:12px">"Is <b>' + esc(data.column) +
            '</b> the field <b>' + esc(data.mapping) + '</b>?"</span>' +
            '<span style="color:#94A3B8;font-size:11px">Press 1 = Yes, 2 = No</span>';
    }

    function onPhoneResponse(data) {
        const result = data.confirmed ? "CONFIRMED" : "REJECTED";
        const cls = data.confirmed ? "success" : "warning";
        log("Human " + result + ": \"" + data.column + "\" \u2192 \"" + data.mapping + "\"", cls);
        // Reset browser overlay
        dom.browserOverlay.innerHTML =
            '<svg class="browser-idle-icon" width="40" height="40" viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="18" stroke="#CBD5E1" stroke-width="2"/><path d="M20 2C20 2 28 10 28 20C28 30 20 38 20 38" stroke="#CBD5E1" stroke-width="1.5"/><path d="M20 2C20 2 12 10 12 20C12 30 20 38 20 38" stroke="#CBD5E1" stroke-width="1.5"/><path d="M3 15h34M3 25h34" stroke="#CBD5E1" stroke-width="1.5"/></svg>' +
            '<span>AGI Browser \u2014 Idle</span>';
        showBrowserIdle();

        if (data.confirmed) {
            const phase = state.currentPhase || 1;
            const phaseData = state.phases[phase];
            const existing = phaseData.mappings.find(
                (m) => m.source === data.column && m.target === data.mapping
            );
            if (existing) {
                existing.badge = "human";
                renderMappings(phase);
            } else {
                phaseData.mappings.push({
                    source: data.column,
                    target: data.mapping,
                    badge: "human",
                });
                renderMappings(phase);
            }
        }
    }

    // ── Memory Handlers ────────────────────────────────

    function onMemoryStore(data) {
        state.memoryBank.push({
            source: data.source,
            target: data.target,
            client: data.client,
            recalled: false,
        });
        renderMemoryBank();
        log("Memory stored: " + data.source + " \u2192 " + data.target, "memory");
    }

    function onMemoryRecall(data) {
        // Find the matching item in memory bank and mark it as recalled
        const item = state.memoryBank.find(
            (m) => m.target === data.target && !m.recalled
        );
        if (item) {
            item.recalled = true;
            renderMemoryBank();
        }
        log("Memory recalled: " + data.source + " \u2192 " + data.target, "memory");
    }

    function onMemoryUpdate(data) {
        dom.memoryCount.textContent = (data.total || state.memoryBank.length) + " mappings";
    }

    // ── Deploy Handler ─────────────────────────────────

    function onDeployComplete(data) {
        log("Deployed " + data.records + " records \u2192 " + (data.target || "Google Sheets"), "deploy");
        if (data.url) {
            log("Sheet URL: " + data.url, "deploy");
        }
    }

    // ── Demo Complete Handler ──────────────────────────

    function onDemoComplete(data) {
        state.demoRunning = false;
        resetButton();
        log(
            "Demo complete! Phase 1 calls: " + data.phase1_calls +
            ", Phase 2 calls: " + data.phase2_calls +
            ", Memory: " + data.memory_size,
            "success"
        );
        dom.phase1.card.style.opacity = "1";
        dom.phase2.card.style.opacity = "1";
        showBrowserIdle();

        // Capture summaries if provided
        if (data.summaries) {
            if (data.summaries["1"]) state.results[1] = data.summaries["1"];
            if (data.summaries["2"]) state.results[2] = data.summaries["2"];
            renderResults();
        }

        // Auto-switch to Results tab
        switchTab("results");
    }

    // ── Reset Handler ──────────────────────────────────

    function onReset() {
        state.currentPhase = null;
        state.activeStep = null;
        state.demoRunning = false;
        state.memoryBank = [];
        state.results = {};
        state.phases[1] = { client: "Acme Corp", mappings: [], calls: 0, memoryHits: 0, complete: false };
        state.phases[2] = { client: "Globex Inc", mappings: [], calls: 0, memoryHits: 0, complete: false };
        resetSteps();
        renderMappings(1);
        renderMappings(2);
        renderStats(1);
        renderStats(2);
        renderMemoryBank();
        showBrowserIdle();
        dom.phase1.card.style.opacity = "1";
        dom.phase2.card.style.opacity = "1";
        dom.phase1.log.innerHTML = "";
        dom.phase2.log.innerHTML = "";
        dom.memoryCount.textContent = "0 mappings";
        // Reset results tab
        var resultsEmpty = document.getElementById("results-empty");
        var resultsContent = document.getElementById("results-content");
        if (resultsEmpty) resultsEmpty.style.display = "";
        if (resultsContent) { resultsContent.style.display = "none"; resultsContent.innerHTML = ""; }
        var tabResults = document.getElementById("tab-results");
        if (tabResults) tabResults.classList.remove("has-data");
        switchTab("setup");
        log("Dashboard reset \u2014 ready for demo", "info");
    }

    // ── Renderers ──────────────────────────────────────

    function resetSteps() {
        Object.values(dom.steps).forEach((el) => {
            if (el) el.classList.remove("active", "complete", "skipped");
        });
    }

    function resetButton() {
        const btn = document.getElementById("btn-start");
        if (btn) {
            btn.disabled = false;
            btn.classList.remove("running");
            btn.textContent = "Run Pipeline";
        }
    }

    function renderMappings(phase) {
        const phaseData = state.phases[phase];
        const container = phase === 1 ? dom.phase1.mappings : dom.phase2.mappings;
        if (!container) return;

        container.innerHTML = "";
        phaseData.mappings.forEach((m) => {
            const row = document.createElement("div");
            row.className = "mapping-row";

            const badge = m.badge || (m.from_memory ? "memory" : "ai");
            row.innerHTML =
                '<span class="mapping-source">' + esc(m.source) + "</span>" +
                '<span class="mapping-arrow">\u2192</span>' +
                '<span class="mapping-target">' + esc(m.target) + "</span>" +
                '<span class="mapping-badge ' + badge + '">' + badge + "</span>";

            container.appendChild(row);
        });

        renderStats(phase);
    }

    function renderStats(phase) {
        const phaseData = state.phases[phase];
        const refs = phase === 1 ? dom.phase1 : dom.phase2;

        if (refs.calls) {
            refs.calls.textContent = phaseData.calls;
            refs.calls.className = "stat-value " + (phaseData.calls > 0 ? "calls-bad" : "calls-good");
        }
        if (refs.memory) {
            refs.memory.textContent = phaseData.memoryHits;
            refs.memory.className = "stat-value " + (phaseData.memoryHits > 0 ? "memory-hit" : "");
        }
    }

    function renderResults() {
        var resultsEmpty = document.getElementById("results-empty");
        var resultsContent = document.getElementById("results-content");
        var tabResults = document.getElementById("tab-results");

        var phases = Object.keys(state.results);
        if (phases.length === 0) return;

        resultsEmpty.style.display = "none";
        resultsContent.style.display = "";
        resultsContent.innerHTML = "";
        tabResults.classList.add("has-data");

        phases.forEach(function (phaseNum) {
            var s = state.results[phaseNum];
            var phaseLabel = phaseNum === "1" || phaseNum === 1 ? "Phase 1" : "Phase 2";
            var phaseName = phaseNum === "1" || phaseNum === 1 ? "Novice" : "Expert";
            var badgeClass = phaseNum === "1" || phaseNum === 1 ? "phase-badge-novice" : "phase-badge-expert";

            // Build mapping rows from dashboard state
            var phaseData = state.phases[phaseNum] || { mappings: [] };
            var mappingRows = "";
            phaseData.mappings.forEach(function (m) {
                var badge = m.badge || (m.from_memory ? "memory" : "ai");
                mappingRows +=
                    '<div class="result-field-row">' +
                    '<span class="result-field-source">' + esc(m.source) + '</span>' +
                    '<span class="result-field-arrow">\u2192</span>' +
                    '<span class="result-field-target">' + esc(m.target) + '</span>' +
                    '<span class="mapping-badge ' + badge + '">' + badge + '</span>' +
                    '</div>';
            });

            // Sheet link
            var sheetHtml = "";
            if (s.sheet_url) {
                sheetHtml =
                    '<div class="result-sheet">' +
                    '<div class="result-sheet-icon">' +
                    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="1" width="12" height="14" rx="2" stroke="#059669" stroke-width="1.3"/><path d="M5 5h6M5 8h6M5 11h4" stroke="#059669" stroke-width="1" stroke-linecap="round"/></svg>' +
                    '</div>' +
                    '<div class="result-sheet-text">' +
                    '<div class="result-sheet-label">Google Sheet</div>' +
                    '<a class="result-sheet-url" href="' + esc(s.sheet_url) + '" target="_blank">' + esc(s.sheet_url) + '</a>' +
                    '</div></div>';
            } else {
                sheetHtml =
                    '<div class="result-sheet">' +
                    '<div class="result-sheet-icon">' +
                    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="1" width="12" height="14" rx="2" stroke="#059669" stroke-width="1.3"/><path d="M5 5h6M5 8h6M5 11h4" stroke="#059669" stroke-width="1" stroke-linecap="round"/></svg>' +
                    '</div>' +
                    '<div class="result-sheet-text">' +
                    '<div class="result-sheet-label">Google Sheet</div>' +
                    '<span style="font-size:12px;color:var(--slate-400)">Deployed (demo mode)</span>' +
                    '</div></div>';
            }

            // Portal
            var portalDisplay = s.portal_url || "—";

            var card =
                '<div class="result-phase">' +
                '<div class="result-phase-header">' +
                '<div class="result-phase-title">' +
                '<span class="phase-badge ' + badgeClass + '">' + phaseLabel + '</span>' +
                '<h3>' + esc(phaseName) + ' — ' + esc(s.client) + '</h3>' +
                '</div>' +
                '<span class="result-portal">' + esc(portalDisplay) + '</span>' +
                '</div>' +
                '<div class="result-stats">' +
                '<div class="result-stat"><span class="result-stat-value info">' + (s.total_columns || 0) + '</span><span class="result-stat-label">Fields</span></div>' +
                '<div class="result-stat"><span class="result-stat-value good">' + (s.auto_mapped || 0) + '</span><span class="result-stat-label">Auto-mapped</span></div>' +
                '<div class="result-stat"><span class="result-stat-value mem">' + (s.from_memory || 0) + '</span><span class="result-stat-label">From Memory</span></div>' +
                '<div class="result-stat"><span class="result-stat-value warn">' + (s.phone_calls || 0) + '</span><span class="result-stat-label">Phone Calls</span></div>' +
                '</div>' +
                sheetHtml +
                '<div class="result-fields">' +
                '<div class="result-fields-title">Field Mappings</div>' +
                mappingRows +
                '</div>' +
                '</div>';

            resultsContent.innerHTML += card;
        });
    }

    function renderMemoryBank() {
        if (!dom.memoryItems) return;

        dom.memoryItems.innerHTML = "";

        if (state.memoryBank.length === 0) {
            dom.memoryItems.innerHTML = '<div class="memory-empty">No mappings learned yet</div>';
            return;
        }

        state.memoryBank.forEach((m) => {
            const item = document.createElement("div");
            item.className = "memory-item" + (m.recalled ? " recalled" : "");
            item.setAttribute("data-target", m.target);

            const badgeText = m.recalled ? "RECALLED" : "STORED";
            item.innerHTML =
                '<span class="mem-source">' + esc(m.source) + "</span>" +
                '<span class="mem-arrow">\u2192</span>' +
                '<span class="mem-target">' + esc(m.target) + "</span>" +
                '<span class="mem-badge">' + badgeText + "</span>";

            dom.memoryItems.appendChild(item);
        });

        dom.memoryCount.textContent = state.memoryBank.length + " mappings";
    }

    // ── Logging ────────────────────────────────────────

    function log(message, cls) {
        // Route to the active phase's log panel (default to phase 1)
        const phase = state.currentPhase || 1;
        const target = phase === 2 ? dom.phase2.log : dom.phase1.log;
        if (!target) return;

        const entry = document.createElement("div");
        entry.className = "log-entry";

        const now = new Date();
        const ts = now.toLocaleTimeString("en-US", { hour12: false });

        entry.innerHTML =
            '<span class="log-time">' + ts + "</span>" +
            '<span class="log-msg ' + (cls || "") + '">' + esc(message) + "</span>";

        target.appendChild(entry);
        target.scrollTop = target.scrollHeight;

        while (target.children.length > 50) {
            target.removeChild(target.firstChild);
        }
    }

    // ── Util ───────────────────────────────────────────

    function esc(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Init ───────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", function () {
        populateSetupDefaults();
        log("Dashboard loaded \u2014 connecting...", "info");
        connect();
    });
})();
