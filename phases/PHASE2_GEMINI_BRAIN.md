# Phase 2: Gemini Brain -- Nihal

## Status

| Component | Code | Tests | CI |
|-----------|------|-------|----|
| `src/brain.py` | COMPLETED | COMPLETED | COMPLETED |
| `tests/test_phase2_brain.py` | COMPLETED | COMPLETED | COMPLETED |
| `tests/test_phase2_integration.py` | COMPLETED | COMPLETED | COMPLETED |
| `.github/workflows/phase2.yml` | COMPLETED | COMPLETED | COMPLETED |

All Phase 2 deliverables are complete.

---

## Owner & Files

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `src/brain.py` | 221 | COMPLETED | Gemini reasoning engine with confidence scoring |
| `tests/test_phase2_brain.py` | 144 | COMPLETED | 14 unit tests for Brain class |
| `tests/test_phase2_integration.py` | 103 | COMPLETED | 5 integration tests (Brain + Memory + Research) |
| `tests/test_phase2.py` | 107 | COMPLETED | Earlier combined test file (Brain + Research basics) |
| `.github/workflows/phase2.yml` | 42 | COMPLETED | CI pipeline for Phase 2 |

---

## What Was Built

### `src/brain.py` -- Gemini-Powered Reasoning Engine

The Brain is the core intelligence of The FDE. It takes raw CSV column names and sample data, then produces mapping suggestions to the canonical CRM schema with confidence scores. It uses a three-step pipeline: Memory -> Research -> Gemini.

```python
class Brain:
    def __init__(self, memory: MemoryStore, research: ResearchEngine):
        """Initialize with Memory (Phase 1) and Research (Phase 3) dependencies.
        In demo mode, self._client is None (uses mock fallback).
        In production, creates google.genai.Client with Config.GEMINI_API_KEY."""

    def analyze_columns(
        self, columns: list[str], sample_data: dict[str, list[str]], target_schema: dict
    ) -> list[dict]:
        """Main entry point. Returns list of:
        {source_column, target_field, confidence, reasoning, from_memory}

        Pipeline:
        1. For each column, check memory via find_match()
           - If match found: confidence="high", from_memory=True, skip Gemini
        2. For unknown columns (up to 3): call research.get_column_context()
           - Builds research_context string
        3. Pass unknown columns + research context to _gemini_analyze()
           - Mark all Gemini results as from_memory=False
        """

    def _gemini_analyze(
        self, columns, sample_data, target_schema, research_context
    ) -> list[dict]:
        """Build prompt and call Gemini API (or mock fallback).

        Gemini API call:
        - Model: Config.GEMINI_MODEL ("gemini-3-flash-preview")
        - system_instruction: SYSTEM_INSTRUCTION constant
        - response_mime_type: "application/json"
        - response_schema: MAPPING_SCHEMA dict
        - temperature: 0.1 (low for deterministic output)

        On exception: falls back to _mock_analyze()."""

    def _mock_analyze(self, columns, target_schema) -> list[dict]:
        """Deterministic fallback using a known_mappings dict (28 entries).
        Returns {source_column, target_field, confidence, reasoning} per column.
        Unknown columns get confidence="low", target_field="unknown"."""
```

### SYSTEM_INSTRUCTION (Gemini system prompt)

```
You are an expert data mapping agent. Your job is to map source CSV column names
to a target CRM schema.

For each source column, you must:
1. Analyze the column name, sample values, and any provided context
2. Determine which target schema field it maps to
3. Rate your confidence: "high" (>90% sure), "medium" (50-90%), or "low" (<50%)

Be conservative with confidence. If a column name is abbreviated, ambiguous, or
uses non-standard naming, rate it as "low" confidence.

Respond ONLY with valid JSON matching the requested schema.
```

### MAPPING_SCHEMA (Gemini structured output schema)

```json
{
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
          "reasoning": {"type": "string"}
        },
        "required": ["source_column", "target_field", "confidence", "reasoning"]
      }
    }
  },
  "required": ["mappings"]
}
```

### Mock Fallback (`_mock_analyze`)

The `known_mappings` dict covers all 28 column names across both mock CSVs:

| Source Column | Target Field | Mock Confidence |
|---------------|-------------|-----------------|
| `cust_id` | `customer_id` | high |
| `customer_id` | `customer_id` | high |
| `cust_nm` | `full_name` | medium |
| `full_name` | `full_name` | high |
| `cust_lvl_v2` | `subscription_tier` | low |
| `customer_level_ver2` | `subscription_tier` | low |
| `signup_dt` | `signup_date` | medium |
| `registration_date` | `signup_date` | high |
| `email_addr` | `email` | high |
| `contact_email` | `email` | high |
| `phone_num` | `phone` | high |
| `mobile` | `phone` | high |
| `addr_line1` | `address` | medium |
| `street_address` | `address` | high |
| `city_nm` | `city` | medium |
| `city` | `city` | high |
| `st_cd` | `state` | medium |
| `state_code` | `state` | high |
| `zip_cd` | `zip_code` | medium |
| `postal_code` | `zip_code` | high |
| `dob` | `date_of_birth` | medium |
| `date_of_birth` | `date_of_birth` | high |
| `acct_bal` | `account_balance` | medium |
| `balance_usd` | `account_balance` | high |
| `last_login_ts` | `last_login` | medium |
| `last_activity` | `last_login` | medium |
| `is_active_flg` | `is_active` | low |
| `status` | `is_active` | medium |

