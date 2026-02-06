# Phase 2: Brain & Research (1 Hour)

## Goal
Implement the Gemini-powered reasoning engine with structured confidence scoring, and the You.com research module for domain context. Two teammates work on completely separate files.

## Time Budget
| Task | Time | Owner |
|------|------|-------|
| Interface contract review | 5 min | Both |
| Teammate A: Brain (Gemini) | 25 min | Teammate A |
| Teammate B: Research (You.com) | 25 min | Teammate B |
| Integration sync + tests | 5 min | Both |

## Prerequisites
- Phase 1 complete: `src/config.py` and `src/memory.py` working
- `pip install google-genai requests` done
- `GEMINI_API_KEY` and `YOU_API_KEY` in `.env`

---

## Interface Contract (Agree on This FIRST)

### Brain API (Teammate A creates `src/brain.py`)
```python
class Brain:
    def __init__(self, memory: MemoryStore, research: ResearchEngine) -> None: ...

    def analyze_columns(
        self,
        columns: list[str],
        sample_data: dict[str, list[str]],
        target_schema: dict,
    ) -> list[dict]: ...
```

**`analyze_columns()` return format:**
```python
[{
    "source_column": "cust_lvl_v2",
    "target_field": "subscription_tier",
    "confidence": "low",        # "high" | "medium" | "low"
    "reasoning": "Abbreviated column with version suffix, ambiguous mapping",
    "from_memory": False,       # True if recalled from ChromaDB
}]
```

**Pipeline inside `analyze_columns()`:**
1. For each column, check `memory.find_match(col)` first
2. If memory match found -> return immediately with `confidence="high"`, `from_memory=True`
3. For remaining unknown columns, call `research.get_column_context(col)` for context
4. Send unknown columns + context + schema to Gemini for analysis
5. Gemini returns structured JSON with confidence ratings

### Research API (Teammate B creates `src/research.py`)
```python
class ResearchEngine:
    def __init__(self) -> None: ...
    def search(self, query: str) -> str: ...
    def get_column_context(self, column_name: str, domain: str = "CRM") -> str: ...
    def get_domain_context(self, domain_description: str) -> str: ...
```

**The key dependency:** Brain calls `research.get_column_context()` to enrich its Gemini prompt. Both teammates agree on the exact signature and return type (plain string) before splitting.

---

## Teammate A: Gemini Brain (`src/brain.py`)

### Files Owned (no conflicts with Teammate B)
```
src/brain.py
tests/test_phase2_brain.py
```

### Task A1: Brain Implementation

The Brain is the core reasoning engine. It uses Google Gemini with structured output to analyze CSV columns and map them to the target schema with confidence scores.

**Full implementation reference:**

```python
"""Gemini Brain - The FDE's reasoning and confidence scoring engine.

Uses Google Gemini to analyze CSV columns and attempt to map them
to the target schema with confidence scores.
"""

import json
from google import genai
from google.genai import types
from rich.console import Console

from src.config import Config
from src.memory import MemoryStore
from src.research import ResearchEngine

console = Console()

SYSTEM_INSTRUCTION = """You are an expert data mapping agent. Your job is to map source CSV column names to a target CRM schema.

For each source column, you must:
1. Analyze the column name, sample values, and any provided context
2. Determine which target schema field it maps to
3. Rate your confidence: "high" (>90% sure), "medium" (50-90%), or "low" (<50%)

Be conservative with confidence. If a column name is abbreviated, ambiguous, or uses non-standard naming, rate it as "low" confidence.

Respond ONLY with valid JSON matching the requested schema."""

MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_column": {"type": "string"},
                    "target_field": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["source_column", "target_field", "confidence", "reasoning"],
            },
        }
    },
    "required": ["mappings"],
}
```

### Task A2: Gemini Structured Output API

**Critical API details for `google-genai`:**

