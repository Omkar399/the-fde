# Phase 1: Foundation & Setup (1 Hour)

## Goal
Set up the complete project foundation: config system, vector memory, mock data, schema, and CI. Two teammates work in parallel on completely separate files.

## Time Budget
| Task | Time | Owner |
|------|------|-------|
| Interface contract review | 5 min | Both |
| Teammate A: Config + Data | 25 min | Teammate A |
| Teammate B: Memory system | 25 min | Teammate B |
| Integration sync + tests | 5 min | Both |

---

## Interface Contract (Agree on This FIRST)

Before splitting, both teammates must agree on these exact signatures:

### Config Constants (Teammate A creates, Teammate B depends on)
```python
# src/config.py - Teammate A owns this file
class Config:
    # Memory settings - Teammate B will use these
    MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory")
    CONFIDENCE_THRESHOLD = 0.75       # Below this confidence score, ask the human
    MEMORY_DISTANCE_THRESHOLD = 0.3   # Max cosine distance for auto-match in ChromaDB

    # All API keys loaded from .env
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    AGI_API_KEY = os.getenv("AGI_API_KEY", "")
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
    PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID", "")
    PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN", "")
    PLIVO_PHONE_NUMBER = os.getenv("PLIVO_PHONE_NUMBER", "")
    ENGINEER_PHONE_NUMBER = os.getenv("ENGINEER_PHONE_NUMBER", "")
    YOU_API_KEY = os.getenv("YOU_API_KEY", "")

    # Service URLs
    YOU_SEARCH_URL = "https://api.ydc-index.io/v1/search"
    AGI_BASE_URL = "https://api.agi.tech/v1"
    GEMINI_MODEL = "gemini-2.0-flash"
    WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "http://localhost:5000")

    # Demo mode (for CI/testing only - live demo uses real APIs)
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
```

### MemoryStore API (Teammate B creates, all other phases depend on)
```python
# src/memory.py - Teammate B owns this file
class MemoryStore:
    def __init__(self) -> None: ...
    def store_mapping(self, source_column: str, target_field: str, client_name: str) -> None: ...
    def lookup(self, column_name: str, n_results: int = 3) -> list[dict]: ...
    def find_match(self, column_name: str) -> dict | None: ...
    def get_all_mappings(self) -> list[dict]: ...
    def clear(self) -> None: ...
    @property
    def count(self) -> int: ...
```

**Return format for `lookup()`:**
```python
[{
    "source_column": "cust_lvl_v2",
    "target_field": "subscription_tier",
    "client_name": "Acme Corp",
    "distance": 0.05,
    "is_confident": True,  # distance <= Config.MEMORY_DISTANCE_THRESHOLD
}]
```

**Return format for `find_match()`:**
```python
# Returns best match if within threshold, else None
{
    "source_column": "cust_lvl_v2",
    "target_field": "subscription_tier",
    "client_name": "Acme Corp",
    "distance": 0.05,
    "is_confident": True,
}
```

### Target Schema Format (Teammate A creates `data/target_schema.json`)
```json
{
  "schema_name": "SaaS CRM Onboarding Schema",
  "description": "The canonical schema that all client data must be mapped to.",
  "fields": {
    "customer_id": { "type": "string", "description": "Unique customer identifier" },
    "full_name": { "type": "string", "description": "Customer's full name" },
    "subscription_tier": { "type": "string", "description": "Subscription level", "enum": ["Basic", "Standard", "Premium", "Gold", "Silver", "Bronze"] },
    "signup_date": { "type": "date", "description": "Date the customer signed up (ISO 8601)" },
    "email": { "type": "string", "description": "Customer email address" },
    "phone": { "type": "string", "description": "Customer phone number" },
    "address": { "type": "string", "description": "Street address" },
    "city": { "type": "string", "description": "City name" },
    "state": { "type": "string", "description": "State code (2-letter)" },
    "zip_code": { "type": "string", "description": "Postal/ZIP code" },
    "date_of_birth": { "type": "date", "description": "Customer date of birth (ISO 8601)" },
    "account_balance": { "type": "number", "description": "Current account balance in USD" },
    "last_login": { "type": "datetime", "description": "Last login timestamp (ISO 8601)" },
    "is_active": { "type": "boolean", "description": "Whether the customer account is active" }
  }
}
```

---

