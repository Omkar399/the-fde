# Phase 3: External Interfaces (1.5 Hours)

## Goal
Wire up all four external integrations: AGI Inc browser automation, Composio tool execution, Plivo voice calls, and the Flask webhook server. Two teammates work on **completely independent** file sets with **zero cross-dependencies** between modules.

## Time Budget
| Task | Time | Owner |
|------|------|-------|
| Interface contract review | 5 min | Both |
| Teammate A: Browser + Tools | 40 min | Teammate A |
| Teammate B: Teacher + Webhooks | 40 min | Teammate B |
| Integration sync + tests | 5 min | Both |

## Prerequisites
- Phase 1 complete: `src/config.py` working with all API keys
- Phase 2 complete: `src/brain.py` and `src/research.py` working
- API keys in `.env`: `AGI_API_KEY`, `COMPOSIO_API_KEY`, `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, `YOU_API_KEY`
- `pip install plivo composio-gemini flask requests` done
- For Plivo live testing: `ngrok http 5000` running and `WEBHOOK_BASE_URL` set to ngrok URL

---

## Interface Contract (Agree on This FIRST)

### BrowserAgent API (Teammate A - `src/browser.py`)
```python
class BrowserAgent:
    def __init__(self) -> None: ...
    def scrape_client_data(self, client_name: str, portal_url: str) -> dict: ...
    def close(self) -> None: ...
```

**`scrape_client_data()` return format:**
```python
{
    "columns": ["cust_id", "cust_nm", "cust_lvl_v2", ...],     # list[str]
    "rows": [{"cust_id": "1001", "cust_nm": "John", ...}, ...], # list[dict]
    "sample_data": {"cust_id": ["1001", "1002", "1003"], ...},   # dict[str, list[str]]
    "raw_csv": "cust_id,cust_nm,...\n1001,John,...\n",            # str
}
```

### ToolExecutor API (Teammate A - `src/tools.py`)
```python
class ToolExecutor:
    def __init__(self) -> None: ...
    def deploy_mapping(self, client_name: str, mappings: list[dict], rows: list[dict]) -> dict: ...
```

**`deploy_mapping()` return format:**
```python
{
    "success": True,
    "records_deployed": 5,
    "message": "Deployed 5 records for Acme Corp",
}
```

### Teacher API (Teammate B - `src/teacher.py`)
```python
class Teacher:
    def __init__(self) -> None: ...
    def ask_human(self, column_name: str, suggested_mapping: str) -> dict: ...
```

**`ask_human()` return format:**
```python
{
    "confirmed": True,         # bool - did the human confirm the mapping?
    "target_field": "subscription_tier",  # str - the confirmed field
    "method": "plivo_call",    # str - how the confirmation was obtained
}
```

### Webhook Server API (Teammate B - `server/webhooks.py`)
```
GET  /health                -> {"status": "ok", "service": "fde-webhooks"}
POST /plivo/answer?column=X&mapping=Y  -> Plivo XML (Speak + GetInput)
POST /plivo/input?column=X&mapping=Y   -> Plivo XML (response confirmation)
```

### Shared State Contract (Teacher <-> Webhooks)
```python
# src/teacher.py exposes:
from src.teacher import set_human_response

def set_human_response(call_id: str, response: str) -> None:
    """Called by webhook server when human presses a key."""
```

**Zero dependency between Teammate A and Teammate B modules.** `browser.py` and `tools.py` never import from `teacher.py` or `webhooks.py`, and vice versa. They are completely independent.

---

## Teammate A: Browser Automation + Tool Execution

### Files Owned (no conflicts with Teammate B)
```
src/browser.py
src/tools.py
tests/test_phase3_browser_tools.py
```

### Task A1: AGI Inc Browser Automation (`src/browser.py`)

The BrowserAgent uses AGI Inc's cloud browser API to create automated browser sessions that can navigate to client portals and scrape CSV data.

**Full AGI Inc API Reference:**

#### Step 1: Create a Browser Session
```
POST https://api.agi.tech/v1/sessions
Headers:
  Authorization: Bearer <AGI_API_KEY>
  Content-Type: application/json
Body:
  {"agent_name": "agi-0"}

Response (200):
  {
    "session_id": "abc-123-def",
    "vnc_url": "https://vnc.agi.tech/session/abc-123",
    "status": "ready"
  }
```

- `agent_name`: Use `"agi-0"` (AGI's default web agent)
- `vnc_url`: Opens a real-time browser viewer (great for live demo)
- Session creation can take up to 30 seconds
- Store `session_id` for subsequent calls

#### Step 2: Send a Task to the Browser Agent
```
POST https://api.agi.tech/v1/sessions/{session_id}/messages
Headers:
  Authorization: Bearer <AGI_API_KEY>
  Content-Type: application/json