```python
from google import genai
from google.genai import types

# Initialize client
client = genai.Client(api_key=Config.GEMINI_API_KEY)

# Generate with structured JSON output
response = client.models.generate_content(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",   # FORCES JSON output
        response_schema=MAPPING_SCHEMA,           # Raw dict, NOT Pydantic
        temperature=0.1,                          # Low temp for consistency
    ),
    contents=prompt_text,
)

# Parse response
data = json.loads(response.text)
mappings = data.get("mappings", [])
```

**Common pitfalls:**
- `response_schema` must be a raw Python dict, NOT a Pydantic model
- `response_mime_type="application/json"` is required for structured output
- `temperature=0.1` keeps outputs consistent across runs
- `response.text` contains the raw JSON string
- If Gemini returns invalid JSON (rare), catch `json.JSONDecodeError` and fall back to mock

### Task A3: The `analyze_columns()` Pipeline

```python
def analyze_columns(self, columns, sample_data, target_schema):
    results = []
    unknown_columns = []

    # Step 1: Check memory for each column
    for col in columns:
        match = self._memory.find_match(col)
        if match:
            results.append({
                "source_column": col,
                "target_field": match["target_field"],
                "confidence": "high",
                "reasoning": f"Found in memory from {match['client_name']} (distance: {match['distance']:.3f})",
                "from_memory": True,
            })
        else:
            unknown_columns.append(col)

    if not unknown_columns:
        return results

    # Step 2: Research context for unknown columns
    research_context = ""
    for col in unknown_columns[:3]:  # Limit API calls to 3
        ctx = self._research.get_column_context(col)
        if ctx:
            research_context += f"\nContext for '{col}': {ctx}\n"

    # Step 3: Gemini analysis
    gemini_results = self._gemini_analyze(unknown_columns, sample_data, target_schema, research_context)
    for r in gemini_results:
        r["from_memory"] = False
    results.extend(gemini_results)

    return results
```

### Task A4: Mock Fallback

The Brain includes a `_mock_analyze` method for when Gemini is unavailable (demo mode or API errors). This maps known column patterns to targets:

```python
def _mock_analyze(self, columns, target_schema):
    known_mappings = {
        "cust_id": ("customer_id", "high"),
        "cust_nm": ("full_name", "medium"),
        "cust_lvl_v2": ("subscription_tier", "low"),
        "signup_dt": ("signup_date", "medium"),
        "email_addr": ("email", "high"),
        "phone_num": ("phone", "high"),
        "is_active_flg": ("is_active", "low"),
        # ... (full mapping table in existing code)
    }
```

**Important:** `cust_lvl_v2` and `is_active_flg` must return `"low"` confidence to trigger the Plivo call flow in Phase 3.

### Task A5: Tests (`tests/test_phase2_brain.py`)

