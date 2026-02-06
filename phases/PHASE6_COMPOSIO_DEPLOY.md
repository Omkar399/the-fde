# Phase 6: Composio Deploy -- Omkar

## Status

| Aspect | Status |
|--------|--------|
| Source code | COMPLETED |
| Unit tests | REMAINING |
| CI workflow | REMAINING |
| Integration | Wired into Phase 7 (Agent step 5) |

---

## Owner & Files

**Owner:** Omkar

| File | Lines | Purpose |
|------|-------|---------|
| `src/tools.py` | 124 | `ToolExecutor` class -- Composio-based execution layer for deploying mapped data |
| `src/config.py` | 41 | `Config.COMPOSIO_API_KEY` and `Config.DEMO_MODE` used by ToolExecutor |

---

## What Was Built

`ToolExecutor` is the final step in the FDE pipeline. After the Brain analyzes columns, the Teacher confirms uncertain mappings, and Memory stores learnings, the ToolExecutor transforms source data using the confirmed mappings and deploys it to the target SaaS system via Composio.

### Class: `ToolExecutor`

**`__init__(self)`**
- Checks `Config.DEMO_MODE`. If `False`, attempts to import `composio_gemini.ComposioToolSet`.
- Initializes `self._toolset` with `ComposioToolSet(api_key=Config.COMPOSIO_API_KEY)` on success, or `None` on failure.
- Prints a yellow warning if the import or initialization fails (graceful degradation).

**`deploy_mapping(self, client_name, mappings, rows) -> dict`**
- Public entry point. Returns `{"success": bool, "records_deployed": int, "message": str}`.
- In `DEMO_MODE`, delegates to `_mock_deploy()`.
- Otherwise, tries `_composio_deploy()` and falls back to `_mock_deploy()` on any exception.

**`_composio_deploy(self, client_name, mappings, rows) -> dict`**
- Calls `_transform_data(mappings, rows)` to remap column names.
- If `self._toolset` is available, executes `Action.GOOGLESHEETS_BATCH_UPDATE` with `params={"data": transformed, "client_name": client_name}`.
- Checks `response.get("success", False)` if the response is a dict; otherwise assumes `True`.
- Returns the standard result dict.

**`_mock_deploy(self, client_name, mappings, rows) -> dict`**
- Simulates deployment with three `time.sleep()` calls and Rich console output.
- Always returns `{"success": True, ...}`.

**`_transform_data(self, mappings, rows) -> list[dict]`**
- Builds a mapping dict: `{source_column: target_field}` for all mappings where `target_field` exists and is not `"unknown"`.
- For each row, creates a new dict with keys renamed from source to target.
- Returns the list of transformed rows.

### Data Transformation Logic

```python
# Build rename map, skipping unknown targets
mapping_dict = {
    m["source_column"]: m["target_field"]
    for m in mappings
    if m.get("target_field") and m["target_field"] != "unknown"
}

# Apply to each row
transformed = []
for row in rows:
    new_row = {}
    for src_col, value in row.items():
        target = mapping_dict.get(src_col)
        if target:
            new_row[target] = value
    transformed.append(new_row)
```

Key behaviors:
- Columns mapped to `"unknown"` are silently dropped.
- Columns with no mapping entry are silently dropped.
- Empty mappings list produces a list of empty dicts (one per row).
- Empty rows list produces an empty list.

---

## API Reference

### Composio Setup

| Item | Value |
|------|-------|
| Package | `composio-gemini>=0.1.0` |
| Auth setup | `composio add googlesheets` (one-time CLI authorization) |
| Env var | `COMPOSIO_API_KEY` |
| ToolSet init | `ComposioToolSet(api_key=Config.COMPOSIO_API_KEY)` |

### Composio Execution

```python
from composio_gemini import ComposioToolSet, Action

toolset = ComposioToolSet(api_key="...")
response = toolset.execute_action(
    action=Action.GOOGLESHEETS_BATCH_UPDATE,
    params={
        "data": [{"customer_id": "1001", "full_name": "John Smith", ...}],
        "client_name": "Acme Corp",
    },
)
```

