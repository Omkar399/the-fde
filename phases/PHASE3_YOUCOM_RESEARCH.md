# Phase 3: You.com Research Engine -- Nihal

## Status

| Component | Code | Tests | CI |
|-----------|------|-------|----|
| `src/research.py` | COMPLETED | COMPLETED | COMPLETED |
| `tests/test_phase2_research.py` | COMPLETED | COMPLETED | COMPLETED |
| `.github/workflows/phase2.yml` | COMPLETED | COMPLETED | COMPLETED |

All Phase 3 deliverables are complete. Tests and CI are bundled with Phase 2 since Brain and Research are tightly coupled.

---

## Owner & Files

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `src/research.py` | 79 | COMPLETED | You.com Search API integration with caching and mock mode |
| `tests/test_phase2_research.py` | 111 | COMPLETED | 19 unit tests across 5 test classes |
| `.github/workflows/phase2.yml` | 42 | COMPLETED | Shared CI pipeline (runs Research tests as "Teammate B") |

---

## What Was Built

### `src/research.py` -- You.com Research Engine

The ResearchEngine provides domain context to the Brain (Phase 2) so it can make better guesses about ambiguous column names. When the Brain encounters an unknown column like `cust_lvl_v2`, it asks the ResearchEngine "What does cust_lvl typically mean in CRM data?" and gets back relevant snippets that inform the Gemini prompt.

```python
class ResearchEngine:
    def __init__(self):
        """Initialize with empty in-memory cache dict."""
        self._cache: dict[str, str] = {}

    def search(self, query: str) -> str:
        """Search You.com for context. Returns concatenated snippet text.

        Flow:
        1. Check self._cache for exact query match -> return cached result
        2. If Config.DEMO_MODE: return _mock_search(query)
        3. Call You.com API: GET https://api.ydc-index.io/v1/search
           - Header: X-API-Key = Config.YOU_API_KEY
           - Param: query = query
           - Timeout: 10 seconds
        4. Parse response JSON: results.web[].snippets[]
        5. Concatenate top 5 snippets, cache, return
        6. On any exception: log warning, return empty string"""

    def get_column_context(self, column_name: str, domain: str = "CRM") -> str:
        """Convenience method. Builds query:
        'What does the column '{column_name}' typically mean in {domain} data?
         Standard field name mapping.'
        Then calls self.search(query)."""

    def get_domain_context(self, domain_description: str) -> str:
        """Convenience method. Builds query:
        'Standard data schema and field names for {domain_description}'
        Then calls self.search(query)."""

    def _mock_search(self, query: str) -> str:
        """Deterministic mock responses for demo mode.
        Checks query for keywords and returns relevant context.
        Caches mock responses too."""
```

### Mock Search Responses

The `_mock_search` method matches keywords in the query against a dict of 5 known patterns:

| Keyword in Query | Mock Response |
|-----------------|---------------|
| `cust_lvl` | "Customer level typically refers to the subscription tier or membership grade in CRM systems. Common mappings: tier, level, grade, plan." |
| `signup` | "Signup date refers to when a customer first registered. Standard field: signup_date, registration_date, created_at." |
| `dob` | "DOB is a common abbreviation for Date of Birth. Standard field: date_of_birth, birth_date." |
| `acct_bal` | "Account balance represents the current monetary balance. Standard field: account_balance, balance." |
| `flg` | "FLG or flag typically represents a boolean indicator. Common: is_active, active_flag, status." |
| *(no match)* | "This column name follows common CRM data conventions." |

Mock responses are cached in `self._cache` just like real responses, so the cache-hit path is exercised in demo mode too.

### Demo Mode Behavior

When `Config.DEMO_MODE` is `True`:
1. `search()` checks cache first (same as production)
2. Instead of calling the You.com API, calls `_mock_search(query)`
3. Mock responses are cached, so repeated calls for the same query hit cache
4. `get_column_context()` and `get_domain_context()` work normally (they just call `search()`)

### Caching Strategy

- Cache key: exact query string
- Cache scope: instance-level (`self._cache` dict)
- Cache lifetime: duration of the `ResearchEngine` instance
- No TTL, no eviction -- fine for a single-run agent session
- Both real API responses and mock responses are cached identically

---

## API Reference

### You.com Search API