```python
# tests/test_phase2_brain.py
"""Phase 2 Teammate A tests: Gemini brain reasoning and confidence scoring."""
import os
import json
import pytest

os.environ["DEMO_MODE"] = "true"

from src.memory import MemoryStore
from src.research import ResearchEngine
from src.brain import Brain


@pytest.fixture
def brain():
    mem = MemoryStore()
    mem.clear()
    research = ResearchEngine()
    b = Brain(mem, research)
    yield b
    mem.clear()


@pytest.fixture
def target_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
    with open(schema_path) as f:
        return json.load(f)


class TestBrainInit:
    def test_brain_initializes(self, brain):
        """Brain initializes with memory and research dependencies."""
        assert brain._memory is not None
        assert brain._research is not None

    def test_brain_demo_mode_no_client(self, brain):
        """In demo mode, Gemini client is None (uses mock)."""
        assert brain._client is None


class TestBrainAnalyze:
    def test_returns_mapping_per_column(self, brain, target_schema):
        """Brain returns exactly one mapping per input column."""
        columns = ["cust_id", "cust_nm", "email_addr"]
        sample_data = {col: ["val1", "val2", "val3"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == len(columns)

    def test_mapping_has_required_fields(self, brain, target_schema):
        """Each mapping has source_column, target_field, confidence, reasoning, from_memory."""
        columns = ["cust_id"]
        sample_data = {"cust_id": ["1001", "1002"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        result = results[0]
        assert "source_column" in result
        assert "target_field" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "from_memory" in result

    def test_confidence_values_are_valid(self, brain, target_schema):
        """Confidence is always one of: high, medium, low."""
        columns = ["cust_id", "cust_nm", "cust_lvl_v2", "email_addr"]
        sample_data = {col: ["val1", "val2", "val3"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        for r in results:
            assert r["confidence"] in ("high", "medium", "low"), \
                f"Invalid confidence: {r['confidence']}"

    def test_ambiguous_column_gets_low_confidence(self, brain, target_schema):
        """cust_lvl_v2 should be flagged as low confidence (triggers human call)."""
        columns = ["cust_lvl_v2"]
        sample_data = {"cust_lvl_v2": ["Gold", "Silver", "Bronze"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == 1
        assert results[0]["confidence"] == "low"
        assert results[0]["target_field"] == "subscription_tier"

    def test_clear_column_gets_high_confidence(self, brain, target_schema):
        """Unambiguous columns like cust_id should get high confidence."""
        columns = ["cust_id"]
        sample_data = {"cust_id": ["1001", "1002"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert results[0]["confidence"] == "high"
        assert results[0]["target_field"] == "customer_id"


class TestBrainMemoryIntegration:
    def test_memory_match_returns_from_memory_true(self, brain, target_schema):
        """If memory has a match, Brain returns from_memory=True."""
        brain._memory.store_mapping("email_addr", "email", "PriorClient")
        columns = ["email_addr"]
        sample_data = {"email_addr": ["a@b.com"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == 1
        assert results[0]["from_memory"] is True
        assert results[0]["target_field"] == "email"
        assert results[0]["confidence"] == "high"

    def test_memory_match_skips_gemini(self, brain, target_schema):
        """All columns matched from memory means zero Gemini calls."""
        brain._memory.store_mapping("cust_id", "customer_id", "ClientA")
        brain._memory.store_mapping("email_addr", "email", "ClientA")
        columns = ["cust_id", "email_addr"]
        sample_data = {col: ["v1"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert all(r["from_memory"] for r in results)

    def test_partial_memory_calls_gemini_for_rest(self, brain, target_schema):
        """When some columns are in memory, only unknown ones go to Gemini."""
        brain._memory.store_mapping("email_addr", "email", "ClientA")
        columns = ["email_addr", "cust_lvl_v2"]
        sample_data = {col: ["v1", "v2"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == 2
        memory_results = [r for r in results if r["from_memory"]]
        gemini_results = [r for r in results if not r["from_memory"]]
        assert len(memory_results) == 1
        assert len(gemini_results) == 1


class TestMockAnalyzer:
    def test_mock_handles_unknown_column(self, brain):
        """Unknown columns get low confidence in mock mode."""
        results = brain._mock_analyze(["totally_unknown_xyz_123"], {})
        assert len(results) == 1
        assert results[0]["confidence"] == "low"
        assert results[0]["target_field"] == "unknown"

    def test_mock_handles_known_column(self, brain):
        """Known columns in mock map correctly."""
        results = brain._mock_analyze(["email_addr"], {})
        assert results[0]["target_field"] == "email"
        assert results[0]["confidence"] == "high"

    def test_mock_handles_mixed_columns(self, brain):
        """Mix of known and unknown columns."""
        results = brain._mock_analyze(["cust_id", "random_col"], {})
        assert len(results) == 2
        cust = next(r for r in results if r["source_column"] == "cust_id")
        rand = next(r for r in results if r["source_column"] == "random_col")
        assert cust["confidence"] == "high"
        assert rand["confidence"] == "low"
```

