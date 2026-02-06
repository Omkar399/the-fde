# Phase 5: Plivo Voice Teacher -- Omkar

## Status

| Area       | Status         |
| ---------- | -------------- |
| Code       | COMPLETED      |
| Tests      | REMAINING      |
| CI         | REMAINING      |
| Integration| COMPLETED (used by Agent step 3) |

---

## Owner & Files

**Owner:** Omkar

| File                   | Lines | Purpose                                      |
| ---------------------- | ----- | -------------------------------------------- |
| `src/teacher.py`       | 128   | `Teacher` class + module-level shared state for webhook responses |
| `server/webhooks.py`   | 89    | Flask app with Plivo XML endpoints + health check |
| `server/__init__.py`   | --    | Package marker                               |

---

## What Was Built

A human-in-the-loop feedback system using Plivo voice calls. When the Brain (Phase 2) maps a column with low confidence, the Agent calls the Teacher to phone the human engineer. The engineer presses 1 (confirm) or 2 (reject) on their phone's keypad. A Flask webhook server receives the DTMF response and feeds it back to the Teacher via shared module-level state.

### Module-Level Shared State (`src/teacher.py`)

```python
_pending_responses: dict[str, str | None] = {}   # call_id -> human response
_response_lock = threading.Lock()                 # thread-safe access
```

| Function | Signature | Behavior |
| -------- | --------- | -------- |
| `set_human_response` | `(call_id: str, response: str) -> None` | Acquires `_response_lock`, stores `response` in `_pending_responses[call_id]`. Called by the webhook server. |

### Class: `Teacher`

| Method | Signature | Behavior |
| ------ | --------- | -------- |
| `__init__` | `()` | Creates `plivo.RestClient(auth_id, auth_token)` in production; sets `self._client = None` in demo mode. |
| `ask_human` | `(column_name: str, suggested_mapping: str) -> dict` | Entry point. Returns `{confirmed: bool, target_field: str, method: str}`. Routes to `_plivo_call` or `_mock_ask` based on `Config.DEMO_MODE`. On API failure, falls back to `_mock_ask`. |
| `_plivo_call` | `(column_name: str, suggested_mapping: str) -> dict` | Constructs `answer_url` with column/mapping query params, calls `self._client.calls.create(from_, to_, answer_url, answer_method="POST")`. Seeds `_pending_responses[call_uuid] = None`, then waits via `_wait_for_response`. Returns confirmed/rejected dict. |
| `_wait_for_response` | `(call_id: str, timeout: int = 60) -> str` | Polls `_pending_responses` every 1 second up to `timeout`. Returns the human's digit or `"timeout"`. |
| `_mock_ask` | `(column_name: str, suggested_mapping: str) -> dict` | Simulates phone ringing with Rich output and `time.sleep` delays. Always returns `{confirmed: True, target_field: suggested_mapping, method: "demo_simulated"}`. |

### Flask App: `server/webhooks.py`

| Endpoint | Method | Behavior |
| -------- | ------ | -------- |
| `/plivo/answer` | GET, POST | Reads `column` and `mapping` from query params. Returns Plivo XML with `SpeakElement` (question text) inside a `GetInputElement` (DTMF, `digit_end_timeout=5`, redirects to `/plivo/input`). Falls through to "I didn't receive any input" speak if no digits collected. |
| `/plivo/input` | GET, POST | Reads `Digits` and `CallUUID` from form data, `column` and `mapping` from query params. Digit `"1"` = confirm, `"2"` = reject, anything else = `"invalid"`. Calls `set_human_response(call_uuid, digit)`. Returns Plivo XML with confirmation speak. |
| `/health` | GET | Returns `{"status": "ok", "service": "fde-webhooks"}`. |
| `start_server` | function | `app.run(host="0.0.0.0", port=port, debug=False)`. |

### Return Shape (`ask_human`)

```python
{
    "confirmed": True,          # bool -- did the human confirm?
    "target_field": "email",    # str  -- the suggested (or confirmed) target field
    "method": "plivo_call"      # str  -- "plivo_call", "demo_simulated", or fallback
}
```

---

## API Reference

### Plivo Voice API

**Authentication:** `plivo.RestClient(auth_id=Config.PLIVO_AUTH_ID, auth_token=Config.PLIVO_AUTH_TOKEN)`