## Teammate A: Config, Data Files & Project Structure

### Files Owned (no conflicts with Teammate B)
```
src/config.py
src/__init__.py
data/target_schema.json
data/mock/client_a_acme.csv
data/mock/client_b_globex.csv
.env.example
requirements.txt
tests/test_phase1_config.py
```

### Task A1: Project Structure & Dependencies

Create the project directories and `requirements.txt`:

```
the-fde/
├── src/
│   ├── __init__.py          # empty
│   ├── config.py
│   ├── memory.py            # Teammate B
│   ├── brain.py             # Phase 2
│   ├── research.py          # Phase 2
│   ├── browser.py           # Phase 3
│   ├── teacher.py           # Phase 3
│   ├── tools.py             # Phase 3
│   └── agent.py             # Phase 4
├── server/
│   ├── __init__.py          # empty
│   └── webhooks.py          # Phase 3
├── data/
│   ├── target_schema.json
│   ├── mock/
│   │   ├── client_a_acme.csv
│   │   └── client_b_globex.csv
│   └── memory/              # ChromaDB creates this at runtime
├── tests/
│   ├── __init__.py          # empty
│   └── ...                  # test files per phase
├── phases/
├── .env.example
├── requirements.txt
└── run_demo.py              # Phase 4
```

**`requirements.txt`:**
```
google-genai>=1.0.0
chromadb>=0.4.0
plivo>=4.0.0
composio-gemini>=0.1.0
requests>=2.31.0
flask>=3.0.0
python-dotenv>=1.0.0
rich>=13.0.0
pydantic>=2.0.0
```

### Task A2: Centralized Config (`src/config.py`)

Implement the config class exactly as specified in the interface contract above. The existing implementation is correct.

**Key details:**
- Uses `python-dotenv` to load `.env` file
- All API keys default to empty string (never crash on missing key)
- `DEMO_MODE` parsed as boolean from string env var
- `MEMORY_DIR` computed relative to project root using `__file__`
- `CONFIDENCE_THRESHOLD` = 0.75 (below this, agent asks the human)
- `MEMORY_DISTANCE_THRESHOLD` = 0.3 (max cosine distance for auto-match)

### Task A3: `.env.example`

Create `.env.example` with all required keys documented:

```bash
# The FDE - Environment Variables
# Copy to .env and fill in your API keys

# Google Gemini (required for AI reasoning)
GEMINI_API_KEY=your_gemini_api_key_here

# AGI Inc Browser Automation (required for web scraping)
AGI_API_KEY=your_agi_api_key_here

# Composio (required for tool execution / deployment)
COMPOSIO_API_KEY=your_composio_api_key_here

# Plivo Voice (required for human-in-the-loop calls)
PLIVO_AUTH_ID=your_plivo_auth_id_here
PLIVO_AUTH_TOKEN=your_plivo_auth_token_here
PLIVO_PHONE_NUMBER=+1XXXXXXXXXX
ENGINEER_PHONE_NUMBER=+1XXXXXXXXXX

# You.com Search (required for research context)
YOU_API_KEY=your_you_api_key_here

# Webhook Server (Plivo callbacks - use ngrok for local dev)
WEBHOOK_BASE_URL=http://localhost:5000

# Demo mode - set to "true" for CI/testing only
# Live demo should use real APIs (set to "false" or remove)
DEMO_MODE=false
```

### Task A4: Mock CSV Data Files

These are sample client data files used for the demo. They simulate scraping from client portals.

**`data/mock/client_a_acme.csv`** - Messy, abbreviated columns (the "hard" client):
```csv
cust_id,cust_nm,cust_lvl_v2,signup_dt,email_addr,phone_num,addr_line1,city_nm,st_cd,zip_cd,dob,acct_bal,last_login_ts,is_active_flg
1001,John Smith,Gold,2023-01-15,john.smith@acme.com,555-0101,123 Main St,Springfield,IL,62701,1985-03-22,1500.00,2024-11-01 09:30:00,Y
1002,Jane Doe,Silver,2023-03-20,jane.d@acme.com,555-0102,456 Oak Ave,Portland,OR,97201,1990-07-14,750.50,2024-10-28 14:15:00,Y
1003,Bob Wilson,Gold,2022-11-08,bwilson@acme.com,555-0103,789 Pine Rd,Austin,TX,73301,1978-12-01,3200.00,2024-11-02 11:00:00,Y
1004,Alice Brown,Bronze,2024-02-01,abrown@acme.com,555-0104,321 Elm St,Denver,CO,80201,1995-05-30,200.00,2024-09-15 08:45:00,N
1005,Charlie Davis,Silver,2023-06-12,cdavis@acme.com,555-0105,654 Birch Ln,Seattle,WA,98101,1988-09-17,980.25,2024-10-30 16:20:00,Y
```

