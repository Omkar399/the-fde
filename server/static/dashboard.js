/**
 * THE FDE - Live Dashboard SSE Client
 * Vanilla JS - no frameworks.
 */

(function () {
    "use strict";

    // ── State ──────────────────────────────────────────
    const state = {
        connected: false,
        currentPhase: null,   // 1 or 2
        activeStep: null,     // 'scrape', 'analyze', 'call', 'learn', 'deploy'
        phases: {
            1: { client: "Acme Corp", mappings: [], calls: 0, memoryHits: 0, complete: false },
            2: { client: "Globex Inc", mappings: [], calls: 0, memoryHits: 0, complete: false },
        },
    };

    // ── DOM refs ───────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        liveBadge: $(".live-badge"),
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
        },
        phase2: {
            card: $("#phase-2"),
            mappings: $("#phase-2-mappings"),
            calls: $("#phase-2-calls"),
            memory: $("#phase-2-memory"),
        },
        eventLog: $("#event-log"),
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
            // EventSource will auto-reconnect
        };
    }

    // ── Event Handler ──────────────────────────────────
    function handleEvent(event) {
        const { type, data } = event;

        switch (type) {
            case "phase_start":
                onPhaseStart(data);
                break;
            case "phase_complete":
                onPhaseComplete(data);
                break;
            case "step_start":
                onStepStart(data);
                break;
            case "step_complete":
                onStepComplete(data);
                break;
            case "mapping_result":
                onMappingResult(data);
                break;
            case "phone_call":
                onPhoneCall(data);
                break;
            case "phone_response":
                onPhoneResponse(data);
                break;
            case "memory_update":
                onMemoryUpdate(data);
                break;
            case "deploy_complete":
                onDeployComplete(data);
                break;
            case "reset":
                onReset();
                break;
            default:
                log(data.message || type, "info");
        }
    }

    // ── Event Handlers ─────────────────────────────────

    function onPhaseStart(data) {
        state.currentPhase = data.phase;
        resetSteps();
        log(`Phase ${data.phase} started — ${data.client}`, "info");

        // Highlight active phase card
        if (data.phase === 1) {
            dom.phase1.card.style.opacity = "1";
            dom.phase2.card.style.opacity = "0.3";
        } else {
            dom.phase1.card.style.opacity = "0.6";
            dom.phase2.card.style.opacity = "1";
        }
    }

    function onPhaseComplete(data) {
        const phaseData = state.phases[data.phase];
        phaseData.complete = true;
        resetSteps();
        log(`Phase ${data.phase} complete!`, "success");

        const card = data.phase === 1 ? dom.phase1.card : dom.phase2.card;
        card.classList.add("phase-complete-flash");
        setTimeout(() => card.classList.remove("phase-complete-flash"), 600);
    }

    function onStepStart(data) {
        state.activeStep = data.step;
        // Reset all steps, then mark current as active
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
        log(data.message || `Step: ${data.step}`, "info");
    }

    function onStepComplete(data) {
        const stepEl = dom.steps[data.step];
        if (stepEl) {
            stepEl.classList.remove("active");
            stepEl.classList.add("complete");
        }
        log(data.message || `${data.step} complete`, "success");
    }

    function onMappingResult(data) {
        const phase = state.currentPhase || 1;
        const phaseData = state.phases[phase];
        phaseData.mappings.push(data);

        if (data.from_memory) {
            phaseData.memoryHits++;
        }

        renderMappings(phase);
        const badge = data.from_memory ? "memory" : "ai";
        log(`${data.source} → ${data.target} [${badge}]`, data.from_memory ? "memory" : "info");
    }

    function onPhoneCall(data) {
        const phase = state.currentPhase || 1;
        state.phases[phase].calls++;
        renderStats(phase);
        log(`Calling human: "${data.column}" → "${data.mapping}"`, "phone");
    }

    function onPhoneResponse(data) {
        const result = data.confirmed ? "CONFIRMED" : "REJECTED";
        const cls = data.confirmed ? "success" : "warning";
        log(`Human ${result}: "${data.column}" → "${data.mapping}"`, cls);

        if (data.confirmed) {
            // Update the mapping badge to 'human'
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

    function onMemoryUpdate(data) {
        log(`Memory: stored ${data.count || 1} new mapping(s)`, "memory");
    }

    function onDeployComplete(data) {
        log(`Deployed ${data.records} records → ${data.target || "Google Sheets"}`, "deploy");
        if (data.url) {
            log(`Sheet URL: ${data.url}`, "deploy");
        }
    }

    function onReset() {
        state.currentPhase = null;
        state.activeStep = null;
        state.phases[1] = { client: "Acme Corp", mappings: [], calls: 0, memoryHits: 0, complete: false };
        state.phases[2] = { client: "Globex Inc", mappings: [], calls: 0, memoryHits: 0, complete: false };
        resetSteps();
        renderMappings(1);
        renderMappings(2);
        renderStats(1);
        renderStats(2);
        dom.phase1.card.style.opacity = "1";
        dom.phase2.card.style.opacity = "1";
        dom.eventLog.innerHTML = "";
        log("Dashboard reset — waiting for demo...", "info");
    }

    // ── Renderers ──────────────────────────────────────

    function resetSteps() {
        Object.values(dom.steps).forEach((el) => {
            if (el) {
                el.classList.remove("active", "complete", "skipped");
            }
        });
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
                `<span class="mapping-source">${esc(m.source)}</span>` +
                `<span class="mapping-arrow">→</span>` +
                `<span class="mapping-target">${esc(m.target)}</span>` +
                `<span class="mapping-badge ${badge}">${badge}</span>`;

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

    // ── Logging ────────────────────────────────────────

    function log(message, cls) {
        const entry = document.createElement("div");
        entry.className = "log-entry";

        const now = new Date();
        const ts = now.toLocaleTimeString("en-US", { hour12: false });

        entry.innerHTML =
            `<span class="log-time">${ts}</span>` +
            `<span class="log-msg ${cls || ""}">${esc(message)}</span>`;

        dom.eventLog.appendChild(entry);
        dom.eventLog.scrollTop = dom.eventLog.scrollHeight;

        // Keep last 100 entries
        while (dom.eventLog.children.length > 100) {
            dom.eventLog.removeChild(dom.eventLog.firstChild);
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
        log("Dashboard loaded — connecting...", "info");
        connect();
    });
})();
