"""Flask webhook server for Plivo voice call callbacks, mock client portals,
and the live demo dashboard with SSE.

Routes:
- /plivo/answer    — Plivo answer callback (multi-round speech+DTMF)
- /plivo/input     — Plivo speech/DTMF input callback
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
import re
import sys
import time

# Ensure project root is in path when running as script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, Response, render_template, redirect, url_for
from plivo import plivoxml

import threading

from src.teacher import get_call_session, set_mapping_response, mark_session_complete
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


# ── Speech Parsing Helpers ──────────────────────────────

_CONFIRM_WORDS = {"yes", "yeah", "yep", "correct", "right", "confirmed", "affirmative", "sure", "okay"}
_REJECT_WORDS = {"no", "nope", "wrong", "incorrect", "negative", "reject"}

# Patterns for extracting a corrected field name from speech
_CORRECTION_PATTERNS = [
    r"(?:should be|change to|map to|it's|it is|use|make it|that's)\s+(.+)",
    r"(?:no|nope|wrong)[,.\s]+(?:it's|it should be|use|map to|that's)\s+(.+)",
]


def _extract_field_from_speech(text: str, target_fields: list[str]) -> str | None:
    """Fuzzy-match a target field name from spoken text.

    Handles:
    - Exact match: "email"
    - Underscores as spaces: "email address" -> "email_address"
    - Substring match: "the email field" -> "email"
    - Correction phrases: "should be email_address" -> "email_address"
    """
    if not text or not target_fields:
        return None

    text_lower = text.lower().strip()

    # Try extracting the field name from correction phrases first
    candidate = text_lower
    for pattern in _CORRECTION_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            candidate = match.group(1).strip().rstrip(".")
            break

    # Clean up: remove articles, extra spaces
    candidate = re.sub(r"\b(the|a|an|field|column)\b", "", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)

    # Build lookup: field name -> normalized forms
    for field_name in target_fields:
        field_lower = field_name.lower()
        # Exact match
        if candidate == field_lower:
            return field_name
        # Underscore-as-space match: "email address" matches "email_address"
        if candidate == field_lower.replace("_", " "):
            return field_name
        # Space-as-underscore: "email_address" matches "email_address"
        if candidate.replace(" ", "_") == field_lower:
            return field_name

    # Substring match: does the candidate contain a field name?
    for field_name in target_fields:
        field_lower = field_name.lower()
        if field_lower in candidate or field_lower.replace("_", " ") in candidate:
            return field_name

    # Reverse substring: does any field name contain the candidate?
    if len(candidate) >= 3:
        for field_name in target_fields:
            if candidate in field_name.lower() or candidate in field_name.lower().replace("_", " "):
                return field_name

    return None


_MIN_SPEECH_CONFIDENCE = 0.4  # Ignore speech below this confidence (ambient noise)


def _parse_human_response(
    digits: str,
    speech_text: str,
    target_fields: list[str],
    suggested_mapping: str,
    confidence: float | None = None,
) -> dict:
    """Classify the human's response.

    Returns:
        {"action": "confirmed"|"rejected"|"corrected"|"unclear", "corrected_to": str|None}
    """
    # DTMF always takes priority — unambiguous button press
    if digits == "1":
        return {"action": "confirmed", "corrected_to": None}
    if digits == "2":
        return {"action": "rejected", "corrected_to": None}

    # Speech processing — gate on confidence to filter ambient noise
    if not speech_text or not speech_text.strip():
        return {"action": "unclear", "corrected_to": None}

    # If Plivo gave us a confidence score and it's too low, treat as noise
    if confidence is not None and confidence < _MIN_SPEECH_CONFIDENCE:
        app.logger.info(
            "Ignoring low-confidence speech (%.2f < %.2f): %r",
            confidence, _MIN_SPEECH_CONFIDENCE, speech_text,
        )
        return {"action": "unclear", "corrected_to": None}

    text_lower = speech_text.lower().strip()

    # Check for simple confirm/reject first
    words = set(re.split(r"[\s,.\-!?]+", text_lower))
    if words & _CONFIRM_WORDS and not (words & _REJECT_WORDS):
        return {"action": "confirmed", "corrected_to": None}
    if words & _REJECT_WORDS:
        # Check if they also provided a correction
        field_match = _extract_field_from_speech(text_lower, target_fields)
        if field_match and field_match.lower() != suggested_mapping.lower():
            return {"action": "corrected", "corrected_to": field_match}
        return {"action": "rejected", "corrected_to": None}

    # Not a clear yes/no — try to extract a field name (implicit correction)
    field_match = _extract_field_from_speech(text_lower, target_fields)
    if field_match and field_match.lower() != suggested_mapping.lower():
        return {"action": "corrected", "corrected_to": field_match}

    return {"action": "unclear", "corrected_to": None}


# ── Plivo Webhook Routes ────────────────────────────────

_MAX_RETRIES = 2  # Max times to retry a question before auto-confirming


@app.route("/plivo/answer", methods=["GET", "POST"])
def answer_call():
    """Handle Plivo answer callback — speak the current question and collect speech+DTMF."""
    session_id = request.args.get("session_id", "")
    index = int(request.args.get("index", "0"))
    retry = int(request.args.get("retry", "0"))

    session = get_call_session(session_id)
    if not session or index >= len(session.questions):
        response = plivoxml.ResponseElement()
        response.add(plivoxml.SpeakElement(
            "Sorry, there was an error with this call. Goodbye."
        ))
        return Response(response.to_string(), mimetype="text/xml")

    question = session.questions[index]
    total = len(session.questions)

    # Build the spoken prompt — split into two parts:
    #   1. The question itself (spoken BEFORE GetInput, so it plays fully
    #      without ambient noise triggering barge-in / early input detection)
    #   2. A short instruction inside GetInput (plays right before listening)
    if index == 0 and retry == 0:
        intro = (
            f"Hello, this is the FDE agent. "
            f"I have {total} mapping{'s' if total > 1 else ''} to verify with you. "
        )
    elif retry > 0:
        intro = "Let me repeat. "
    else:
        intro = f"Next question, {index + 1} of {total}. "

    question_text = (
        f"{intro}"
        f"I found a column called {question.source_column}. "
        f"I think it maps to {question.suggested_mapping}."
    )
    input_prompt = "Press 1 for yes, 2 for no, or say the correct field name."

    response = plivoxml.ResponseElement()

    # Speak the full question first — no input detection active, so ambient
    # noise cannot interrupt it.
    response.add(plivoxml.SpeakElement(question_text))

    action_url = (
        f"{request.host_url}plivo/input"
        f"?session_id={session_id}&index={index}&retry={retry}"
    )

    # Now open GetInput to listen — only the short instruction prompt plays
    # while the speech/DTMF engine is active.
    get_input = plivoxml.GetInputElement(
        action=action_url,
        method="POST",
        input_type="dtmf speech",
        execution_timeout="15",
        digit_end_timeout="10",
        speech_end_timeout="3",
        speech_model="phone_call",
        redirect=True,
    )
    get_input.add_speak(content=input_prompt)
    response.add(get_input)

    # Fallback if GetInput times out with no input at all:
    # increment retry and try again, or auto-confirm and move on.
    next_retry = retry + 1
    if next_retry > _MAX_RETRIES:
        # Auto-confirm after max retries and move to next question
        response.add(plivoxml.SpeakElement(
            f"No response received. I'll confirm {question.source_column} "
            f"maps to {question.suggested_mapping} and move on."
        ))
        # We need to record this and chain to next — use a redirect to a
        # special auto-confirm path via /plivo/input with autoconfirm flag
        auto_url = (
            f"{request.host_url}plivo/input"
            f"?session_id={session_id}&index={index}&autoconfirm=1"
        )
        response.add(plivoxml.RedirectElement(auto_url))
    else:
        fallback_url = (
            f"{request.host_url}plivo/answer"
            f"?session_id={session_id}&index={index}&retry={next_retry}"
        )
        response.add(plivoxml.SpeakElement(
            "I didn't hear anything. Let me repeat."
        ))
        response.add(plivoxml.RedirectElement(fallback_url))

    return Response(response.to_string(), mimetype="text/xml")


@app.route("/plivo/input", methods=["GET", "POST"])
def handle_input():
    """Handle speech/DTMF input from the human for one question."""
    session_id = request.args.get("session_id", "")
    index = int(request.args.get("index", "0"))
    retry = int(request.args.get("retry", "0"))
    autoconfirm = request.args.get("autoconfirm", "")

    digits = request.form.get("Digits", "")
    speech_text = request.form.get("Speech", "") or request.form.get("SpeechText", "")
    confidence_str = request.form.get("Confidence", "")
    confidence = float(confidence_str) if confidence_str else None

    # Log what Plivo actually sent for debugging
    app.logger.info(
        "Plivo input: session=%s index=%s digits=%r speech=%r confidence=%s autoconfirm=%s form_keys=%s",
        session_id, index, digits, speech_text, confidence_str, autoconfirm,
        list(request.form.keys()),
    )

    session = get_call_session(session_id)
    if not session or index >= len(session.questions):
        response = plivoxml.ResponseElement()
        response.add(plivoxml.SpeakElement("Session error. Goodbye."))
        return Response(response.to_string(), mimetype="text/xml")

    question = session.questions[index]
    total = len(session.questions)

    # Handle auto-confirm (retry limit exceeded or explicit flag)
    if autoconfirm == "1":
        parsed = {"action": "confirmed", "corrected_to": None}
    else:
        # Parse the response — pass confidence so low-confidence noise is ignored
        parsed = _parse_human_response(
            digits, speech_text, session.target_fields, question.suggested_mapping,
            confidence=confidence,
        )

    response = plivoxml.ResponseElement()

    if parsed["action"] == "unclear":
        next_retry = retry + 1
        if next_retry > _MAX_RETRIES:
            # Too many retries — auto-confirm and move on
            app.logger.info("Max retries reached for index=%s, auto-confirming", index)
            parsed = {"action": "confirmed", "corrected_to": None}
            response.add(plivoxml.SpeakElement(
                f"I'll go ahead and confirm {question.source_column} "
                f"maps to {question.suggested_mapping}."
            ))
            # Fall through to record + chain logic below
        else:
            # Retry: redirect back to the same question
            response.add(plivoxml.SpeakElement(
                "I didn't quite catch that. Let me ask again."
            ))
            retry_url = (
                f"{request.host_url}plivo/answer"
                f"?session_id={session_id}&index={index}&retry={next_retry}"
            )
            response.add(plivoxml.RedirectElement(retry_url))
            return Response(response.to_string(), mimetype="text/xml")

    # Record the response
    set_mapping_response(
        session_id=session_id,
        index=index,
        response=parsed["action"],
        corrected_to=parsed.get("corrected_to"),
        speech_text=speech_text or None,
        confidence=confidence,
    )

    # Emit event for dashboard
    emit_event("phone_response", {
        "session_id": session_id,
        "question_index": index,
        "total_questions": total,
        "column": question.source_column,
        "mapping": question.suggested_mapping,
        "confirmed": parsed["action"] in ("confirmed", "corrected"),
        "corrected": parsed["action"] == "corrected",
        "corrected_to": parsed.get("corrected_to"),
        "method": "speech" if speech_text else "dtmf",
    })

    # Speak acknowledgment (only if we haven't already spoken above)
    if autoconfirm != "1" and not (retry > 0 and parsed["action"] == "confirmed"):
        if parsed["action"] == "confirmed":
            response.add(plivoxml.SpeakElement(
                f"Got it. Confirmed: {question.source_column} maps to {question.suggested_mapping}."
            ))
        elif parsed["action"] == "corrected":
            corrected_to = parsed["corrected_to"]
            response.add(plivoxml.SpeakElement(
                f"Got it. I'll map {question.source_column} to {corrected_to} instead."
            ))
        elif parsed["action"] == "rejected":
            response.add(plivoxml.SpeakElement(
                f"Understood. I will skip the mapping for {question.source_column}."
            ))

    # Chain to next question or end
    next_index = index + 1
    if next_index < total:
        next_url = (
            f"{request.host_url}plivo/answer"
            f"?session_id={session_id}&index={next_index}&retry=0"
        )
        response.add(plivoxml.RedirectElement(next_url))
    else:
        response.add(plivoxml.SpeakElement(
            "That's all the questions. Thank you for your help! Goodbye."
        ))
        mark_session_complete(session_id)

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


# ── Landing Page ────────────────────────────────────────

@app.route("/", methods=["GET"])
def landing():
    """Startup landing page."""
    return render_template("landing.html")


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
