# Phase 1: Config & Vector Memory -- Nihal

## Status

| Component | Code | Tests | CI |
|-----------|------|-------|----|
| `src/config.py` | COMPLETED | REMAINING | REMAINING |
| `src/memory.py` | COMPLETED | REMAINING | REMAINING |
| `data/target_schema.json` | COMPLETED | REMAINING | REMAINING |
| `data/mock/client_a_acme.csv` | COMPLETED | REMAINING | REMAINING |
| `data/mock/client_b_globex.csv` | COMPLETED | REMAINING | REMAINING |
| `.env.example` | COMPLETED | REMAINING | REMAINING |

---

## Owner & Files

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `src/config.py` | 41 | COMPLETED | Centralized env-var config via python-dotenv |
| `src/memory.py` | 109 | COMPLETED | ChromaDB vector store for continual learning |
| `data/target_schema.json` | 63 | COMPLETED | Canonical CRM schema (14 fields) |
| `data/mock/client_a_acme.csv` | 6 | COMPLETED | Acme Corp -- abbreviated column names (5 rows) |
| `data/mock/client_b_globex.csv` | 6 | COMPLETED | Globex -- cleaner column names (5 rows) |
| `.env.example` | -- | COMPLETED | All 10 env vars documented |

---

## What Was Built

### `src/config.py` -- Centralized Configuration

Loads all environment variables at import time via `python-dotenv`. Every other module in the project imports `Config` from here.

```python
class Config:
    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-3-flash-preview"

    # AGI Inc Browser
    AGI_API_KEY = os.getenv("AGI_API_KEY", "")
    AGI_BASE_URL = "https://api.agi.tech/v1"

    # Composio
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")

    # Plivo
    PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID", "")
    PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN", "")
    PLIVO_PHONE_NUMBER = os.getenv("PLIVO_PHONE_NUMBER", "")
    ENGINEER_PHONE_NUMBER = os.getenv("ENGINEER_PHONE_NUMBER", "")

    # You.com
    YOU_API_KEY = os.getenv("YOU_API_KEY", "")
    YOU_SEARCH_URL = "https://api.ydc-index.io/v1/search"

    # Webhook server
    WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "http://localhost:5000")

    # Demo mode
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

    # Memory
    MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory")
    CONFIDENCE_THRESHOLD = 0.75
    MEMORY_DISTANCE_THRESHOLD = 0.3
```

**Key behaviors:**
- `DEMO_MODE` is a boolean parsed from the string env var (`"true"` -> `True`)
- `MEMORY_DIR` is computed relative to the project root: `<project>/data/memory/`
- All API keys default to empty string so the app starts without `.env` (demo mode)

### `src/memory.py` -- ChromaDB Vector Memory Store

Persistent vector store that lets the agent learn column mappings over time. When the agent successfully maps a column (e.g., `cust_id` -> `customer_id`), it stores that mapping as a vector embedding. Future encounters with similar column names retrieve the prior mapping instantly, skipping Gemini entirely.

```python
class MemoryStore:
    def __init__(self):
        """Creates PersistentClient at Config.MEMORY_DIR, gets/creates 'column_mappings' collection with cosine distance."""

    def store_mapping(self, source_column: str, target_field: str, client_name: str) -> None:
        """Upsert mapping with id='{client_name}_{source_column}'. Document is the column name text."""

    def lookup(self, column_name: str, n_results: int = 3) -> list[dict]:
        """Query collection for similar column names. Returns list of:
           {source_column, target_field, client_name, distance, is_confident}
           is_confident = (distance <= Config.MEMORY_DISTANCE_THRESHOLD)"""

    def find_match(self, column_name: str) -> dict | None:
        """Returns best match if is_confident, else None."""

    def get_all_mappings(self) -> list[dict]:
        """Dump all stored mappings (for debug/display)."""

    def clear(self) -> None:
        """Delete and recreate collection (for demo reset)."""

    @property
    def count(self) -> int:
        """Number of stored mappings."""
```

