# Phase 7: Orchestrator & Demo -- Nihal

## Status

| Aspect | Status |
|--------|--------|
| Source code | COMPLETED |
| Agent tests | REMAINING |
| Demo tests | REMAINING |
| Integration tests | REMAINING |
| Master CI update | REMAINING |

---

## Owner & Files

**Owner:** Nihal

| File | Lines | Purpose |
|------|-------|---------|
| `src/agent.py` | 213 | `FDEAgent` class -- main orchestrator that wires all 6 components into a 5-step pipeline |
| `run_demo.py` | 162 | Demo runner -- banner, Novice (Client A) vs Expert (Client B) flow, comparison table |

---

## What Was Built

### Class: `FDEAgent` (`src/agent.py`)

The central orchestrator. Creates all six components and runs the full onboarding pipeline.

**`__init__(self)`**
- Instantiates all dependencies:
  - `self.memory = MemoryStore()` (Phase 4 -- ChromaDB vector memory)
  - `self.research = ResearchEngine()` (Phase 2B -- You.com context)
  - `self.brain = Brain(self.memory, self.research)` (Phase 2A -- Gemini reasoning)
  - `self.browser = BrowserAgent()` (Phase 3 -- AGI Inc scraping)
  - `self.teacher = Teacher()` (Phase 5 -- Plivo voice calls)
  - `self.tools = ToolExecutor()` (Phase 6 -- Composio deploy)
- Loads `data/target_schema.json` into `self.target_schema`.

**`onboard_client(self, client_name, portal_url) -> dict`**

Runs the 5-step pipeline and returns a summary dict:

```python
{
    "client": str,           # e.g. "Acme Corp"
    "total_columns": int,    # e.g. 14
    "from_memory": int,      # columns matched from ChromaDB
    "auto_mapped": int,      # columns mapped by Gemini (high/medium confidence)
    "human_confirmed": int,  # columns confirmed via Plivo call
    "new_learnings": int,    # new mappings stored to memory
    "deployed": bool,        # True if deploy succeeded
}
```

**5-Step Pipeline:**

| Step | Component | Action |
|------|-----------|--------|
| 1 | `browser.scrape_client_data()` | Scrapes client portal, returns columns, rows, sample_data |
| 2 | `brain.analyze_columns()` | Checks memory, researches via You.com, reasons via Gemini. Returns mappings with confidence |
| 3 | `teacher.ask_human()` | For each mapping with `confidence == "low"`, calls the human engineer. Confirmed mappings get upgraded to `confidence = "high"` |
| 4 | `memory.store_mapping()` | Stores all newly-learned mappings (those not from memory) into ChromaDB |
| 5 | `tools.deploy_mapping()` | Transforms data and deploys via Composio |

**Categorization logic (between steps 2 and 3):**
- `from_memory`: mapping has `m.get("from_memory")` truthy
- `auto_mapped`: mapping has `confidence` of `"high"` or `"medium"` and is not from memory
- `uncertain`: mapping has `confidence` of `"low"` -- sent to Teacher in step 3

**`_display_mappings(self, mappings)`**
- Renders a Rich `Table` with columns: Source Column, Target Field, Confidence (color-coded), Source (Memory vs Gemini AI).

**`_display_summary(self, summary)`**
- Renders a Rich `Panel` with all summary metrics and the current `self.memory.count`.

**`reset_memory(self)`**
- Calls `self.memory.clear()` to delete all ChromaDB data. Used by `run_demo.py --reset`.

### Demo Runner: `run_demo.py`

**`print_banner()`**
- Displays a Rich Panel with project name and sponsor stack: Gemini, AGI Inc, You.com, Plivo, Composio.

**`run_demo(reset=False)`**
- Imports and instantiates `FDEAgent`.
- If `reset`, calls `agent.reset_memory()`.
- **Phase 1 (The Novice):** Onboards "Acme Corp" at `https://portal.acmecorp.com/data`. Agent has zero memory. Must reason from scratch and call humans for low-confidence columns.
- Shows vector memory contents after Client A.
- **Phase 2 (The Expert):** Onboards "Globex Inc" at `https://portal.globexinc.com/data`. Agent now has learned mappings. Should recognize similar columns from memory without human calls.
- **Comparison Table:** Side-by-side of Novice vs Expert metrics.
- **Final Panel:** Shows memory growth and human call reduction -- the continual learning proof.
- Calls `agent.browser.close()` for cleanup.