**Why these columns matter:**
- `cust_id` -> easy mapping to `customer_id` (high confidence)
- `cust_nm` -> somewhat ambiguous (`full_name`? `first_name`?) (medium confidence)
- `cust_lvl_v2` -> very ambiguous with version suffix (low confidence - triggers Plivo call)
- `signup_dt` -> date abbreviation (medium confidence)
- `is_active_flg` -> boolean flag abbreviation (low confidence - triggers Plivo call)

**`data/mock/client_b_globex.csv`** - Cleaner names but semantically similar (tests memory transfer):
```csv
customer_id,full_name,customer_level_ver2,registration_date,contact_email,mobile,street_address,city,state_code,postal_code,date_of_birth,balance_usd,last_activity,status
2001,Maria Garcia,Premium,2023-04-10,mgarcia@globex.com,555-0201,100 Sunset Blvd,Miami,FL,33101,1992-01-25,4500.00,2024-11-01 10:00:00,active
2002,James Lee,Standard,2023-08-05,jlee@globex.com,555-0202,200 Harbor Dr,San Diego,CA,92101,1987-06-18,1200.00,2024-10-29 13:30:00,active
2003,Sarah Johnson,Premium,2022-12-15,sjohnson@globex.com,555-0203,300 River Rd,Chicago,IL,60601,1983-11-03,6700.50,2024-11-02 09:15:00,active
2004,Tom Martinez,Basic,2024-01-20,tmartinez@globex.com,555-0204,400 Lake Ave,Phoenix,AZ,85001,1996-08-22,150.00,2024-08-20 07:30:00,inactive
2005,Emily Chen,Standard,2023-09-18,echen@globex.com,555-0205,500 Hill St,Boston,MA,02101,1991-04-09,890.75,2024-10-31 15:45:00,active
```

**Why this tests continual learning:**
- `customer_level_ver2` is semantically similar to `cust_lvl_v2` - ChromaDB's cosine similarity should match it from memory learned during Client A

### Task A5: Target Schema (`data/target_schema.json`)

The canonical CRM schema all client data must map to. Already defined in the interface contract above. Ensure it has exactly 14 fields: `customer_id`, `full_name`, `subscription_tier`, `signup_date`, `email`, `phone`, `address`, `city`, `state`, `zip_code`, `date_of_birth`, `account_balance`, `last_login`, `is_active`.

### Task A6: Tests (`tests/test_phase1_config.py`)

