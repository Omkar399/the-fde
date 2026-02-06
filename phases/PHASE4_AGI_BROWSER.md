# Phase 4: AGI Inc Browser Agent -- Nihal

## Status

| Area       | Status         |
| ---------- | -------------- |
| Code       | COMPLETED      |
| Tests      | REMAINING      |
| CI         | REMAINING      |
| Integration| COMPLETED (used by Agent step 1) |

---

## Owner & Files

**Owner:** Nihal

| File                  | Lines | Purpose                                  |
| --------------------- | ----- | ---------------------------------------- |
| `src/browser.py`      | 169   | `BrowserAgent` class -- scrape client portals via AGI Inc API |
| `data/mock/client_a_acme.csv`   | 6 | Mock CSV for Acme Corp (5 data rows, 14 columns) |
| `data/mock/client_b_globex.csv` | 6 | Mock CSV for Globex Inc (5 data rows, 14 columns) |

---

## What Was Built

`BrowserAgent` automates client portal scraping through the AGI Inc browser-automation API. In production it creates a remote browser session, instructs it to navigate to a portal URL, and polls for a CSV result. In demo mode (or on API failure) it loads a local CSV from `data/mock/`.

### Class: `BrowserAgent`

| Method | Signature | Behavior |
| ------ | --------- | -------- |
| `__init__` | `()` | Sets `_session_id = None`. No network calls. |
| `scrape_client_data` | `(client_name: str, portal_url: str) -> dict` | Entry point. Returns `{columns, rows, sample_data, raw_csv}`. Routes to `_agi_scrape` or `_mock_scrape` based on `Config.DEMO_MODE`. On API failure, falls back to `_mock_scrape`. |
| `_agi_scrape` | `(client_name: str, portal_url: str) -> dict` | Creates AGI session (`POST /sessions` with `agent_name="agi-0"`), sends navigation task (`POST /sessions/{id}/messages`), polls for CSV via `_poll_for_result`. |
| `_poll_for_result` | `(headers: dict, max_polls: int = 30) -> str \| None` | Polls `GET /sessions/{id}/messages?after_id=N` every 2 seconds up to `max_polls` times. Returns the first message whose content contains both `,` and `\n` (CSV heuristic). Returns `None` if session finishes or errors without CSV. |
| `_mock_scrape` | `(client_name: str) -> dict` | Loads CSV from `data/mock/` using file map. Simulates browser delay with `time.sleep`. |
| `_parse_csv` | `(raw_csv: str) -> dict` | Uses `csv.DictReader` on `io.StringIO(raw_csv)`. Returns `{columns: list, rows: list[dict], sample_data: dict, raw_csv: str}`. `sample_data` is a dict mapping each column name to its first 3 row values. |
| `close` | `()` | Sends `DELETE /sessions/{id}` if a session is active and not in demo mode. Resets `_session_id = None`. |

### Mock File Map

| `client_name` argument | CSV file loaded                |
| ----------------------- | ------------------------------ |
| `"Acme Corp"`           | `data/mock/client_a_acme.csv`  |
| `"Globex Inc"`          | `data/mock/client_b_globex.csv`|
| anything else           | `data/mock/client_a_acme.csv` (default) |

### Return Shape

```python
{
    "columns": ["cust_id", "cust_nm", ...],         # list[str] -- header names
    "rows": [{"cust_id": "1001", ...}, ...],         # list[dict] -- all data rows
    "sample_data": {"cust_id": ["1001", "1002", "1003"], ...},  # dict[str, list] -- first 3 values
    "raw_csv": "cust_id,cust_nm,...\n1001,..."        # str -- original CSV text
}
```

---

## API Reference

### AGI Inc Browser Automation API

**Base URL:** `https://api.agi.tech/v1` (from `Config.AGI_BASE_URL`)

**Authentication:** Bearer token via `Authorization: Bearer {Config.AGI_API_KEY}`

| Endpoint | Method | Request Body | Response | Purpose |
| -------- | ------ | ------------ | -------- | ------- |
| `/sessions` | POST | `{"agent_name": "agi-0"}` | `{"session_id": str, "vnc_url": str, "status": str}` | Create a new browser session |
| `/sessions/{id}/messages` | POST | `{"content": str}` | `{"message_id": str, "status": str}` | Send a navigation/scrape task |
| `/sessions/{id}/messages` | GET | Query: `after_id=N` | `{"messages": [{id, type, content}], "status": str}` | Poll for results |
| `/sessions/{id}` | DELETE | -- | `{"status": "deleted"}` | Clean up session |

### Message Types