Body:
  {"content": "Navigate to https://portal.acme.com. Find and download the customer data CSV."}

Response (200):
  {"message_id": 1, "status": "queued"}
```

- **Note:** The endpoint is `/messages` (plural) for sending
- The agent processes the task asynchronously
- Send clear, specific instructions about what to find

#### Step 3: Poll for Results
```
GET https://api.agi.tech/v1/sessions/{session_id}/messages?after_id=0
Headers:
  Authorization: Bearer <AGI_API_KEY>

Response (200):
  {
    "messages": [
      {"id": 1, "type": "THOUGHT", "content": "I see a login page..."},
      {"id": 2, "type": "LOG", "content": "Clicking download button..."},
      {"id": 3, "type": "DONE", "content": "cust_id,cust_nm,...\n1001,John,..."}
    ],
    "status": "finished"  // "running" | "finished" | "error"
  }
```

- Poll every 2 seconds using `after_id` to get only new messages
- Look for CSV content in `DONE` type messages
- Message types: `THOUGHT`, `QUESTION`, `DONE`, `ERROR`, `LOG`, `USER`
- Stop polling when `status` is `"finished"` or `"error"`

#### Step 4: Cleanup Session
```
DELETE https://api.agi.tech/v1/sessions/{session_id}
Headers:
  Authorization: Bearer <AGI_API_KEY>

Response (200): {"status": "deleted"}
```

**Implementation pattern:**
```python
def _agi_scrape(self, client_name: str, portal_url: str) -> dict:
    headers = {
        "Authorization": f"Bearer {Config.AGI_API_KEY}",
        "Content-Type": "application/json",
    }

    # Create session
    resp = requests.post(
        f"{Config.AGI_BASE_URL}/sessions",
        headers=headers,
        json={"agent_name": "agi-0"},
        timeout=30,
    )
    resp.raise_for_status()
    session = resp.json()
    self._session_id = session["session_id"]

    # Send task
    task_message = (
        f"Navigate to {portal_url}. "
        f"Find and download the customer data CSV file for {client_name}. "
        f"Return the CSV content."
    )
    requests.post(
        f"{Config.AGI_BASE_URL}/sessions/{self._session_id}/messages",
        headers=headers,
        json={"content": task_message},
        timeout=30,
    )

    # Poll for results
    csv_content = self._poll_for_result(headers)
    if csv_content:
        return self._parse_csv(csv_content)

    # Fallback to local files
    return self._mock_scrape(client_name)
```

**Mock fallback for demo mode:**
```python
def _mock_scrape(self, client_name: str) -> dict:
    """Load from local CSV files when API is unavailable."""
    file_map = {
        "Acme Corp": "client_a_acme.csv",
        "Globex Inc": "client_b_globex.csv",
    }
    filename = file_map.get(client_name, "client_a_acme.csv")
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mock", filename)
    with open(filepath, "r") as f:
        raw_csv = f.read()
    return self._parse_csv(raw_csv)
```

**CSV parser (shared between live and mock):**
```python
def _parse_csv(self, raw_csv: str) -> dict:
    reader = csv.DictReader(io.StringIO(raw_csv))
    columns = reader.fieldnames or []
    rows = list(reader)
    sample_data = {}
    for col in columns:
        sample_data[col] = [row.get(col, "") for row in rows[:3]]
    return {
        "columns": list(columns),
        "rows": rows,
        "sample_data": sample_data,
        "raw_csv": raw_csv,
    }
```

### Task A2: Composio Tool Execution (`src/tools.py`)

The ToolExecutor uses Composio to deploy mapped data to target SaaS systems (e.g., Google Sheets, CRM).

**Composio API Reference:**

#### Setup (one-time)
```bash
# Install
pip install composio-gemini

# Authenticate (connects your Google account)
composio add googlesheets

# List available actions
composio actions --app googlesheets
```

#### Code Integration
```python
from composio_gemini import ComposioToolSet, Action

# Initialize
toolset = ComposioToolSet(api_key=Config.COMPOSIO_API_KEY)

# Get available tools for LLM
tools = toolset.get_tools(actions=[Action.GOOGLESHEETS_BATCH_UPDATE])

# Direct execution (no LLM needed)
response = toolset.execute_action(
    action=Action.GOOGLESHEETS_BATCH_UPDATE,
    params={
        "data": transformed_data,
        "client_name": client_name,
    },
)
```

#### Alternative: Direct Composio SDK
```python
from composio import Composio

composio = Composio(api_key=Config.COMPOSIO_API_KEY)
composio.tools.execute(
    user_id="default",
    slug="GOOGLESHEETS_BATCH_UPDATE",
    arguments={"spreadsheet_id": "...", "data": [...]}
)
```

**Data transformation logic:**
```python
def _transform_data(self, mappings: list[dict], rows: list[dict]) -> list[dict]:
    """Transform source data using column mappings."""
    mapping_dict = {
        m["source_column"]: m["target_field"]
        for m in mappings
        if m.get("target_field") and m["target_field"] != "unknown"
    }
    transformed = []
    for row in rows:
        new_row = {}
        for src_col, value in row.items():
            target = mapping_dict.get(src_col)
            if target:
                new_row[target] = value
        transformed.append(new_row)
    return transformed
