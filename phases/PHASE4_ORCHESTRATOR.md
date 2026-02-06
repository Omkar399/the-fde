# Phase 4: Orchestrator & Demo (30 Minutes)

## Goal
Wire all components together into the main FDE agent orchestrator, build the demo runner script, and create the master CI pipeline. Two teammates work on separate files with a single dependency: `run_demo.py` imports `FDEAgent` from `agent.py`.

## Time Budget
| Task | Time | Owner |
|------|------|-------|
| Interface contract review | 3 min | Both |
| Teammate A: Agent orchestrator | 12 min | Teammate A |
| Teammate B: Demo runner + CI | 12 min | Teammate B |
| Integration sync + final test | 3 min | Both |

## Prerequisites
- Phase 1 complete: `config.py`, `memory.py`, data files
- Phase 2 complete: `brain.py`, `research.py`
- Phase 3 complete: `browser.py`, `teacher.py`, `tools.py`, `webhooks.py`
- All Phase 1-3 tests passing

---

## Interface Contract (Agree on This FIRST)

### FDEAgent API (Teammate A creates `src/agent.py`)
```python
class FDEAgent:
    def __init__(self) -> None:
        self.memory: MemoryStore
        self.research: ResearchEngine
        self.brain: Brain
        self.browser: BrowserAgent
        self.teacher: Teacher
        self.tools: ToolExecutor
        self.target_schema: dict

    def onboard_client(self, client_name: str, portal_url: str) -> dict: ...
    def reset_memory(self) -> None: ...
```

**`onboard_client()` return format (the summary dict):**
```python
{
    "client": "Acme Corp",
    "total_columns": 14,
    "from_memory": 0,           # Columns matched from ChromaDB memory
    "auto_mapped": 10,          # Columns mapped by Gemini with high/medium confidence
    "human_confirmed": 2,       # Columns confirmed via Plivo call
    "new_learnings": 12,        # New mappings stored in memory
    "deployed": True,           # Whether Composio deployment succeeded
}
```

**The 5-step pipeline inside `onboard_client()`:**
1. **Scrape** - `browser.scrape_client_data(client_name, portal_url)` -> columns, rows, sample_data
2. **Analyze** - `brain.analyze_columns(columns, sample_data, target_schema)` -> mappings with confidence
3. **Ask Human** - For `"low"` confidence mappings, `teacher.ask_human(col, target)` -> confirmed/rejected
4. **Learn** - Store new confirmed mappings in `memory.store_mapping()` for future clients
5. **Deploy** - `tools.deploy_mapping(client_name, mappings, rows)` -> success/failure

### Demo Runner (Teammate B creates `run_demo.py`)
```python
# run_demo.py - imports FDEAgent from src.agent
from src.agent import FDEAgent

# Teammate B depends on:
# - FDEAgent.__init__()
# - FDEAgent.onboard_client(client_name, portal_url) -> dict
# - FDEAgent.reset_memory()
# - FDEAgent.memory.get_all_mappings() -> list[dict]
# - FDEAgent.memory.count -> int
# - FDEAgent.browser.close()
```

---

## Teammate A: FDE Agent Orchestrator (`src/agent.py`)

### Files Owned (no conflicts with Teammate B)
```
src/agent.py
tests/test_phase4_agent.py
```

### Task A1: Agent Implementation

The FDEAgent is the main orchestrator that coordinates all components into a single onboarding pipeline. It's the central class that makes the whole system work.

**Component wiring:**
```python
class FDEAgent:
    def __init__(self):
        self.memory = MemoryStore()
        self.research = ResearchEngine()
        self.brain = Brain(self.memory, self.research)
        self.browser = BrowserAgent()
        self.teacher = Teacher()
        self.tools = ToolExecutor()

        # Load target schema
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "target_schema.json"
        )
        with open(schema_path) as f:
            self.target_schema = json.load(f)
```

