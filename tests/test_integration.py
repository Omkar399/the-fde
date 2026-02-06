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
        """Full Novice->Intermediate->Expert flow across 3 clients.

        This is the core integration test that validates the entire FDE pipeline:
        1. Agent starts with empty memory (novice)
        2. Onboards Client A -- learns mappings
        3. Onboards Client B -- reuses learned mappings
        4. Onboards Client C -- demonstrates mastery with accumulated memory
        5. Learning curve shows decreasing human calls across all 3 clients
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

        # === INTERMEDIATE: Client B ===
        summary_b = agent.onboard_client("Globex Inc", "https://portal.globexinc.com/data")

        # Verify Client B results
        assert summary_b["client"] == "Globex Inc"
        assert summary_b["total_columns"] == 14
        assert summary_b["deployed"] is True

        # Client B should benefit from Client A's learnings
        assert summary_b["from_memory"] > 0, (
            "Client B should find memory matches from Client A's learnings"
        )
        assert summary_b["from_memory"] > summary_a["from_memory"], (
            f"Intermediate should use more memory (B={summary_b['from_memory']}) "
            f"than Novice (A={summary_a['from_memory']})"
        )
        assert summary_b["human_confirmed"] <= summary_a["human_confirmed"], (
            f"Intermediate should need fewer human calls (B={summary_b['human_confirmed']}) "
            f"than Novice (A={summary_a['human_confirmed']})"
        )

        memory_after_b = agent.memory.count
        assert memory_after_b >= memory_after_a, (
            "Memory should not shrink after onboarding Client B"
        )

        # === EXPERT: Client C ===
        summary_c = agent.onboard_client("Initech Ltd", "https://portal.initech.com/data")

        # Verify Client C results
        assert summary_c["client"] == "Initech Ltd"
        assert summary_c["total_columns"] == 14
        assert summary_c["deployed"] is True

        # Client C should benefit from accumulated memory
        assert summary_c["from_memory"] > 0, (
            "Client C should find memory matches from prior learnings"
        )
        assert summary_c["human_confirmed"] <= summary_a["human_confirmed"], (
            f"Expert should need fewer human calls (C={summary_c['human_confirmed']}) "
            f"than Novice (A={summary_a['human_confirmed']})"
        )

        # Memory should have grown further
        memory_after_c = agent.memory.count
        assert memory_after_c >= memory_after_b, (
            "Memory should not shrink after onboarding Client C"
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

        agent.onboard_client("Initech Ltd", "https://portal.initech.com/data")
        count_after_c = agent.memory.count

        assert count_after_b >= count_after_a, "Memory should persist and potentially grow"
        assert count_after_c >= count_after_b, "Memory should persist after 3rd client"
        all_mappings = agent.memory.get_all_mappings()
        clients_seen = {m["client_name"] for m in all_mappings}
        assert "Acme Corp" in clients_seen, "Client A mappings should still be in memory"
        assert "Globex Inc" in clients_seen, "Client B mappings should still be in memory"