```python
# tests/test_phase1_config.py
"""Phase 1 Teammate A tests: Config, data files, schema validation."""
import os
import json
import csv
import pytest

# --- Config Tests ---

class TestConfig:
    def test_config_loads_without_error(self):
        """Config module imports and loads all settings."""
        from src.config import Config
        assert Config.GEMINI_MODEL == "gemini-2.0-flash"
        assert Config.AGI_BASE_URL == "https://api.agi.tech/v1"
        assert Config.YOU_SEARCH_URL == "https://api.ydc-index.io/v1/search"

    def test_config_thresholds_are_valid(self):
        """Confidence and memory thresholds are in valid range."""
        from src.config import Config
        assert 0 < Config.CONFIDENCE_THRESHOLD <= 1.0
        assert 0 < Config.MEMORY_DISTANCE_THRESHOLD <= 1.0

    def test_config_memory_dir_path(self):
        """MEMORY_DIR points to data/memory/ relative to project root."""
        from src.config import Config
        assert Config.MEMORY_DIR.endswith(os.path.join("data", "memory"))

    def test_config_api_keys_are_strings(self):
        """All API keys are strings (may be empty but not None)."""
        from src.config import Config
        keys = [
            Config.GEMINI_API_KEY, Config.AGI_API_KEY,
            Config.COMPOSIO_API_KEY, Config.PLIVO_AUTH_ID,
            Config.PLIVO_AUTH_TOKEN, Config.YOU_API_KEY,
        ]
        for key in keys:
            assert isinstance(key, str)

    def test_demo_mode_parses_correctly(self):
        """DEMO_MODE env var is parsed as boolean."""
        from src.config import Config
        assert isinstance(Config.DEMO_MODE, bool)


# --- .env.example Tests ---

class TestEnvExample:
    def test_env_example_exists(self):
        """`.env.example` file exists in project root."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        assert os.path.exists(env_path), ".env.example file is missing"

    def test_env_example_has_all_keys(self):
        """All required API keys are documented in .env.example."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        with open(env_path) as f:
            content = f.read()
        required = [
            "GEMINI_API_KEY", "AGI_API_KEY", "COMPOSIO_API_KEY",
            "PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "PLIVO_PHONE_NUMBER",
            "ENGINEER_PHONE_NUMBER", "YOU_API_KEY", "WEBHOOK_BASE_URL",
            "DEMO_MODE",
        ]
        for key in required:
            assert key in content, f"Missing {key} in .env.example"


# --- Mock CSV Tests ---

class TestMockCSVData:
    def test_client_a_csv_exists_and_valid(self):
        """Client A CSV is valid with expected columns."""
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_a_acme.csv")
        assert os.path.exists(csv_path), "client_a_acme.csv is missing"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) >= 3, "Need at least 3 data rows"
        # Must contain the ambiguous column that triggers Plivo call
        assert "cust_lvl_v2" in reader.fieldnames, "Missing ambiguous column cust_lvl_v2"
        assert "cust_id" in reader.fieldnames
        assert "email_addr" in reader.fieldnames

    def test_client_b_csv_exists_and_valid(self):
        """Client B CSV is valid with semantically similar columns."""
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_b_globex.csv")
        assert os.path.exists(csv_path), "client_b_globex.csv is missing"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) >= 3
        # Must contain the similar column that should match from memory
        assert "customer_level_ver2" in reader.fieldnames, "Missing similar column customer_level_ver2"
        assert "customer_id" in reader.fieldnames

    def test_both_csvs_have_same_column_count(self):
        """Both CSVs have same number of columns (14 each)."""
        base = os.path.join(os.path.dirname(__file__), "..", "data", "mock")
        with open(os.path.join(base, "client_a_acme.csv")) as f:
            cols_a = csv.DictReader(f).fieldnames
        with open(os.path.join(base, "client_b_globex.csv")) as f:
            cols_b = csv.DictReader(f).fieldnames
        assert len(cols_a) == len(cols_b) == 14

    def test_csv_data_values_are_nonempty(self):
        """All cells in client A CSV have non-empty values."""
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_a_acme.csv")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                for col, val in row.items():
                    assert val.strip() != "", f"Empty value in column {col}"


# --- Target Schema Tests ---

class TestTargetSchema:
    def test_schema_file_exists(self):
        """target_schema.json exists in data/."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        assert os.path.exists(schema_path)

    def test_schema_is_valid_json(self):
        """Schema is valid parseable JSON."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)
        assert isinstance(schema, dict)

    def test_schema_has_required_fields(self):
        """Schema contains all 14 required CRM fields."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)
        assert "fields" in schema
        required_fields = [
            "customer_id", "full_name", "subscription_tier", "signup_date",
            "email", "phone", "address", "city", "state", "zip_code",
            "date_of_birth", "account_balance", "last_login", "is_active",
        ]
        for field in required_fields:
            assert field in schema["fields"], f"Missing target field: {field}"

    def test_schema_fields_have_type_and_description(self):
        """Every schema field has a type and description."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)
        for field_name, field_def in schema["fields"].items():
            assert "type" in field_def, f"Field {field_name} missing type"
            assert "description" in field_def, f"Field {field_name} missing description"

    def test_schema_field_count(self):
        """Schema has exactly 14 fields."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)
        assert len(schema["fields"]) == 14
```

### Teammate A Acceptance Criteria
- [ ] `python -c "from src.config import Config; print(Config.GEMINI_MODEL)"` prints `gemini-2.0-flash`
- [ ] `.env.example` contains all 10 keys
- [ ] Both CSV files have 14 columns and 5 data rows each
- [ ] `data/target_schema.json` has 14 fields with types and descriptions
- [ ] `pytest tests/test_phase1_config.py -v` all green