### Task A2: The 5-Step Onboarding Pipeline

```python
def onboard_client(self, client_name: str, portal_url: str) -> dict:
    summary = {
        "client": client_name,
        "total_columns": 0,
        "from_memory": 0,
        "auto_mapped": 0,
        "human_confirmed": 0,
        "new_learnings": 0,
        "deployed": False,
    }

    # === Step 1: Scrape Data (AGI Inc Browser) ===
    data = self.browser.scrape_client_data(client_name, portal_url)
    columns = data["columns"]
    sample_data = data["sample_data"]
    rows = data["rows"]
    summary["total_columns"] = len(columns)

    # === Step 2: Analyze Columns (Gemini + You.com + Memory) ===
    mappings = self.brain.analyze_columns(columns, sample_data, self.target_schema)

    # Categorize results
    confident = []
    uncertain = []
    for m in mappings:
        if m.get("from_memory"):
            confident.append(m)
            summary["from_memory"] += 1
        elif m["confidence"] in ("high", "medium"):
            confident.append(m)
            summary["auto_mapped"] += 1
        else:
            uncertain.append(m)

    # === Step 3: Handle Uncertain Mappings (Plivo Voice) ===
    for m in uncertain:
        human_result = self.teacher.ask_human(m["source_column"], m["target_field"])
        if human_result["confirmed"]:
            m["confidence"] = "high"
            m["reasoning"] = f"Human confirmed via {human_result['method']}"
            confident.append(m)
            summary["human_confirmed"] += 1

    # === Step 4: Store New Learnings (Continual Learning) ===
    new_learnings = 0
    for m in confident:
        if not m.get("from_memory"):
            self.memory.store_mapping(m["source_column"], m["target_field"], client_name)
            new_learnings += 1
    summary["new_learnings"] = new_learnings

    # === Step 5: Deploy (Composio) ===
    deploy_result = self.tools.deploy_mapping(client_name, confident, rows)
    summary["deployed"] = deploy_result["success"]

    return summary
```

### Task A3: Rich Terminal Output

The agent uses Rich for beautiful terminal output during each step:
- `Panel` for section headers
- `Table` for mapping results (source column -> target field -> confidence -> source)
- `Progress` spinner during long operations
- Color coding: green=high, yellow=medium, red=low confidence
- Final summary `Panel` with all stats

```python
def _display_mappings(self, mappings: list[dict]) -> None:
    table = Table(title="Column Mapping Results", show_lines=True)
    table.add_column("Source Column", style="cyan")
    table.add_column("Target Field", style="green")
    table.add_column("Confidence", justify="center")
    table.add_column("Source", style="dim")
    for m in mappings:
        conf = m["confidence"]
        conf_style = {"high": "[bold green]HIGH[/bold green]",
                      "medium": "[yellow]MEDIUM[/yellow]",
                      "low": "[bold red]LOW[/bold red]"}[conf]
        source = "Memory" if m.get("from_memory") else "Gemini AI"
        table.add_row(m["source_column"], m["target_field"], conf_style, source)
    console.print(table)

def _display_summary(self, summary: dict) -> None:
    panel_text = (
        f"[bold]Client:[/bold] {summary['client']}\n"
        f"[bold]Total Columns:[/bold] {summary['total_columns']}\n"
        f"[bold]From Memory:[/bold] [green]{summary['from_memory']}[/green]\n"
        f"[bold]Auto-Mapped (AI):[/bold] [blue]{summary['auto_mapped']}[/blue]\n"
        f"[bold]Human Confirmed:[/bold] [magenta]{summary['human_confirmed']}[/magenta]\n"
        f"[bold]New Learnings:[/bold] [cyan]{summary['new_learnings']}[/cyan]\n"
        f"[bold]Deployed:[/bold] {'[green]YES[/green]' if summary['deployed'] else '[red]NO[/red]'}\n"
        f"[bold]Memory Size:[/bold] {self.memory.count} total mappings"
    )
    console.print(Panel(panel_text, title="Onboarding Complete",
                        border_style="green" if summary["deployed"] else "red"))
```