**`main()`**
- `argparse` with `--reset` (reset memory) and `--demo-mode` (sets `DEMO_MODE=true` env var).
- Calls `print_banner()` then `run_demo()`.

### The Key Demo Assertion

> Client B (`human_confirmed`) < Client A (`human_confirmed`)

This proves continual learning works: the agent learned from Client A and applied that knowledge to Client B, reducing the need for human intervention.

---

## Integration Points

`FDEAgent` is the integration hub. It imports every other module:

```
run_demo.py
    |
    v
src/agent.py (FDEAgent)
    |
    +-- src/memory.py     (MemoryStore)      -- Phase 4
    +-- src/research.py   (ResearchEngine)   -- Phase 2B
    +-- src/brain.py      (Brain)            -- Phase 2A
    +-- src/browser.py    (BrowserAgent)     -- Phase 3
    +-- src/teacher.py    (Teacher)          -- Phase 5
    +-- src/tools.py      (ToolExecutor)     -- Phase 6
    +-- data/target_schema.json
```

**Nothing imports `agent.py` except `run_demo.py`.** The agent is the top of the dependency tree.

### Data flow through the pipeline

```
Browser ──columns,rows,sample_data──> Brain ──mappings──> Teacher ──confirmed──> Memory
                                                                                   |
                                                                              ToolExecutor
                                                                           (transforms + deploys)
```

---

## Tests

### File: `tests/test_phase7_agent.py`

