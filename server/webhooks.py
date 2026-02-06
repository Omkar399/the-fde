"""Flask webhook server for Plivo voice call callbacks.

This server handles:
- /plivo/answer - Returns XML to speak the question and collect DTMF input
- /plivo/input  - Receives the human's keypress response
"""

from flask import Flask, request, Response
from plivo import plivoxml

from src.teacher import set_human_response

app = Flask(__name__)


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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "fde-webhooks"}


def start_server(port: int = 5000):
    """Start the webhook server."""
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    start_server()