| Detail | Value |
|--------|-------|
| Endpoint | `GET https://api.ydc-index.io/v1/search` |
| Auth | Header `X-API-Key: {Config.YOU_API_KEY}` |
| Query param | `query` (string) |
| Timeout | 10 seconds |
| SDK | Plain `requests.get()` (no SDK) |

**Request:**
```http
GET https://api.ydc-index.io/v1/search?query=What+does+cust_lvl+mean+in+CRM+data
X-API-Key: your-you-api-key
```

**Response structure (relevant fields):**
```json
{
  "results": {
    "web": [
      {
        "title": "...",
        "url": "...",
        "snippets": [
          "Customer level typically refers to...",
          "Common CRM field mappings include..."
        ]
      },
      ...
    ]
  }
}
```

**How we use it:**
```python
data = response.json()
snippets = []
for result in data.get("results", {}).get("web", []):
    snippets.extend(result.get("snippets", []))
context = "\n".join(snippets[:5])  # Top 5 snippets only
```

**Error handling:**
- `response.raise_for_status()` catches HTTP errors
- All exceptions are caught, logged as `[yellow]You.com search failed: {e}[/yellow]`, and return empty string
- The agent continues working even if research fails (graceful degradation)

---

## Integration Points

### Imports FROM

| Module | What | Why |
|--------|------|-----|
| `src/config.py` (Phase 1) | `Config` | API key, search URL, demo mode flag |

### Imported BY

| Module | How |
|--------|-----|
| `src/brain.py` (Phase 2) | Dependency injected via `Brain.__init__(memory, research)` |
| `tests/test_phase2_research.py` | Direct unit testing |
| `tests/test_phase2_integration.py` | Integration testing via Brain |

### Data Flow

```
Brain.analyze_columns() encounters unknown columns
  |
  |-- Step 2: RESEARCH (this module)
  |     for col in unknown_columns[:3]:       # Limit to 3 API calls
  |       research.get_column_context(col)
  |         |
  |         |-- Builds query string:
  |         |   "What does the column '{col}' typically mean in CRM data?
  |         |    Standard field name mapping."
  |         |
  |         |-- Calls self.search(query)
  |         |     |-- Cache check
  |         |     |-- You.com API call (or mock)
  |         |     |-- Returns concatenated snippets string
  |         |
  |         |-- Brain appends to research_context:
  |             "Context for '{col}': {snippets}\n"
  |
  |-- research_context is passed to Gemini prompt (Step 3)
  |     RESEARCH CONTEXT:
  |     Context for 'cust_lvl_v2': Customer level typically refers to...
```

**Rate limiting:**
The Brain limits research calls to `unknown_columns[:3]` -- at most 3 You.com API calls per `analyze_columns()` invocation. This prevents excessive API usage when processing CSVs with many unknown columns.

---

## Tests

### `tests/test_phase2_research.py` -- 19 tests (COMPLETED)

Located at `tests/test_phase2_research.py` (111 lines). All tests run with `DEMO_MODE=true`.

| Class | Test | What It Verifies |
|-------|------|-----------------|
| **TestResearchInit** | | |
| | `test_research_initializes` | Empty cache dict on init |
| **TestResearchSearch** | | |
| | `test_search_returns_string` | `search()` returns non-empty string |
| | `test_search_caches_results` | Same query returns same cached result |
| | `test_search_different_queries_cached_separately` | Different queries have separate cache entries |
| | `test_search_never_crashes` | Nonsense queries return string, never raise |
| **TestResearchColumnContext** | | |
| | `test_get_column_context_returns_string` | Returns string for `cust_lvl_v2` |
| | `test_column_context_for_known_abbreviations` | `dob` returns non-empty context |
| | `test_column_context_with_custom_domain` | Custom domain param works (e.g., "healthcare") |
| **TestResearchDomainContext** | | |
| | `test_get_domain_context_returns_string` | Returns string for "healthcare CRM" |
| | `test_domain_context_is_cached` | Domain query appears in cache |
| **TestResearchMockMode** | | |
| | `test_mock_returns_relevant_context_for_cust_lvl` | `cust_lvl` query returns tier/level/subscription context |
| | `test_mock_returns_relevant_context_for_dob` | `dob` query returns birth/date context |
| | `test_mock_returns_default_for_unknown` | Unknown terms get default response |
| | `test_mock_caches_results` | Mock responses are cached |

