"""Phase 7 tests: FDEAgent orchestrator -- init, pipeline, continual learning."""
import os
import json
import pytest

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
        assert agent.tools._client is None
