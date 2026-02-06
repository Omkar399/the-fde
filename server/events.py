"""Event bus for bridging agent pipeline events to the live dashboard via SSE.

Uses a module-level queue pattern (same as teacher.py shared state).
The agent calls emit_event() at each pipeline step, and the SSE endpoint
streams events to connected dashboard clients.
"""

import json
import queue
import threading
import time

# Module-level state
_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()
_event_history: list[dict] = []
_history_lock = threading.Lock()


def emit_event(event_type: str, data: dict | None = None) -> None:
    """Emit an event from the agent pipeline to all SSE subscribers.

    Args:
        event_type: e.g. 'step_start', 'mapping_result', 'phone_call'
        data: arbitrary JSON-serializable payload
    """
    event = {
        "type": event_type,
        "data": data or {},
        "timestamp": time.time(),
    }

    # Store in history
    with _history_lock:
        _event_history.append(event)

    # Push to all subscribers
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def subscribe() -> queue.Queue:
    """Create a new subscriber queue. Returns it for reading events."""
    q = queue.Queue(maxsize=256)
    with _subscribers_lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    """Remove a subscriber queue."""
    with _subscribers_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def get_history() -> list[dict]:
    """Return all events emitted so far (for late-joining clients)."""
    with _history_lock:
        return list(_event_history)


def reset() -> None:
    """Clear event history for demo restart."""
    with _history_lock:
        _event_history.clear()


def format_sse(event: dict) -> str:
    """Format an event as an SSE message string."""
    return f"data: {json.dumps(event)}\n\n"