| Type | Meaning |
| ---- | ------- |
| `THOUGHT` | Agent's reasoning step (informational) |
| `QUESTION` | Agent needs clarification |
| `DONE` | Task completed -- content may contain CSV |
| `ERROR` | Task failed |
| `LOG` | Debug/status log |
| `USER` | User-sent message |

### CSV Detection Heuristic

The poller treats any message content containing both `,` and `\n` as CSV data. This is intentionally simple for the hackathon.

---

## Integration Points

```
Agent.onboard_client()
    |
    +-- Step 1: self.browser.scrape_client_data(client_name, portal_url)
    |           Returns {columns, rows, sample_data, raw_csv}
    |
    +-- columns & sample_data feed into Step 2 (Brain.analyze_columns)
    +-- rows feed into Step 5 (ToolExecutor.deploy_mapping)
```

**Config keys used:**
- `Config.AGI_API_KEY` -- Bearer token for AGI Inc API
- `Config.AGI_BASE_URL` -- API base URL (`https://api.agi.tech/v1`)
- `Config.DEMO_MODE` -- When `"true"`, skip API calls entirely and use mock CSVs

**Called by:** `FDEAgent.onboard_client()` in `src/agent.py` (step 1)

**Depends on:** `src/config.py`, `data/mock/*.csv`, `requests`, `csv`, `io`, `time`, `rich`

---

## Tests

File: `tests/test_phase4_browser.py`

```python
"""Phase 4 tests: AGI Inc BrowserAgent in demo mode."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.browser import BrowserAgent


@pytest.fixture
def browser():
    b = BrowserAgent()
    yield b
    b.close()


# ---------------------------------------------------------------------------
# TestBrowserInit -- verify construction and teardown
# ---------------------------------------------------------------------------
class TestBrowserInit:
    def test_init_session_is_none(self):
        """BrowserAgent starts with no active session."""
        b = BrowserAgent()
        assert b._session_id is None

    def test_close_on_fresh_instance(self):
        """Calling close() on a fresh instance does not raise."""
        b = BrowserAgent()
        b.close()  # should be a no-op
        assert b._session_id is None


# ---------------------------------------------------------------------------
# TestBrowserScrapeClientA -- Acme Corp mock data
# ---------------------------------------------------------------------------
class TestBrowserScrapeClientA:
    def test_returns_valid_structure(self, browser):
        """scrape_client_data returns dict with required keys."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert isinstance(result, dict)
        assert "columns" in result
        assert "rows" in result
        assert "sample_data" in result
        assert "raw_csv" in result

    def test_columns_match_acme_csv(self, browser):
        """Columns match the header row in client_a_acme.csv."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        expected = [
            "cust_id", "cust_nm", "cust_lvl_v2", "signup_dt", "email_addr",
            "phone_num", "addr_line1", "city_nm", "st_cd", "zip_cd",
            "dob", "acct_bal", "last_login_ts", "is_active_flg",
        ]
        assert result["columns"] == expected

    def test_rows_count(self, browser):
        """Acme CSV has 5 data rows."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert len(result["rows"]) == 5

    def test_sample_data_has_three_values(self, browser):
        """sample_data contains at most 3 values per column."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        for col, values in result["sample_data"].items():
            assert len(values) <= 3
            assert col in result["columns"]


# ---------------------------------------------------------------------------
# TestBrowserScrapeClientB -- Globex Inc mock data
# ---------------------------------------------------------------------------
class TestBrowserScrapeClientB:
    def test_columns_match_globex_csv(self, browser):
        """Columns match the header row in client_b_globex.csv."""
        result = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        expected = [
            "customer_id", "full_name", "customer_level_ver2",
            "registration_date", "contact_email", "mobile",
            "street_address", "city", "state_code", "postal_code",
            "date_of_birth", "balance_usd", "last_activity", "status",
        ]
        assert result["columns"] == expected

    def test_rows_count(self, browser):
        """Globex CSV has 5 data rows."""
        result = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        assert len(result["rows"]) == 5


# ---------------------------------------------------------------------------
# TestBrowserFallback -- unknown client name
# ---------------------------------------------------------------------------
class TestBrowserFallback:
    def test_unknown_client_falls_back_to_acme(self, browser):
        """An unrecognized client name loads the default (Acme Corp) CSV."""
        result = browser.scrape_client_data("Unknown Co", "https://example.com")
        assert result["columns"][0] == "cust_id"
        assert len(result["rows"]) == 5


# ---------------------------------------------------------------------------
# TestBrowserCSVParser -- _parse_csv unit tests
# ---------------------------------------------------------------------------
class TestBrowserCSVParser:
    def test_simple_parse(self):
        """_parse_csv correctly splits a two-row CSV."""
        b = BrowserAgent()
        raw = "name,age\nAlice,30\nBob,25\n"
        result = b._parse_csv(raw)
        assert result["columns"] == ["name", "age"]
        assert len(result["rows"]) == 2
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][1]["age"] == "25"

    def test_sample_data_limited_to_three(self):
        """sample_data includes at most 3 values even with more rows."""
        b = BrowserAgent()
        raw = "x\n1\n2\n3\n4\n5\n"
        result = b._parse_csv(raw)
        assert len(result["sample_data"]["x"]) == 3
        assert result["sample_data"]["x"] == ["1", "2", "3"]

    def test_preserves_raw_csv(self):
        """raw_csv key contains the original CSV string unmodified."""
        b = BrowserAgent()
        raw = "col_a,col_b\nfoo,bar\n"
        result = b._parse_csv(raw)
        assert result["raw_csv"] == raw
```