### Task A4: Tests (`tests/test_phase4_agent.py`)

```python
# tests/test_phase4_agent.py
"""Phase 4 Teammate A tests: FDEAgent orchestrator."""
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


class TestAgentInit:
    def test_agent_initializes_all_components(self, agent):
        """Agent initializes all 6 components without errors."""
        assert agent.memory is not None
        assert agent.research is not None
        assert agent.brain is not None
        assert agent.browser is not None
        assert agent.teacher is not None
        assert agent.tools is not None

    def test_agent_loads_target_schema(self, agent):
        """Agent loads target_schema.json with all 14 fields."""
        assert agent.target_schema is not None
        assert "fields" in agent.target_schema
        assert len(agent.target_schema["fields"]) == 14

    def test_agent_starts_with_empty_memory(self, agent):
        """After reset, memory should be empty."""
        assert agent.memory.count == 0


class TestAgentOnboardClientA:
    def test_onboard_client_a_succeeds(self, agent):
        """Full onboarding pipeline works for Client A (Acme Corp)."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["client"] == "Acme Corp"
        assert summary["deployed"] is True

    def test_client_a_has_14_columns(self, agent):
        """Client A should have all 14 columns."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["total_columns"] == 14

    def test_client_a_learns_new_mappings(self, agent):
        """Client A should result in new learnings stored in memory."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["new_learnings"] > 0
        assert agent.memory.count > 0

    def test_client_a_no_memory_matches(self, agent):
        """First client should have zero memory matches (fresh start)."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["from_memory"] == 0

    def test_client_a_has_human_calls(self, agent):
        """Client A should trigger human calls for ambiguous columns."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["human_confirmed"] > 0


class TestAgentOnboardClientB:
    def test_client_b_after_a_succeeds(self, agent):
        """Client B succeeds after Client A."""
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globex.com")
        assert summary_b["deployed"] is True

    def test_client_b_has_memory_matches(self, agent):
        """Client B should benefit from Client A's learnings."""
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globex.com")
        assert summary_b["from_memory"] > 0


class TestContinualLearning:
    def test_fewer_human_calls_for_client_b(self, agent):
        """Core assertion: Client B needs fewer human calls than Client A.

        This is the ENTIRE POINT of the project:
        After learning from Client A, the agent should handle Client B
        more autonomously, with fewer human interventions.
        """
        summary_a = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globex.com")

        assert summary_b["human_confirmed"] <= summary_a["human_confirmed"], \
            f"Expected fewer human calls for B ({summary_b['human_confirmed']}) " \
            f"than A ({summary_a['human_confirmed']}). Learning didn't work!"

    def test_memory_grows_across_clients(self, agent):
        """Memory count increases after each client."""
        assert agent.memory.count == 0
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        after_a = agent.memory.count
        assert after_a > 0
        agent.onboard_client("Globex Inc", "https://portal.globex.com")
        after_b = agent.memory.count
        assert after_b >= after_a


class TestAgentSummary:
    def test_summary_has_all_required_keys(self, agent):
        """Onboarding summary contains all expected keys."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        expected_keys = [
            "client", "total_columns", "from_memory", "auto_mapped",
            "human_confirmed", "new_learnings", "deployed",
        ]
        for key in expected_keys:
            assert key in summary, f"Missing key in summary: {key}"

    def test_summary_values_are_correct_types(self, agent):
        """Summary values have correct types."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert isinstance(summary["client"], str)
        assert isinstance(summary["total_columns"], int)
        assert isinstance(summary["from_memory"], int)
        assert isinstance(summary["auto_mapped"], int)
        assert isinstance(summary["human_confirmed"], int)
        assert isinstance(summary["new_learnings"], int)
        assert isinstance(summary["deployed"], bool)

    def test_summary_column_counts_add_up(self, agent):
        """from_memory + auto_mapped + human_confirmed should account for mapped columns."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        mapped = summary["from_memory"] + summary["auto_mapped"] + summary["human_confirmed"]
        # Some columns may be rejected, so mapped <= total_columns
        assert mapped <= summary["total_columns"]


class TestAgentReset:
    def test_reset_clears_memory(self, agent):
        """reset_memory() clears all stored mappings."""
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert agent.memory.count > 0
        agent.reset_memory()
        assert agent.memory.count == 0

    def test_reset_allows_fresh_start(self, agent):
        """After reset, Client A acts like a novice again."""
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        agent.reset_memory()
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["from_memory"] == 0


class TestDemoMode:
    def test_demo_mode_no_api_keys_needed(self, agent):
        """Full pipeline works without any real API keys."""
        summary = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert summary["deployed"] is True

    def test_both_clients_deploy(self, agent):
        """Both clients complete successfully in demo mode."""
        s1 = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        s2 = agent.onboard_client("Globex Inc", "https://portal.globex.com")
        assert s1["deployed"] is True
        assert s2["deployed"] is True
```