| Operation | SDK Call | Notes |
| --------- | -------- | ----- |
| Make outbound call | `client.calls.create(from_=PLIVO_PHONE_NUMBER, to_=ENGINEER_PHONE_NUMBER, answer_url=url, answer_method="POST")` | `answer_url` must be publicly reachable (use ngrok for local dev) |
| Collect DTMF input | `plivoxml.GetInputElement(action=url, method="POST", input_type="dtmf", digit_end_timeout="5", redirect=True)` | Nested inside `ResponseElement`; contains a `SpeakElement` child |
| Speak text | `plivoxml.SpeakElement(content)` | TTS to the caller |
| Build XML response | `plivoxml.ResponseElement()` -> `.add(...)` -> `.to_string()` | Returned as `Response(xml, mimetype="text/xml")` |

### Plivo XML Structure (answer)

```xml
<Response>
  <GetInput action="http://host/plivo/input?column=X&mapping=Y"
            method="POST" inputType="dtmf" digitEndTimeout="5" redirect="true">
    <Speak>Hello, this is the FDE agent. I found a data column called X...</Speak>
  </GetInput>
  <Speak>I didn't receive any input. Goodbye.</Speak>
</Response>
```

### Webhook Data Flow

```
Plivo Cloud                    Flask Server                   Teacher
    |                              |                            |
    |-- POST /plivo/answer ------->|                            |
    |<-- XML (Speak + GetInput) ---|                            |
    |                              |                            |
    |  (human presses digit)       |                            |
    |                              |                            |
    |-- POST /plivo/input -------->|                            |
    |   form: Digits=1, CallUUID=X |                            |
    |                              |-- set_human_response(X,1)->|
    |<-- XML (confirmation speak) -|                            |
    |                              |                     _wait_for_response
    |                              |                     returns "1"
```

---

## Integration Points

```
Agent.onboard_client()
    |
    +-- Step 2: Brain.analyze_columns() -> mappings with confidence
    |
    +-- Step 3: for each mapping where confidence == "low":
    |           self.teacher.ask_human(source_column, target_field)
    |           -> {confirmed, target_field, method}
    |
    +-- If confirmed: promote to "high" confidence, add to confident list
    +-- If rejected: skip the column
```

**Config keys used:**
- `Config.PLIVO_AUTH_ID` -- Plivo account auth ID
- `Config.PLIVO_AUTH_TOKEN` -- Plivo account auth token
- `Config.PLIVO_PHONE_NUMBER` -- Plivo caller number (from_)
- `Config.ENGINEER_PHONE_NUMBER` -- Human engineer's phone (to_)
- `Config.WEBHOOK_BASE_URL` -- Public URL for answer_url (default `http://localhost:5000`)
- `Config.DEMO_MODE` -- When `"true"`, skip real Plivo calls, simulate human pressing 1

**Called by:** `FDEAgent.onboard_client()` in `src/agent.py` (step 3)

**Depends on:** `src/config.py`, `plivo`, `threading`, `time`, `flask`, `rich`

**Cross-module import:** `server/webhooks.py` imports `set_human_response` from `src/teacher.py`

---

## Tests

### File: `tests/test_phase5_plivo.py`

```python
"""Phase 5 tests: Plivo Teacher in demo mode."""
import os
import threading
import pytest

os.environ["DEMO_MODE"] = "true"

from src.teacher import Teacher, set_human_response, _pending_responses, _response_lock


@pytest.fixture
def teacher():
    return Teacher()


@pytest.fixture(autouse=True)
def clear_pending():
    """Ensure _pending_responses is clean before each test."""
    with _response_lock:
        _pending_responses.clear()
    yield
    with _response_lock:
        _pending_responses.clear()


# ---------------------------------------------------------------------------
# TestTeacherInit -- verify construction
# ---------------------------------------------------------------------------
class TestTeacherInit:
    def test_client_is_none_in_demo(self, teacher):
        """In demo mode, Plivo client is None."""
        assert teacher._client is None

    def test_teacher_creates_without_error(self):
        """Teacher can be instantiated in demo mode without Plivo credentials."""
        t = Teacher()
        assert t is not None


# ---------------------------------------------------------------------------
# TestTeacherAskHuman -- demo-mode behavior
# ---------------------------------------------------------------------------
class TestTeacherAskHuman:
    def test_returns_confirmed_in_demo(self, teacher):
        """Mock ask always confirms in demo mode."""
        result = teacher.ask_human("cust_lvl_v2", "subscription_tier")
        assert result["confirmed"] is True

    def test_returns_correct_target_field(self, teacher):
        """The suggested mapping is echoed back as target_field."""
        result = teacher.ask_human("email_addr", "email")
        assert result["target_field"] == "email"

    def test_method_is_demo_simulated(self, teacher):
        """Demo mode sets method to 'demo_simulated'."""
        result = teacher.ask_human("phone_num", "phone")
        assert result["method"] == "demo_simulated"


# ---------------------------------------------------------------------------
# TestTeacherSharedState -- set_human_response and thread safety
# ---------------------------------------------------------------------------
class TestTeacherSharedState:
    def test_set_and_retrieve_response(self):
        """set_human_response stores value retrievable under the call_id."""
        set_human_response("call-123", "1")
        with _response_lock:
            assert _pending_responses["call-123"] == "1"

    def test_concurrent_writes(self):
        """Multiple threads writing responses do not corrupt shared state."""
        errors = []

        def writer(call_id, value):
            try:
                set_human_response(call_id, value)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"call-{i}", str(i)))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        with _response_lock:
            assert len(_pending_responses) == 20
            for i in range(20):
                assert _pending_responses[f"call-{i}"] == str(i)
```