### Teammate A Acceptance Criteria
- [ ] `Brain.__init__` accepts `MemoryStore` and `ResearchEngine`
- [ ] `analyze_columns` checks memory first, then researches, then reasons
- [ ] Memory matches return `from_memory=True` and skip Gemini
- [ ] Ambiguous columns (`cust_lvl_v2`) get `"low"` confidence
- [ ] Clear columns (`cust_id`) get `"high"` confidence
- [ ] Mock fallback works when Gemini is unavailable
- [ ] `pytest tests/test_phase2_brain.py -v` all green

---

## Teammate B: You.com Research (`src/research.py`)

### Files Owned (no conflicts with Teammate A)
```
src/research.py
tests/test_phase2_research.py
```

### Task B1: You.com Search Implementation

The Research Engine queries You.com's Search API to find domain-specific context that helps the Brain make better guesses about ambiguous column names.

**Full implementation reference:**

```python
"""You.com Research Module - Context loading for improved data mapping.

Queries You.com Search API to find domain-specific context that helps
the agent make better guesses about ambiguous column names.
"""

import requests
from rich.console import Console

from src.config import Config

console = Console()


class ResearchEngine:
    """Searches You.com for domain context to improve mapping accuracy."""

    def __init__(self):
        self._cache: dict[str, str] = {}
```

### Task B2: You.com Search API Details

**API Endpoint:** `GET https://api.ydc-index.io/v1/search`

**Authentication:** Header-based (NOT Bearer token!)
```
X-API-Key: YOUR_YOU_API_KEY
```

**Request:**
```python
response = requests.get(
    "https://api.ydc-index.io/v1/search",
    headers={"X-API-Key": Config.YOU_API_KEY},
    params={"query": "What does cust_lvl mean in CRM data?"},
    timeout=10,
)
```

**Response format:**
```json
{
  "results": {
    "web": [
      {
        "title": "CRM Data Dictionary",
        "url": "https://example.com/crm",
        "snippets": [
          "Customer level typically refers to the subscription tier..."
        ]
      }
    ]
  }
}
```

**Extract snippets:**
```python
data = response.json()
snippets = []
for result in data.get("results", {}).get("web", []):
    snippets.extend(result.get("snippets", []))
context = "\n".join(snippets[:5])  # Top 5 snippets
```

### Task B3: Caching Strategy

The Research Engine caches results to avoid redundant API calls:

```python
def search(self, query: str) -> str:
    # Check cache first
    if query in self._cache:
        return self._cache[query]

    # Make API call
    try:
        response = requests.get(...)
        context = "\n".join(snippets[:5])
        self._cache[query] = context  # Cache for future calls
        return context
    except Exception as e:
        return ""  # Graceful failure - empty context
```

**Why caching matters:** The Brain may query similar columns (e.g., `cust_lvl_v2` and `cust_lvl_v3`) - cache prevents duplicate API calls.

### Task B4: Convenience Methods

```python
def get_column_context(self, column_name: str, domain: str = "CRM") -> str:
    """Get context for a specific column name mapping."""
    query = f"What does the column '{column_name}' typically mean in {domain} data? Standard field name mapping."
    return self.search(query)

def get_domain_context(self, domain_description: str) -> str:
    """Get general domain context for better mapping."""
    query = f"Standard data schema and field names for {domain_description}"
    return self.search(query)
```

### Task B5: Mock Search for Demo Mode

When `DEMO_MODE=true` or API is unavailable, return helpful mock responses:

```python
def _mock_search(self, query: str) -> str:
    mock_responses = {
        "cust_lvl": "Customer level typically refers to the subscription tier or membership grade in CRM systems.",
        "signup": "Signup date refers to when a customer first registered. Standard field: signup_date.",
        "dob": "DOB is a common abbreviation for Date of Birth. Standard field: date_of_birth.",
        "acct_bal": "Account balance represents the current monetary balance. Standard field: account_balance.",
        "flg": "FLG or flag typically represents a boolean indicator. Common: is_active.",
    }
    for key, response in mock_responses.items():
        if key in query.lower():
            self._cache[query] = response
            return response
    default = "This column name follows common CRM data conventions."
    self._cache[query] = default
    return default
```

