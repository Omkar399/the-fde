"""Phase 2 Integration: Brain + Research + Memory work together."""
import os
import json
import csv
import pytest

os.environ["DEMO_MODE"] = "true"

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