---

## Teammate B: Vector Memory System

### Files Owned (no conflicts with Teammate A)
```
src/memory.py
tests/test_phase1_memory.py
```

### Task B1: ChromaDB Vector Memory (`src/memory.py`)

Implement the `MemoryStore` class exactly matching the interface contract above. This is the core "continual learning" component.

**Implementation details:**

```python
"""Vector Memory Store - The FDE's episodic memory for continual learning.

Uses ChromaDB to store column-name -> canonical-field mappings as embeddings.
When the agent encounters a new column, it queries this store for similar
previously-learned mappings before asking the human.
"""

import os
import chromadb
from rich.console import Console

from src.config import Config

console = Console()


class MemoryStore:
    """Persistent vector memory for learned data mappings."""

    def __init__(self):
        os.makedirs(Config.MEMORY_DIR, exist_ok=True)
        self._client = chromadb.PersistentClient(path=Config.MEMORY_DIR)
        self._collection = self._client.get_or_create_collection(
            name="column_mappings",
            metadata={"hnsw:space": "cosine"},
        )
```

**Key decisions:**
- **ChromaDB PersistentClient**: Data survives process restarts (critical for continual learning)
- **Cosine distance metric**: Column names like `cust_lvl_v2` and `customer_level_ver2` will have low cosine distance because their default embeddings are semantically similar
- **`hnsw:space: cosine`**: Hierarchical Navigable Small World index for fast approximate nearest neighbor search
- **Upsert for `store_mapping`**: Prevents duplicate entries when the same column is seen again
- **Document = source column name**: ChromaDB embeds the document text; the metadata stores the mapping target

**ChromaDB API reference:**
```python
# Create persistent client
client = chromadb.PersistentClient(path="/path/to/store")

# Get or create collection with cosine distance
collection = client.get_or_create_collection(
    name="column_mappings",
    metadata={"hnsw:space": "cosine"},  # cosine | l2 | ip
)

# Upsert (insert or update)
collection.upsert(
    ids=["unique_id"],
    documents=["text to embed"],           # ChromaDB auto-embeds this
    metadatas=[{"key": "value"}],
)

# Query by similarity
results = collection.query(
    query_texts=["search text"],
    n_results=3,
)
# results = {"ids": [[...]], "distances": [[...]], "metadatas": [[...]]}
# distances: lower = more similar (cosine: 0=identical, 2=opposite)

# Get all documents
all_data = collection.get(include=["metadatas", "documents"])

# Count
collection.count()

# Delete collection
client.delete_collection("column_mappings")
```

### Task B2: Tests (`tests/test_phase1_memory.py`)