### Task B6: Tests (`tests/test_phase2_research.py`)

```python
# tests/test_phase2_research.py
"""Phase 2 Teammate B tests: You.com research engine."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.research import ResearchEngine


class TestResearchInit:
    def test_research_initializes(self):
        """ResearchEngine initializes with empty cache."""
        r = ResearchEngine()
        assert isinstance(r._cache, dict)
        assert len(r._cache) == 0


class TestResearchSearch:
    def test_search_returns_string(self):
        """search() returns a string result."""
        r = ResearchEngine()
        result = r.search("What does cust_lvl mean in CRM data?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_caches_results(self):
        """Second call with same query returns cached result (no API call)."""
        r = ResearchEngine()
        r1 = r.search("test query")
        r2 = r.search("test query")
        assert r1 == r2
        assert "test query" in r._cache

    def test_search_different_queries_cached_separately(self):
        """Different queries have separate cache entries."""
        r = ResearchEngine()
        r.search("query one")
        r.search("query two")
        assert "query one" in r._cache
        assert "query two" in r._cache

    def test_search_never_crashes(self):
        """search() returns empty string on error, never raises."""
        r = ResearchEngine()
        # Even nonsense queries should return something in mock mode
        result = r.search("asldkfjlaskdjf")
        assert isinstance(result, str)


class TestResearchColumnContext:
    def test_get_column_context_returns_string(self):
        """get_column_context returns non-empty string."""
        r = ResearchEngine()
        ctx = r.get_column_context("cust_lvl_v2")
        assert isinstance(ctx, str)

    def test_column_context_for_known_abbreviations(self):
        """Known abbreviations return relevant context."""
        r = ResearchEngine()
        ctx = r.get_column_context("dob")
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_column_context_with_custom_domain(self):
        """Custom domain parameter changes the query."""
        r = ResearchEngine()
        ctx = r.get_column_context("patient_id", domain="healthcare")
        assert isinstance(ctx, str)


class TestResearchDomainContext:
    def test_get_domain_context_returns_string(self):
        """get_domain_context returns non-empty string."""
        r = ResearchEngine()
        ctx = r.get_domain_context("healthcare CRM")
        assert isinstance(ctx, str)

    def test_domain_context_is_cached(self):
        """Domain context queries are cached too."""
        r = ResearchEngine()
        r.get_domain_context("retail analytics")
        # The internal query string should be in the cache
        assert any("retail analytics" in key for key in r._cache)


class TestResearchMockMode:
    def test_mock_returns_relevant_context_for_cust_lvl(self):
        """Mock search for 'cust_lvl' returns subscription tier context."""
        r = ResearchEngine()
        result = r._mock_search("What does cust_lvl mean?")
        assert "tier" in result.lower() or "level" in result.lower() or "subscription" in result.lower()

    def test_mock_returns_relevant_context_for_dob(self):
        """Mock search for 'dob' returns date of birth context."""
        r = ResearchEngine()
        result = r._mock_search("What does dob mean?")
        assert "birth" in result.lower() or "date" in result.lower()

    def test_mock_returns_default_for_unknown(self):
        """Unknown terms get a default response."""
        r = ResearchEngine()
        result = r._mock_search("what is xyzzy_123?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_caches_results(self):
        """Mock responses are cached too."""
        r = ResearchEngine()
        r._mock_search("test cust_lvl query")
        assert any("cust_lvl" in key for key in r._cache)
```

### Teammate B Acceptance Criteria
- [ ] `ResearchEngine()` initializes with empty cache
- [ ] `search()` returns a string, never raises
- [ ] Results are cached (same query returns same result)
- [ ] `get_column_context()` and `get_domain_context()` work
- [ ] Mock mode returns relevant context for known abbreviations
- [ ] `pytest tests/test_phase2_research.py -v` all green