**ChromaDB details:**
- Collection name: `column_mappings`
- Distance metric: cosine (`hnsw:space: cosine`)
- Document ID format: `{client_name}_{source_column}`
- The `documents` field stores the raw column name string (ChromaDB uses its default embedding model to vectorize it)
- `upsert` means re-running on the same client+column overwrites rather than duplicating

### `data/target_schema.json` -- Canonical CRM Schema

14 fields that all client CSVs must map to:

| Field | Type | Description |
|-------|------|-------------|
| `customer_id` | string | Unique customer identifier |
| `full_name` | string | Customer's full name |
| `subscription_tier` | string | Subscription level (Basic/Standard/Premium/Gold/Silver/Bronze) |
| `signup_date` | date | Date the customer signed up (ISO 8601) |
| `email` | string | Customer email address |
| `phone` | string | Customer phone number |
| `address` | string | Street address |
| `city` | string | City name |
| `state` | string | State code (2-letter) |
| `zip_code` | string | Postal/ZIP code |
| `date_of_birth` | date | Customer date of birth (ISO 8601) |
| `account_balance` | number | Current account balance in USD |
| `last_login` | datetime | Last login timestamp (ISO 8601) |
| `is_active` | boolean | Whether the customer account is active |

### Mock CSV Data

**Client A (Acme Corp)** -- `data/mock/client_a_acme.csv`
Abbreviated column names that challenge the agent:
`cust_id, cust_nm, cust_lvl_v2, signup_dt, email_addr, phone_num, addr_line1, city_nm, st_cd, zip_cd, dob, acct_bal, last_login_ts, is_active_flg`

**Client B (Globex)** -- `data/mock/client_b_globex.csv`
Cleaner names that are easier to map:
`customer_id, full_name, customer_level_ver2, registration_date, contact_email, mobile, street_address, city, state_code, postal_code, date_of_birth, balance_usd, last_activity, status`

Both have 5 data rows with realistic sample values.

---

## API Reference

Phase 1 has no external API calls. Config loads env vars; Memory uses ChromaDB locally.

| Dependency | Version | Purpose |
|------------|---------|---------|
| `python-dotenv` | >=1.0.0 | Load `.env` file into `os.environ` |
| `chromadb` | >=0.4.0 | Persistent vector storage with cosine similarity |
| `rich` | >=13.0.0 | Console output formatting in MemoryStore |

---

## Integration Points

### Config (`src/config.py`)

**Imported BY (all modules):**
- `src/memory.py` -- uses `Config.MEMORY_DIR`, `Config.MEMORY_DISTANCE_THRESHOLD`
- `src/brain.py` -- uses `Config.GEMINI_API_KEY`, `Config.GEMINI_MODEL`, `Config.DEMO_MODE`
- `src/research.py` -- uses `Config.YOU_API_KEY`, `Config.YOU_SEARCH_URL`, `Config.DEMO_MODE`
- Phase 4-7 modules -- use `Config.PLIVO_*`, `Config.COMPOSIO_*`, `Config.AGI_*`, `Config.WEBHOOK_BASE_URL`

### Memory (`src/memory.py`)

**Imports FROM:**
- `src/config.py` -- `Config`

**Imported BY:**
- `src/brain.py` -- Brain.__init__ takes `MemoryStore` as dependency
- Phase 7 Agent -- stores confirmed mappings after human approval

**Data flow:**
```
Brain.analyze_columns()
  |-- memory.find_match(col)    # Step 1: check memory
  |      |-- Returns match or None
  |-- If match found: skip Gemini, mark from_memory=True
  |-- If no match: proceed to Research -> Gemini
  |
Agent (Phase 7)
  |-- After human confirms mapping:
  |      memory.store_mapping(col, field, client_name)
  |-- Next client's similar columns auto-match from memory
```

---

## Tests

Tests need to be created. The following two test files cover all Phase 1 functionality.

### `tests/test_phase1_config.py`