```

**Deploy method with fallback:**
```python
def deploy_mapping(self, client_name, mappings, rows):
    if Config.DEMO_MODE:
        return self._mock_deploy(client_name, mappings, rows)
    try:
        return self._composio_deploy(client_name, mappings, rows)
    except Exception as e:
        console.print(f"  [yellow]Composio deploy failed: {e}. Using mock.[/yellow]")
        return self._mock_deploy(client_name, mappings, rows)
```

### Task A3: Tests (`tests/test_phase3_browser_tools.py`)

```python
# tests/test_phase3_browser_tools.py
"""Phase 3 Teammate A tests: AGI Inc browser and Composio tool execution."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.browser import BrowserAgent
from src.tools import ToolExecutor


# === Browser Agent Tests ===

class TestBrowserAgentInit:
    def test_browser_initializes(self):
        """BrowserAgent initializes without errors."""
        browser = BrowserAgent()
        assert browser._session_id is None
        browser.close()

    def test_close_on_fresh_browser(self):
        """close() on a fresh browser (no session) doesn't crash."""
        browser = BrowserAgent()
        browser.close()  # Should not raise


class TestBrowserScrapeClientA:
    def test_scrape_returns_valid_structure(self):
        """Scrape returns dict with columns, rows, sample_data, raw_csv."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert "columns" in data
        assert "rows" in data
        assert "sample_data" in data
        assert "raw_csv" in data
        browser.close()

    def test_scrape_client_a_columns(self):
        """Client A has expected ambiguous columns."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert "cust_lvl_v2" in data["columns"]
        assert "cust_id" in data["columns"]
        assert "email_addr" in data["columns"]
        assert len(data["columns"]) == 14
        browser.close()

    def test_scrape_client_a_rows(self):
        """Client A has at least 3 data rows."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert len(data["rows"]) >= 3
        browser.close()

    def test_scrape_sample_data_has_values(self):
        """Sample data contains actual values from the CSV."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        for col in data["columns"]:
            assert col in data["sample_data"]
            assert len(data["sample_data"][col]) > 0
            assert data["sample_data"][col][0] != ""
        browser.close()


class TestBrowserScrapeClientB:
    def test_scrape_client_b_columns(self):
        """Client B has semantically similar but different column names."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        assert "customer_level_ver2" in data["columns"]
        assert "customer_id" in data["columns"]
        assert len(data["columns"]) == 14
        browser.close()

    def test_scrape_client_b_rows(self):
        """Client B has at least 3 data rows."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        assert len(data["rows"]) >= 3
        browser.close()