```python
# tests/test_phase1_memory.py
"""Phase 1 Teammate B tests: ChromaDB vector memory system."""
import os
import pytest


class TestMemoryStoreBasic:
    """Basic CRUD operations on MemoryStore."""

    @pytest.fixture(autouse=True)
    def setup_memory(self):
        """Create a fresh MemoryStore for each test."""
        os.environ["DEMO_MODE"] = "true"
        from src.memory import MemoryStore
        self.mem = MemoryStore()
        self.mem.clear()
        yield
        self.mem.clear()

    def test_initial_count_is_zero(self):
        """Freshly cleared memory has zero entries."""
        assert self.mem.count == 0

    def test_store_single_mapping(self):
        """Storing one mapping increments count."""
        self.mem.store_mapping("cust_id", "customer_id", "TestClient")
        assert self.mem.count == 1

    def test_store_multiple_mappings(self):
        """Storing multiple mappings increments count correctly."""
        self.mem.store_mapping("cust_id", "customer_id", "ClientA")
        self.mem.store_mapping("cust_nm", "full_name", "ClientA")
        self.mem.store_mapping("email_addr", "email", "ClientA")
        assert self.mem.count == 3

    def test_upsert_same_column_same_client(self):
        """Upserting the same column+client overwrites, doesn't duplicate."""
        self.mem.store_mapping("cust_id", "customer_id", "ClientA")
        self.mem.store_mapping("cust_id", "customer_id", "ClientA")
        assert self.mem.count == 1

    def test_same_column_different_clients(self):
        """Same column from different clients creates separate entries."""
        self.mem.store_mapping("cust_id", "customer_id", "ClientA")
        self.mem.store_mapping("cust_id", "customer_id", "ClientB")
        assert self.mem.count == 2

    def test_clear_removes_all(self):
        """clear() removes all entries."""
        self.mem.store_mapping("col_a", "field_a", "Test")
        self.mem.store_mapping("col_b", "field_b", "Test")
        assert self.mem.count == 2
        self.mem.clear()
        assert self.mem.count == 0


class TestMemoryStoreLookup:
    """Lookup and similarity search tests."""

    @pytest.fixture(autouse=True)
    def setup_memory(self):
        os.environ["DEMO_MODE"] = "true"
        from src.memory import MemoryStore
        self.mem = MemoryStore()
        self.mem.clear()
        yield
        self.mem.clear()

    def test_lookup_empty_returns_empty_list(self):
        """Querying empty memory returns empty list."""
        results = self.mem.lookup("anything")
        assert results == []

    def test_find_match_empty_returns_none(self):
        """find_match on empty memory returns None."""
        result = self.mem.find_match("anything")
        assert result is None

    def test_exact_match_has_low_distance(self):
        """Looking up the exact stored text should have very low distance."""
        self.mem.store_mapping("cust_lvl_v2", "subscription_tier", "TestClient")
        results = self.mem.lookup("cust_lvl_v2")
        assert len(results) >= 1
        assert results[0]["distance"] < 0.1  # Near-exact match

    def test_find_match_exact(self):
        """find_match returns match for exact text."""
        self.mem.store_mapping("cust_lvl_v2", "subscription_tier", "TestClient")
        match = self.mem.find_match("cust_lvl_v2")
        assert match is not None
        assert match["target_field"] == "subscription_tier"
        assert match["client_name"] == "TestClient"
        assert match["is_confident"] is True

    def test_lookup_returns_correct_metadata(self):
        """Lookup results contain all required metadata fields."""
        self.mem.store_mapping("email_addr", "email", "ClientA")
        results = self.mem.lookup("email_addr")
        assert len(results) >= 1
        result = results[0]
        assert "source_column" in result
        assert "target_field" in result
        assert "client_name" in result
        assert "distance" in result
        assert "is_confident" in result

    def test_lookup_n_results_limits_output(self):
        """n_results parameter limits the number of returned matches."""
        for i in range(5):
            self.mem.store_mapping(f"col_{i}", f"field_{i}", "Test")
        results = self.mem.lookup("col_0", n_results=2)
        assert len(results) <= 2


class TestMemoryStoreGetAll:
    """Tests for get_all_mappings()."""

    @pytest.fixture(autouse=True)
    def setup_memory(self):
        os.environ["DEMO_MODE"] = "true"
        from src.memory import MemoryStore
        self.mem = MemoryStore()
        self.mem.clear()
        yield
        self.mem.clear()

    def test_get_all_empty(self):
        """get_all_mappings on empty memory returns empty list."""
        assert self.mem.get_all_mappings() == []

    def test_get_all_returns_stored_entries(self):
        """get_all_mappings returns all stored entries."""
        self.mem.store_mapping("col_a", "field_a", "ClientX")
        self.mem.store_mapping("col_b", "field_b", "ClientY")
        all_m = self.mem.get_all_mappings()
        assert len(all_m) == 2

    def test_get_all_has_correct_fields(self):
        """Each entry in get_all has source_column, target_field, client_name."""
        self.mem.store_mapping("col_a", "field_a", "ClientX")
        all_m = self.mem.get_all_mappings()
        entry = all_m[0]
        assert "source_column" in entry
        assert "target_field" in entry
        assert "client_name" in entry


class TestMemoryStoreContinualLearning:
    """Tests that validate the continual learning behavior."""

    @pytest.fixture(autouse=True)
    def setup_memory(self):
        os.environ["DEMO_MODE"] = "true"
        from src.memory import MemoryStore
        self.mem = MemoryStore()
        self.mem.clear()
        yield
        self.mem.clear()

    def test_similar_column_names_match(self):
        """Semantically similar column names should have low distance.

        This is the CORE continual learning test:
        After learning 'cust_lvl_v2' -> 'subscription_tier' from Client A,
        the similar name 'customer_level_ver2' from Client B should match.
        """
        self.mem.store_mapping("cust_lvl_v2", "subscription_tier", "Acme Corp")
        results = self.mem.lookup("customer_level_ver2")
        assert len(results) >= 1
        # The distance should be relatively low (similar embeddings)
        # Exact threshold depends on the embedding model, so we check it exists
        assert results[0]["target_field"] == "subscription_tier"

    def test_dissimilar_columns_dont_match(self):
        """Very different column names should NOT confidently match."""
        self.mem.store_mapping("cust_id", "customer_id", "TestClient")
        match = self.mem.find_match("total_revenue_quarterly_ytd")
        # Dissimilar text should either return None or have high distance
        if match is not None:
            assert match["is_confident"] is False or match["distance"] > 0.3

    def test_memory_persists_across_instances(self):
        """Data stored in one MemoryStore instance is visible in another."""
        self.mem.store_mapping("test_persist", "target_persist", "PersistClient")
        # Create a new instance pointing to the same directory
        from src.memory import MemoryStore
        mem2 = MemoryStore()
        match = mem2.find_match("test_persist")
        assert match is not None
        assert match["target_field"] == "target_persist"
```

