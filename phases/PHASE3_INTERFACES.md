# Phase 3: External Interfaces (Hour 3: 1:00 PM - 2:30 PM)

## Goal
Wire up AGI Inc browser, Plivo voice calls, and Composio tool execution.

## Tasks

### 3.1 AGI Inc Browser Automation (`src/browser.py`)
- [ ] Create browser session via AGI API (`POST /v1/sessions`)
- [ ] Send task to navigate and scrape (`POST /v1/sessions/{id}/message`)
- [ ] Poll for completion (`GET /v1/sessions/{id}/messages?after_id=N`)
- [ ] Parse CSV from agent response
- [ ] Graceful fallback to local mock files if API unavailable
- [ ] Display `vnc_url` so user can watch browser live

### 3.2 Plivo Voice Calls (`src/teacher.py` + `server/webhooks.py`)
- [ ] Outbound call to human engineer (`client.calls.create()`)
- [ ] TTS message describing the uncertain mapping (`SpeakElement`)
- [ ] Collect DTMF response via `GetInputElement` (Press 1=Yes, 2=No)
- [ ] Flask webhook server for `/plivo/answer` and `/plivo/input`
- [ ] Thread-safe shared state for collecting responses
- [ ] Return human's decision back to the agent

### 3.3 Composio Tool Execution (`src/tools.py`)
- [ ] Initialize `ComposioToolSet` with API key
- [ ] Transform source data using learned mappings
- [ ] Execute deployment action (e.g., Google Sheets batch update)
- [ ] Report success/failure with record count

### 3.4 GitHub Workflow Update
- [ ] Add Phase 3 test step to `ci.yml`
- [ ] Ensure all external API calls are mocked in CI

```yaml
      - name: Test Phase 3
        run: pytest tests/test_phase3.py -v
```

### 3.5 Tests - Phase 3

```python
# tests/test_phase3.py
"""Phase 3 tests: browser, voice, and tool execution in demo mode."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.browser import BrowserAgent
from src.teacher import Teacher
from src.tools import ToolExecutor


class TestBrowserAgent:
    def test_mock_scrape_client_a(self):
        """Browser returns valid data for Client A in demo mode."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert "columns" in data
        assert "rows" in data
        assert "sample_data" in data
        assert len(data["columns"]) > 5
        assert len(data["rows"]) >= 3
        assert "cust_lvl_v2" in data["columns"]
        browser.close()

    def test_mock_scrape_client_b(self):
        """Browser returns valid data for Client B in demo mode."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        assert "customer_level_ver2" in data["columns"]
        assert len(data["rows"]) >= 3
        browser.close()

    def test_sample_data_has_values(self):
        """Sample data contains actual values from CSV."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        for col in data["columns"]:
            assert col in data["sample_data"]
            assert len(data["sample_data"][col]) > 0
        browser.close()

    def test_unknown_client_falls_back(self):
        """Unknown client name falls back to Client A data."""
        browser = BrowserAgent()
        data = browser.scrape_client_data("Unknown Corp", "https://unknown.com")
        assert len(data["columns"]) > 0
        browser.close()

    def test_parse_csv_handles_raw_string(self):
        """_parse_csv correctly parses a raw CSV string."""
        browser = BrowserAgent()
        raw = "name,age\nAlice,30\nBob,25\n"
        result = browser._parse_csv(raw)
        assert result["columns"] == ["name", "age"]
        assert len(result["rows"]) == 2
        browser.close()


class TestTeacher:
    def test_mock_ask_confirms(self):
        """Teacher returns confirmed=True in demo mode."""
        teacher = Teacher()
        result = teacher.ask_human("cust_lvl_v2", "subscription_tier")
        assert result["confirmed"] is True
        assert result["target_field"] == "subscription_tier"
        assert result["method"] == "demo_simulated"

    def test_mock_ask_returns_dict(self):
        """Response has all required keys."""
        teacher = Teacher()
        result = teacher.ask_human("unknown_col", "some_field")
        assert "confirmed" in result
        assert "target_field" in result
        assert "method" in result


class TestToolExecutor:
    def test_mock_deploy_succeeds(self):
        """Deployment returns success in demo mode."""
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

    def test_transform_data_maps_columns(self):
        """_transform_data correctly renames columns."""
        tools = ToolExecutor()
        mappings = [
            {"source_column": "old_name", "target_field": "new_name"},
            {"source_column": "skip_me", "target_field": "unknown"},
        ]
        rows = [{"old_name": "val1", "skip_me": "val2"}]
        result = tools._transform_data(mappings, rows)
        assert len(result) == 1
        assert "new_name" in result[0]
        assert "unknown" not in result[0]  # "unknown" fields are skipped

    def test_empty_deploy(self):
        """Deploying zero rows still succeeds."""
        tools = ToolExecutor()
        result = tools.deploy_mapping("EmptyClient", [], [])
        assert result["success"] is True
        assert result["records_deployed"] == 0


class TestWebhookServer:
    def test_health_endpoint(self):
        """Webhook server health check returns OK."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json["status"] == "ok"

    def test_answer_returns_xml(self):
        """Answer endpoint returns valid Plivo XML."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post("/plivo/answer?column=test_col&mapping=test_field")
        assert resp.status_code == 200
        assert resp.content_type == "text/xml"
        assert b"<Response>" in resp.data
        assert b"<Speak>" in resp.data or b"<GetInput>" in resp.data

    def test_input_handler_digit_1(self):
        """Input handler processes digit 1 (confirm)."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post(
            "/plivo/input?column=test&mapping=field",
            data={"Digits": "1", "CallUUID": "test-uuid"},
        )
        assert resp.status_code == 200
        assert b"<Speak>" in resp.data

    def test_input_handler_digit_2(self):
        """Input handler processes digit 2 (reject)."""
        from server.webhooks import app
        client = app.test_client()
        resp = client.post(
            "/plivo/input?column=test&mapping=field",
            data={"Digits": "2", "CallUUID": "test-uuid"},
        )
        assert resp.status_code == 200
        assert b"will not map" in resp.data
```