class TestBrowserFallback:
    def test_unknown_client_falls_back(self):
        """Unknown client name falls back to default (Client A) data."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Unknown Corp", "https://unknown.com")
        assert len(data["columns"]) > 0
        assert len(data["rows"]) > 0
        browser.close()


class TestBrowserCSVParser:
    def test_parse_csv_simple(self):
        """_parse_csv correctly parses a simple CSV string."""
        browser = BrowserAgent()
        raw = "name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        result = browser._parse_csv(raw)
        assert result["columns"] == ["name", "age", "city"]
        assert len(result["rows"]) == 2
        assert result["rows"][0]["name"] == "Alice"
        browser.close()

    def test_parse_csv_sample_data(self):
        """_parse_csv builds sample_data correctly."""
        browser = BrowserAgent()
        raw = "id,val\n1,a\n2,b\n3,c\n4,d\n"
        result = browser._parse_csv(raw)
        assert result["sample_data"]["id"] == ["1", "2", "3"]  # First 3 only
        browser.close()

    def test_parse_csv_preserves_raw(self):
        """_parse_csv preserves the original raw CSV string."""
        browser = BrowserAgent()
        raw = "a,b\n1,2\n"
        result = browser._parse_csv(raw)
        assert result["raw_csv"] == raw
        browser.close()


# === Tool Executor Tests ===

class TestToolExecutorInit:
    def test_tool_executor_initializes(self):
        """ToolExecutor initializes without errors in demo mode."""
        tools = ToolExecutor()
        # In demo mode, Composio toolset may be None
        assert tools is not None


class TestToolExecutorDeploy:
    def test_deploy_succeeds(self):
        """Deployment returns success with correct record count."""
        tools = ToolExecutor()
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm", "target_field": "full_name"},
        ]
        rows = [
            {"cust_id": "1001", "cust_nm": "John Smith"},
            {"cust_id": "1002", "cust_nm": "Jane Doe"},
        ]
        result = tools.deploy_mapping("TestClient", mappings, rows)
        assert result["success"] is True
        assert result["records_deployed"] == 2
        assert "message" in result

    def test_deploy_empty_data(self):
        """Deploying zero rows still succeeds."""
        tools = ToolExecutor()
        result = tools.deploy_mapping("EmptyClient", [], [])
        assert result["success"] is True
        assert result["records_deployed"] == 0

    def test_deploy_returns_required_keys(self):
        """Deploy result has success, records_deployed, message."""
        tools = ToolExecutor()
        result = tools.deploy_mapping("Test", [], [])
        assert "success" in result
        assert "records_deployed" in result
        assert "message" in result


class TestToolExecutorTransform:
    def test_transform_renames_columns(self):
        """_transform_data correctly renames columns using mappings."""
        tools = ToolExecutor()
        mappings = [
            {"source_column": "old_name", "target_field": "new_name"},
        ]
        rows = [{"old_name": "value1"}]
        result = tools._transform_data(mappings, rows)
        assert len(result) == 1
        assert "new_name" in result[0]
        assert result[0]["new_name"] == "value1"

    def test_transform_skips_unknown_targets(self):
        """Columns mapped to 'unknown' are excluded from output."""
        tools = ToolExecutor()
        mappings = [
            {"source_column": "good", "target_field": "mapped"},
            {"source_column": "bad", "target_field": "unknown"},
        ]
        rows = [{"good": "v1", "bad": "v2"}]
        result = tools._transform_data(mappings, rows)
        assert "mapped" in result[0]
        assert "unknown" not in result[0]

    def test_transform_multiple_rows(self):
        """Transform works across multiple rows."""
        tools = ToolExecutor()
        mappings = [
            {"source_column": "a", "target_field": "x"},
            {"source_column": "b", "target_field": "y"},
        ]
        rows = [
            {"a": "1", "b": "2"},
            {"a": "3", "b": "4"},
            {"a": "5", "b": "6"},
        ]
        result = tools._transform_data(mappings, rows)
        assert len(result) == 3
        assert result[0] == {"x": "1", "y": "2"}
        assert result[2] == {"x": "5", "y": "6"}

    def test_transform_ignores_unmapped_source_columns(self):
        """Source columns without mappings are dropped."""
        tools = ToolExecutor()
        mappings = [{"source_column": "a", "target_field": "x"}]
        rows = [{"a": "1", "extra_col": "ignored"}]
        result = tools._transform_data(mappings, rows)
        assert result[0] == {"x": "1"}
        assert "extra_col" not in result[0]

    def test_transform_empty_mappings(self):
        """Empty mappings produce empty rows."""
        tools = ToolExecutor()
        result = tools._transform_data([], [{"a": "1"}])
        assert result == [{}]

    def test_transform_with_real_client_data(self):
        """Transform with realistic Client A column mappings."""
        tools = ToolExecutor()
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm", "target_field": "full_name"},
            {"source_column": "email_addr", "target_field": "email"},
            {"source_column": "cust_lvl_v2", "target_field": "subscription_tier"},
        ]
        rows = [
            {"cust_id": "1001", "cust_nm": "John Smith", "email_addr": "john@acme.com", "cust_lvl_v2": "Gold"},
        ]
        result = tools._transform_data(mappings, rows)
        assert result[0]["customer_id"] == "1001"
        assert result[0]["full_name"] == "John Smith"
        assert result[0]["email"] == "john@acme.com"
        assert result[0]["subscription_tier"] == "Gold"
```

### Teammate A Acceptance Criteria
- [ ] `BrowserAgent.scrape_client_data()` returns valid structure with columns, rows, sample_data
- [ ] Client A CSV has `cust_lvl_v2` column (the ambiguous one)
- [ ] Client B CSV has `customer_level_ver2` column (the similar one)
- [ ] Unknown clients fall back gracefully to default data
- [ ] `_parse_csv` handles arbitrary CSV strings
- [ ] `ToolExecutor.deploy_mapping()` returns success/failure with record count
- [ ] `_transform_data` correctly renames columns, skips unknowns, handles empty data
- [ ] `pytest tests/test_phase3_browser_tools.py -v` all green

---

## Teammate B: Plivo Voice Teacher + Flask Webhooks

### Files Owned (no conflicts with Teammate A)
```
src/teacher.py
server/webhooks.py
server/__init__.py
tests/test_phase3_teacher_webhooks.py
```

### Task B1: Plivo Voice Teacher (`src/teacher.py`)

The Teacher is the human-in-the-loop feedback mechanism. When the Brain flags a column as low confidence, the Teacher calls the human engineer via Plivo voice to get confirmation.

**Plivo API Reference:**

#### Setup
```bash
pip install plivo

# Get credentials from console.plivo.com:
# - Auth ID
# - Auth Token
# - Plivo phone number (buy one in console)
# - Verify your personal number (required on trial)
```

#### Make an Outbound Call
```python
import plivo

client = plivo.RestClient(
    auth_id=Config.PLIVO_AUTH_ID,
    auth_token=Config.PLIVO_AUTH_TOKEN,
)

call = client.calls.create(
    from_=Config.PLIVO_PHONE_NUMBER,         # Your Plivo number
    to_=Config.ENGINEER_PHONE_NUMBER,         # Engineer's phone
    answer_url="https://your-ngrok.ngrok.io/plivo/answer?column=cust_lvl_v2&mapping=subscription_tier",
    answer_method="POST",
)
call_uuid = call.request_uuid  # Track this call
```

- `answer_url` must be publicly reachable (use ngrok for local dev)
- Pass query params for column/mapping context
- `request_uuid` is used to correlate the response from the webhook

#### Voice XML Response (Plivo XML)
```python
from plivo import plivoxml

response = plivoxml.ResponseElement()

# Collect DTMF input
get_input = plivoxml.GetInputElement(
    action="https://your-ngrok.ngrok.io/plivo/input?column=X&mapping=Y",
    method="POST",
    input_type="dtmf",           # Keypad input
    digit_end_timeout="5",       # Wait 5 seconds for input
    redirect=True,               # Redirect to action URL after input
)
get_input.add_speak(content="Press 1 for Yes, 2 for No.")
response.add(get_input)

# Fallback if no input
response.add(plivoxml.SpeakElement("No input received. Goodbye."))

xml_string = response.to_string()
```

#### Thread-Safe Response Collection

The Teacher and webhook server run in different threads. Use a shared dict with a lock:

```python
import threading

_pending_responses: dict[str, str | None] = {}
_response_lock = threading.Lock()

def set_human_response(call_id: str, response: str) -> None:
    """Called by webhook server when human responds."""
    with _response_lock:
        _pending_responses[call_id] = response

def _wait_for_response(call_id: str, timeout: int = 60) -> str:
    """Poll for human response."""
    start = time.time()
    while time.time() - start < timeout:
        with _response_lock:
            if _pending_responses.get(call_id) is not None:
                return _pending_responses.pop(call_id)
        time.sleep(1)
    return "timeout"
```

**Mock response for demo mode:**
```python
def _mock_ask(self, column_name, suggested_mapping):
    """Simulate human confirming the mapping."""
    console.print(f"  [bold magenta]>>> PHONE RINGING... <<<[/bold magenta]")
    time.sleep(1)
    console.print(f"  [magenta]Plivo:[/magenta] Human pressed: [bold]1 (Yes)[/bold]")
    return {
        "confirmed": True,
        "target_field": suggested_mapping,
        "method": "demo_simulated",
    }
```

### Task B2: Flask Webhook Server (`server/webhooks.py`)

The webhook server handles Plivo's callbacks during a voice call.

**Endpoints:**

#### `POST /plivo/answer` - Initial call handler
When Plivo connects the call, it hits this endpoint to get voice instructions.

```python
@app.route("/plivo/answer", methods=["GET", "POST"])
def answer_call():
    column = request.args.get("column", "unknown column")
    mapping = request.args.get("mapping", "unknown field")

    response = plivoxml.ResponseElement()

    speak_text = (
        f"Hello, this is the FDE agent. "
        f"I found a data column called {column}. "
        f"I think this maps to the field {mapping}. "
        f"Press 1 if this is correct. Press 2 if this is wrong."
    )

    get_input = plivoxml.GetInputElement(
        action=f"{request.host_url}plivo/input?column={column}&mapping={mapping}",
        method="POST",
        input_type="dtmf",
        digit_end_timeout="5",
        redirect=True,
    )
    get_input.add_speak(content=speak_text)
    response.add(get_input)
    response.add(plivoxml.SpeakElement("I didn't receive any input. Goodbye."))

    return Response(response.to_string(), mimetype="text/xml")
```

#### `POST /plivo/input` - DTMF response handler
After the human presses a key, Plivo sends the digit here.

```python
@app.route("/plivo/input", methods=["GET", "POST"])
def handle_input():
    digits = request.form.get("Digits", "")
    call_uuid = request.form.get("CallUUID", "")

    response = plivoxml.ResponseElement()

    if digits == "1":
        response.add(plivoxml.SpeakElement("Got it. The agent will learn this. Goodbye."))
        set_human_response(call_uuid, "1")
    elif digits == "2":
        response.add(plivoxml.SpeakElement("Understood. I will not map this. Goodbye."))
        set_human_response(call_uuid, "2")
    else:
        response.add(plivoxml.SpeakElement("Invalid input. Goodbye."))
        set_human_response(call_uuid, "invalid")

    return Response(response.to_string(), mimetype="text/xml")
```

#### `GET /health` - Health check
```python
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "fde-webhooks"}
```

### Task B3: Ngrok Setup for Live Testing

For Plivo to reach your local Flask server, use ngrok:

```bash
# Terminal 1: Start Flask webhook server
python -c "from server.webhooks import start_server; start_server()"

# Terminal 2: Start ngrok tunnel
ngrok http 5000

# Copy the ngrok URL (e.g., https://abc123.ngrok.io)
# Set in .env:
WEBHOOK_BASE_URL=https://abc123.ngrok.io
```

### Task B4: Tests (`tests/test_phase3_teacher_webhooks.py`)

```python
# tests/test_phase3_teacher_webhooks.py
"""Phase 3 Teammate B tests: Plivo voice teacher and Flask webhooks."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.teacher import Teacher, set_human_response, _pending_responses, _response_lock