Any column not in this dict returns `confidence="low"`, `target_field="unknown"`.

### Demo Mode Behavior

When `Config.DEMO_MODE` is `True`:
1. `Brain.__init__` sets `self._client = None` (no Gemini API client created)
2. `_gemini_analyze` skips the API call entirely, goes straight to `_mock_analyze`
3. Memory and Research still run normally (Research has its own mock mode)

---

## API Reference

### Google Gemini API (via `google-genai` SDK)

| Detail | Value |
|--------|-------|
| SDK | `google-genai >= 1.0.0` |
| Client init | `genai.Client(api_key=Config.GEMINI_API_KEY)` |
| Method | `client.models.generate_content()` |
| Model | `gemini-3-flash-preview` |
| Temperature | `0.1` |
| Response format | `application/json` with `response_schema` |
| Config class | `google.genai.types.GenerateContentConfig` |

**Request flow:**
```
Brain._gemini_analyze()
  -> client.models.generate_content(
       model="gemini-3-flash-preview",
       config=GenerateContentConfig(
         system_instruction=SYSTEM_INSTRUCTION,
         response_mime_type="application/json",
         response_schema=MAPPING_SCHEMA,
         temperature=0.1,
       ),
       contents=prompt,
     )
  -> json.loads(response.text)
  -> return data["mappings"]
```

**Error handling:** Any exception from the Gemini call is caught, logged with `[red]Gemini error: {e}[/red]`, and falls back to `_mock_analyze()`.

---

## Integration Points

### Imports FROM

| Module | What | Why |
|--------|------|-----|
| `src/config.py` (Phase 1) | `Config` | API key, model name, demo mode flag |
| `src/memory.py` (Phase 1) | `MemoryStore` | Dependency injected via `__init__` |
| `src/research.py` (Phase 3) | `ResearchEngine` | Dependency injected via `__init__` |

### Imported BY

| Module | How |
|--------|-----|
| Phase 7 Agent | Creates `Brain(memory, research)` and calls `analyze_columns()` |
| `tests/test_phase2_brain.py` | Direct unit testing |
| `tests/test_phase2_integration.py` | Integration testing with all dependencies |

### Data Flow

```
Agent (Phase 7) calls brain.analyze_columns(columns, sample_data, schema)
  |
  |-- Step 1: MEMORY CHECK (Phase 1)
  |     for each column:
  |       memory.find_match(col)
  |         -> if match (distance <= 0.3): return {from_memory: True, confidence: "high"}
  |         -> if no match: add to unknown_columns list
  |
  |-- Step 2: RESEARCH (Phase 3) -- only for unknown columns
  |     for col in unknown_columns[:3]:
  |       research.get_column_context(col)
  |         -> builds research_context string
  |
  |-- Step 3: GEMINI ANALYSIS
  |     _gemini_analyze(unknown_columns, sample_data, schema, research_context)
  |       -> Gemini API call (or _mock_analyze fallback)
  |       -> returns [{source_column, target_field, confidence, reasoning}]
  |       -> marks all as from_memory=False
  |
  |-- Returns: combined results (memory matches + Gemini analysis)
```

---

## Tests

### `tests/test_phase2_brain.py` -- 14 tests (COMPLETED)

Located at `tests/test_phase2_brain.py` (144 lines).

| Class | Test | What It Verifies |
|-------|------|-----------------|
| `TestBrainInit` | `test_brain_initializes` | Memory and research dependencies are set |
| `TestBrainInit` | `test_brain_demo_mode_no_client` | `self._client is None` in demo mode |
| `TestBrainAnalyze` | `test_returns_mapping_per_column` | Output length == input length |
| `TestBrainAnalyze` | `test_mapping_has_required_fields` | Each result has all 5 required keys |
| `TestBrainAnalyze` | `test_confidence_values_are_valid` | Confidence is one of high/medium/low |
| `TestBrainAnalyze` | `test_ambiguous_column_gets_low_confidence` | `cust_lvl_v2` -> low confidence |
| `TestBrainAnalyze` | `test_clear_column_gets_high_confidence` | `cust_id` -> high confidence |
| `TestBrainMemoryIntegration` | `test_memory_match_returns_from_memory_true` | Pre-seeded memory match -> `from_memory=True` |
| `TestBrainMemoryIntegration` | `test_memory_match_skips_gemini` | All columns from memory -> zero Gemini calls |
| `TestBrainMemoryIntegration` | `test_partial_memory_calls_gemini_for_rest` | Mix of memory + Gemini results |
| `TestMockAnalyzer` | `test_mock_handles_unknown_column` | Unknown -> `confidence="low"`, `target_field="unknown"` |
| `TestMockAnalyzer` | `test_mock_handles_known_column` | `email_addr` -> `email`, high |
| `TestMockAnalyzer` | `test_mock_handles_mixed_columns` | Mix of known + unknown |