### File: `tests/test_phase5_webhooks.py`

```python
"""Phase 5 tests: Flask webhook endpoints for Plivo callbacks."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from server.webhooks import app
from src.teacher import _pending_responses, _response_lock


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clear_pending():
    """Ensure _pending_responses is clean before each test."""
    with _response_lock:
        _pending_responses.clear()
    yield
    with _response_lock:
        _pending_responses.clear()


# ---------------------------------------------------------------------------
# TestWebhookHealth -- basic health check
# ---------------------------------------------------------------------------
class TestWebhookHealth:
    def test_health_returns_ok(self, client):
        """GET /health returns status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "fde-webhooks"


# ---------------------------------------------------------------------------
# TestWebhookAnswer -- Plivo answer callback
# ---------------------------------------------------------------------------
class TestWebhookAnswer:
    def test_returns_xml_content_type(self, client):
        """POST /plivo/answer returns text/xml."""
        resp = client.post("/plivo/answer?column=email&mapping=email")
        assert resp.content_type == "text/xml"

    def test_contains_speak_text(self, client):
        """Response XML contains the column name in spoken text."""
        resp = client.post("/plivo/answer?column=cust_lvl_v2&mapping=subscription_tier")
        xml = resp.data.decode()
        assert "cust_lvl_v2" in xml
        assert "subscription_tier" in xml

    def test_contains_get_input(self, client):
        """Response XML contains a GetInput element for DTMF collection."""
        resp = client.post("/plivo/answer?column=test_col&mapping=test_field")
        xml = resp.data.decode()
        assert "GetInput" in xml or "getInput" in xml.lower()

    def test_fallback_speak_on_no_input(self, client):
        """Response XML has a fallback speak for no-input scenario."""
        resp = client.post("/plivo/answer?column=col&mapping=field")
        xml = resp.data.decode()
        assert "didn" in xml.lower() or "no input" in xml.lower()


# ---------------------------------------------------------------------------
# TestWebhookInput -- DTMF digit handling
# ---------------------------------------------------------------------------
class TestWebhookInput:
    def test_digit_1_confirms(self, client):
        """Pressing 1 stores '1' in pending responses."""
        resp = client.post(
            "/plivo/input?column=email&mapping=email",
            data={"Digits": "1", "CallUUID": "uuid-abc"},
        )
        assert resp.status_code == 200
        with _response_lock:
            assert _pending_responses.get("uuid-abc") == "1"

    def test_digit_2_rejects(self, client):
        """Pressing 2 stores '2' in pending responses."""
        resp = client.post(
            "/plivo/input?column=col&mapping=field",
            data={"Digits": "2", "CallUUID": "uuid-def"},
        )
        assert resp.status_code == 200
        with _response_lock:
            assert _pending_responses.get("uuid-def") == "2"

    def test_invalid_digit(self, client):
        """Any digit other than 1 or 2 stores 'invalid'."""
        resp = client.post(
            "/plivo/input?column=col&mapping=field",
            data={"Digits": "5", "CallUUID": "uuid-ghi"},
        )
        assert resp.status_code == 200
        with _response_lock:
            assert _pending_responses.get("uuid-ghi") == "invalid"

    def test_response_is_xml(self, client):
        """Input handler returns XML response."""
        resp = client.post(
            "/plivo/input?column=col&mapping=field",
            data={"Digits": "1", "CallUUID": "uuid-xml"},
        )
        assert resp.content_type == "text/xml"
```

### Running Tests

```bash
# Teacher tests
DEMO_MODE=true pytest tests/test_phase5_plivo.py -v

# Webhook tests
DEMO_MODE=true pytest tests/test_phase5_webhooks.py -v

# Both
DEMO_MODE=true pytest tests/test_phase5_plivo.py tests/test_phase5_webhooks.py -v
```

---

## CI Workflow

File: `.github/workflows/phase5.yml`

