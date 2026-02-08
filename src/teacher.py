"""Plivo Voice Teacher - The FDE's feedback mechanism for uncertain mappings.

When the agent encounters columns it can't confidently map, it calls
the human engineer via Plivo voice call to get ground truth.  A single
call walks through ALL uncertain mappings using multi-round speech
conversation (STT with DTMF fallback).
"""

import time
import uuid
import threading
from dataclasses import dataclass, field

import plivo
from rich.console import Console

from src.config import Config

console = Console()

# ── Data structures ────────────────────────────────────


@dataclass
class MappingQuestion:
    """One uncertain mapping being asked about during a phone call."""

    source_column: str
    suggested_mapping: str
    response: str | None = None        # "confirmed" | "rejected" | "corrected"
    corrected_to: str | None = None    # target field name if corrected
    speech_text: str | None = None     # raw speech transcript
    confidence: float | None = None    # STT confidence score


@dataclass
class CallSession:
    """Tracks all questions for a single phone call."""

    questions: list[MappingQuestion] = field(default_factory=list)
    current_index: int = 0
    target_fields: list[str] = field(default_factory=list)
    complete: bool = False


# ── Module-level shared state ──────────────────────────

_call_sessions: dict[str, CallSession] = {}
_session_lock = threading.Lock()


def create_call_session(
    session_id: str,
    questions: list[MappingQuestion],
    target_fields: list[str],
) -> None:
    """Create a session before the Plivo call starts."""
    with _session_lock:
        _call_sessions[session_id] = CallSession(
            questions=questions,
            current_index=0,
            target_fields=target_fields,
            complete=False,
        )


def set_mapping_response(
    session_id: str,
    index: int,
    response: str,
    corrected_to: str | None = None,
    speech_text: str | None = None,
    confidence: float | None = None,
) -> None:
    """Called by the webhook when the human answers one question."""
    with _session_lock:
        session = _call_sessions.get(session_id)
        if not session or index >= len(session.questions):
            return
        q = session.questions[index]
        q.response = response
        q.corrected_to = corrected_to
        q.speech_text = speech_text
        q.confidence = confidence


def mark_session_complete(session_id: str) -> None:
    """Mark a call session as fully complete (all questions answered or call ended)."""
    with _session_lock:
        session = _call_sessions.get(session_id)
        if session:
            session.complete = True


def get_call_session(session_id: str) -> CallSession | None:
    """Read a session (for webhook use)."""
    with _session_lock:
        return _call_sessions.get(session_id)


def pop_call_session(session_id: str) -> CallSession | None:
    """Remove and return a session (for cleanup)."""
    with _session_lock:
        return _call_sessions.pop(session_id, None)


# ── Teacher class ──────────────────────────────────────