### `tests/test_phase2_integration.py` -- 5 tests (COMPLETED)

Located at `tests/test_phase2_integration.py` (103 lines).

| Test | What It Verifies |
|------|-----------------|
| `test_brain_uses_research_for_context` | Research is called for unknown columns |
| `test_full_pipeline_memory_then_research_then_gemini` | Full 3-step pipeline works end-to-end |
| `test_all_client_a_columns_get_mappings` | All 14 Client A columns produce mappings |
| `test_continual_learning_flow` | Learn from Client A, then Client B benefits |

### `tests/test_phase2.py` -- Combined smoke tests (COMPLETED)

Located at `tests/test_phase2.py` (107 lines). Contains 8 combined tests for both Brain and Research.

---

## CI Workflow

### `.github/workflows/phase2.yml` (COMPLETED)

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

**Triggers:** Runs on push/PR when `src/brain.py`, `src/research.py`, or `tests/test_phase2_*.py` change.

**Steps:**
1. Checkout + Python 3.11 setup
2. Install `requirements.txt` + `pytest` + `ruff`
3. Lint `src/brain.py` and `src/research.py` with ruff
4. Run Brain unit tests (14 tests)
5. Run Research unit tests (19 tests)
6. Run integration tests (5 tests)

All steps run with `DEMO_MODE=true` so no API keys are required in CI.

---

## Debug Checklist

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: cannot import name 'genai' from 'google'` | Wrong package installed (`google-ai` vs `google-genai`) | `pip install google-genai>=1.0.0` |
| `Gemini error: 403 Forbidden` | Invalid or expired `GEMINI_API_KEY` | Regenerate key at Google AI Studio |
| `Gemini error: 429 Too Many Requests` | Rate limit exceeded | Wait and retry; reduce batch size |
| Mock fallback returns `target_field="unknown"` | Column not in `known_mappings` dict | Expected for genuinely unknown columns; add to dict if needed |
| `json.JSONDecodeError` from Gemini response | Gemini returned non-JSON despite `response_mime_type` | Falls back to mock automatically; check prompt if persistent |
| `confidence` always `"high"` from memory | All columns were previously stored in memory | Expected -- `clear()` memory to test fresh Gemini analysis |
| `from_memory` always `False` | Memory is empty or columns don't match any stored entries | Check `memory.count` and stored mappings |
| Research context is empty string | You.com API failed or `DEMO_MODE=true` with unmatched query | Check `_mock_search` responses or API key |
| `temperature=0.1` gives inconsistent results | Gemini structured output can still vary slightly | Expected; confidence levels may shift between runs |
| Test fixture `brain` has stale memory | Previous test didn't clear memory | Ensure `mem.clear()` in both fixture setup and teardown |

---

## Smoke Test

```bash
# From project root
DEMO_MODE=true python -c "
from src.memory import MemoryStore
from src.research import ResearchEngine
from src.brain import Brain
import json

mem = MemoryStore()
mem.clear()
research = ResearchEngine()
brain = Brain(mem, research)

with open('data/target_schema.json') as f:
    schema = json.load(f)

columns = ['cust_id', 'cust_lvl_v2', 'email_addr']
sample_data = {col: ['val1', 'val2'] for col in columns}
results = brain.analyze_columns(columns, sample_data, schema)

for r in results:
    print(f\"  {r['source_column']:20s} -> {r['target_field']:20s} [{r['confidence']:6s}] (memory: {r['from_memory']})\")

assert len(results) == 3, f'Expected 3 results, got {len(results)}'
mem.clear()
print('PASS: Phase 2 smoke test')
"
```

---

## Definition of Done

- [x] `src/brain.py` implements Brain class with 3-step pipeline (memory -> research -> Gemini)
- [x] Gemini API call uses structured JSON output with `response_schema`
- [x] Mock fallback covers all 28 column names from both CSVs
- [x] Demo mode skips Gemini client creation entirely
- [x] `tests/test_phase2_brain.py` -- 14 unit tests passing
- [x] `tests/test_phase2_integration.py` -- 5 integration tests passing
- [x] `tests/test_phase2.py` -- 8 combined tests passing
- [x] `.github/workflows/phase2.yml` -- CI pipeline created and green
- [x] All tests pass with `DEMO_MODE=true` (no API keys needed)
