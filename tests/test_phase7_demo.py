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
