# Phase 1: Foundation & Setup (Hour 1: 11:00 AM - 12:00 PM)

## Goal
Set up project skeleton, dependencies, config, mock data, vector memory system, and CI pipeline.

## Tasks

### 1.1 Environment Setup
- [ ] Create project structure (`src/`, `data/`, `server/`, `phases/`, `tests/`)
- [ ] Create `requirements.txt` with all dependencies
- [ ] Create `.env.example` with all required API keys
- [ ] Create `config.py` for centralized configuration

### 1.2 Mock Data
- [ ] Create `data/mock/client_a_acme.csv` - Messy CSV with ambiguous columns
- [ ] Create `data/mock/client_b_globex.csv` - Similar but different column names
- [ ] Create `data/target_schema.json` - The "correct" SaaS schema to map to

### 1.3 Vector Memory System
- [ ] Implement `src/memory.py` using ChromaDB
- [ ] Embedding-based storage of column name -> canonical field mappings
- [ ] Similarity search with distance thresholds
- [ ] Persistence across runs (the "continual learning" part)

### 1.4 GitHub Workflow - CI Foundation
- [ ] Create `.github/workflows/ci.yml` - runs on every push/PR
- [ ] Lint step: `flake8` or `ruff` for code quality
- [ ] Test step: `pytest` with demo mode enabled
- [ ] Env: inject `DEMO_MODE=true` so CI never hits real APIs

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pip install pytest ruff
      - name: Lint
        run: ruff check src/ tests/
      - name: Test Phase 1
        run: pytest tests/test_phase1.py -v
```

### 1.5 Tests - Phase 1
- [ ] Create `tests/__init__.py`
- [ ] Create `tests/test_phase1.py`

```python
# tests/test_phase1.py
"""Phase 1 tests: config, mock data, and vector memory."""
import os
import json
import csv
import pytest

def test_config_loads():
    """Config module loads without errors."""
    os.environ["DEMO_MODE"] = "true"
    from src.config import Config
    assert Config.DEMO_MODE is True
    assert Config.CONFIDENCE_THRESHOLD > 0
    assert Config.MEMORY_DISTANCE_THRESHOLD > 0

def test_env_example_has_all_keys():
    """All required API keys are documented in .env.example."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
    with open(env_path) as f:
        content = f.read()
    required = ["GEMINI_API_KEY", "AGI_API_KEY", "COMPOSIO_API_KEY",
                "PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "YOU_API_KEY"]
    for key in required:
        assert key in content, f"Missing {key} in .env.example"

def test_mock_csv_client_a_valid():
    """Client A CSV is valid and has expected ambiguous columns."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_a_acme.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= 3, "Need at least 3 rows"
    assert "cust_lvl_v2" in reader.fieldnames, "Missing ambiguous column"

def test_mock_csv_client_b_valid():
    """Client B CSV is valid and has similar-but-different columns."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_b_globex.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= 3
    assert "customer_level_ver2" in reader.fieldnames

def test_target_schema_valid():
    """Target schema JSON is valid and has required fields."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
    with open(schema_path) as f:
        schema = json.load(f)
    assert "fields" in schema
    required_fields = ["customer_id", "full_name", "subscription_tier", "email"]
    for field in required_fields:
        assert field in schema["fields"], f"Missing target field: {field}"

def test_memory_store_crud():
    """MemoryStore can store, lookup, and clear mappings."""
    os.environ["DEMO_MODE"] = "true"
    from src.memory import MemoryStore
    mem = MemoryStore()
    mem.clear()

    # Initially empty
    assert mem.count == 0
    assert mem.find_match("anything") is None

    # Store a mapping
    mem.store_mapping("cust_lvl_v2", "subscription_tier", "TestClient")
    assert mem.count == 1

    # Lookup exact match
    match = mem.find_match("cust_lvl_v2")
    assert match is not None
    assert match["target_field"] == "subscription_tier"

    # Lookup similar match
    match = mem.find_match("customer_level_ver2")
    # May or may not match depending on embedding similarity

    # Clear
    mem.clear()
    assert mem.count == 0

def test_memory_get_all_mappings():
    """get_all_mappings returns stored entries."""
    os.environ["DEMO_MODE"] = "true"
    from src.memory import MemoryStore
    mem = MemoryStore()
    mem.clear()
    mem.store_mapping("col_a", "field_a", "ClientX")
    mem.store_mapping("col_b", "field_b", "ClientX")
    all_m = mem.get_all_mappings()
    assert len(all_m) == 2
    mem.clear()
```

### 1.6 Debug Checklist
- [ ] **Import errors**: Run `python -c "from src.config import Config; print('OK')"` - if it fails, check `python-dotenv` is installed
- [ ] **ChromaDB path issues**: Check `Config.MEMORY_DIR` exists. Run `ls data/memory/` after first memory test
- [ ] **CSV encoding**: If CSV parsing fails, check for BOM or non-UTF8 characters. Open in `vim` or `hexdump`
- [ ] **Schema validation**: Run `python -c "import json; json.load(open('data/target_schema.json'))"` to validate JSON
- [ ] **Permission errors**: If ChromaDB fails on CI, check the runner has write access to `data/memory/`

```bash
# Quick smoke test for Phase 1
DEMO_MODE=true python -c "
from src.config import Config
from src.memory import MemoryStore
print(f'Demo mode: {Config.DEMO_MODE}')
m = MemoryStore()
m.store_mapping('test_col', 'test_field', 'Debug')
result = m.find_match('test_col')
print(f'Memory works: {result is not None}')
m.clear()
print('Phase 1: ALL OK')
"
```

## Key Dependencies
```
google-genai          # Gemini API
chromadb              # Vector database for episodic memory
plivo                 # Voice calls
composio-gemini       # Tool execution
requests              # You.com API + AGI Inc API
flask                 # Webhook server for Plivo
python-dotenv         # Environment variables
rich                  # Beautiful terminal output
pytest                # Testing
ruff                  # Linting
```

## Definition of Done
- All tests in `test_phase1.py` pass
- GitHub Actions CI runs green
- `MemoryStore` can store/retrieve/clear mappings
- All mock data files are valid
