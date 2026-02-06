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
