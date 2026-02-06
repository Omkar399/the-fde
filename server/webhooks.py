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
- /demo/start      — Start the agent (Phase 1 or 2)
- /demo/reset      — Reset agent memory
- /health          — Health check
"""

import csv
import io
import os
import sys
import time
import threading
import json

# Ensure project root is in path when running as script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, Response, render_template, redirect, url_for, jsonify
from plivo import plivoxml

from src.teacher import set_human_response
from server.events import subscribe, unsubscribe, get_history, format_sse, emit_event, reset as reset_events
from src.config import Config

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

def run_agent_phase(phase: int):
    """Run the agent logic in a separate thread."""
    from src.agent import FDEAgent
    agent = FDEAgent()
    
    if phase == 1:
        client_name = "Acme Corp"
        url_key = "acme"
    else:
        client_name = "Globex Inc"
        url_key = "globex"
        
    portal_base = Config.WEBHOOK_BASE_URL.rstrip("/")
    portal_url = f"{portal_base}/portal/{url_key}"
    
    emit_event("phase_start", {"phase": phase, "client": client_name})
    try:
        agent.onboard_client(client_name, portal_url)
        emit_event("phase_complete", {"phase": phase, "client": client_name})
    except Exception as e:
        emit_event("error", {"message": str(e)})
        print(f"Agent Error: {e}")

@app.route("/demo/start", methods=["POST"])
def start_demo():
    """Start the demo agent."""
    data = request.json or {}
    phase = data.get("phase", 1)
    
    thread = threading.Thread(target=run_agent_phase, args=(phase,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "phase": phase})

@app.route("/demo/reset", methods=["POST"])
def reset_demo():
    """Reset agent memory and events."""
    from src.agent import FDEAgent
    agent = FDEAgent()
    agent.reset_memory()
    reset_events()
    emit_event("reset", {})
    return jsonify({"status": "reset"})


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