### 3.6 Debug Checklist

#### AGI Inc Browser
- [ ] **401 Unauthorized**: Verify `AGI_API_KEY` is set and valid. Test: `curl -H "Authorization: Bearer $AGI_API_KEY" https://api.agi.tech/v1/sessions`
- [ ] **Session creation timeout**: AGI server may be slow (~30s). Increase `timeout` param
- [ ] **No CSV in response**: The agent may return results in `DONE` type messages. Check `msg["type"]` not just content
- [ ] **Message endpoint**: Use `/message` (singular) for sending, `/messages` (plural) for polling
- [ ] **VNC viewer**: Use `session["vnc_url"]` to watch the agent work in real-time

#### Plivo Voice
- [ ] **Call not ringing**: On trial accounts, destination must be a verified number. Verify at console.plivo.com
- [ ] **answer_url not reachable**: Plivo must reach your server. Use `ngrok http 5000` and set `WEBHOOK_BASE_URL`
- [ ] **No DTMF received**: Check `set_input_type('dtmf')` is set on `GetInputElement`
- [ ] **XML parse error**: Always return `mimetype='text/xml'`. Test with: `curl -X POST localhost:5000/plivo/answer`
- [ ] **Thread safety**: `_pending_responses` dict is shared between Flask threads and the main agent. Use the lock

#### Composio
- [ ] **Import error**: Ensure `pip install composio-gemini` not just `composio`
- [ ] **Auth not connected**: Run `composio add googlesheets` to connect your account first
- [ ] **Action not found**: Action slugs are long. Use `Action.GOOGLESHEETS_BATCH_UPDATE` from the enum, not a string

```bash
# Quick smoke test for Phase 3
DEMO_MODE=true python -c "
from src.browser import BrowserAgent
from src.teacher import Teacher
from src.tools import ToolExecutor

# Browser
b = BrowserAgent()
data = b.scrape_client_data('Acme Corp', 'https://mock.com')
print(f'Browser: {len(data[\"columns\"])} columns, {len(data[\"rows\"])} rows')
b.close()

# Teacher
t = Teacher()
result = t.ask_human('test_col', 'test_field')
print(f'Teacher: confirmed={result[\"confirmed\"]}')

# Tools
tools = ToolExecutor()
deploy = tools.deploy_mapping('Test', [{'source_column':'a','target_field':'b'}], [{'a':'1'}])
print(f'Tools: success={deploy[\"success\"]}')

print('Phase 3: ALL OK')
"
```

## API Details

### AGI Inc (api.agi.tech)
```python
# Create session
POST https://api.agi.tech/v1/sessions
Headers: Authorization: Bearer <AGI_API_KEY>
Body: {"agent_name": "agi-0"}
Response: {"session_id": "...", "vnc_url": "https://vnc.agi.tech/...", "status": "ready"}

# Send task (note: /message singular)
POST https://api.agi.tech/v1/sessions/{session_id}/message
Body: {"message": "Navigate to ... and download CSV", "start_url": "https://..."}

# Poll results (note: /messages plural)
GET https://api.agi.tech/v1/sessions/{session_id}/messages?after_id=0
Response: {"messages": [...], "status": "running|finished|error"}
# Message types: THOUGHT, QUESTION, DONE, ERROR, LOG, USER
```

### Plivo Voice
```python
# Make outbound call
client = plivo.RestClient(auth_id, auth_token)
call = client.calls.create(
    from_='PLIVO_NUMBER',
    to_='ENGINEER_NUMBER',
    answer_url='https://your-ngrok.ngrok.io/plivo/answer',
    answer_method='POST',
)
# call.request_uuid -> track the call

# XML Response with DTMF collection
response = plivoxml.ResponseElement()
get_input = plivoxml.GetInputElement(
    action=f'{BASE_URL}/plivo/input', method='POST',
    input_type='dtmf', digit_end_timeout='5', redirect=True,
)
get_input.add_speak(content="Press 1 for Yes, 2 for No")
response.add(get_input)
```

### Composio
```python
from composio_gemini import Action, ComposioToolSet
toolset = ComposioToolSet(api_key=COMPOSIO_API_KEY)

# LLM-driven tool use
tools = toolset.get_tools(actions=[Action.GOOGLESHEETS_BATCH_UPDATE])

# Direct execution (no LLM)
from composio import Composio
composio = Composio(api_key=COMPOSIO_API_KEY)
composio.tools.execute(user_id="default", slug="GOOGLESHEETS_BATCH_UPDATE", arguments={...})
```

## Definition of Done
- All tests in `test_phase3.py` pass (including webhook tests)
- Browser scrapes data and falls back gracefully
- Teacher simulates a voice call in demo mode
- Tools transform and deploy data correctly
- Webhook server returns valid Plivo XML