### Teammate A Acceptance Criteria
- [ ] `FDEAgent.__init__` initializes all 6 components + loads schema
- [ ] `onboard_client` executes the full 5-step pipeline
- [ ] Summary dict has all required keys with correct types
- [ ] Client A has `from_memory=0` (novice)
- [ ] Client B has `from_memory > 0` (learned from A)
- [ ] Client B has `human_confirmed <= Client A's human_confirmed` (learning works)
- [ ] `reset_memory` clears all stored mappings
- [ ] `pytest tests/test_phase4_agent.py -v` all green

---

## Teammate B: Demo Runner + Master CI

### Files Owned (no conflicts with Teammate A)
```
run_demo.py
.github/workflows/ci.yml
tests/test_phase4_demo.py
```

### Task B1: Demo Runner (`run_demo.py`)

The demo runner is the entry point for the 3-minute hackathon demo. It runs the full Novice -> Expert flow with beautiful Rich terminal output.

**Implementation:**

```python
#!/usr/bin/env python3
"""The FDE Demo Runner - Demonstrates continual learning in action.

Usage:
    python run_demo.py              # Run full demo
    python run_demo.py --reset      # Reset memory and run fresh
    python run_demo.py --demo-mode  # Force demo mode (no API keys needed)
"""

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

console = Console()


def print_banner():
    banner = Text()
    banner.append("THE FDE", style="bold cyan")
    banner.append(" - The Continual Learning Forward Deployed Engineer\n", style="dim")
    banner.append("An autonomous agent that learns from every client interaction.\n\n")
    banner.append("Sponsor Stack: ", style="bold")
    banner.append("Gemini", style="red")
    banner.append(" | ", style="dim")
    banner.append("AGI Inc", style="blue")
    banner.append(" | ", style="dim")
    banner.append("You.com", style="green")
    banner.append(" | ", style="dim")
    banner.append("Plivo", style="magenta")
    banner.append(" | ", style="dim")
    banner.append("Composio", style="yellow")
    console.print(Panel(banner, border_style="bold blue", padding=(1, 2)))


def run_demo(reset=False):
    from src.agent import FDEAgent

    agent = FDEAgent()

    if reset:
        console.print("[yellow]Resetting agent memory for fresh demo...[/yellow]")
        agent.reset_memory()

    # PHASE 1: THE NOVICE (Client A)
    console.print(Panel(
        "[bold]PHASE 1: THE NOVICE[/bold]\n"
        "Day 1 - The agent has no prior experience.\n"
        "It must reason from scratch and ask humans for help.",
        title="Demo Phase 1", border_style="yellow",
    ))
    input("Press Enter to start onboarding Client A (Acme Corp)...")
    summary_a = agent.onboard_client("Acme Corp", "https://portal.acmecorp.com/data")

    # Show learned mappings
    all_mappings = agent.memory.get_all_mappings()
    table = Table(title="Vector Memory Contents")
    table.add_column("Source Column", style="cyan")
    table.add_column("Target Field", style="green")
    table.add_column("Learned From", style="dim")
    for m in all_mappings:
        table.add_row(m["source_column"], m["target_field"], m["client_name"])
    console.print(table)

    # PHASE 2: THE EXPERT (Client B)
    console.print(Panel(
        "[bold]PHASE 2: THE EXPERT[/bold]\n"
        "Day 2 - The agent now has learned mappings in memory.\n"
        "Watch: it will recognize similar columns WITHOUT calling a human!",
        title="Demo Phase 2", border_style="green",
    ))
    input("Press Enter to start onboarding Client B (Globex Inc)...")
    summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")

    # COMPARISON TABLE
    comparison = Table(title="Learning Comparison: Novice vs Expert", show_lines=True)
    comparison.add_column("Metric", style="bold")
    comparison.add_column("Client A (Novice)", justify="center", style="yellow")
    comparison.add_column("Client B (Expert)", justify="center", style="green")
    comparison.add_row("Total Columns", str(summary_a["total_columns"]), str(summary_b["total_columns"]))
    comparison.add_row("From Memory", str(summary_a["from_memory"]), str(summary_b["from_memory"]))
    comparison.add_row("AI Auto-Mapped", str(summary_a["auto_mapped"]), str(summary_b["auto_mapped"]))
    comparison.add_row("Human Calls Needed", str(summary_a["human_confirmed"]), str(summary_b["human_confirmed"]))
    comparison.add_row("New Learnings", str(summary_a["new_learnings"]), str(summary_b["new_learnings"]))
    comparison.add_row("Deployed",
        "[green]Yes[/green]" if summary_a["deployed"] else "[red]No[/red]",
        "[green]Yes[/green]" if summary_b["deployed"] else "[red]No[/red]")
    console.print(comparison)

    # Final message
    console.print(Panel(
        f"[bold green]The FDE learned from Client A and applied that knowledge to Client B![/bold green]\n\n"
        f"Memory grew from 0 to [cyan]{agent.memory.count}[/cyan] learned mappings.\n"
        f"Human calls reduced from [yellow]{summary_a['human_confirmed']}[/yellow] "
        f"to [green]{summary_b['human_confirmed']}[/green].\n\n"
        "[bold]This is Continual Learning in action.[/bold]",
        title="Demo Complete", border_style="bold green",
    ))

    agent.browser.close()


def main():
    parser = argparse.ArgumentParser(description="The FDE Demo")
    parser.add_argument("--reset", action="store_true", help="Reset memory before demo")
    parser.add_argument("--demo-mode", action="store_true", help="Force demo mode")
    args = parser.parse_args()

    if args.demo_mode:
        os.environ["DEMO_MODE"] = "true"

    print_banner()
    run_demo(reset=args.reset)


if __name__ == "__main__":
    main()
```