### Running Tests

```bash
DEMO_MODE=true pytest tests/test_phase4_browser.py -v
```

---

## CI Workflow

File: `.github/workflows/phase4.yml`

```yaml
name: "Phase 4: AGI Browser"

on:
  push:
    paths:
      - "src/browser.py"
      - "tests/test_phase4_*.py"
  pull_request:
    paths:
      - "src/browser.py"
      - "tests/test_phase4_*.py"

jobs:
  phase4-tests:
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

      - name: Lint Phase 4 files
        run: ruff check src/browser.py

      - name: Run Phase 4 tests
        run: pytest tests/test_phase4_browser.py -v
```

---

## Debug Checklist

| Symptom | Likely Cause | Fix |
| ------- | ------------ | --- |
| `FileNotFoundError` on mock CSV | Working directory is wrong or `data/mock/` is missing | Run from repo root; confirm `data/mock/client_a_acme.csv` exists |
| `scrape_client_data` returns Acme data for Globex | Client name string does not match `"Globex Inc"` exactly (case-sensitive) | Pass the exact string `"Globex Inc"` |
| `_agi_scrape` raises `ConnectionError` | AGI Inc API is unreachable or `AGI_API_KEY` is unset | Set `AGI_API_KEY` in `.env`; verify network; code auto-falls back to mock |
| `_poll_for_result` returns `None` | Session completed before CSV was detected, or CSV heuristic missed content | Increase `max_polls`; check that the response truly contains `,` and `\n` |
| `_parse_csv` returns empty columns | Raw CSV string is empty or has no header line | Inspect `raw_csv` content; ensure the file is not blank |
| `close()` silently fails | `DELETE /sessions/{id}` returned a non-2xx; exception is swallowed | Check API logs; this is by design (best-effort cleanup) |
| Tests import error: `ModuleNotFoundError: src` | Running pytest from wrong directory or missing `__init__.py` | Run `pytest` from the repo root; confirm `src/__init__.py` exists |
| `sample_data` has fewer than 3 values | Source CSV has fewer than 3 data rows | Expected behavior -- `sample_data` reflects actual data, capped at 3 |

---

## Smoke Test

Quick manual verification in a Python REPL:

```python
import os
os.environ["DEMO_MODE"] = "true"

from src.browser import BrowserAgent

b = BrowserAgent()
result = b.scrape_client_data("Acme Corp", "https://portal.acme.com")

print(f"Columns ({len(result['columns'])}): {result['columns'][:4]}...")
print(f"Rows: {len(result['rows'])}")
print(f"Sample (cust_id): {result['sample_data']['cust_id']}")
print(f"Raw CSV starts with: {result['raw_csv'][:50]}...")

b.close()
```

Expected output:

```
Columns (14): ['cust_id', 'cust_nm', 'cust_lvl_v2', 'signup_dt']...
Rows: 5
Sample (cust_id): ['1001', '1002', '1003']
Raw CSV starts with: cust_id,cust_nm,cust_lvl_v2,signup_dt,email_addr,...
```

---

## Definition of Done

- [ ] `tests/test_phase4_browser.py` exists with all 12 tests passing
- [ ] `.github/workflows/phase4.yml` exists and triggers on `src/browser.py` and `tests/test_phase4_*` changes
- [ ] `DEMO_MODE=true pytest tests/test_phase4_browser.py -v` passes with 12/12 green
- [ ] CI workflow runs successfully on push to `main` or PR
- [ ] No lint errors from `ruff check src/browser.py`