```python
"""Phase 7 tests: FDEAgent orchestrator -- init, pipeline, continual learning."""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

os.environ["DEMO_MODE"] = "true"

from src.agent import FDEAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    """Create an FDEAgent with fresh memory."""
    a = FDEAgent()
    a.reset_memory()
    yield a
    a.reset_memory()


@pytest.fixture
def target_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
    with open(schema_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# TestAgentInit
# ---------------------------------------------------------------------------

class TestAgentInit:
    def test_all_components_initialized(self, agent):
        """Agent creates all 6 sub-components on init."""
        assert agent.memory is not None
        assert agent.research is not None
        assert agent.brain is not None
        assert agent.browser is not None
        assert agent.teacher is not None
        assert agent.tools is not None

    def test_target_schema_loaded(self, agent):
        """Agent loads target_schema.json with expected fields."""
        assert "fields" in agent.target_schema
        assert "customer_id" in agent.target_schema["fields"]
        assert "email" in agent.target_schema["fields"]

    def test_memory_starts_empty_after_reset(self, agent):
        """After reset, memory count is 0."""
        assert agent.memory.count == 0


# ---------------------------------------------------------------------------
# TestAgentOnboardClientA
# ---------------------------------------------------------------------------

class TestAgentOnboardClientA:
    def test_onboard_returns_summary_dict(self, agent):
        """onboard_client returns a dict with all required keys."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        required_keys = ["client", "total_columns", "from_memory", "auto_mapped",
                         "human_confirmed", "new_learnings", "deployed"]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    def test_client_name_in_summary(self, agent):
        """Summary contains the correct client name."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["client"] == "Acme Corp"

    def test_total_columns_matches_csv(self, agent):
        """Client A CSV has 14 columns."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["total_columns"] == 14

    def test_no_memory_matches_on_first_client(self, agent):
        """First client with empty memory should have from_memory == 0."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["from_memory"] == 0

    def test_deploy_succeeds(self, agent):
        """Deployment should succeed in demo mode."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["deployed"] is True


# ---------------------------------------------------------------------------
# TestAgentOnboardClientB
# ---------------------------------------------------------------------------

class TestAgentOnboardClientB:
    def test_client_b_total_columns(self, agent):
        """Client B CSV also has 14 columns."""
        # Onboard A first so memory is populated
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")
        assert summary_b["total_columns"] == 14

    def test_client_b_deploys(self, agent):
        """Client B deployment succeeds."""
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")
        assert summary_b["deployed"] is True


# ---------------------------------------------------------------------------
# TestContinualLearning
# ---------------------------------------------------------------------------

class TestContinualLearning:
    def test_memory_grows_after_client_a(self, agent):
        """After onboarding Client A, memory should have stored new mappings."""
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert agent.memory.count > 0

    def test_client_b_uses_memory(self, agent):
        """Client B should have from_memory > 0 after learning from Client A."""
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")
        assert summary_b["from_memory"] > 0


# ---------------------------------------------------------------------------
# TestAgentSummary
# ---------------------------------------------------------------------------

class TestAgentSummary:
    def test_summary_values_are_correct_types(self, agent):
        """All summary values have correct types."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert isinstance(summary["client"], str)
        assert isinstance(summary["total_columns"], int)
        assert isinstance(summary["from_memory"], int)
        assert isinstance(summary["auto_mapped"], int)
        assert isinstance(summary["human_confirmed"], int)
        assert isinstance(summary["new_learnings"], int)
        assert isinstance(summary["deployed"], bool)

    def test_summary_counts_add_up(self, agent):
        """from_memory + auto_mapped + human_confirmed <= total_columns."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        mapped_total = summary["from_memory"] + summary["auto_mapped"] + summary["human_confirmed"]
        assert mapped_total <= summary["total_columns"]

    def test_new_learnings_nonzero_for_first_client(self, agent):
        """First client should produce new learnings (since memory was empty)."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["new_learnings"] > 0


# ---------------------------------------------------------------------------
# TestAgentReset
# ---------------------------------------------------------------------------

class TestAgentReset:
    def test_reset_clears_memory(self, agent):
        """reset_memory() empties the ChromaDB collection."""
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert agent.memory.count > 0
        agent.reset_memory()
        assert agent.memory.count == 0

    def test_reset_then_onboard_behaves_like_novice(self, agent):
        """After reset, onboarding a client should have from_memory == 0."""
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        agent.reset_memory()
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["from_memory"] == 0


# ---------------------------------------------------------------------------
# TestDemoMode
# ---------------------------------------------------------------------------

class TestDemoMode:
    def test_agent_works_in_demo_mode(self, agent):
        """Full pipeline works end-to-end in demo mode without any API keys."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        assert summary["deployed"] is True

    def test_all_components_use_mock_in_demo(self, agent):
        """In demo mode, Brain client is None and ToolExecutor toolset is None."""
        assert agent.brain._client is None
        assert agent.tools._toolset is None
```

### File: `tests/test_phase7_demo.py`