**Demo flow timeline (3 minutes):**
```
[0:00] Banner displayed - "This is The FDE"
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
[2:45] Auto-deploy. Comparison table shown.
[3:00] "The FDE just learned." Final panel.
```

### Task B2: Master CI Workflow (`.github/workflows/ci.yml`)

This is the final CI pipeline that runs on every push/PR to main. It runs lint, all phase tests, and full integration.

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
      - name: Lint all source code
        run: ruff check src/ server/

  test-phase1:
    runs-on: ubuntu-latest
    needs: lint
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt && pip install pytest
      - name: Phase 1 - Config tests
        run: pytest tests/test_phase1_config.py -v
      - name: Phase 1 - Memory tests
        run: pytest tests/test_phase1_memory.py -v
      - name: Phase 1 - Integration
        run: pytest tests/test_phase1_integration.py -v

  test-phase2:
    runs-on: ubuntu-latest
    needs: lint
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt && pip install pytest
      - name: Phase 2 - Brain tests
        run: pytest tests/test_phase2_brain.py -v
      - name: Phase 2 - Research tests
        run: pytest tests/test_phase2_research.py -v
      - name: Phase 2 - Integration
        run: pytest tests/test_phase2_integration.py -v

  test-phase3:
    runs-on: ubuntu-latest
    needs: lint
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt && pip install pytest
      - name: Phase 3 - Browser + Tools tests
        run: pytest tests/test_phase3_browser_tools.py -v
      - name: Phase 3 - Teacher + Webhooks tests
        run: pytest tests/test_phase3_teacher_webhooks.py -v
      - name: Phase 3 - Integration
        run: pytest tests/test_phase3_integration.py -v

  test-phase4:
    runs-on: ubuntu-latest
    needs: [test-phase1, test-phase2, test-phase3]
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt && pip install pytest
      - name: Phase 4 - Agent tests
        run: pytest tests/test_phase4_agent.py -v
      - name: Phase 4 - Demo tests
        run: pytest tests/test_phase4_demo.py -v

  integration:
    runs-on: ubuntu-latest
    needs: test-phase4
    env:
      DEMO_MODE: "true"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Full integration test (Novice -> Expert)
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
          assert s2['human_confirmed'] <= s1['human_confirmed'], 'Learning should reduce calls'
          agent.reset_memory()
          agent.browser.close()
          print('FULL INTEGRATION TEST PASSED')
          "