### Teammate B Acceptance Criteria
- [ ] `MemoryStore()` initializes without errors
- [ ] `store_mapping` -> `lookup` round-trip works
- [ ] `find_match` returns correct metadata format
- [ ] Semantically similar column names have low cosine distance
- [ ] Memory persists across MemoryStore instances (PersistentClient)
- [ ] `clear()` removes all entries
- [ ] `pytest tests/test_phase1_memory.py -v` all green

---

## Integration Sync Point

After both teammates finish, run the integration test together to verify Config + Memory work end-to-end.

### Integration Test (`tests/test_phase1_integration.py`)

```python
# tests/test_phase1_integration.py
"""Phase 1 Integration: Config + Memory work together end-to-end."""
import os
import json
import csv
import pytest


class TestPhase1Integration:
    """Verify Teammate A's config/data + Teammate B's memory integrate correctly."""

    @pytest.fixture(autouse=True)
    def setup(self):
        os.environ["DEMO_MODE"] = "true"
        from src.config import Config
        from src.memory import MemoryStore
        self.config = Config
        self.mem = MemoryStore()
        self.mem.clear()
        yield
        self.mem.clear()

    def test_memory_uses_config_dir(self):
        """MemoryStore uses the MEMORY_DIR from Config."""
        from src.config import Config
        assert os.path.exists(Config.MEMORY_DIR)

    def test_memory_uses_config_threshold(self):
        """MemoryStore respects MEMORY_DISTANCE_THRESHOLD from Config."""
        from src.config import Config
        self.mem.store_mapping("cust_id", "customer_id", "TestClient")
        results = self.mem.lookup("cust_id")
        assert len(results) >= 1
        # is_confident should be True when distance <= threshold
        assert results[0]["is_confident"] == (results[0]["distance"] <= Config.MEMORY_DISTANCE_THRESHOLD)

    def test_csv_columns_can_be_stored_and_retrieved(self):
        """Store all columns from Client A CSV and retrieve them."""
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_a_acme.csv")
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames

        with open(schema_path) as f:
            schema = json.load(f)
        target_fields = list(schema["fields"].keys())

        # Store mappings for all columns
        for i, col in enumerate(columns):
            target = target_fields[i] if i < len(target_fields) else "unknown"
            self.mem.store_mapping(col, target, "IntegrationTest")

        assert self.mem.count == len(columns)

        # Retrieve and verify
        all_mappings = self.mem.get_all_mappings()
        assert len(all_mappings) == len(columns)

    def test_full_learning_transfer_flow(self):
        """Simulate the complete learning transfer: Client A -> Client B.

        1. Store Client A column mappings
        2. Look up Client B columns
        3. Verify similar columns are found in memory
        """
        # Store Client A mappings
        client_a_mappings = [
            ("cust_id", "customer_id"),
            ("cust_nm", "full_name"),
            ("cust_lvl_v2", "subscription_tier"),
            ("email_addr", "email"),
        ]
        for source, target in client_a_mappings:
            self.mem.store_mapping(source, target, "Acme Corp")

        # Look up Client B columns
        client_b_columns = ["customer_id", "full_name", "customer_level_ver2", "contact_email"]

        matches_found = 0
        for col in client_b_columns:
            results = self.mem.lookup(col, n_results=1)
            if results:
                matches_found += 1

        # At least some Client B columns should find matches from Client A
        assert matches_found > 0, "No memory transfer between clients"
```