class Teacher:
    """Plivo-based voice call interface for human-in-the-loop feedback."""

    def __init__(self):
        if not Config.DEMO_MODE:
            self._client = plivo.RestClient(
                auth_id=Config.PLIVO_AUTH_ID,
                auth_token=Config.PLIVO_AUTH_TOKEN,
            )
        else:
            self._client = None

    # ── Public API ─────────────────────────────────────

    def ask_human_batch(
        self,
        uncertain_mappings: list[dict],
        target_fields: list[str],
    ) -> list[dict]:
        """Make ONE phone call covering all uncertain mappings.

        Args:
            uncertain_mappings: list of mapping dicts with 'source_column' and 'target_field'
            target_fields: all valid target field names (for correction matching)

        Returns:
            list of result dicts per mapping:
            {
                "confirmed": bool,
                "target_field": str,
                "corrected": bool,
                "method": str,
                "speech_text": str | None,
            }
        """
        if not uncertain_mappings:
            return []

        if Config.DEMO_MODE:
            return self._mock_ask_batch(uncertain_mappings, target_fields)

        try:
            return self._plivo_call_batch(uncertain_mappings, target_fields)
        except Exception as e:
            console.print(f"  [yellow]Plivo call failed: {e}. Using simulated response.[/yellow]")
            return self._mock_ask_batch(uncertain_mappings, target_fields)

    def ask_human(self, column_name: str, suggested_mapping: str) -> dict:
        """Backward-compatible single-mapping wrapper around ask_human_batch."""
        results = self.ask_human_batch(
            [{"source_column": column_name, "target_field": suggested_mapping}],
            [suggested_mapping],
        )
        if results:
            r = results[0]
            return {
                "confirmed": r["confirmed"],
                "target_field": r["target_field"],
                "method": r["method"],
            }
        return {"confirmed": False, "target_field": suggested_mapping, "method": "error"}

    # ── Real Plivo call (batch) ────────────────────────

    def _plivo_call_batch(
        self,
        uncertain_mappings: list[dict],
        target_fields: list[str],
    ) -> list[dict]:
        """Make one Plivo voice call that loops through all uncertain mappings."""
        session_id = str(uuid.uuid4())

        questions = [
            MappingQuestion(
                source_column=m["source_column"],
                suggested_mapping=m["target_field"],
            )
            for m in uncertain_mappings
        ]
        create_call_session(session_id, questions, target_fields)

        answer_url = (
            f"{Config.WEBHOOK_BASE_URL}/plivo/answer"
            f"?session_id={session_id}&index=0"
        )

        console.print(
            f"  [magenta]Plivo:[/magenta] Calling {Config.ENGINEER_PHONE_NUMBER} "
            f"({len(questions)} questions)..."
        )

        call = self._client.calls.create(
            from_=Config.PLIVO_PHONE_NUMBER,
            to_=Config.ENGINEER_PHONE_NUMBER,
            answer_url=answer_url,
            answer_method="POST",
        )
        call_uuid = call.request_uuid if hasattr(call, "request_uuid") else "unknown"
        console.print(f"  [magenta]Plivo:[/magenta] Call UUID: {call_uuid}")

        self._wait_for_batch_complete(session_id, timeout=120)

        session = pop_call_session(session_id)
        if session:
            return self._session_to_results(session)

        return [
            {
                "confirmed": False,
                "target_field": m["target_field"],
                "corrected": False,
                "method": "plivo_call",
                "speech_text": None,
            }
            for m in uncertain_mappings
        ]

    def _wait_for_batch_complete(self, session_id: str, timeout: int = 120) -> None:
        """Poll the session until all questions are answered or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            with _session_lock:
                session = _call_sessions.get(session_id)
                if not session:
                    return
                if session.complete:
                    return
            time.sleep(1)

    def _session_to_results(self, session: CallSession) -> list[dict]:
        """Convert a completed CallSession into a list of result dicts."""
        results = []
        for q in session.questions:
            if q.response == "confirmed":
                results.append({
                    "confirmed": True,
                    "target_field": q.suggested_mapping,
                    "corrected": False,
                    "method": "plivo_call",
                    "speech_text": q.speech_text,
                })
                console.print(
                    f"  [green]Human confirmed:[/green] "
                    f"'{q.source_column}' -> '{q.suggested_mapping}'"
                )
            elif q.response == "corrected" and q.corrected_to:
                results.append({
                    "confirmed": True,
                    "target_field": q.corrected_to,
                    "corrected": True,
                    "method": "plivo_call",
                    "speech_text": q.speech_text,
                })
                console.print(
                    f"  [yellow]Human corrected:[/yellow] "
                    f"'{q.source_column}' -> '{q.corrected_to}' "
                    f"(was '{q.suggested_mapping}')"
                )
            else:
                results.append({
                    "confirmed": False,
                    "target_field": q.suggested_mapping,
                    "corrected": False,
                    "method": "plivo_call",
                    "speech_text": q.speech_text,
                })
                console.print(
                    f"  [red]Human rejected:[/red] mapping for '{q.source_column}'"
                )
        return results

    # ── Demo simulation (batch) ────────────────────────

    def _mock_ask_batch(
        self,
        uncertain_mappings: list[dict],
        target_fields: list[str],
    ) -> list[dict]:
        """Simulate a multi-round phone conversation for demo mode.

        First mapping: confirmed.
        Second mapping (if exists): corrected to a different target field (to showcase the feature).
        Remaining: confirmed.
        """
        results = []

        console.print()
        console.print("  [bold magenta]>>> PHONE RINGING... <<<[/bold magenta]")
        console.print(
            f"  [magenta]Plivo:[/magenta] Calling engineer "
            f"({len(uncertain_mappings)} questions in one call)..."
        )
        time.sleep(1)

        for i, m in enumerate(uncertain_mappings):
            src = m["source_column"]
            tgt = m["target_field"]

            console.print(
                f"\n  [magenta]Plivo:[/magenta] Question {i + 1}/{len(uncertain_mappings)}: "
                f"\"Is '{src}' the field '{tgt}'? "
                f"Say yes, no, or the correct field name.\""
            )
            time.sleep(1)

            if i == 1 and len(uncertain_mappings) > 1:
                # Second mapping: simulate a correction
                # Pick a different target field that isn't already the suggestion
                alt = None
                for tf in target_fields:
                    if tf != tgt and not any(
                        r["target_field"] == tf for r in results
                    ):
                        alt = tf
                        break
                if alt:
                    console.print(
                        f"  [magenta]Plivo:[/magenta] Human said: "
                        f"[bold]\"No, that should be {alt}\"[/bold]"
                    )
                    console.print(
                        f"  [yellow]Human corrected:[/yellow] "
                        f"'{src}' -> '{alt}' (was '{tgt}')"
                    )
                    results.append({
                        "confirmed": True,
                        "target_field": alt,
                        "corrected": True,
                        "method": "demo_simulated",
                        "speech_text": f"no that should be {alt}",
                    })
                    time.sleep(0.5)
                    continue

            # Default: confirm
            console.print(
                f"  [magenta]Plivo:[/magenta] Human said: [bold]\"Yes\"[/bold]"
            )
            console.print(
                f"  [green]Human confirmed:[/green] '{src}' -> '{tgt}'"
            )
            results.append({
                "confirmed": True,
                "target_field": tgt,
                "corrected": False,
                "method": "demo_simulated",
                "speech_text": "yes",
            })
            time.sleep(0.5)

        console.print(
            f"\n  [magenta]Plivo:[/magenta] Call complete. "
            f"{len(results)} mappings resolved."
        )
        return results