**Alternative pattern** (not used in this codebase but available):
```python
composio.tools.execute(user_id="...", slug="googlesheets_batch_update", arguments={...})
```

---

## Integration Points

```
Phase 7 (Agent)                          Phase 6 (ToolExecutor)
    |                                         |
    | step 5: tools.deploy_mapping(           |
    |           client_name,                  |
    |           confident_mappings,           |
    |           rows)                         |
    |  -------------------------------------> |
    |                                         | _transform_data()
    |                                         | _composio_deploy() or _mock_deploy()
    |  <------------------------------------- |
    | result = {success, records_deployed,    |
    |           message}                      |
```

- **Imported by:** `src/agent.py` (Phase 7) -- `from src.tools import ToolExecutor`
- **Imports:** `src.config.Config` (Phase 1)
- **No other modules import this.** ToolExecutor is a leaf node in the dependency graph.

### Data contract

The `mappings` parameter comes from Brain (Phase 2) + Teacher (Phase 5) and has this shape:
```python
[
    {"source_column": "cust_id", "target_field": "customer_id", "confidence": "high", ...},
    {"source_column": "cust_lvl_v2", "target_field": "subscription_tier", "confidence": "high", ...},
]
```

The `rows` parameter comes from Browser (Phase 3) and has this shape:
```python
[
    {"cust_id": "1001", "cust_nm": "John Smith", "cust_lvl_v2": "Gold", ...},
    {"cust_id": "1002", "cust_nm": "Jane Doe", "cust_lvl_v2": "Silver", ...},
]
```

---

## Tests

File: `tests/test_phase6_composio.py`