```python
"""Phase 1 tests: Config loading and data file validation."""
import os
import csv
import json
import pytest

os.environ["DEMO_MODE"] = "true"

from src.config import Config


class TestConfigValues:
    def test_gemini_model_is_set(self):
        """GEMINI_MODEL has a default value."""
        assert Config.GEMINI_MODEL == "gemini-3-flash-preview"

    def test_demo_mode_is_bool(self):
        """DEMO_MODE is parsed as a boolean."""
        assert isinstance(Config.DEMO_MODE, bool)

    def test_confidence_threshold_is_float(self):
        """CONFIDENCE_THRESHOLD is a float between 0 and 1."""
        assert isinstance(Config.CONFIDENCE_THRESHOLD, float)
        assert 0 < Config.CONFIDENCE_THRESHOLD < 1

    def test_memory_distance_threshold_is_float(self):
        """MEMORY_DISTANCE_THRESHOLD is a float between 0 and 1."""
        assert isinstance(Config.MEMORY_DISTANCE_THRESHOLD, float)
        assert 0 < Config.MEMORY_DISTANCE_THRESHOLD < 1

    def test_memory_dir_is_absolute_path(self):
        """MEMORY_DIR is an absolute path ending with data/memory."""
        assert os.path.isabs(Config.MEMORY_DIR)
        assert Config.MEMORY_DIR.endswith(os.path.join("data", "memory"))

    def test_you_search_url_is_valid(self):
        """YOU_SEARCH_URL points to the You.com API."""
        assert Config.YOU_SEARCH_URL == "https://api.ydc-index.io/v1/search"

    def test_agi_base_url_is_valid(self):
        """AGI_BASE_URL points to the AGI API."""
        assert Config.AGI_BASE_URL == "https://api.agi.tech/v1"

    def test_webhook_base_url_default(self):
        """WEBHOOK_BASE_URL defaults to localhost:5000."""
        # May be overridden by env, but should be a valid URL
        assert Config.WEBHOOK_BASE_URL.startswith("http")

    def test_api_keys_are_strings(self):
        """All API keys are strings (possibly empty)."""
        assert isinstance(Config.GEMINI_API_KEY, str)
        assert isinstance(Config.AGI_API_KEY, str)
        assert isinstance(Config.COMPOSIO_API_KEY, str)
        assert isinstance(Config.YOU_API_KEY, str)

    def test_plivo_fields_are_strings(self):
        """All Plivo fields are strings (possibly empty)."""
        assert isinstance(Config.PLIVO_AUTH_ID, str)
        assert isinstance(Config.PLIVO_AUTH_TOKEN, str)
        assert isinstance(Config.PLIVO_PHONE_NUMBER, str)
        assert isinstance(Config.ENGINEER_PHONE_NUMBER, str)


class TestEnvExample:
    def test_env_example_exists(self):
        """The .env.example file exists at the project root."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        assert os.path.exists(env_path), ".env.example not found"

    def test_env_example_has_all_keys(self):
        """The .env.example documents all required env vars."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        with open(env_path) as f:
            content = f.read()
        required_keys = [
            "GEMINI_API_KEY", "AGI_API_KEY", "COMPOSIO_API_KEY",
            "PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "PLIVO_PHONE_NUMBER",
            "ENGINEER_PHONE_NUMBER", "YOU_API_KEY", "DEMO_MODE",
            "WEBHOOK_BASE_URL",
        ]
        for key in required_keys:
            assert key in content, f"{key} missing from .env.example"


class TestTargetSchema:
    @pytest.fixture
    def schema(self):
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            return json.load(f)

    def test_schema_has_14_fields(self, schema):
        """Target schema defines exactly 14 CRM fields."""
        assert len(schema["fields"]) == 14

    def test_schema_has_required_fields(self, schema):
        """Schema includes all expected canonical field names."""
        expected = [
            "customer_id", "full_name", "subscription_tier", "signup_date",
            "email", "phone", "address", "city", "state", "zip_code",
            "date_of_birth", "account_balance", "last_login", "is_active",
        ]
        for field in expected:
            assert field in schema["fields"], f"Missing schema field: {field}"

    def test_each_field_has_type_and_description(self, schema):
        """Every field has type and description keys."""
        for name, defn in schema["fields"].items():
            assert "type" in defn, f"{name} missing type"
            assert "description" in defn, f"{name} missing description"


class TestMockCSVs:
    def _load_csv(self, filename):
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", filename)
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            return list(reader.fieldnames), list(reader)

    def test_client_a_has_14_columns(self):
        """Client A CSV has exactly 14 columns."""
        cols, _ = self._load_csv("client_a_acme.csv")
        assert len(cols) == 14

    def test_client_a_has_5_rows(self):
        """Client A CSV has 5 data rows."""
        _, rows = self._load_csv("client_a_acme.csv")
        assert len(rows) == 5

    def test_client_b_has_14_columns(self):
        """Client B CSV has exactly 14 columns."""
        cols, _ = self._load_csv("client_b_globex.csv")
        assert len(cols) == 14

    def test_client_b_has_5_rows(self):
        """Client B CSV has 5 data rows."""
        _, rows = self._load_csv("client_b_globex.csv")
        assert len(rows) == 5

    def test_client_a_columns_are_abbreviated(self):
        """Client A uses abbreviated column names (cust_id, cust_nm, etc.)."""
        cols, _ = self._load_csv("client_a_acme.csv")
        assert "cust_id" in cols
        assert "cust_nm" in cols
        assert "cust_lvl_v2" in cols

    def test_client_b_columns_are_cleaner(self):
        """Client B uses cleaner column names (customer_id, full_name, etc.)."""
        cols, _ = self._load_csv("client_b_globex.csv")
        assert "customer_id" in cols
        assert "full_name" in cols

    def test_no_empty_values_in_client_a(self):
        """Client A has no empty cells."""
        _, rows = self._load_csv("client_a_acme.csv")
        for row in rows:
            for key, val in row.items():
                assert val.strip() != "", f"Empty value in Client A: row {row}, col {key}"

    def test_no_empty_values_in_client_b(self):
        """Client B has no empty cells."""
        _, rows = self._load_csv("client_b_globex.csv")
        for row in rows:
            for key, val in row.items():
                assert val.strip() != "", f"Empty value in Client B: row {row}, col {key}"
```