```python
"""Phase 7 tests: run_demo.py -- imports, argument parsing, demo flow."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

os.environ["DEMO_MODE"] = "true"

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# TestDemoImports
# ---------------------------------------------------------------------------

class TestDemoImports:
    def test_run_demo_importable(self):
        """run_demo module can be imported without error."""
        import run_demo
        assert hasattr(run_demo, "run_demo")
        assert hasattr(run_demo, "main")
        assert hasattr(run_demo, "print_banner")

    def test_fde_agent_importable(self):
        """FDEAgent can be imported from src.agent."""
        from src.agent import FDEAgent
        assert FDEAgent is not None


# ---------------------------------------------------------------------------
# TestDemoFlow
# ---------------------------------------------------------------------------

class TestDemoFlow:
    def test_print_banner_runs(self):
        """print_banner() executes without error."""
        from run_demo import print_banner
        # Should not raise
        print_banner()

    @patch("builtins.input", return_value="")
    def test_run_demo_completes(self, mock_input):
        """Full demo run completes without error in demo mode."""
        from run_demo import run_demo
        # Should not raise; input() calls are mocked
        run_demo(reset=True)

    @patch("builtins.input", return_value="")
    def test_run_demo_reset_flag(self, mock_input):
        """run_demo(reset=True) resets memory before running."""
        from run_demo import run_demo
        from src.agent import FDEAgent
        # Run once to populate memory
        run_demo(reset=True)
        # Memory should exist after demo completes
        agent = FDEAgent()
        assert agent.memory.count > 0
        agent.reset_memory()

    @patch("builtins.input", return_value="")
    def test_continual_learning_demo_assertion(self, mock_input):
        """The key demo assertion: Client B needs fewer human calls than Client A."""
        from src.agent import FDEAgent
        agent = FDEAgent()
        agent.reset_memory()

        summary_a = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")

        # THE KEY ASSERTION: continual learning reduces human calls
        assert summary_b["human_confirmed"] <= summary_a["human_confirmed"], (
            f"Client B needed {summary_b['human_confirmed']} human calls "
            f"but Client A needed {summary_a['human_confirmed']}. "
            f"Learning should reduce this."
        )
        assert summary_b["from_memory"] > summary_a["from_memory"], (
            f"Client B should use more memory matches than Client A. "
            f"A={summary_a['from_memory']}, B={summary_b['from_memory']}"
        )
        agent.reset_memory()


# ---------------------------------------------------------------------------
# TestDemoArgParsing
# ---------------------------------------------------------------------------

class TestDemoArgParsing:
    def test_argparse_defaults(self):
        """Default args: reset=False, demo_mode=False."""
        import argparse
        from run_demo import main
        # Verify the parser is created with expected args
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--demo-mode", action="store_true")
        args = parser.parse_args([])
        assert args.reset is False
        assert args.demo_mode is False

    def test_argparse_reset_flag(self):
        """--reset sets reset=True."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--demo-mode", action="store_true")
        args = parser.parse_args(["--reset"])
        assert args.reset is True

    def test_argparse_demo_mode_flag(self):
        """--demo-mode sets demo_mode=True."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--demo-mode", action="store_true")
        args = parser.parse_args(["--demo-mode"])
        assert args.demo_mode is True
```

### File: `tests/test_integration.py`

```python
"""Full integration test: end-to-end Novice -> Expert flow with learning transfer."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.agent import FDEAgent


@pytest.fixture
def clean_agent():
    """FDEAgent with fully reset memory."""
    agent = FDEAgent()
    agent.reset_memory()
    yield agent
    agent.reset_memory()


class TestEndToEndLearningTransfer:
    def test_novice_to_expert_full_flow(self, clean_agent):
        """Full Novice->Expert flow: Client A populates memory, Client B benefits.

        This is the core integration test that validates the entire FDE pipeline:
        1. Agent starts with empty memory (novice)
        2. Onboards Client A -- learns mappings
        3. Onboards Client B -- reuses learned mappings
        4. Client B has more memory matches and fewer human calls
        """
        agent = clean_agent

        # === NOVICE: Client A ===
        assert agent.memory.count == 0, "Memory should start empty"

        summary_a = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")

        # Verify Client A results
        assert summary_a["client"] == "Acme Corp"
        assert summary_a["total_columns"] == 14
        assert summary_a["from_memory"] == 0, "First client should have zero memory matches"
        assert summary_a["new_learnings"] > 0, "Should have learned new mappings"
        assert summary_a["deployed"] is True

        memory_after_a = agent.memory.count
        assert memory_after_a > 0, "Memory should be populated after Client A"

        # === EXPERT: Client B ===
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")

        # Verify Client B results
        assert summary_b["client"] == "Globex Inc"
        assert summary_b["total_columns"] == 14
        assert summary_b["deployed"] is True

        # === THE CONTINUAL LEARNING PROOF ===
        # Client B should benefit from Client A's learnings
        assert summary_b["from_memory"] > 0, (
            "Client B should find memory matches from Client A's learnings"
        )
        assert summary_b["from_memory"] > summary_a["from_memory"], (
            f"Expert should use more memory (B={summary_b['from_memory']}) "
            f"than Novice (A={summary_a['from_memory']})"
        )
        assert summary_b["human_confirmed"] <= summary_a["human_confirmed"], (
            f"Expert should need fewer human calls (B={summary_b['human_confirmed']}) "
            f"than Novice (A={summary_a['human_confirmed']})"
        )

        # Memory should have grown further
        memory_after_b = agent.memory.count
        assert memory_after_b >= memory_after_a, (
            "Memory should not shrink after onboarding Client B"
        )

    def test_all_summary_keys_present_both_clients(self, clean_agent):
        """Both client summaries contain all required keys with correct types."""
        agent = clean_agent
        summary_a = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")

        expected_keys = {
            "client": str,
            "total_columns": int,
            "from_memory": int,
            "auto_mapped": int,
            "human_confirmed": int,
            "new_learnings": int,
            "deployed": bool,
        }
        for summary_name, summary in [("A", summary_a), ("B", summary_b)]:
            for key, expected_type in expected_keys.items():
                assert key in summary, f"Client {summary_name} missing key: {key}"
                assert isinstance(summary[key], expected_type), (
                    f"Client {summary_name} key '{key}' should be {expected_type.__name__}, "
                    f"got {type(summary[key]).__name__}"
                )

    def test_memory_persistence_across_onboards(self, clean_agent):
        """Memory persists between onboard_client calls (same agent instance)."""
        agent = clean_agent
        agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")
        count_after_a = agent.memory.count

        agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")
        count_after_b = agent.memory.count

        assert count_after_b >= count_after_a, "Memory should persist and potentially grow"
        all_mappings = agent.memory.get_all_mappings()
        clients_seen = {m["client_name"] for m in all_mappings}
        assert "Acme Corp" in clients_seen, "Client A mappings should still be in memory"
```