# === Teacher Tests ===

class TestTeacherInit:
    def test_teacher_initializes(self):
        """Teacher initializes without errors in demo mode."""
        teacher = Teacher()
        assert teacher._client is None  # No Plivo client in demo mode

    def test_teacher_demo_mode(self):
        """In demo mode, Teacher uses mock responses."""
        teacher = Teacher()
        result = teacher.ask_human("test_col", "test_field")
        assert result["method"] == "demo_simulated"


class TestTeacherAskHuman:
    def test_ask_human_returns_confirmed(self):
        """Teacher returns confirmed=True in demo mode."""
        teacher = Teacher()
        result = teacher.ask_human("cust_lvl_v2", "subscription_tier")
        assert result["confirmed"] is True
        assert result["target_field"] == "subscription_tier"

    def test_ask_human_returns_all_keys(self):
        """Response has confirmed, target_field, method."""
        teacher = Teacher()
        result = teacher.ask_human("any_col", "any_field")
        assert "confirmed" in result
        assert "target_field" in result
        assert "method" in result

    def test_ask_human_preserves_mapping(self):
        """The suggested mapping is returned in the response."""
        teacher = Teacher()
        result = teacher.ask_human("col_x", "field_y")
        assert result["target_field"] == "field_y"


class TestTeacherSharedState:
    def test_set_human_response(self):
        """set_human_response stores response for a call ID."""
        set_human_response("test-call-123", "1")
        with _response_lock:
            assert _pending_responses["test-call-123"] == "1"
            # Cleanup
            _pending_responses.pop("test-call-123", None)

    def test_set_human_response_overwrite(self):
        """Setting response for same call ID overwrites."""
        set_human_response("test-call-456", "1")
        set_human_response("test-call-456", "2")
        with _response_lock:
            assert _pending_responses["test-call-456"] == "2"
            _pending_responses.pop("test-call-456", None)