```python
"""Phase 6 tests: Composio ToolExecutor -- deploy mapping and data transformation."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ["DEMO_MODE"] = "true"

from src.tools import ToolExecutor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def executor():
    """Create a ToolExecutor in demo mode."""
    return ToolExecutor()


@pytest.fixture
def sample_mappings():
    """Standard set of column mappings."""
    return [
        {"source_column": "cust_id", "target_field": "customer_id"},
        {"source_column": "cust_nm", "target_field": "full_name"},
        {"source_column": "email_addr", "target_field": "email"},
    ]


@pytest.fixture
def sample_rows():
    """Sample data rows matching Client A CSV."""
    return [
        {"cust_id": "1001", "cust_nm": "John Smith", "email_addr": "john@acme.com"},
        {"cust_id": "1002", "cust_nm": "Jane Doe", "email_addr": "jane@acme.com"},
    ]


# ---------------------------------------------------------------------------
# TestToolExecutorInit
# ---------------------------------------------------------------------------

class TestToolExecutorInit:
    def test_demo_mode_toolset_is_none(self, executor):
        """In demo mode, _toolset is None (no Composio import attempted)."""
        assert executor._toolset is None


# ---------------------------------------------------------------------------
# TestToolExecutorDeploy
# ---------------------------------------------------------------------------

class TestToolExecutorDeploy:
    def test_deploy_success(self, executor, sample_mappings, sample_rows):
        """deploy_mapping returns success=True with correct record count."""
        result = executor.deploy_mapping("Acme Corp", sample_mappings, sample_rows)
        assert result["success"] is True
        assert result["records_deployed"] == 2
        assert "Acme Corp" in result["message"]

    def test_deploy_empty_data(self, executor, sample_mappings):
        """Deploying with zero rows succeeds with records_deployed=0."""
        result = executor.deploy_mapping("EmptyClient", sample_mappings, [])
        assert result["success"] is True
        assert result["records_deployed"] == 0

    def test_deploy_result_has_required_keys(self, executor, sample_mappings, sample_rows):
        """Result dict always contains success, records_deployed, message."""
        result = executor.deploy_mapping("TestCorp", sample_mappings, sample_rows)
        assert "success" in result
        assert "records_deployed" in result
        assert "message" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["records_deployed"], int)
        assert isinstance(result["message"], str)


# ---------------------------------------------------------------------------
# TestToolExecutorTransform
# ---------------------------------------------------------------------------

class TestToolExecutorTransform:
    def test_renames_columns(self, executor):
        """Source columns are renamed to target fields."""
        mappings = [{"source_column": "cust_id", "target_field": "customer_id"}]
        rows = [{"cust_id": "1001"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]

    def test_skips_unknown_target(self, executor):
        """Mappings with target_field='unknown' are excluded from output."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "weird_col", "target_field": "unknown"},
        ]
        rows = [{"cust_id": "1001", "weird_col": "garbage"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]
        assert "unknown" not in result[0]

    def test_multiple_rows(self, executor):
        """Transform works correctly across multiple rows."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "email_addr", "target_field": "email"},
        ]
        rows = [
            {"cust_id": "1001", "email_addr": "a@b.com"},
            {"cust_id": "1002", "email_addr": "c@d.com"},
            {"cust_id": "1003", "email_addr": "e@f.com"},
        ]
        result = executor._transform_data(mappings, rows)
        assert len(result) == 3
        assert result[0] == {"customer_id": "1001", "email": "a@b.com"}
        assert result[2] == {"customer_id": "1003", "email": "e@f.com"}

    def test_ignores_unmapped_source_columns(self, executor):
        """Source columns without a mapping entry are dropped from output."""
        mappings = [{"source_column": "cust_id", "target_field": "customer_id"}]
        rows = [{"cust_id": "1001", "extra_col": "should_vanish"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]
        assert "extra_col" not in result[0]

    def test_empty_mappings(self, executor):
        """Empty mappings list produces rows of empty dicts."""
        rows = [{"cust_id": "1001"}, {"cust_id": "1002"}]
        result = executor._transform_data([], rows)
        assert len(result) == 2
        assert result[0] == {}
        assert result[1] == {}

    def test_skips_mapping_without_target_field(self, executor):
        """Mappings missing the target_field key are skipped."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm"},  # No target_field key
        ]
        rows = [{"cust_id": "1001", "cust_nm": "John"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]

    def test_real_client_data_transform(self, executor):
        """Transform with realistic Client A data and full mappings."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm", "target_field": "full_name"},
            {"source_column": "cust_lvl_v2", "target_field": "subscription_tier"},
            {"source_column": "signup_dt", "target_field": "signup_date"},
            {"source_column": "email_addr", "target_field": "email"},
            {"source_column": "phone_num", "target_field": "phone"},
            {"source_column": "addr_line1", "target_field": "address"},
            {"source_column": "city_nm", "target_field": "city"},
            {"source_column": "st_cd", "target_field": "state"},
            {"source_column": "zip_cd", "target_field": "zip_code"},
            {"source_column": "dob", "target_field": "date_of_birth"},
            {"source_column": "acct_bal", "target_field": "account_balance"},
            {"source_column": "last_login_ts", "target_field": "last_login"},
            {"source_column": "is_active_flg", "target_field": "is_active"},
        ]
        rows = [
            {
                "cust_id": "1001", "cust_nm": "John Smith",
                "cust_lvl_v2": "Gold", "signup_dt": "2023-01-15",
                "email_addr": "john.smith@acme.com", "phone_num": "555-0101",
                "addr_line1": "123 Main St", "city_nm": "Springfield",
                "st_cd": "IL", "zip_cd": "62701",
                "dob": "1985-03-22", "acct_bal": "1500.00",
                "last_login_ts": "2024-11-01 09:30:00", "is_active_flg": "Y",
            },
        ]
        result = executor._transform_data(mappings, rows)
        assert len(result) == 1
        row = result[0]
        assert row["customer_id"] == "1001"
        assert row["full_name"] == "John Smith"
        assert row["subscription_tier"] == "Gold"
        assert row["email"] == "john.smith@acme.com"
        assert row["state"] == "IL"
        assert row["is_active"] == "Y"
        # Verify all 14 target fields present
        assert len(row) == 14
```

