"""Flask webhook server for Plivo voice call callbacks, mock client portals,
and the live demo dashboard with SSE.

Routes:
- /plivo/answer    — Plivo answer callback (TwiML-like XML)
- /plivo/input     — Plivo DTMF input callback
- /portal/<client> — Mock enterprise login page
- /portal/<client>/dashboard — Mock data dashboard with CSV table
- /portal/<client>/download  — Raw CSV download
- /dashboard       — Live demo dashboard (dark theme, SSE-driven)
- /dashboard/events — SSE endpoint for real-time pipeline events
- /health          — Health check
"""

import csv
import io
import os
import sys
import time

# Ensure project root is in path when running as script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, Response, render_template, redirect, url_for
from plivo import plivoxml

import threading

from src.teacher import set_human_response
from server.events import emit_event, subscribe, unsubscribe, get_history, format_sse, reset as reset_events
from src.config import Config

# Track demo state
_demo_running = False
_demo_lock = threading.Lock()

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)

# ── Portal Configuration ────────────────────────────────

PORTAL_CONFIGS = {
    "acme": {
        "client_name": "Acme Corp",
        "primary_color": "#003366",
        "csv_file": "client_a_acme.csv",
    },
    "globex": {
        "client_name": "Globex Inc",
        "primary_color": "#336633",
        "csv_file": "client_b_globex.csv",
    },
}


def _load_csv(client_key: str) -> tuple[list[str], list[dict], str]:
    """Load CSV data for a portal client. Returns (columns, rows, raw_csv)."""
    config = PORTAL_CONFIGS.get(client_key)
    if not config:
        return [], [], ""
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "mock", config["csv_file"]
    )
    with open(csv_path, "r") as f:
        raw_csv = f.read()
    reader = csv.DictReader(io.StringIO(raw_csv))
    columns = reader.fieldnames or []
    rows = list(reader)
    return columns, rows, raw_csv


# ── Plivo Webhook Routes ────────────────────────────────

@app.route("/plivo/answer", methods=["GET", "POST"])
def answer_call():
    """Handle Plivo answer callback - speak the question and collect input."""
    column = request.args.get("column", "unknown column")
    mapping = request.args.get("mapping", "unknown field")

    response = plivoxml.ResponseElement()

    # Speak the question
    speak_text = (
        f"Hello, this is the FDE agent. "
        f"I found a data column called {column}. "
        f"I think this maps to the field {mapping}. "
        f"Press 1 if this is correct. Press 2 if this is wrong."
    )

    # Use GetInput to collect DTMF
    get_input = plivoxml.GetInputElement(
        action=f"{request.host_url}plivo/input?column={column}&mapping={mapping}",
        method="POST",
        input_type="dtmf",
        digit_end_timeout="5",
        redirect=True,
    )
    get_input.add_speak(content=speak_text)
    response.add(get_input)

    # If no input, repeat
    response.add(plivoxml.SpeakElement("I didn't receive any input. Goodbye."))

    return Response(response.to_string(), mimetype="text/xml")


@app.route("/plivo/input", methods=["GET", "POST"])
def handle_input():
    """Handle DTMF input from the human."""
    digits = request.form.get("Digits", "")
    call_uuid = request.form.get("CallUUID", "")
    column = request.args.get("column", "")
    mapping = request.args.get("mapping", "")

    response = plivoxml.ResponseElement()

    if digits == "1":
        response.add(plivoxml.SpeakElement(
            f"Got it. Mapping {column} to {mapping}. The agent will learn this. Goodbye."
        ))
        set_human_response(call_uuid, "1")
    elif digits == "2":
        response.add(plivoxml.SpeakElement(
            f"Understood. I will not map {column} to {mapping}. Goodbye."
        ))
        set_human_response(call_uuid, "2")
    else:
        response.add(plivoxml.SpeakElement("Invalid input. Goodbye."))
        set_human_response(call_uuid, "invalid")

    return Response(response.to_string(), mimetype="text/xml")


# ── Mock Portal Routes ──────────────────────────────────

@app.route("/portal/<client_key>", methods=["GET"])
def portal_login(client_key):
    """Show the ugly legacy login page."""
    config = PORTAL_CONFIGS.get(client_key)
    if not config:
        return "Unknown client portal", 404
    return render_template(
        "portal_login.html",
        client_name=config["client_name"],
        client_key=client_key,
        primary_color=config["primary_color"],
    )


@app.route("/portal/<client_key>", methods=["POST"])
def portal_login_submit(client_key):
    """Handle login form submission — always succeeds, redirects to dashboard."""
    config = PORTAL_CONFIGS.get(client_key)
    if not config:
        return "Unknown client portal", 404
    return redirect(url_for("portal_dashboard", client_key=client_key))