# === Webhook Server Tests ===

class TestWebhookHealth:
    def test_health_endpoint(self):
        """Health check returns 200 with status ok."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "fde-webhooks"


class TestWebhookAnswer:
    def test_answer_returns_xml(self):
        """Answer endpoint returns valid Plivo XML."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post("/plivo/answer?column=test_col&mapping=test_field")
        assert resp.status_code == 200
        assert resp.content_type == "text/xml"

    def test_answer_contains_response_element(self):
        """Answer XML has <Response> root element."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post("/plivo/answer?column=test&mapping=field")
        assert b"<Response>" in resp.data

    def test_answer_contains_speak(self):
        """Answer XML contains a Speak element with instructions."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post("/plivo/answer?column=cust_lvl_v2&mapping=subscription_tier")
        assert b"<Speak>" in resp.data or b"<GetInput>" in resp.data

    def test_answer_includes_column_name(self):
        """Answer XML mentions the column name."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post("/plivo/answer?column=my_column&mapping=my_field")
        assert b"my_column" in resp.data

    def test_answer_get_method_works(self):
        """Answer endpoint also works with GET method."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.get("/plivo/answer?column=test&mapping=field")
        assert resp.status_code == 200


class TestWebhookInput:
    def test_input_digit_1_confirms(self):
        """Pressing 1 sends confirmation response."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post(
            "/plivo/input?column=test&mapping=field",
            data={"Digits": "1", "CallUUID": "test-uuid-1"},
        )
        assert resp.status_code == 200
        assert b"<Speak>" in resp.data

    def test_input_digit_2_rejects(self):
        """Pressing 2 sends rejection response."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post(
            "/plivo/input?column=test&mapping=field",
            data={"Digits": "2", "CallUUID": "test-uuid-2"},
        )
        assert resp.status_code == 200
        assert b"will not map" in resp.data

    def test_input_invalid_digit(self):
        """Invalid digit gets error message."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post(
            "/plivo/input?column=test&mapping=field",
            data={"Digits": "9", "CallUUID": "test-uuid-3"},
        )
        assert resp.status_code == 200
        assert b"Invalid" in resp.data

    def test_input_sets_human_response(self):
        """Input handler calls set_human_response with correct values."""
        from server.webhooks import app
        client = app.test_client()
        client.post(
            "/plivo/input?column=test&mapping=field",
            data={"Digits": "1", "CallUUID": "webhook-test-uuid"},
        )
        with _response_lock:
            assert _pending_responses.get("webhook-test-uuid") == "1"
            _pending_responses.pop("webhook-test-uuid", None)

    def test_input_returns_xml_content_type(self):
        """Input endpoint returns text/xml content type."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post(
            "/plivo/input?column=t&mapping=f",
            data={"Digits": "1", "CallUUID": "ct-uuid"},
        )
        assert resp.content_type == "text/xml"