---

## CI Workflow

File: `.github/workflows/phase6.yml`

```yaml
name: "Phase 6: Composio Deploy"

on:
  push:
    paths:
      - "src/tools.py"
      - "tests/test_phase6_*.py"
  pull_request:
    paths:
      - "src/tools.py"
      - "tests/test_phase6_*.py"

jobs:
  phase6-tests:
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

      - name: Lint Phase 6 files
        run: ruff check src/tools.py --select E,F,W --ignore E501,F541

      - name: Run Phase 6 tests
        run: pytest tests/test_phase6_composio.py -v
```

---

## Debug Checklist

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: composio_gemini` | `composio-gemini` not installed | `pip install composio-gemini>=0.1.0` |
| `_toolset is None` outside demo mode | Composio import failed silently | Check the yellow warning in console output; verify `COMPOSIO_API_KEY` is set |
| `deploy_mapping` returns mock result in production | `_composio_deploy` raised an exception | Check exception message in yellow console output; verify Composio auth with `composio whoami` |
| Transformed data has empty dicts | All mappings have `target_field = "unknown"` or are missing the key | Verify Brain/Teacher produced valid mappings with non-unknown targets |
| `records_deployed` is 0 but `success` is True | Rows list was empty or all source columns were unmapped | Check that Browser returned non-empty rows and mappings cover actual columns |
| `KeyError: 'source_column'` in `_transform_data` | Mapping dict is malformed (missing `source_column` key) | Validate mapping structure before calling deploy; Brain should always include this key |
| Google Sheets update fails via Composio | OAuth token expired or sheet permissions changed | Run `composio add googlesheets` again to re-authorize |
| Tests fail with `time.sleep` taking too long | Mock deploy has 1.3s of sleep calls | Tests run in demo mode which uses `_mock_deploy`; this is expected latency |
| `DEMO_MODE` not respected | Environment variable not set before import | Set `os.environ["DEMO_MODE"] = "true"` before importing `src.tools` |

---

## Smoke Test

```bash
# 1. Verify import works
DEMO_MODE=true python -c "from src.tools import ToolExecutor; t = ToolExecutor(); print('toolset:', t._toolset)"
# Expected: toolset: None

# 2. Quick deploy test
DEMO_MODE=true python -c "
from src.tools import ToolExecutor
t = ToolExecutor()
result = t.deploy_mapping('SmokeTest', [{'source_column': 'a', 'target_field': 'b'}], [{'a': '1'}])
print(result)
assert result['success'] is True
assert result['records_deployed'] == 1
print('SMOKE TEST PASSED')
"

# 3. Transform-only test
DEMO_MODE=true python -c "
from src.tools import ToolExecutor
t = ToolExecutor()
out = t._transform_data(
    [{'source_column': 'x', 'target_field': 'y'}, {'source_column': 'z', 'target_field': 'unknown'}],
    [{'x': '1', 'z': '2'}]
)
assert out == [{'y': '1'}], f'Got: {out}'
print('TRANSFORM SMOKE TEST PASSED')
"

# 4. Run the full test suite
DEMO_MODE=true pytest tests/test_phase6_composio.py -v
```

---

## Definition of Done

- [ ] `tests/test_phase6_composio.py` exists with all 11 tests (1 init + 3 deploy + 7 transform)
- [ ] All 11 tests pass: `DEMO_MODE=true pytest tests/test_phase6_composio.py -v`
- [ ] `.github/workflows/phase6.yml` exists and triggers on `src/tools.py` and `tests/test_phase6_*` changes
- [ ] `ruff check src/tools.py` passes with zero errors
- [ ] Smoke test commands above all produce `PASSED` output
- [ ] Phase 7 agent integration still works: `DEMO_MODE=true python -c "from src.agent import FDEAgent"`