@app.route("/portal/<client_key>/dashboard", methods=["GET"])
def portal_dashboard(client_key):
    """Show the data dashboard with CSV table."""
    config = PORTAL_CONFIGS.get(client_key)
    if not config:
        return "Unknown client portal", 404

    columns, rows, _ = _load_csv(client_key)
    return render_template(
        "portal_dashboard.html",
        client_name=config["client_name"],
        client_key=client_key,
        primary_color=config["primary_color"],
        columns=columns,
        rows=rows,
        row_count=len(rows),
        last_updated="11/02/2003 11:30 AM",
    )


@app.route("/portal/<client_key>/download", methods=["GET"])
def portal_download(client_key):
    """Return raw CSV file for download."""
    config = PORTAL_CONFIGS.get(client_key)
    if not config:
        return "Unknown client portal", 404

    _, _, raw_csv = _load_csv(client_key)
    return Response(
        raw_csv,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={client_key}_data.csv"},
    )


# ── Live Dashboard Routes ───────────────────────────────

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Serve the live demo dashboard."""
    return render_template("dashboard.html")


@app.route("/dashboard/events", methods=["GET"])
def dashboard_events():
    """SSE endpoint — streams pipeline events to the dashboard."""
    def event_stream():
        q = subscribe()
        try:
            # Send initial keepalive so the browser fires onopen
            yield ": connected\n\n"

            # Send event history for late joiners
            for event in get_history():
                yield format_sse(event)

            # Stream new events
            while True:
                try:
                    event = q.get(timeout=15)
                    yield format_sse(event)
                except Exception:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            unsubscribe(q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Demo Control Routes ─────────────────────────────────

def _run_demo_background(config=None):
    """Run the full demo pipeline in a background thread."""
    global _demo_running
    try:
        from src.agent import FDEAgent

        config = config or {}
        clients = config.get("clients", [])
        target_fields = config.get("target_fields")

        # Build target_schema override from setup panel fields
        target_schema = None
        if target_fields:
            target_schema = {
                "schema_name": "SaaS CRM Onboarding Schema",
                "description": "User-configured target schema.",
                "fields": {
                    f["name"]: {"type": f.get("type", "string"), "description": f["name"]}
                    for f in target_fields
                },
            }

        agent = FDEAgent(target_schema=target_schema)
        agent.reset_memory()
        reset_events()
        emit_event("reset", {})

        portal_base = Config.WEBHOOK_BASE_URL.rstrip("/")

        # Client 1 defaults
        c1 = clients[0] if len(clients) > 0 else {}
        c1_name = c1.get("name") or "Acme Corp"
        c1_url = c1.get("portal_url") or f"{portal_base}/portal/acme"
        c1_creds = {"username": c1.get("username") or "admin", "password": c1.get("password") or "admin123"} if c1 else None

        # Phase 1: Novice
        emit_event("phase_start", {"phase": 1, "client": c1_name})
        summary_a = agent.onboard_client(
            client_name=c1_name,
            portal_url=c1_url,
            credentials=c1_creds,
        )
        emit_event("phase_complete", {"phase": 1, "client": c1_name, "summary": summary_a})

        # Brief pause between phases
        time.sleep(2)

        # Client 2 defaults
        c2 = clients[1] if len(clients) > 1 else {}
        c2_name = c2.get("name") or "Globex Inc"
        c2_url = c2.get("portal_url") or f"{portal_base}/portal/globex"
        c2_creds = {"username": c2.get("username") or "admin", "password": c2.get("password") or "admin123"} if c2 else None

        # Phase 2: Expert
        emit_event("phase_start", {"phase": 2, "client": c2_name})
        summary_b = agent.onboard_client(
            client_name=c2_name,
            portal_url=c2_url,
            credentials=c2_creds,
        )
        emit_event("phase_complete", {"phase": 2, "client": c2_name, "summary": summary_b})

        emit_event("demo_complete", {
            "phase1_calls": summary_a.get("phone_calls", 0),
            "phase2_calls": summary_b.get("phone_calls", 0),
            "memory_size": agent.memory.count,
            "summaries": {
                "1": summary_a,
                "2": summary_b,
            },
        })

        agent.browser.close()
    except Exception as e:
        emit_event("error", {"message": str(e)})
    finally:
        with _demo_lock:
            _demo_running = False


@app.route("/demo/start", methods=["POST"])
def demo_start():
    """Start the demo pipeline in a background thread."""
    global _demo_running
    with _demo_lock:
        if _demo_running:
            return {"status": "already_running"}, 409
        _demo_running = True

    config = request.get_json(silent=True) or {}
    thread = threading.Thread(target=_run_demo_background, args=(config,), daemon=True)
    thread.start()
    return {"status": "started"}


@app.route("/demo/status", methods=["GET"])
def demo_status():
    """Check if the demo is currently running."""
    return {"running": _demo_running}


# ── Health ──────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "fde-webhooks"}


# ── Server Entry Point ──────────────────────────────────

def start_server(port: int = 5001):
    """Start the webhook server."""
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    start_server()
