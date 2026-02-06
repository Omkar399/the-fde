/**
 * THE FDE - Live Dashboard Client
 * Features: SSE, ApexCharts, Neural Visualizer, Audio Synthesis, Interactive Controls
 * Product Polish: Particles, Tour, Confetti, Toasts
 */

(function () {
    "use strict";

    // ── Audio Engine ───────────────────────────────────
    class AudioEngine {
        constructor() {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.ctx.createGain();
            this.masterGain.gain.value = 0.3; // Default volume
            this.masterGain.connect(this.ctx.destination);
            this.enabled = true;
        }

        resume() {
            if (this.ctx.state === 'suspended') this.ctx.resume();
        }

        playTone(freq, type, duration, startTime = 0) {
            if (!this.enabled) return;
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            
            osc.type = type;
            osc.frequency.setValueAtTime(freq, this.ctx.currentTime + startTime);
            
            gain.gain.setValueAtTime(0.5, this.ctx.currentTime + startTime);
            gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + startTime + duration);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            
            osc.start(this.ctx.currentTime + startTime);
            osc.stop(this.ctx.currentTime + startTime + duration);
        }

        playProcessing() {
            this.playTone(800 + Math.random() * 400, 'sine', 0.1);
        }

        playBrainThought() {
            this.playTone(300, 'triangle', 0.15);
            this.playTone(400, 'sine', 0.15, 0.05);
        }

        playSuccess() {
            this.playTone(600, 'sine', 0.3);
            this.playTone(900, 'sine', 0.4, 0.1);
        }

        playAlert() {
            this.playTone(200, 'square', 0.3);
            this.playTone(180, 'square', 0.3, 0.15);
        }

        playConnect() {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.frequency.setValueAtTime(200, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(800, this.ctx.currentTime + 0.5);
            gain.gain.setValueAtTime(0, this.ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.5, this.ctx.currentTime + 0.1);
            gain.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 0.5);
            osc.connect(gain);
            gain.connect(this.masterGain);
            osc.start();
            osc.stop(this.ctx.currentTime + 0.5);
        }
    }

    const audio = new AudioEngine();

    // ── State ──────────────────────────────────────────
    const state = {
        connected: false,
        currentPhase: null,
        activeStep: null,
        phases: {
            1: { 
                client: "Acme Corp", 
                mappings: [], 
                calls: 0, 
                memoryHits: 0,
                callHistory: [0,0,0,0,0,0,0,0,0,0],
                memoryHistory: [0,0,0,0,0,0,0,0,0,0]
            },
            2: { 
                client: "Globex Inc", 
                mappings: [], 
                calls: 0, 
                memoryHits: 0,
                callHistory: [0,0,0,0,0,0,0,0,0,0],
                memoryHistory: [0,0,0,0,0,0,0,0,0,0]
            },
        },
        charts: {}
    };

    // ── DOM refs ───────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    
    const dom = {
        statusIndicator: $(".status-indicator"),
        liveText: $(".live-text"),
        neural: {
            container: $(".neural-visualizer"),
            text: $("#ai-thought"),
            fill: $(".gauge-fill")
        },
        steps: {
            scrape: $("#step-scrape"),
            analyze: $("#step-analyze"),
            call: $("#step-call"),
            learn: $("#step-learn"),
            deploy: $("#step-deploy"),
        },
        phase1: {
            widget: $("#phase-1"),
            mappings: $("#phase-1-mappings"),
            calls: $("#phase-1-calls"),
            memory: $("#phase-1-memory"),
            statusPill: $("#phase-1 .status-pill")
        },
        phase2: {
            widget: $("#phase-2"),
            mappings: $("#phase-2-mappings"),
            calls: $("#phase-2-calls"),
            memory: $("#phase-2-memory"),
            statusPill: $("#phase-2 .status-pill")
        },
        eventLog: $("#event-log"),
        controls: {
            reset: $("#btn-reset"),
            startP1: $("#btn-start-p1"),
            startP2: $("#btn-start-p2"),
            tour: $("#btn-tour")
        }
    };

    // ── Initialization ─────────────────────────────────
    
    function initParticles() {
        if (window.tsParticles) {
            tsParticles.load("particles-js", {
                background: { color: { value: "transparent" } },
                fpsLimit: 60,
                interactivity: {
                    events: {
                        onHover: { enable: true, mode: "grab" },
                        resize: true
                    },
                    modes: { grab: { distance: 140, links: { opacity: 1 } } }
                },
                particles: {
                    color: { value: "#5E6AD2" },
                    links: {
                        color: "#5E6AD2",
                        distance: 120,
                        enable: true,
                        opacity: 0.2,
                        width: 1
                    },
                    move: {
                        direction: "none",
                        enable: true,
                        outModes: { default: "bounce" },
                        random: false,
                        speed: 1,
                        straight: false
                    },
                    number: { density: { enable: true, area: 800 }, value: 40 },
                    opacity: { value: 0.5 },
                    shape: { type: "circle" },
                    size: { value: { min: 1, max: 3 } }
                },
                detectRetina: true
            });
        }
    }

    // ── Chart Config ───────────────────────────────────
    const sparklineOptions = (color) => ({
        series: [{ data: [0,0,0,0,0,0,0,0,0,0] }],
        chart: {
            type: 'area',
            height: 40,
            sparkline: { enabled: true },
            animations: { enabled: true, easing: 'easeinout', speed: 800 }
        },
        stroke: { curve: 'smooth', width: 2 },
        fill: { opacity: 0.3 },
        colors: [color],
        tooltip: { fixed: { enabled: false }, x: { show: false }, y: { title: { formatter: () => '' } }, marker: { show: false } }
    });

    function initCharts() {
        state.charts.p1Calls = new ApexCharts($("#chart-calls-1"), sparklineOptions('#D29922'));
        state.charts.p1Calls.render();
        state.charts.p1Memory = new ApexCharts($("#chart-memory-1"), sparklineOptions('#5E6AD2'));
        state.charts.p1Memory.render();
        state.charts.p2Calls = new ApexCharts($("#chart-calls-2"), sparklineOptions('#D29922'));
        state.charts.p2Calls.render();
        state.charts.p2Memory = new ApexCharts($("#chart-memory-2"), sparklineOptions('#5E6AD2'));
        state.charts.p2Memory.render();
    }

    function updateCharts(phase) {
        const p = state.phases[phase];
        if (phase === 1) {
            state.charts.p1Calls.updateSeries([{ data: p.callHistory }]);
            state.charts.p1Memory.updateSeries([{ data: p.memoryHistory }]);
        } else {
            state.charts.p2Calls.updateSeries([{ data: p.callHistory }]);
            state.charts.p2Memory.updateSeries([{ data: p.memoryHistory }]);
        }
    }

    // ── Product Tour ───────────────────────────────────
    function initTour() {
        const driver = window.driver.js.driver;
        const tour = driver({
            showProgress: true,
            steps: [
                { popover: { title: 'Welcome to The FDE', description: 'This is the autonomous onboarding agent dashboard.' } },
                { element: '#neural-section', popover: { title: 'Neural Link', description: 'Visualizes the AI\'s real-time thought process and confidence levels.' } },
                { element: '#pipeline-section', popover: { title: 'Execution Pipeline', description: 'Tracks the 5-step agent lifecycle: Scrape, Analyze, Call, Learn, Deploy.' } },
                { element: '#mission-grid', popover: { title: 'Mission Control', description: 'Monitors active client onboarding tasks and performance metrics.' } },
                { element: '#controls-area', popover: { title: 'Interactive Controls', description: 'Use these buttons to start the demo scenarios manually.' } },
                { element: '#logs-section', popover: { title: 'System Events', description: 'Live stream of all system activities with detailed JSON payloads.' } },
            ]
        });

        dom.controls.tour.addEventListener("click", () => tour.drive());
    }

    // ── Control Handlers ───────────────────────────────
    function bindControls() {
        dom.controls.reset.addEventListener("click", () => {
            audio.resume();
            fetch("/demo/reset", { method: "POST" })
                .then(() => {
                    log("Reset command sent", "system");
                    audio.playProcessing();
                    Notiflix.Notify.info('System Reset Initiated');
                });
        });

        dom.controls.startP1.addEventListener("click", () => {
            audio.resume();
            fetch("/demo/start", { 
                method: "POST", 
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ phase: 1 })
            }).then(() => {
                log("Starting Phase 1 sequence...", "system");
                Notiflix.Notify.success('Starting Phase 1: The Novice');
            });
        });

        dom.controls.startP2.addEventListener("click", () => {
            audio.resume();
            fetch("/demo/start", { 
                method: "POST", 
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ phase: 2 })
            }).then(() => {
                log("Starting Phase 2 sequence...", "system");
                Notiflix.Notify.success('Starting Phase 2: The Expert');
            });
        });
    }

    // ── SSE Connection ─────────────────────────────────
    function connect() {
        const evtSource = new EventSource("/dashboard/events");

        evtSource.onopen = function () {
            state.connected = true;
            dom.statusIndicator.classList.add("connected");
            dom.liveText.textContent = "LIVE";
            log("Connected to event stream", "system");
            audio.resume();
            audio.playConnect();
            Notiflix.Notify.success('Uplink Established');
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
            dom.statusIndicator.classList.remove("connected");
            dom.liveText.textContent = "DISCONNECTED";
            Notiflix.Notify.failure('Uplink Lost');
        };
    }

    // ── Event Handler ──────────────────────────────────
    function handleEvent(event) {
        const { type, data } = event;

        if (['step_start', 'analyze', 'learn'].includes(type) || (data && data.step === 'analyze')) {
            activateNeural(true, "Analyzing Data Patterns...");
        } else if (type === 'brain_thought') {
            activateNeural(true, data.thought, data.confidence);
            audio.playBrainThought();
        } else if (type === 'phone_call') {
            activateNeural(true, "Awaiting Human Input...", 10);
            audio.playAlert();
            Notiflix.Notify.warning('Human Intervention Required');
        } else {
            activateNeural(false);
        }

        if (type !== 'brain_thought') audio.playProcessing();

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
            case "brain_thought":
                break;
            default:
                log(data.message || type, "info", data);
        }
    }

    // ── Logic ──────────────────────────────────────────

    function activateNeural(active, text, confidence = 0) {
        if (active) {
            dom.neural.container.classList.add("active");
            if (text) dom.neural.text.textContent = text;
            const target = confidence || Math.floor(Math.random() * 40) + 50; 
            dom.neural.fill.style.width = `${target}%`;
        } else {
            dom.neural.container.classList.remove("active");
            dom.neural.text.textContent = "Idle...";
            dom.neural.fill.style.width = "0%";
        }
    }

    function onPhaseStart(data) {
        state.currentPhase = data.phase;
        resetSteps();
        log(`Phase ${data.phase} started — ${data.client}`, "system");

        if (data.phase === 1) {
            activateWidget(dom.phase1);
            dimWidget(dom.phase2);
            dom.phase1.mappings.innerHTML = "";
        } else {
            dimWidget(dom.phase1);
            activateWidget(dom.phase2);
            dom.phase2.mappings.innerHTML = "";
        }
    }

    function onPhaseComplete(data) {
        state.phases[data.phase].complete = true;
        resetSteps();
        log(`Phase ${data.phase} complete!`, "success");
        audio.playSuccess();
        
        // Trigger Confetti
        if (window.confetti) {
            confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
        }
        Notiflix.Notify.success(`Phase ${data.phase} Complete!`);

        const refs = data.phase === 1 ? dom.phase1 : dom.phase2;
        refs.statusPill.textContent = "Complete";
        refs.statusPill.style.color = "var(--success)";
        refs.statusPill.style.borderColor = "var(--success)";
    }

    function onStepStart(data) {
        state.activeStep = data.step;
        Object.values(dom.steps).forEach((el) => {
            if (el && !el.classList.contains("complete")) el.classList.remove("active");
        });
        const stepEl = dom.steps[data.step];
        if (stepEl) {
            stepEl.classList.remove("skipped");
            stepEl.classList.add("active");
        }
        
        let type = "info";
        if (data.step === 'analyze') type = "brain";
        if (data.step === 'call') type = "phone";
        
        log(data.message || `Step: ${data.step}`, type);
    }

    function onStepComplete(data) {
        const stepEl = dom.steps[data.step];
        if (stepEl) {
            stepEl.classList.remove("active");
            stepEl.classList.add("complete");
        }
    }

    function onMappingResult(data) {
        const phase = state.currentPhase || 1;
        const phaseData = state.phases[phase];
        phaseData.mappings.push(data);

        if (data.from_memory) {
            phaseData.memoryHits++;
            phaseData.memoryHistory.push(phaseData.memoryHits);
            phaseData.memoryHistory.shift();
            activateNeural(true, "Memory Match Found", 95);
            audio.playSuccess();
            Notiflix.Notify.info('Recall: Pattern matched from memory');
        } else {
            activateNeural(true, "Reasoning...", 45);
        }

        renderMappings(phase);
        updateCharts(phase);
        
        const type = data.from_memory ? "memory" : "brain";
        log(`Mapped ${data.source} → ${data.target}`, type, data);
        setTimeout(() => activateNeural(false), 800);
    }

    function onPhoneCall(data) {
        const phase = state.currentPhase || 1;
        state.phases[phase].calls++;
        const p = state.phases[phase];
        p.callHistory.push(p.calls);
        p.callHistory.shift();
        updateCharts(phase);
        renderStats(phase);
        log(`Calling human: "${data.column}" → "${data.mapping}"`, "phone", data);
    }

    function onPhoneResponse(data) {
        const cls = data.confirmed ? "success" : "warning";
        log(`Human response: ${data.confirmed ? "CONFIRMED" : "REJECTED"}`, cls, data);
        if (data.confirmed) audio.playSuccess();

        if (data.confirmed) {
            const phase = state.currentPhase || 1;
            const phaseData = state.phases[phase];
            const existing = phaseData.mappings.find(m => m.source === data.column && m.target === data.mapping);
            if (!existing) {
                phaseData.mappings.push({
                    source: data.column,
                    target: data.mapping,
                    badge: "human"
                });
            } else {
                existing.badge = "human";
            }
            renderMappings(phase);
        }
    }

    function onMemoryUpdate(data) {
        log(`Consolidated ${data.count || 1} new pattern(s) to Long-term Memory`, "memory");
        activateNeural(true, "Learning...", 100);
        setTimeout(() => activateNeural(false), 1000);
    }

    function onDeployComplete(data) {
        log(`Deployed ${data.records} records to ${data.target || "Google Sheets"}`, "deploy", data);
        audio.playSuccess();
        Notiflix.Notify.success('Deployment Successful');
    }

    function onReset() {
        state.currentPhase = null;
        state.activeStep = null;
        state.phases[1] = { client: "Acme Corp", mappings: [], calls: 0, memoryHits: 0, complete: false, callHistory: Array(10).fill(0), memoryHistory: Array(10).fill(0) };
        state.phases[2] = { client: "Globex Inc", mappings: [], calls: 0, memoryHits: 0, complete: false, callHistory: Array(10).fill(0), memoryHistory: Array(10).fill(0) };
        resetSteps();
        dom.phase1.mappings.innerHTML = '<div class="empty-state">Waiting for agent...</div>';
        dom.phase2.mappings.innerHTML = '<div class="empty-state">Waiting for agent...</div>';
        renderStats(1);
        renderStats(2);
        if (state.charts.p1Calls) {
            state.charts.p1Calls.updateSeries([{ data: Array(10).fill(0) }]);
            state.charts.p1Memory.updateSeries([{ data: Array(10).fill(0) }]);
            state.charts.p2Calls.updateSeries([{ data: Array(10).fill(0) }]);
            state.charts.p2Memory.updateSeries([{ data: Array(10).fill(0) }]);
        }
        dom.phase1.widget.classList.remove("active", "dimmed");
        dom.phase2.widget.classList.remove("active", "dimmed");
        dom.phase1.statusPill.textContent = "Waiting";
        dom.phase2.statusPill.textContent = "Pending";
        dom.phase1.statusPill.style.color = "";
        dom.phase1.statusPill.style.borderColor = "";
        dom.phase2.statusPill.style.color = "";
        dom.phase2.statusPill.style.borderColor = "";
        dom.eventLog.innerHTML = "";
        log("Dashboard reset — waiting for demo...", "system");
        audio.playProcessing();
    }

    // ── Renderers ──────────────────────────────────────

    function resetSteps() {
        Object.values(dom.steps).forEach((el) => {
            if (el) el.classList.remove("active", "complete", "skipped");
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
            const badgeType = m.badge || (m.from_memory ? "memory" : "ai");
            row.innerHTML =
                `<span class="mapping-source" title="${esc(m.source)}">${esc(m.source)}</span>` +
                `<span class="mapping-arrow">→</span>` +
                `<span class="mapping-target" title="${esc(m.target)}">` +
                    `${esc(m.target)}` +
                    `<span class="mapping-tag tag-${badgeType}">${badgeType}</span>` +
                `</span>`;
            container.appendChild(row);
        });
        
        container.scrollTop = container.scrollHeight;
        renderStats(phase);
    }

    function renderStats(phase) {
        const phaseData = state.phases[phase];
        const refs = phase === 1 ? dom.phase1 : dom.phase2;
        if (refs.calls) refs.calls.textContent = phaseData.calls;
        if (refs.memory) refs.memory.textContent = phaseData.memoryHits;
    }

    function activateWidget(refs) {
        refs.widget.classList.remove("dimmed");
        refs.widget.classList.add("active");
        refs.statusPill.textContent = "Processing";
        refs.statusPill.style.color = "var(--accent-primary)";
        refs.statusPill.style.borderColor = "var(--accent-primary)";
    }

    function dimWidget(refs) {
        refs.widget.classList.remove("active");
        refs.widget.classList.add("dimmed");
    }

    // ── Logging ────────────────────────────────────────

    function log(message, type = "info", jsonData = null) {
        const entry = document.createElement("div");
        entry.className = `log-entry type-${type}`;
        const now = new Date();
        const ts = now.toLocaleTimeString("en-US", { hour12: false });
        
        let jsonHtml = "";
        if (jsonData) {
            const jsonStr = JSON.stringify(jsonData, null, 2);
            jsonHtml = `<pre class="language-json"><code class="language-json">${esc(jsonStr)}</code></pre>`;
        }

        entry.innerHTML =
            `<span class="log-time">${ts}</span>` +
            `<div class="log-content">` +
                `<span class="log-msg ${type}">${esc(message)}</span>` +
                jsonHtml +
            `</div>`;

        dom.eventLog.appendChild(entry);
        dom.eventLog.scrollTop = dom.eventLog.scrollHeight;

        if (jsonData && window.Prism) {
            Prism.highlightAllUnder(entry);
        }

        while (dom.eventLog.children.length > 50) {
            dom.eventLog.removeChild(dom.eventLog.firstChild);
        }
    }

    function esc(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Init ───────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", function () {
        initCharts();
        bindControls();
        initParticles();
        initTour();
        tippy('[data-tippy-content]'); 
        
        // Init Notiflix
        if (window.Notiflix) {
            Notiflix.Notify.init({ position: 'right-top', cssAnimationStyle: 'zoom' });
        }

        log("System initialized. Waiting for uplink...", "system");
        connect();
        
        // Initial interaction to unlock AudioContext
        document.body.addEventListener('click', () => {
            audio.resume();
        }, { once: true });
    });
})();