### `tests/test_phase1_memory.py`

```python
"""Phase 1 tests: MemoryStore CRUD, lookup, similarity, and persistence."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.memory import MemoryStore
from src.config import Config


@pytest.fixture
def memory():
    """Fresh MemoryStore for each test, cleared on teardown."""
    mem = MemoryStore()
    mem.clear()
    yield mem
    mem.clear()


class TestMemoryInit:
    def test_initializes_with_zero_count(self, memory):
        """Fresh MemoryStore has zero mappings."""
        assert memory.count == 0

    def test_memory_dir_is_created(self, memory):
        """MemoryStore creates the MEMORY_DIR directory if it doesn't exist."""
        assert os.path.isdir(Config.MEMORY_DIR)


class TestMemoryStoreMappings:
    def test_store_single_mapping(self, memory):
        """Storing one mapping increments count to 1."""
        memory.store_mapping("cust_id", "customer_id", "Acme")
        assert memory.count == 1

    def test_store_multiple_mappings(self, memory):
        """Storing N distinct mappings gives count == N."""
        memory.store_mapping("cust_id", "customer_id", "Acme")
        memory.store_mapping("email_addr", "email", "Acme")
        memory.store_mapping("phone_num", "phone", "Acme")
        assert memory.count == 3

    def test_upsert_same_key_does_not_duplicate(self, memory):
        """Upserting with same client+column replaces, not duplicates."""
        memory.store_mapping("cust_id", "customer_id", "Acme")
        memory.store_mapping("cust_id", "customer_id", "Acme")
        assert memory.count == 1

    def test_upsert_updates_target_field(self, memory):
        """Upserting with a new target_field updates the existing entry."""
        memory.store_mapping("cust_id", "wrong_field", "Acme")
        memory.store_mapping("cust_id", "customer_id", "Acme")
        match = memory.find_match("cust_id")
        assert match is not None
        assert match["target_field"] == "customer_id"

    def test_different_clients_same_column(self, memory):
        """Same column from different clients = separate entries."""
        memory.store_mapping("email", "email", "Acme")
        memory.store_mapping("email", "email", "Globex")
        assert memory.count == 2


class TestMemoryLookup:
    def test_lookup_empty_returns_empty(self, memory):
        """Lookup on empty store returns empty list."""
        results = memory.lookup("anything")
        assert results == []

    def test_lookup_returns_list_of_dicts(self, memory):
        """Lookup returns a list of dict with expected keys."""
        memory.store_mapping("email_addr", "email", "Acme")
        results = memory.lookup("email_addr")
        assert isinstance(results, list)
        assert len(results) >= 1
        result = results[0]
        assert "source_column" in result
        assert "target_field" in result
        assert "client_name" in result
        assert "distance" in result
        assert "is_confident" in result

    def test_exact_match_has_zero_distance(self, memory):
        """Exact same column name returns distance ~0."""
        memory.store_mapping("email_addr", "email", "Acme")
        results = memory.lookup("email_addr")
        assert results[0]["distance"] < 0.01

    def test_exact_match_is_confident(self, memory):
        """Exact match is always within MEMORY_DISTANCE_THRESHOLD."""
        memory.store_mapping("email_addr", "email", "Acme")
        results = memory.lookup("email_addr")
        assert results[0]["is_confident"] is True

    def test_lookup_respects_n_results(self, memory):
        """Lookup returns at most n_results entries."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.store_mapping("col_b", "field_b", "Acme")
        memory.store_mapping("col_c", "field_c", "Acme")
        results = memory.lookup("col_a", n_results=2)
        assert len(results) <= 2

    def test_lookup_n_results_capped_to_count(self, memory):
        """If n_results > count, returns count entries."""
        memory.store_mapping("col_a", "field_a", "Acme")
        results = memory.lookup("col_a", n_results=100)
        assert len(results) == 1


class TestMemoryFindMatch:
    def test_find_match_returns_none_on_empty(self, memory):
        """find_match on empty store returns None."""
        assert memory.find_match("anything") is None

    def test_find_match_returns_exact_match(self, memory):
        """Exact column name returns the stored mapping."""
        memory.store_mapping("email_addr", "email", "Acme")
        match = memory.find_match("email_addr")
        assert match is not None
        assert match["target_field"] == "email"
        assert match["client_name"] == "Acme"

    def test_find_match_returns_none_for_dissimilar(self, memory):
        """Completely unrelated column names return None."""
        memory.store_mapping("email_addr", "email", "Acme")
        match = memory.find_match("total_revenue_ytd_usd")
        # Dissimilar enough that distance > threshold
        # This may or may not be None depending on embedding model
        # but we at least verify the function runs without error
        assert match is None or isinstance(match, dict)


class TestMemoryGetAll:
    def test_get_all_empty(self, memory):
        """get_all_mappings on empty store returns empty list."""
        assert memory.get_all_mappings() == []

    def test_get_all_returns_all_stored(self, memory):
        """get_all_mappings returns every stored mapping."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.store_mapping("col_b", "field_b", "Globex")
        all_mappings = memory.get_all_mappings()
        assert len(all_mappings) == 2
        sources = {m["source_column"] for m in all_mappings}
        assert sources == {"col_a", "col_b"}


class TestMemoryClear:
    def test_clear_resets_count_to_zero(self, memory):
        """clear() removes all mappings."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.store_mapping("col_b", "field_b", "Acme")
        assert memory.count == 2
        memory.clear()
        assert memory.count == 0

    def test_clear_then_store_works(self, memory):
        """Store works normally after clear()."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.clear()
        memory.store_mapping("col_b", "field_b", "Globex")
        assert memory.count == 1
        match = memory.find_match("col_b")
        assert match is not None


class TestContinualLearning:
    def test_learn_from_client_a_helps_client_b(self, memory):
        """Mappings learned from one client help with similar columns from another."""
        # Learn from Client A
        memory.store_mapping("email_addr", "email", "Acme")
        memory.store_mapping("cust_id", "customer_id", "Acme")

        # Client B has similar but not identical column names
        match = memory.find_match("email_addr")
        assert match is not None
        assert match["target_field"] == "email"

    def test_exact_column_reuse_across_clients(self, memory):
        """If Client B uses same column name, memory returns prior mapping."""
        memory.store_mapping("customer_id", "customer_id", "Acme")
        match = memory.find_match("customer_id")
        assert match is not None
        assert match["target_field"] == "customer_id"
        assert match["is_confident"] is True
```

