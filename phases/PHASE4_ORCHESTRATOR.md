# Phase 4: Orchestrator & Demo (Hour 4: 2:30 PM - 4:30 PM)

## Goal
Wire everything together into the main agent loop, polish for the 3-minute demo, and finalize CI.

## Tasks

### 4.1 Main Agent Loop (`src/agent.py`)
- [ ] Orchestrate the full pipeline:
  1. Browser fetches data from client portal
  2. Brain analyzes + maps columns with confidence
  3. High confidence -> auto-map
  4. Low confidence -> call human via Plivo
  5. Store new mappings in vector memory
  6. Execute deployment via Composio
- [ ] Rich terminal output showing each step
- [ ] Summary panel at the end with stats

### 4.2 Demo Runner (`run_demo.py`)
- [ ] Phase 1 (Novice): Run agent on Client A
  - Shows browser scraping
  - Shows Gemini reasoning
  - Triggers Plivo call for uncertain columns
  - Stores learned mappings
- [ ] Phase 2 (Expert): Run agent on Client B
  - Shows browser scraping
  - Shows memory match (no call needed!)
  - Auto-maps and deploys
- [ ] Beautiful terminal UI with Rich
- [ ] `--reset` flag to clear memory
- [ ] `--demo-mode` flag to skip real APIs

### 4.3 Polish
- [ ] Error handling and graceful fallbacks in all modules
- [ ] Demo mode works fully offline
- [ ] Comparison table: Novice vs Expert

### 4.4 GitHub Workflow - Final CI
- [ ] Update `ci.yml` to run all test phases
- [ ] Add integration test that runs the full demo
- [ ] Add artifact upload for test results

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff
      - run: ruff check src/ tests/ server/

  test:
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

      - name: Phase 1 - Foundation
        run: pytest tests/test_phase1.py -v

      - name: Phase 2 - Brain & Research
        run: pytest tests/test_phase2.py -v

      - name: Phase 3 - Interfaces
        run: pytest tests/test_phase3.py -v

      - name: Phase 4 - Integration
        run: pytest tests/test_phase4.py -v

  integration:
    runs-on: ubuntu-latest
    needs: test
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Full demo run (non-interactive)
        run: |
          python -c "
          import os
          os.environ['DEMO_MODE'] = 'true'
          from src.agent import FDEAgent
          agent = FDEAgent()
          agent.reset_memory()
          s1 = agent.onboard_client('Acme Corp', 'https://portal.acme.com')
          assert s1['deployed'], 'Client A deployment failed'
          assert s1['human_confirmed'] > 0, 'Expected human calls for Client A'
          s2 = agent.onboard_client('Globex Inc', 'https://portal.globex.com')
          assert s2['deployed'], 'Client B deployment failed'
          assert s2['from_memory'] > 0, 'Expected memory matches for Client B'
          assert s2['human_confirmed'] < s1['human_confirmed'], 'Client B should need fewer calls'
          print('INTEGRATION TEST PASSED')
          agent.browser.close()
          "