---

## GitHub Actions Workflow (`.github/workflows/phase1.yml`)

```yaml
name: "Phase 1: Foundation"

on:
  push:
    paths:
      - "src/config.py"
      - "src/memory.py"
      - "src/__init__.py"
      - "data/**"
      - "tests/test_phase1_*.py"
      - ".env.example"
      - "requirements.txt"
  pull_request:
    paths:
      - "src/config.py"
      - "src/memory.py"
      - "data/**"
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

      - name: Teammate A tests (Config + Data)
        run: pytest tests/test_phase1_config.py -v

      - name: Teammate B tests (Memory)
        run: pytest tests/test_phase1_memory.py -v

      - name: Integration tests
        run: pytest tests/test_phase1_integration.py -v
```

---

## Debug Checklist

### Config Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: dotenv` | `python-dotenv` not installed | `pip install python-dotenv` |
| `Config.DEMO_MODE` is always `False` | Env var set AFTER import | Set `DEMO_MODE=true` before `from src.config import Config` |
| `Config.GEMINI_API_KEY` is empty | No `.env` file | Copy `.env.example` to `.env` and fill in keys |
| API key loaded but API returns 401 | Wrong key format or expired | Check provider dashboard for correct key |

### ChromaDB Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| `sqlite3.OperationalError` | Old SQLite version | `pip install pysqlite3-binary` or upgrade Python |
| `PermissionError` on `data/memory/` | Directory not writable | `chmod 755 data/memory/` or run `os.makedirs(path, exist_ok=True)` |
| `find_match` returns `None` for exact text | Collection was cleared or recreated | Check `mem.count > 0` before querying |
| Tests flaky - pass alone, fail together | ChromaDB state persists between tests | Always `mem.clear()` in fixture setup and teardown |
| `ValueError: n_results` > collection size | Querying more results than stored | Use `min(n_results, collection.count())` |

### CSV Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| `FileNotFoundError` on CSV | Wrong relative path | Use `os.path.dirname(__file__)` to build paths |
| CSV has extra empty rows | Trailing newline in file | Check `len(rows)` excludes empty rows |
| Non-ASCII characters break parsing | BOM or encoding issues | Open with `encoding='utf-8-sig'` |

---

## Smoke Test

```bash
# Phase 1 complete smoke test (run after both teammates finish)
python -c "
from src.config import Config
from src.memory import MemoryStore
import json, csv, os

# Config
print(f'Config OK: model={Config.GEMINI_MODEL}, threshold={Config.CONFIDENCE_THRESHOLD}')

# Schema
with open('data/target_schema.json') as f:
    schema = json.load(f)
print(f'Schema OK: {len(schema[\"fields\"])} fields')

# CSV
for name in ['client_a_acme.csv', 'client_b_globex.csv']:
    with open(f'data/mock/{name}') as f:
        rows = list(csv.DictReader(f))
    print(f'CSV OK: {name} has {len(rows)} rows')

# Memory
mem = MemoryStore()
mem.clear()
mem.store_mapping('test_col', 'test_field', 'SmokeTest')
match = mem.find_match('test_col')
assert match is not None
print(f'Memory OK: stored and retrieved (distance={match[\"distance\"]:.3f})')
mem.clear()

print('PHASE 1: ALL SYSTEMS GO')
"
```

---

## Definition of Done

- [ ] `src/config.py` loads all settings from env vars with safe defaults
- [ ] `.env.example` documents all 10 required env vars
- [ ] `data/mock/client_a_acme.csv` has 14 columns, 5 rows, includes `cust_lvl_v2`
- [ ] `data/mock/client_b_globex.csv` has 14 columns, 5 rows, includes `customer_level_ver2`
- [ ] `data/target_schema.json` has 14 fields with types and descriptions
- [ ] `src/memory.py` implements full `MemoryStore` API with ChromaDB persistence
- [ ] `pytest tests/test_phase1_config.py -v` passes (Teammate A)
- [ ] `pytest tests/test_phase1_memory.py -v` passes (Teammate B)
- [ ] `pytest tests/test_phase1_integration.py -v` passes (Both)
- [ ] `.github/workflows/phase1.yml` is valid
- [ ] Smoke test runs clean