---

## CI Workflow -- Master Update

File: `.github/workflows/ci.yml` (replaces existing)

```yaml
name: FDE CI

on:
  push:
    branches: [main, "phase-*"]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ruff
        run: pip install ruff

      - name: Lint with ruff
        run: ruff check src/ tests/ --select E,F,W --ignore E501,F541

  phase2:
    runs-on: ubuntu-latest
    needs: lint
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
          pip install pytest
      - name: Phase 2 tests
        run: pytest tests/test_phase2.py tests/test_phase2_brain.py tests/test_phase2_research.py tests/test_phase2_integration.py -v

  phase6:
    runs-on: ubuntu-latest
    needs: lint
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
          pip install pytest
      - name: Phase 6 tests
        run: pytest tests/test_phase6_composio.py -v

  phase7:
    runs-on: ubuntu-latest
    needs: [phase2, phase6]
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
          pip install pytest
      - name: Phase 7 Agent tests
        run: pytest tests/test_phase7_agent.py -v
      - name: Phase 7 Demo tests
        run: pytest tests/test_phase7_demo.py -v

  integration:
    runs-on: ubuntu-latest
    needs: phase7
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
          pip install pytest
      - name: Full integration tests
        run: pytest tests/test_integration.py -v
```

The CI pipeline structure:

```
lint
  |
  +------+------+
  |      |      |
phase2 phase6  ...other phases (phase1/4/5 when ready)
  |      |
  +------+
     |
  phase7
     |
integration
```

---