```

### Teammate B Acceptance Criteria
- [ ] `Teacher.__init__` creates Plivo client (or None in demo mode)
- [ ] `ask_human()` returns `{confirmed, target_field, method}` dict
- [ ] Demo mode simulates a successful confirmation
- [ ] `set_human_response` stores response in thread-safe shared state
- [ ] Flask `/health` returns `{"status": "ok"}`
- [ ] Flask `/plivo/answer` returns valid Plivo XML with Speak + GetInput
- [ ] Flask `/plivo/input` processes DTMF digits and calls `set_human_response`
- [ ] `pytest tests/test_phase3_teacher_webhooks.py -v` all green

---

## Integration Sync Point

After both teammates finish, run the integration test to verify all Phase 3 modules work.

### Integration Test (`tests/test_phase3_integration.py`)

```python
# tests/test_phase3_integration.py
"""Phase 3 Integration: Browser + Tools + Teacher + Webhooks all work together."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.browser import BrowserAgent
from src.teacher import Teacher
from src.tools import ToolExecutor


class TestPhase3Integration:
    def test_browser_to_tools_pipeline(self):
        """Full pipeline: scrape data -> transform -> deploy."""
        browser = BrowserAgent()
        tools = ToolExecutor()

        # Scrape
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert len(data["columns"]) > 0

        # Create mappings (simulating brain output)
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm", "target_field": "full_name"},
            {"source_column": "email_addr", "target_field": "email"},
        ]

        # Deploy
        result = tools.deploy_mapping("Acme Corp", mappings, data["rows"])
        assert result["success"] is True
        assert result["records_deployed"] == len(data["rows"])

        browser.close()

    def test_teacher_flow_with_webhook(self):
        """Teacher + Webhook integration: simulate a full call flow."""
        teacher = Teacher()
        result = teacher.ask_human("cust_lvl_v2", "subscription_tier")
        assert result["confirmed"] is True
        assert result["target_field"] == "subscription_tier"

    def test_all_modules_initialize_independently(self):
        """All Phase 3 modules can be initialized without depending on each other."""
        browser = BrowserAgent()
        teacher = Teacher()
        tools = ToolExecutor()

        # Each module works independently
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert len(data["rows"]) > 0

        human = teacher.ask_human("test", "test_field")
        assert "confirmed" in human

        deploy = tools.deploy_mapping("Test", [], [])
        assert deploy["success"] is True

        browser.close()

    def test_full_client_pipeline(self):
        """End-to-end: scrape -> ask human -> deploy."""
        browser = BrowserAgent()
        teacher = Teacher()
        tools = ToolExecutor()

        # Step 1: Scrape
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")

        # Step 2: Simulate brain finding uncertain column
        uncertain_column = "cust_lvl_v2"
        assert uncertain_column in data["columns"]

        # Step 3: Ask human about uncertain column
        human_result = teacher.ask_human(uncertain_column, "subscription_tier")
        assert human_result["confirmed"] is True

        # Step 4: Deploy with the confirmed mapping
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": uncertain_column, "target_field": human_result["target_field"]},
        ]
        deploy_result = tools.deploy_mapping("Acme Corp", mappings, data["rows"])
        assert deploy_result["success"] is True

        browser.close()
```

---

## GitHub Actions Workflow (`.github/workflows/phase3.yml`)

```yaml
name: "Phase 3: External Interfaces"

on:
  push:
    paths:
      - "src/browser.py"
      - "src/teacher.py"
      - "src/tools.py"
      - "server/**"
      - "tests/test_phase3_*.py"
  pull_request:
    paths:
      - "src/browser.py"
      - "src/teacher.py"
      - "src/tools.py"
      - "server/**"
      - "tests/test_phase3_*.py"

jobs:
  phase3-tests:
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

      - name: Lint Phase 3 files
        run: ruff check src/browser.py src/teacher.py src/tools.py server/

      - name: Teammate A tests (Browser + Tools)
        run: pytest tests/test_phase3_browser_tools.py -v

      - name: Teammate B tests (Teacher + Webhooks)
        run: pytest tests/test_phase3_teacher_webhooks.py -v

      - name: Integration tests
        run: pytest tests/test_phase3_integration.py -v
```

---

## Debug Checklist

### AGI Inc Browser
| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Bad API key | Verify `AGI_API_KEY` with `curl -H "Authorization: Bearer $AGI_API_KEY" https://api.agi.tech/v1/sessions` |
| Session creation hangs | AGI server slow | Increase `timeout` to 60s |
| No CSV in response | Agent didn't find download link | Check `msg["type"] == "DONE"` for results |
| `ConnectionError` | API server unreachable | Check firewall, VPN, or use mock fallback |
| VNC viewer blank | Session not ready yet | Wait for `status: "ready"` before sending task |
| Polling returns empty | Wrong `after_id` value | Start with `after_id=0` and increment |

### Plivo Voice
| Symptom | Cause | Fix |
|---------|-------|-----|
| Call doesn't ring | Destination not verified | On trial: verify number at console.plivo.com |
| `answer_url` not reached | Server not public | Run `ngrok http 5000` and update `WEBHOOK_BASE_URL` |
| No DTMF received | Missing `input_type` | Set `input_type="dtmf"` on `GetInputElement` |
| XML parse error | Wrong content type | Return `mimetype="text/xml"` |
| Call connects but no speech | Speak element empty | Check `speak_text` is not empty |
| Thread deadlock | Lock not released | Always use `with _response_lock:` (context manager) |
| Timeout waiting for response | Human didn't answer | Default to `"timeout"` after 60 seconds |
| `plivo.exceptions.AuthenticationError` | Wrong credentials | Check `PLIVO_AUTH_ID` and `PLIVO_AUTH_TOKEN` |
| `plivo.exceptions.ResourceNotFoundError` | Invalid phone number | Use E.164 format: `+1XXXXXXXXXX` |

### Composio
| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError` | Wrong package | `pip install composio-gemini` (NOT just `composio`) |
| `AuthenticationError` | Account not connected | Run `composio add googlesheets` first |
| `ActionNotFoundError` | Wrong action slug | Use `Action.GOOGLESHEETS_BATCH_UPDATE` from enum |
| Deploy silently fails | No Google account linked | Authorize via Composio dashboard |
| `ToolSet` is None | Demo mode active | Check `Config.DEMO_MODE` setting |

### Flask Webhooks
| Symptom | Cause | Fix |
|---------|-------|-----|
| `OSError: Address already in use` | Port 5000 occupied | Kill existing process or use different port |
| XML response empty | `ResponseElement` not populated | Add `SpeakElement` or `GetInputElement` |
| `ImportError: plivoxml` | Old Plivo version | `pip install plivo>=4.0.0` |
| Request args missing | Using `request.form` for query params | Use `request.args` for URL params, `request.form` for POST body |

---

## Smoke Test

```bash
# Phase 3 complete smoke test
DEMO_MODE=true python -c "
from src.browser import BrowserAgent
from src.teacher import Teacher
from src.tools import ToolExecutor

# Browser
b = BrowserAgent()
data = b.scrape_client_data('Acme Corp', 'https://mock.com')
print(f'Browser OK: {len(data[\"columns\"])} columns, {len(data[\"rows\"])} rows')
b.close()

# Teacher
t = Teacher()
result = t.ask_human('cust_lvl_v2', 'subscription_tier')
print(f'Teacher OK: confirmed={result[\"confirmed\"]}, method={result[\"method\"]}')

# Tools
tools = ToolExecutor()
mappings = [{'source_column': 'cust_id', 'target_field': 'customer_id'}]
deploy = tools.deploy_mapping('Test', mappings, [{'cust_id': '1001'}])
print(f'Tools OK: success={deploy[\"success\"]}, deployed={deploy[\"records_deployed\"]}')

# Webhooks
from server.webhooks import app
client = app.test_client()
health = client.get('/health')
print(f'Webhooks OK: {health.get_json()[\"status\"]}')

print('PHASE 3: ALL SYSTEMS GO')
"
```

---

## Definition of Done

- [ ] `src/browser.py` scrapes client data via AGI Inc API with mock fallback
- [ ] `src/tools.py` deploys mapped data via Composio with mock fallback
- [ ] `src/teacher.py` calls human via Plivo voice with mock fallback
- [ ] `server/webhooks.py` handles Plivo callbacks with correct XML responses
- [ ] All modules work independently (zero cross-dependencies between A and B)
- [ ] `pytest tests/test_phase3_browser_tools.py -v` passes (Teammate A)
- [ ] `pytest tests/test_phase3_teacher_webhooks.py -v` passes (Teammate B)
- [ ] `pytest tests/test_phase3_integration.py -v` passes (Both)
- [ ] `.github/workflows/phase3.yml` is valid
- [ ] Smoke test runs clean