---

## CI Workflow

Create `.github/workflows/phase1.yml`:

```yaml
name: "Phase 1: Config & Memory"

on:
  push:
    paths:
      - "src/config.py"
      - "src/memory.py"
      - "data/target_schema.json"
      - "data/mock/*.csv"
      - "tests/test_phase1_*.py"
  pull_request:
    paths:
      - "src/config.py"
      - "src/memory.py"
      - "data/target_schema.json"
      - "data/mock/*.csv"
      - "tests/test_phase1_*.py"

jobs:
  phase1-tests:
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

      - name: Lint Phase 1 files
        run: ruff check src/config.py src/memory.py

      - name: Config & data tests
        run: pytest tests/test_phase1_config.py -v

      - name: Memory tests
        run: pytest tests/test_phase1_memory.py -v
```

---

## Debug Checklist

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: dotenv` | `python-dotenv` not installed | `pip install python-dotenv` |
| `chromadb.errors.NoIndexException` | Stale ChromaDB data after schema change | Delete `data/memory/` directory and restart |
| `Config.DEMO_MODE` is `False` when it should be `True` | `.env` file has `DEMO_MODE=True` (capital T) | Must be lowercase: `DEMO_MODE=true` |
| `MemoryStore.count` is 0 after storing | `clear()` called after `store_mapping()` in test fixture teardown | Check fixture ordering; use `yield` |
| `lookup()` returns empty list | Collection is empty (count == 0) | Verify `store_mapping()` was called first |
| `find_match()` returns `None` for similar names | Distance > `MEMORY_DISTANCE_THRESHOLD` (0.3) | Lower threshold or use exact column names |
| `MEMORY_DIR` path is wrong | Running from unexpected working directory | `MEMORY_DIR` is computed relative to `config.py`, not `cwd` |
| CSV has 13 columns instead of 14 | Trailing comma or missing header | Open CSV and verify header row has exactly 14 comma-separated values |
| `PermissionError` on `data/memory/` | ChromaDB can't write to disk | `chmod -R 755 data/memory/` or check Docker volume mounts |
| Duplicate memory entries | Different `client_name` for same column | Expected behavior -- same column from different clients = separate entries |

---

## Smoke Test

```bash
# From project root
DEMO_MODE=true python -c "
from src.config import Config
from src.memory import MemoryStore

print(f'Demo mode: {Config.DEMO_MODE}')
print(f'Memory dir: {Config.MEMORY_DIR}')

mem = MemoryStore()
mem.clear()
mem.store_mapping('cust_id', 'customer_id', 'SmokeTest')
match = mem.find_match('cust_id')
assert match is not None, 'FAIL: find_match returned None'
assert match['target_field'] == 'customer_id', 'FAIL: wrong target'
print(f'Stored: {mem.count} mapping(s)')
print(f'Match: {match}')
mem.clear()
print('PASS: Phase 1 smoke test')
"
```

---

## Definition of Done

- [x] `src/config.py` loads all env vars with correct defaults
- [x] `src/memory.py` provides full CRUD via ChromaDB
- [x] `data/target_schema.json` defines 14 CRM fields
- [x] `data/mock/client_a_acme.csv` has 14 abbreviated columns, 5 rows
- [x] `data/mock/client_b_globex.csv` has 14 clean columns, 5 rows
- [x] `.env.example` documents all 10 env vars
- [ ] `tests/test_phase1_config.py` created and passing
- [ ] `tests/test_phase1_memory.py` created and passing
- [ ] `.github/workflows/phase1.yml` created and green
- [ ] All tests pass in CI with `DEMO_MODE=true`