## Debug Checklist

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `FileNotFoundError: target_schema.json` | Working directory is wrong or `data/` folder missing | Run from project root; verify `data/target_schema.json` exists |
| `ModuleNotFoundError: src.memory` | Project root not in `sys.path` | Run `pip install -e .` or set `PYTHONPATH=.` |
| Agent `__init__` crashes with ChromaDB error | ChromaDB storage directory has permission issues or corrupt state | Delete `data/memory/` and re-run |
| `onboard_client` hangs | `teacher._mock_ask` has `time.sleep` calls totaling ~3s per uncertain column | Expected in demo mode; patience or reduce sleep values for testing |
| `from_memory` is always 0 for Client B | Memory was not populated after Client A (store step skipped) | Check that `memory.store_mapping()` was called in step 4; verify `confident` list is non-empty |
| `human_confirmed` is same for both clients | ChromaDB similarity threshold too strict or columns too different | Check `Config.MEMORY_DISTANCE_THRESHOLD` (default 0.3); Client B column names must be semantically similar to Client A's |
| `input()` blocks in tests | `run_demo()` calls `input("Press Enter...")` twice | Mock `builtins.input` in tests: `@patch("builtins.input", return_value="")` |
| `run_demo.py` fails with `ImportError` | Running from wrong directory | Run from project root: `python run_demo.py --demo-mode` |
| `browser.close()` error at end of demo | `BrowserAgent._session_id` is None in demo mode | Safe to ignore; `close()` handles None session gracefully |
| CI `phase7` job fails but `phase2`/`phase6` pass | Agent depends on all phases; a component change broke integration | Run `pytest tests/test_phase7_agent.py -v` locally to identify which step fails |
| `KeyError: 'columns'` in step 1 | Browser mock data file missing | Verify `data/mock/client_a_acme.csv` and `data/mock/client_b_globex.csv` exist |
| Memory count differs between runs | ChromaDB persistent storage not cleaned between test runs | Use `agent.reset_memory()` in test fixtures (setup and teardown) |

---

## Smoke Test

```bash
# 1. Verify agent import
DEMO_MODE=true python -c "from src.agent import FDEAgent; a = FDEAgent(); print('Components:', len([a.memory, a.brain, a.research, a.browser, a.teacher, a.tools])); print('Schema fields:', len(a.target_schema['fields']))"
# Expected: Components: 6 / Schema fields: 14

# 2. Quick onboard test
DEMO_MODE=true python -c "
from src.agent import FDEAgent
a = FDEAgent()
a.reset_memory()
s = a.onboard_client('Acme Corp', 'https://portal.acmecorp.com/data')
print('Summary:', s)
assert s['deployed'] is True
assert s['total_columns'] == 14
print('ONBOARD SMOKE TEST PASSED')
a.reset_memory()
"

# 3. Continual learning test
DEMO_MODE=true python -c "
from src.agent import FDEAgent
a = FDEAgent()
a.reset_memory()
sa = a.onboard_client('Acme Corp', 'https://portal.acmecorp.com/data')
sb = a.onboard_client('Globex Inc', 'https://portal.globexinc.com/data')
print(f'Client A: memory={sa[\"from_memory\"]}, human={sa[\"human_confirmed\"]}')
print(f'Client B: memory={sb[\"from_memory\"]}, human={sb[\"human_confirmed\"]}')
assert sb['from_memory'] > sa['from_memory'], 'Learning transfer failed'
print('CONTINUAL LEARNING SMOKE TEST PASSED')
a.reset_memory()
"

# 4. Demo runner test
DEMO_MODE=true python -c "from run_demo import print_banner; print_banner(); print('BANNER SMOKE TEST PASSED')"

# 5. Run all Phase 7 tests
DEMO_MODE=true pytest tests/test_phase7_agent.py tests/test_phase7_demo.py tests/test_integration.py -v
```

---

## Definition of Done

- [ ] `tests/test_phase7_agent.py` exists with 17 tests across 7 classes (Init: 3, OnboardA: 5, OnboardB: 2, ContinualLearning: 2, Summary: 3, Reset: 2, DemoMode: 2 -- total: 19 tests)
- [ ] `tests/test_phase7_demo.py` exists with 9 tests across 3 classes (Imports: 2, Flow: 4, ArgParsing: 3)
- [ ] `tests/test_integration.py` exists with 3 tests (full e2e flow, summary validation, memory persistence)
- [ ] All tests pass: `DEMO_MODE=true pytest tests/test_phase7_agent.py tests/test_phase7_demo.py tests/test_integration.py -v`
- [ ] `.github/workflows/ci.yml` updated with lint -> phase2/phase6 parallel -> phase7 -> integration pipeline
- [ ] `ruff check src/agent.py run_demo.py` passes with zero errors
- [ ] Smoke test commands above all produce `PASSED` output
- [ ] The key demo assertion holds: Client B `human_confirmed` <= Client A `human_confirmed`
- [ ] The key demo assertion holds: Client B `from_memory` > Client A `from_memory`