```yaml
name: "Phase 5: Plivo Voice"

on:
  push:
    paths:
      - "src/teacher.py"
      - "server/**"
      - "tests/test_phase5_*.py"
  pull_request:
    paths:
      - "src/teacher.py"
      - "server/**"
      - "tests/test_phase5_*.py"

jobs:
  phase5-tests:
    runs-on: ubuntu-latest
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest ruff

      - name: Lint Phase 5 files
        run: ruff check src/teacher.py server/webhooks.py

      - name: Teacher tests
        run: pytest tests/test_phase5_plivo.py -v

      - name: Webhook tests
        run: pytest tests/test_phase5_webhooks.py -v
```

---

## Debug Checklist

| Symptom | Likely Cause | Fix |
| ------- | ------------ | --- |
| `ModuleNotFoundError: plivo` | `plivo` package not installed | `pip install plivo`; verify it is in `requirements.txt` |
| `Teacher.__init__` crashes with missing credentials | `DEMO_MODE` is not set to `"true"` and Plivo env vars are empty | Set `DEMO_MODE=true` for local dev, or set `PLIVO_AUTH_ID` / `PLIVO_AUTH_TOKEN` |
| Plivo call created but no DTMF received | `answer_url` is not publicly reachable | Run `ngrok http 5000` and set `WEBHOOK_BASE_URL` to the ngrok URL |
| `_wait_for_response` returns `"timeout"` | Webhook never called `set_human_response`, or `CallUUID` mismatch | Check Flask logs for incoming requests; verify `CallUUID` matches between call creation and webhook |
| Webhook returns 404 | Flask server not running or route not registered | Start server with `python -m server.webhooks` or `start_server()`; confirm routes with `app.url_map` |
| `/plivo/input` stores `""` as Digits | Plivo did not send `Digits` form field | Check Plivo dashboard for call logs; ensure `GetInput` has `redirect=True` |
| `set_human_response` seems lost | `_pending_responses` dict was cleared between set and read | Ensure no test or code path calls `_pending_responses.clear()` unexpectedly |
| `ImportError: cannot import set_human_response` | Circular import or wrong import path | `server/webhooks.py` imports from `src.teacher`; run from repo root so both packages resolve |
| Flask test client returns 405 | Using GET on a POST-only endpoint or vice versa | `/plivo/answer` accepts GET and POST; `/plivo/input` accepts GET and POST; `/health` is GET only |
| XML response missing `GetInput` | `plivoxml` API changed or import failed | Pin `plivo` version in requirements; check `plivoxml.GetInputElement` exists |

---

## Smoke Test

### Teacher (demo mode)

```python
import os
os.environ["DEMO_MODE"] = "true"

from src.teacher import Teacher

t = Teacher()
result = t.ask_human("cust_lvl_v2", "subscription_tier")

print(f"Confirmed: {result['confirmed']}")
print(f"Target: {result['target_field']}")
print(f"Method: {result['method']}")
```

Expected output (with Rich formatting):

```
>>> PHONE RINGING... <<<
Plivo: "Hello! I found a column called 'cust_lvl_v2'. Is this the 'subscription_tier' field? Press 1 for Yes, 2 for No."
Plivo: Human pressed: 1 (Yes)
Human confirmed: 'cust_lvl_v2' -> 'subscription_tier'
Confirmed: True
Target: subscription_tier
Method: demo_simulated
```

### Webhook Server

```bash
# Terminal 1: start the server
DEMO_MODE=true python -m server.webhooks

# Terminal 2: test endpoints
curl http://localhost:5000/health
# -> {"service":"fde-webhooks","status":"ok"}

curl -X POST "http://localhost:5000/plivo/answer?column=email&mapping=email"
# -> <Response><GetInput ...><Speak>Hello, this is the FDE agent...</Speak></GetInput>...</Response>

curl -X POST "http://localhost:5000/plivo/input?column=email&mapping=email" \
     -d "Digits=1&CallUUID=test-uuid"
# -> <Response><Speak>Got it. Mapping email to email...</Speak></Response>
```

---

## Definition of Done

- [ ] `tests/test_phase5_plivo.py` exists with all 7 tests passing (TestTeacherInit: 2, TestTeacherAskHuman: 3, TestTeacherSharedState: 2)
- [ ] `tests/test_phase5_webhooks.py` exists with all 9 tests passing (TestWebhookHealth: 1, TestWebhookAnswer: 4, TestWebhookInput: 4)
- [ ] `.github/workflows/phase5.yml` exists and triggers on `src/teacher.py`, `server/**`, and `tests/test_phase5_*` changes
- [ ] `DEMO_MODE=true pytest tests/test_phase5_plivo.py tests/test_phase5_webhooks.py -v` passes with 16/16 green
- [ ] CI workflow runs successfully on push to `main` or PR
- [ ] No lint errors from `ruff check src/teacher.py server/webhooks.py`