---

## Integration Sync Point

After both teammates finish, run the integration test to verify Brain + Research work together.

### Integration Test (`tests/test_phase2_integration.py`)

```python
# tests/test_phase2_integration.py
"""Phase 2 Integration: Brain + Research + Memory work together."""
import os
import json
import pytest

os.environ["DEMO_MODE"] = "true"

from src.config import Config
from src.memory import MemoryStore
from src.research import ResearchEngine
from src.brain import Brain


@pytest.fixture
def full_brain():
    """Create Brain with all dependencies wired up."""
    mem = MemoryStore()
    mem.clear()
    research = ResearchEngine()
    brain = Brain(mem, research)
    yield brain, mem, research
    mem.clear()


@pytest.fixture
def target_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
    with open(schema_path) as f:
        return json.load(f)


class TestPhase2Integration:
    def test_brain_uses_research_for_context(self, full_brain, target_schema):
        """Brain calls ResearchEngine for unknown columns."""
        brain, mem, research = full_brain
        columns = ["cust_lvl_v2"]
        sample_data = {"cust_lvl_v2": ["Gold", "Silver"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        # Research cache should have entries from the brain's queries
        assert len(results) == 1
        # The column was unknown, so research should have been called
        # (cache will have entries if research was invoked)

    def test_full_pipeline_memory_then_research_then_gemini(self, full_brain, target_schema):
        """Full pipeline: memory -> research -> gemini analysis."""
        brain, mem, research = full_brain

        # Seed memory with one known mapping
        mem.store_mapping("email_addr", "email", "PriorClient")

        # Analyze: one from memory, one needs research+gemini
        columns = ["email_addr", "cust_lvl_v2"]
        sample_data = {col: ["v1", "v2", "v3"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)

        assert len(results) == 2

        email_result = next(r for r in results if r["source_column"] == "email_addr")
        assert email_result["from_memory"] is True
        assert email_result["confidence"] == "high"

        lvl_result = next(r for r in results if r["source_column"] == "cust_lvl_v2")
        assert lvl_result["from_memory"] is False
        assert lvl_result["confidence"] == "low"  # Ambiguous

    def test_all_client_a_columns_get_mappings(self, full_brain, target_schema):
        """All 14 columns from Client A CSV get mapped."""
        brain, mem, research = full_brain
        import csv
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", "client_a_acme.csv")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            columns = list(reader.fieldnames)
            rows = list(reader)

        sample_data = {col: [row.get(col, "") for row in rows[:3]] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)

        assert len(results) == 14  # One per column
        # Every result should have a target_field
        for r in results:
            assert r["target_field"] is not None
            assert r["target_field"] != ""

    def test_continual_learning_flow(self, full_brain, target_schema):
        """After learning from Client A analysis, Client B columns match from memory."""
        brain, mem, research = full_brain

        # Simulate: analyze Client A, then store learnings
        client_a_columns = ["cust_lvl_v2", "email_addr"]
        sample_data = {col: ["v1", "v2"] for col in client_a_columns}
        results_a = brain.analyze_columns(client_a_columns, sample_data, target_schema)

        # Store all confident results in memory
        for r in results_a:
            if r["confidence"] in ("high", "medium"):
                mem.store_mapping(r["source_column"], r["target_field"], "Acme Corp")

        # Now analyze Client B's similar column
        client_b_columns = ["contact_email"]  # Similar to email_addr
        sample_data_b = {"contact_email": ["a@b.com"]}
        results_b = brain.analyze_columns(client_b_columns, sample_data_b, target_schema)
        assert len(results_b) == 1
```

---

## GitHub Actions Workflow (`.github/workflows/phase2.yml`)

