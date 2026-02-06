"""Plivo Voice Teacher - The FDE's feedback mechanism for uncertain mappings.

When the agent encounters a column it can't confidently map, it calls
the human engineer via Plivo voice call to get ground truth.
"""

import time
import threading
import plivo
from rich.console import Console

from src.config import Config

console = Console()

# Shared state for collecting human responses via webhook
_pending_responses: dict[str, str | None] = {}
_response_lock = threading.Lock()


def set_human_response(call_id: str, response: str) -> None:
    """Called by the webhook server when a human responds."""
    with _response_lock:
        _pending_responses[call_id] = response


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

    def ask_human(self, column_name: str, suggested_mapping: str) -> dict:
        """Call the human engineer to confirm a mapping.

        Args:
            column_name: The ambiguous source column
            suggested_mapping: The agent's best guess for the target field

        Returns:
            dict with keys: confirmed (bool), target_field (str), method (str)
        """
        if Config.DEMO_MODE:
            return self._mock_ask(column_name, suggested_mapping)

        try:
            return self._plivo_call(column_name, suggested_mapping)
        except Exception as e:
            console.print(f"  [yellow]Plivo call failed: {e}. Using simulated response.[/yellow]")
            return self._mock_ask(column_name, suggested_mapping)

    def _plivo_call(self, column_name: str, suggested_mapping: str) -> dict:
        """Make an actual Plivo voice call."""
        answer_url = f"{Config.WEBHOOK_BASE_URL}/plivo/answer"
        answer_url += f"?column={column_name}&mapping={suggested_mapping}"

        console.print(
            f"  [magenta]Plivo:[/magenta] Calling {Config.ENGINEER_PHONE_NUMBER}..."
        )
        console.print(
            f"  [magenta]Plivo:[/magenta] \"Is '{column_name}' the field "
            f"'{suggested_mapping}'? Press 1 for Yes, 2 for No.\""
        )

        call = self._client.calls.create(
            from_=Config.PLIVO_PHONE_NUMBER,
            to_=Config.ENGINEER_PHONE_NUMBER,
            answer_url=answer_url,
            answer_method="POST",
        )
        call_uuid = call.request_uuid if hasattr(call, 'request_uuid') else "unknown"

        # Wait for human response via webhook
        _pending_responses[call_uuid] = None
        response = self._wait_for_response(call_uuid, timeout=60)

        if response == "1":
            console.print(f"  [green]Human confirmed:[/green] '{column_name}' -> '{suggested_mapping}'")
            return {
                "confirmed": True,
                "target_field": suggested_mapping,
                "method": "plivo_call",
            }
        else:
            console.print(f"  [red]Human rejected:[/red] mapping for '{column_name}'")
            return {
                "confirmed": False,
                "target_field": suggested_mapping,
                "method": "plivo_call",
            }

    def _wait_for_response(self, call_id: str, timeout: int = 60) -> str:
        """Wait for a human response from the webhook."""
        start = time.time()
        while time.time() - start < timeout:
            with _response_lock:
                if _pending_responses.get(call_id) is not None:
                    return _pending_responses.pop(call_id)
            time.sleep(1)
        return "timeout"

    def _mock_ask(self, column_name: str, suggested_mapping: str) -> dict:
        """Simulate a human response for demo mode."""
        console.print()
        console.print("  [bold magenta]>>> PHONE RINGING... <<<[/bold magenta]")
        time.sleep(1)
        console.print(
            f"  [magenta]Plivo:[/magenta] \"Hello! I found a column called "
            f"'{column_name}'. Is this the '{suggested_mapping}' field? "
            f"Press 1 for Yes, 2 for No.\""
        )
        time.sleep(1.5)
        console.print("  [magenta]Plivo:[/magenta] Human pressed: [bold]1 (Yes)[/bold]")
        console.print(f"  [green]Human confirmed:[/green] '{column_name}' -> '{suggested_mapping}'")
        time.sleep(0.5)

        return {
            "confirmed": True,
            "target_field": suggested_mapping,
            "method": "demo_simulated",
        }