**Additional tests in `tests/test_phase2.py`:**

| Test | What It Verifies |
|------|-----------------|
| `test_mock_search_returns_string` | Basic search returns string in demo mode |
| `test_cache_hit` | Cache hit works |
| `test_column_context` | `get_column_context` works |
| `test_domain_context` | `get_domain_context` works |

---

## CI Workflow

### `.github/workflows/phase2.yml` (COMPLETED -- shared with Phase 2)

Research tests run as "Teammate B tests (Research)" in the Phase 2 CI pipeline:

```yaml
- name: Teammate B tests (Research)
  run: pytest tests/test_phase2_research.py -v
```

The full workflow is documented in `phases/PHASE2_GEMINI_BRAIN.md`. Research is tested in the same pipeline because:
1. Brain depends on Research (they share the same integration tests)
2. Both modules change together during development
3. The CI triggers on changes to `src/research.py` and `tests/test_phase2_*.py`

---

## Debug Checklist

| Symptom | Cause | Fix |
|---------|-------|-----|
| `requests.exceptions.ConnectionError` | No internet or You.com API is down | Falls back to empty string; check network connectivity |
| `requests.exceptions.Timeout` | API response > 10 seconds | Retry; You.com may be slow; the 10s timeout is hardcoded |
| `403 Forbidden` from You.com | Invalid `YOU_API_KEY` | Regenerate key at You.com developer dashboard |
| `KeyError: 'results'` in response parsing | You.com API response format changed | Check `data.get("results", {})` -- should not crash, returns empty |
| Empty string from `search()` | API error caught and swallowed | Check console output for `[yellow]You.com search failed:` message |
| Mock search returns default for everything | Query doesn't contain any of the 5 keywords (`cust_lvl`, `signup`, `dob`, `acct_bal`, `flg`) | Expected behavior -- add more keywords to `_mock_search` if needed |
| Cache grows unbounded | Many unique queries in a single session | Not a problem for typical usage (< 100 queries); restart if needed |
| `get_column_context` returns irrelevant context | Query template may not match domain well | Customize the `domain` parameter or modify the query template |
| Research called for only 3 columns | Brain limits research to `unknown_columns[:3]` | By design -- prevents API abuse; increase limit in `brain.py` if needed |
| `DEMO_MODE` not taking effect | Environment variable not set before import | Set `os.environ["DEMO_MODE"] = "true"` BEFORE importing `src.research` |

---

## Smoke Test

```bash
# From project root
DEMO_MODE=true python -c "
from src.research import ResearchEngine

r = ResearchEngine()
assert len(r._cache) == 0, 'Cache should start empty'

# Test mock search
ctx = r.get_column_context('cust_lvl_v2')
assert len(ctx) > 0, 'Should return non-empty context'
assert 'tier' in ctx.lower() or 'level' in ctx.lower(), 'Should mention tier/level'
print(f'Column context: {ctx[:80]}...')

# Test caching
ctx2 = r.get_column_context('cust_lvl_v2')
assert ctx == ctx2, 'Cache should return same result'
print(f'Cache entries: {len(r._cache)}')

# Test domain context
domain_ctx = r.get_domain_context('SaaS CRM')
assert isinstance(domain_ctx, str), 'Should return string'
print(f'Domain context: {domain_ctx[:80]}...')

# Test unknown term
unknown = r.search('what is xyzzy_42?')
assert isinstance(unknown, str), 'Should return string even for unknown'
print(f'Unknown query result: {unknown[:80]}...')

print('PASS: Phase 3 smoke test')
"
```

---

## Definition of Done

- [x] `src/research.py` implements ResearchEngine with You.com API integration
- [x] `search()` method with in-memory caching
- [x] `get_column_context()` convenience method with configurable domain
- [x] `get_domain_context()` convenience method
- [x] `_mock_search()` with 5 keyword patterns + default fallback
- [x] Graceful error handling (never crashes, returns empty string on failure)
- [x] `tests/test_phase2_research.py` -- 19 unit tests passing
- [x] CI runs Research tests in `.github/workflows/phase2.yml`
- [x] All tests pass with `DEMO_MODE=true` (no API keys needed)