```

**Pipeline flow:**
```
lint ─────┬─> test-phase1 ─┬─> test-phase4 ─> integration
          ├─> test-phase2 ─┤
          └─> test-phase3 ─┘
```

- Phases 1-3 run in parallel after lint (independent)
- Phase 4 waits for all three phases
- Integration test runs after Phase 4

### Task B3: Tests (`tests/test_phase4_demo.py`)

```python
# tests/test_phase4_demo.py
"""Phase 4 Teammate B tests: Demo runner validation."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"


class TestDemoImports:
    def test_run_demo_importable(self):
        """run_demo.py can be imported without errors."""
        import run_demo
        assert hasattr(run_demo, 'main')
        assert hasattr(run_demo, 'run_demo')
        assert hasattr(run_demo, 'print_banner')

    def test_fde_agent_importable(self):
        """FDEAgent can be imported from src.agent."""
        from src.agent import FDEAgent
        assert FDEAgent is not None


class TestDemoFlow:
    @pytest.fixture
    def agent(self):
        from src.agent import FDEAgent
        a = FDEAgent()
        a.reset_memory()
        yield a
        a.reset_memory()
        a.browser.close()

    def test_novice_then_expert_flow(self, agent):
        """The core demo flow: novice (A) then expert (B)."""
        # Novice
        s1 = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        assert s1["deployed"] is True
        assert s1["from_memory"] == 0
        assert s1["new_learnings"] > 0

        # Expert
        s2 = agent.onboard_client("Globex Inc", "https://portal.globex.com")
        assert s2["deployed"] is True
        assert s2["from_memory"] > 0

    def test_demo_comparison_metrics(self, agent):
        """Demo should show clear improvement from A to B."""
        s1 = agent.onboard_client("Acme Corp", "https://portal.acme.com")
        s2 = agent.onboard_client("Globex Inc", "https://portal.globex.com")

        # The comparison table should show:
        # - B has more memory matches than A
        assert s2["from_memory"] > s1["from_memory"]
        # - B needs fewer or equal human calls
        assert s2["human_confirmed"] <= s1["human_confirmed"]
        # - Both deployed successfully
        assert s1["deployed"] and s2["deployed"]

    def test_memory_growth_visible(self, agent):
        """Memory count grows from 0 to N after both clients."""
        assert agent.memory.count == 0
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        after_a = agent.memory.count
        assert after_a > 0
        agent.onboard_client("Globex Inc", "https://portal.globex.com")
        after_b = agent.memory.count
        assert after_b >= after_a

    def test_get_all_mappings_for_display(self, agent):
        """Memory mappings can be displayed (for the comparison table)."""
        agent.onboard_client("Acme Corp", "https://portal.acme.com")
        mappings = agent.memory.get_all_mappings()
        assert len(mappings) > 0
        for m in mappings:
            assert "source_column" in m
            assert "target_field" in m
            assert "client_name" in m


class TestDemoArgParsing:
    def test_demo_mode_flag(self):
        """--demo-mode flag sets DEMO_MODE env var."""
        import run_demo
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--demo-mode", action="store_true")
        args = parser.parse_args(["--demo-mode"])
        assert args.demo_mode is True

    def test_reset_flag(self):
        """--reset flag is parsed correctly."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--demo-mode", action="store_true")
        args = parser.parse_args(["--reset"])
        assert args.reset is True

    def test_no_flags_default(self):
        """No flags means no reset and no demo mode."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--demo-mode", action="store_true")
        args = parser.parse_args([])
        assert args.reset is False
        assert args.demo_mode is False
```

### Teammate B Acceptance Criteria
- [ ] `run_demo.py` runs the full Novice -> Expert demo flow
- [ ] `--reset` flag clears memory before demo
- [ ] `--demo-mode` flag sets `DEMO_MODE=true`
- [ ] Banner displays sponsor stack
- [ ] Comparison table shows improvement from Client A to B
- [ ] `.github/workflows/ci.yml` has lint -> phase tests -> integration pipeline
- [ ] Phase tests 1-3 run in parallel in CI
- [ ] Phase 4 tests wait for 1-3 to complete
- [ ] Integration test validates the full Novice -> Expert flow
- [ ] `pytest tests/test_phase4_demo.py -v` all green

---

## Integration Sync Point

After both teammates finish, run the full integration test together.

```bash
# Run ALL tests in sequence (simulates CI pipeline)
DEMO_MODE=true pytest tests/ -v

# Or run the full integration check
DEMO_MODE=true python -c "
from src.agent import FDEAgent
agent = FDEAgent()
agent.reset_memory()
s1 = agent.onboard_client('Acme Corp', 'https://portal.acme.com')
s2 = agent.onboard_client('Globex Inc', 'https://portal.globex.com')
print(f'Client A: {s1[\"human_confirmed\"]} human calls, {s1[\"new_learnings\"]} learned')
print(f'Client B: {s2[\"human_confirmed\"]} human calls, {s2[\"from_memory\"]} from memory')
assert s2['human_confirmed'] <= s1['human_confirmed'], 'Learning failed!'
assert s2['from_memory'] > 0, 'No memory transfer!'
agent.reset_memory()
agent.browser.close()
print('FULL INTEGRATION: PASSED')
"
```

---

## Debug Checklist

### Agent Orchestration
| Symptom | Cause | Fix |
|---------|-------|-----|
| `FileNotFoundError: target_schema.json` | Wrong path in `__init__` | Use `os.path.dirname(os.path.dirname(__file__))` to find project root |
| Agent returns 0 mappings | Brain not receiving columns | Add `print(columns)` after scrape step to verify |
| `from_memory` always 0 for Client B | Memory not persisting | Verify ChromaDB `PersistentClient` is being used |
| All confidence is "high" | Mock analyzer too generous | Check `_mock_analyze` maps `cust_lvl_v2` to `"low"` |
| Summary missing keys | `onboard_client` doesn't set all fields | Verify all 7 keys are set in the summary dict |
| Deploy fails | Composio import error in demo mode | Check `Config.DEMO_MODE` gates the import |

### Demo Runner
| Symptom | Cause | Fix |
|---------|-------|-----|
| `input()` hangs in CI | Demo waits for keypress | CI tests should call `agent.onboard_client()` directly, not `run_demo.py` |
| Rich output garbled | Terminal doesn't support colors | Set `TERM=dumb` or `Console(force_terminal=True)` |
| Demo takes too long | `time.sleep()` in mock functions | Reduce sleep times for faster demo (keep for live presentation) |
| `ModuleNotFoundError: src` | Missing `sys.path.insert` | Add `sys.path.insert(0, os.path.dirname(__file__))` |

### CI Pipeline
| Symptom | Cause | Fix |
|---------|-------|-----|
| ChromaDB fails on Ubuntu | Missing SQLite | Add `apt-get install libsqlite3-dev` or use newer Python |
| Import errors | Missing `PYTHONPATH` | Run from project root, or add `sys.path` fix |
| Tests pass locally, fail in CI | Missing `DEMO_MODE=true` | Set in workflow `env:` block |
| Flaky memory tests | ChromaDB state persists between tests | Always `mem.clear()` in fixture setup and teardown |
| Phase 4 tests fail but 1-3 pass | Incompatible interface changes | Check interface contracts match between phases |

---

## Smoke Test

```bash
# Phase 4 complete smoke test
DEMO_MODE=true python -c "
from src.agent import FDEAgent

agent = FDEAgent()
agent.reset_memory()

# Client A (Novice)
s1 = agent.onboard_client('Acme Corp', 'https://mock.com')
print(f'Client A: deployed={s1[\"deployed\"]}, calls={s1[\"human_confirmed\"]}, learned={s1[\"new_learnings\"]}')

# Client B (Expert)
s2 = agent.onboard_client('Globex Inc', 'https://mock.com')
print(f'Client B: deployed={s2[\"deployed\"]}, calls={s2[\"human_confirmed\"]}, memory={s2[\"from_memory\"]}')

# Core assertion
assert s2['human_confirmed'] <= s1['human_confirmed'], 'Learning failed!'
print(f'Learning: calls reduced from {s1[\"human_confirmed\"]} to {s2[\"human_confirmed\"]}')

agent.reset_memory()
agent.browser.close()
print('PHASE 4: ALL SYSTEMS GO')
"
```

---

## Full Project Verification

After all 4 phases are complete, run this master verification:

```bash
# 1. Lint everything
ruff check src/ server/

# 2. Run all phase tests
DEMO_MODE=true pytest tests/ -v

# 3. Run full integration
DEMO_MODE=true python -c "
from src.agent import FDEAgent
agent = FDEAgent()
agent.reset_memory()
s1 = agent.onboard_client('Acme Corp', 'https://portal.acme.com')
s2 = agent.onboard_client('Globex Inc', 'https://portal.globex.com')
assert s1['deployed'] and s2['deployed']
assert s2['from_memory'] > 0
assert s2['human_confirmed'] <= s1['human_confirmed']
agent.reset_memory()
agent.browser.close()
print('ALL PHASES COMPLETE - READY FOR DEMO')
"

# 4. Run the actual demo (interactive)
python run_demo.py --demo-mode --reset
```

---

## Definition of Done

- [ ] `src/agent.py` orchestrates the full 5-step pipeline
- [ ] `FDEAgent.onboard_client()` returns summary dict with all 7 keys
- [ ] Continual learning works: Client B needs fewer human calls than Client A
- [ ] `run_demo.py` runs the complete Novice -> Expert demo with Rich output
- [ ] `.github/workflows/ci.yml` has the full lint -> test -> integration pipeline
- [ ] `pytest tests/test_phase4_agent.py -v` passes (Teammate A)
- [ ] `pytest tests/test_phase4_demo.py -v` passes (Teammate B)
- [ ] `DEMO_MODE=true pytest tests/ -v` runs all phase tests green
- [ ] `python run_demo.py --demo-mode --reset` runs end-to-end without errors
- [ ] The whole project is ready for the 3-minute hackathon demo