```

### 4.5 Tests - Phase 4

```python
# tests/test_phase4.py
"""Phase 4 tests: Full agent orchestration and demo flow."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.agent import FDEAgent


@pytest.fixture
def agent():
    a = FDEAgent()
    a.reset_memory()
    yield a
    a.reset_memory()
    a.browser.close()


class TestFDEAgent:
    def test_agent_initializes(self, agent):
        """Agent initializes all components without errors."""
        assert agent.memory is not None
        assert agent.brain is not None
        assert agent.research is not None
        assert agent.browser is not None
        assert agent.teacher is not None
        assert agent.tools is not None
        assert agent.target_schema is not None
        assert "fields" in agent.target_schema

    def test_onboard_client_a(self, agent):
        """Full onboarding pipeline works for Client A."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["client"] == "Acme Corp"
        assert summary["total_columns"] > 0
        assert summary["deployed"] is True
        assert summary["new_learnings"] > 0  # Should learn new mappings

    def test_onboard_client_b_after_a(self, agent):
        """Client B benefits from Client A's learnings."""
        # Onboard A first
        summary_a = agent.onboard_client("Acme Corp", "https://portal.acme.com")

        # Then onboard B
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globex.com")
        assert summary_b["deployed"] is True
        assert summary_b["from_memory"] > 0  # Should have memory matches

    def test_continual_learning_reduces_human_calls(self, agent):
        """Core assertion: Client B needs fewer human calls than A."""
        summary_a = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globex.com")

        # The whole point of the project:
        # After learning from A, B should need fewer human interventions
        assert summary_b["human_confirmed"] <= summary_a["human_confirmed"], \
            f"Expected fewer calls for B ({summary_b['human_confirmed']}) " \
            f"than A ({summary_a['human_confirmed']})"

    def test_memory_grows_after_onboarding(self, agent):
        """Memory count increases after onboarding."""
        assert agent.memory.count == 0
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert agent.memory.count > 0

    def test_reset_memory_clears_all(self, agent):
        """reset_memory() clears all stored mappings."""
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert agent.memory.count > 0
        agent.reset_memory()
        assert agent.memory.count == 0

    def test_summary_has_all_keys(self, agent):
        """Onboarding summary contains all expected keys."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        expected_keys = [
            "client", "total_columns", "from_memory", "auto_mapped",
            "human_confirmed", "new_learnings", "deployed"
        ]
        for key in expected_keys:
            assert key in summary, f"Missing key: {key}"


class TestDemoMode:
    def test_demo_mode_no_api_keys_needed(self, agent):
        """Full pipeline works without any real API keys."""
        # All API keys are empty/placeholder, but demo mode should still work
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["deployed"] is True

    def test_both_clients_deploy_successfully(self, agent):
        """Both clients complete successfully in demo mode."""
        s1 = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        s2 = agent.onboard_client("Globex Inc", "https://portal.globex.com")
        assert s1["deployed"] is True
        assert s2["deployed"] is True
```

### 4.6 Debug Checklist

#### Agent Orchestration
- [ ] **Agent init fails**: Usually a missing file. Check `data/target_schema.json` exists
- [ ] **Onboarding returns no mappings**: Check brain is receiving columns. Add `print(columns)` in `agent.py` after scrape
- [ ] **Memory not persisting between clients**: ChromaDB `PersistentClient` needs write access to `data/memory/`. Check permissions
- [ ] **Wrong confidence levels**: If everything is "high", the mock analyzer may be too generous. Check `_mock_analyze` in `brain.py`

#### Demo Runner
- [ ] **Interactive `input()` hangs in CI**: The demo uses `input("Press Enter...")`. CI tests should call `agent.onboard_client()` directly, not `run_demo.py`
- [ ] **Rich output garbled**: Set `TERM=dumb` or use `Console(force_terminal=True)` if output looks broken
- [ ] **Demo takes too long**: Check `time.sleep()` calls in mock functions. Reduce for CI, keep for live demo

#### GitHub Actions
- [ ] **CI fails on ChromaDB**: ChromaDB needs `sqlite3`. Ubuntu runners have it, but check version. May need: `apt-get install libsqlite3-dev`
- [ ] **Import errors in CI**: Ensure `PYTHONPATH` includes project root. Or use `sys.path.insert(0, ...)` in test files
- [ ] **Tests pass locally, fail in CI**: Usually env vars. Check `DEMO_MODE=true` is set in the workflow `env:` block
- [ ] **Flaky tests**: Memory tests can be flaky if ChromaDB directory persists between runs. Always call `mem.clear()` in fixtures

```bash
# Quick smoke test for Phase 4
DEMO_MODE=true python -c "
from src.agent import FDEAgent

agent = FDEAgent()
agent.reset_memory()

# Client A (Novice)
s1 = agent.onboard_client('Acme Corp', 'https://mock.com')
print(f'Client A: {s1[\"human_confirmed\"]} calls, {s1[\"new_learnings\"]} learned')

# Client B (Expert)
s2 = agent.onboard_client('Globex Inc', 'https://mock.com')
print(f'Client B: {s2[\"human_confirmed\"]} calls, {s2[\"from_memory\"]} from memory')

# The core assertion
print(f'Learning worked: {s2[\"human_confirmed\"]} <= {s1[\"human_confirmed\"]}')

agent.reset_memory()
agent.browser.close()
print('Phase 4: ALL OK')
"
```

## Demo Flow (3 minutes)
```
[0:00] "This is The FDE - a continual learning agent"
[0:15] Trigger Client A onboarding
[0:30] Browser opens, scrapes CSV (AGI Inc)
[0:45] Gemini analyzes - flags uncertain column
[1:00] Phone rings on stage! (Plivo)
[1:15] Human confirms mapping
[1:30] Agent learns, deploys via Composio
[1:45] "Now watch what happens with Client B..."
[2:00] Trigger Client B onboarding
[2:15] Browser scrapes new CSV
[2:30] Memory match found! No call needed!
[2:45] Auto-deploy. "The FDE just learned."
[3:00] Show memory growth visualization
```

## Definition of Done
- All tests in `test_phase4.py` pass
- Integration test runs full Novice->Expert flow
- Client B has fewer human calls than Client A (continual learning works!)
- GitHub Actions CI is fully green: lint -> unit tests -> integration test
- `python run_demo.py --demo-mode --reset` runs end-to-end without errors
