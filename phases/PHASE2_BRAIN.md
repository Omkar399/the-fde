# Phase 2: The Brain & Research (Hour 2: 12:00 PM - 1:00 PM)

## Goal
Implement Gemini-based reasoning with confidence scoring, and You.com context search.

## Tasks

### 2.1 Gemini Reasoning Engine (`src/brain.py`)
- [ ] Initialize Gemini client with system instructions
- [ ] Analyze CSV columns and attempt to map them to target schema
- [ ] Confidence scoring using structured JSON output
- [ ] Return mappings with confidence levels (high/medium/low)
- [ ] Flag uncertain mappings for human review
- [ ] Mock fallback when `DEMO_MODE=true` or Gemini key is missing

### 2.2 You.com Research Module (`src/research.py`)
- [ ] Query You.com Search API (`https://api.ydc-index.io/v1/search`) for domain context
- [ ] Use context to enrich Gemini's reasoning
- [ ] Example: "What is the standard date format for HL7 medical records?"
- [ ] Cache results to avoid redundant API calls
- [ ] Mock fallback for demo mode

### 2.3 Integration
- [ ] Brain queries Memory first (Phase 1)
- [ ] If no memory match, Brain queries You.com for context
- [ ] Brain uses Gemini + context to attempt mapping
- [ ] Brain returns confidence scores per column

### 2.4 GitHub Workflow Update
- [ ] Add Phase 2 test step to `ci.yml`

```yaml
      - name: Test Phase 2
        run: pytest tests/test_phase2.py -v
```

### 2.5 Tests - Phase 2

```python
# tests/test_phase2.py
"""Phase 2 tests: Gemini brain and You.com research in demo mode."""
import os
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


class TestResearchEngine:
    def test_mock_search_returns_string(self):
        """Research engine returns context string in demo mode."""
        r = ResearchEngine()
        result = r.search("What does cust_lvl mean in CRM data?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_cache_hit(self):
        """Second call with same query returns cached result."""
        r = ResearchEngine()
        r1 = r.search("test query")
        r2 = r.search("test query")
        assert r1 == r2

    def test_column_context(self):
        """get_column_context returns non-empty context."""
        r = ResearchEngine()
        ctx = r.get_column_context("cust_lvl_v2")
        assert isinstance(ctx, str)

    def test_domain_context(self):
        """get_domain_context returns non-empty context."""
        r = ResearchEngine()
        ctx = r.get_domain_context("healthcare CRM")
        assert isinstance(ctx, str)


class TestBrain:
    def test_analyze_returns_mappings(self, brain):
        """Brain returns a mapping for each input column."""
        import json
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)

        columns = ["cust_id", "cust_nm", "cust_lvl_v2", "email_addr"]
        sample_data = {col: ["val1", "val2", "val3"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, schema)

        assert len(results) == len(columns)
        for r in results:
            assert "source_column" in r
            assert "target_field" in r
            assert "confidence" in r
            assert r["confidence"] in ("high", "medium", "low")

    def test_ambiguous_column_gets_low_confidence(self, brain):
        """cust_lvl_v2 should be flagged as low confidence."""
        import json
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)

        columns = ["cust_lvl_v2"]
        sample_data = {"cust_lvl_v2": ["Gold", "Silver", "Bronze"]}
        results = brain.analyze_columns(columns, sample_data, schema)

        assert len(results) == 1
        assert results[0]["confidence"] == "low"

    def test_memory_match_skips_gemini(self, brain):
        """If memory has a match, Brain returns it without calling Gemini."""
        import json
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            schema = json.load(f)

        # Pre-seed memory
        brain._memory.store_mapping("email_addr", "email", "PriorClient")

        columns = ["email_addr"]
        sample_data = {"email_addr": ["a@b.com", "c@d.com"]}
        results = brain.analyze_columns(columns, sample_data, schema)

        assert len(results) == 1
        assert results[0]["from_memory"] is True
        assert results[0]["target_field"] == "email"
        assert results[0]["confidence"] == "high"

    def test_mock_analyze_handles_unknown(self, brain):
        """Unknown columns get low confidence in mock mode."""
        results = brain._mock_analyze(["totally_unknown_xyz"], {})
        assert len(results) == 1
        assert results[0]["confidence"] == "low"
```

### 2.6 Debug Checklist
- [ ] **Gemini API key invalid**: Check error message. Common: wrong key format, expired key, billing not enabled. Test with: `python -c "from google import genai; c = genai.Client(api_key='YOUR_KEY'); print(c.models.list())"`
- [ ] **Gemini returns non-JSON**: Check `response_mime_type` is set to `"application/json"`. If still fails, try lowering `temperature` to 0
- [ ] **Gemini schema validation error**: Ensure `response_schema` matches Gemini's expected format. Use raw dict, not Pydantic model directly
- [ ] **You.com 401 Unauthorized**: Check `X-API-Key` header (NOT `Authorization: Bearer`). You.com Search uses header-based auth
- [ ] **You.com empty results**: Try a broader query. Some niche queries return no snippets
- [ ] **Mock mode not activating**: Ensure `DEMO_MODE=true` is in env BEFORE importing config. Environment is read at import time

```bash
# Quick smoke test for Phase 2
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
cols = ['cust_lvl_v2', 'email_addr']
samples = {c: ['v1','v2','v3'] for c in cols}
results = brain.analyze_columns(cols, samples, schema)
for r in results:
    print(f\"{r['source_column']} -> {r['target_field']} ({r['confidence']})\")
mem.clear()
print('Phase 2: ALL OK')
"
```

## API Details

### Gemini (google-genai)
```python
from google import genai
from google.genai import types

client = genai.Client(api_key=GEMINI_API_KEY)
response = client.models.generate_content(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction="You are a data mapping expert...",
        response_mime_type="application/json",
        response_schema=MAPPING_SCHEMA,  # raw dict, not Pydantic
        temperature=0.1,
    ),
    contents=prompt,
)
```

### You.com Search API
```python
response = requests.get(
    "https://api.ydc-index.io/v1/search",
    headers={"X-API-Key": YOU_API_KEY},  # NOT Bearer token
    params={"query": "standard column names for CRM data"}
)
# Extract: response.json()["results"]["web"][*]["snippets"]
```

## Definition of Done
- All tests in `test_phase2.py` pass
- Brain returns mappings with confidence levels for all columns
- Ambiguous columns get LOW confidence
- Memory matches bypass Gemini call
- Demo mode works fully offline