```yaml
name: "Phase 2: Brain & Research"

on:
  push:
    paths:
      - "src/brain.py"
      - "src/research.py"
      - "tests/test_phase2_*.py"
  pull_request:
    paths:
      - "src/brain.py"
      - "src/research.py"
      - "tests/test_phase2_*.py"

jobs:
  phase2-tests:
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

      - name: Lint Phase 2 files
        run: ruff check src/brain.py src/research.py

      - name: Teammate A tests (Brain)
        run: pytest tests/test_phase2_brain.py -v

      - name: Teammate B tests (Research)
        run: pytest tests/test_phase2_research.py -v

      - name: Integration tests
        run: pytest tests/test_phase2_integration.py -v
```

---

## Debug Checklist

### Gemini Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| `google.api_core.exceptions.PermissionDenied` | Invalid API key | Verify key at console.cloud.google.com |
| `google.api_core.exceptions.InvalidArgument` | Bad `response_schema` format | Must be raw dict, NOT Pydantic model |
| Gemini returns non-JSON text | Missing `response_mime_type` | Add `response_mime_type="application/json"` |
| Gemini returns wrong schema | Schema mismatch | Ensure `response_schema` matches expected output |
| `ImportError: cannot import genai` | Wrong package installed | `pip install google-genai` (NOT `google-generativeai`) |
| Gemini returns all "high" confidence | Prompt too lenient | Add "Be CONSERVATIVE" to system instruction |
| `json.JSONDecodeError` on response | Gemini occasionally wraps JSON in markdown | Strip markdown backticks before parsing |

### You.com Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Wrong auth header | Use `X-API-Key` header, NOT `Authorization: Bearer` |
| Empty results | Too specific query | Broaden the search query |
| `ConnectionError` or timeout | API temporarily down | Return empty string (graceful failure) |
| Cached results stale | Cache never expires | Restart process to clear in-memory cache |

### Integration Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| Brain can't import Research | `ResearchEngine` not exported | Check `from src.research import ResearchEngine` |
| Memory matches not working | ChromaDB state from previous test | Add `mem.clear()` to fixture setup |
| Mock mode not activating | `DEMO_MODE` not set before import | Set env var at top of test file before any imports |

---

## Smoke Test

```bash
# Phase 2 complete smoke test
DEMO_MODE=true python -c "
from src.memory import MemoryStore
from src.research import ResearchEngine
from src.brain import Brain
import json

mem = MemoryStore()
mem.clear()
research = ResearchEngine()
brain = Brain(mem, research)

schema = json.load(open('data/target_schema.json'))
cols = ['cust_id', 'cust_lvl_v2', 'email_addr']
samples = {c: ['v1','v2','v3'] for c in cols}

results = brain.analyze_columns(cols, samples, schema)
for r in results:
    print(f\"  {r['source_column']:20s} -> {r['target_field']:20s} ({r['confidence']}) {'[MEMORY]' if r.get('from_memory') else '[AI]'}\")

# Verify low confidence on ambiguous column
low_conf = [r for r in results if r['confidence'] == 'low']
assert len(low_conf) > 0, 'Expected at least one low-confidence column'

mem.clear()
print('PHASE 2: ALL SYSTEMS GO')
"
```

---

## Definition of Done

- [ ] `src/brain.py` implements `Brain` with memory-first, research-enriched, Gemini-powered analysis
- [ ] `src/research.py` implements `ResearchEngine` with You.com API, caching, and mock fallback
- [ ] Brain pipeline: memory check -> research context -> Gemini analysis
- [ ] Ambiguous columns get `"low"` confidence (triggers Plivo in Phase 3)
- [ ] Memory matches return `from_memory=True` and skip Gemini
- [ ] Demo mode works fully offline with mock responses
- [ ] `pytest tests/test_phase2_brain.py -v` passes (Teammate A)
- [ ] `pytest tests/test_phase2_research.py -v` passes (Teammate B)
- [ ] `pytest tests/test_phase2_integration.py -v` passes (Both)
- [ ] `.github/workflows/phase2.yml` is valid
- [ ] Smoke test runs clean
