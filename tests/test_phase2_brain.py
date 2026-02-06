"""Phase 2 Teammate A tests: Gemini brain reasoning and confidence scoring."""
import os
import json
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


@pytest.fixture
def target_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
    with open(schema_path) as f:
        return json.load(f)


class TestBrainInit:
    def test_brain_initializes(self, brain):
        """Brain initializes with memory and research dependencies."""
        assert brain._memory is not None
        assert brain._research is not None

    def test_brain_demo_mode_no_client(self, brain):
        """In demo mode, Gemini client is None (uses mock)."""
        assert brain._client is None


class TestBrainAnalyze:
    def test_returns_mapping_per_column(self, brain, target_schema):
        """Brain returns exactly one mapping per input column."""
        columns = ["cust_id", "cust_nm", "email_addr"]
        sample_data = {col: ["val1", "val2", "val3"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == len(columns)

    def test_mapping_has_required_fields(self, brain, target_schema):
        """Each mapping has source_column, target_field, confidence, reasoning, from_memory."""
        columns = ["cust_id"]
        sample_data = {"cust_id": ["1001", "1002"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        result = results[0]
        assert "source_column" in result
        assert "target_field" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "from_memory" in result

    def test_confidence_values_are_valid(self, brain, target_schema):
        """Confidence is always one of: high, medium, low."""
        columns = ["cust_id", "cust_nm", "cust_lvl_v2", "email_addr"]
        sample_data = {col: ["val1", "val2", "val3"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        for r in results:
            assert r["confidence"] in ("high", "medium", "low"), \
                f"Invalid confidence: {r['confidence']}"

    def test_ambiguous_column_gets_low_confidence(self, brain, target_schema):
        """cust_lvl_v2 should be flagged as low confidence (triggers human call)."""
        columns = ["cust_lvl_v2"]
        sample_data = {"cust_lvl_v2": ["Gold", "Silver", "Bronze"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == 1
        assert results[0]["confidence"] == "low"
        assert results[0]["target_field"] == "subscription_tier"

    def test_clear_column_gets_high_confidence(self, brain, target_schema):
        """Unambiguous columns like cust_id should get high confidence."""
        columns = ["cust_id"]
        sample_data = {"cust_id": ["1001", "1002"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert results[0]["confidence"] == "high"
        assert results[0]["target_field"] == "customer_id"


class TestBrainMemoryIntegration:
    def test_memory_match_returns_from_memory_true(self, brain, target_schema):
        """If memory has a match, Brain returns from_memory=True."""
        brain._memory.store_mapping("email_addr", "email", "PriorClient")
        columns = ["email_addr"]
        sample_data = {"email_addr": ["a@b.com"]}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == 1
        assert results[0]["from_memory"] is True
        assert results[0]["target_field"] == "email"
        assert results[0]["confidence"] == "high"

    def test_memory_match_skips_gemini(self, brain, target_schema):
        """All columns matched from memory means zero Gemini calls."""
        brain._memory.store_mapping("cust_id", "customer_id", "ClientA")
        brain._memory.store_mapping("email_addr", "email", "ClientA")
        columns = ["cust_id", "email_addr"]
        sample_data = {col: ["v1"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert all(r["from_memory"] for r in results)

    def test_partial_memory_calls_gemini_for_rest(self, brain, target_schema):
        """When some columns are in memory, only unknown ones go to Gemini."""
        brain._memory.store_mapping("email_addr", "email", "ClientA")
        columns = ["email_addr", "cust_lvl_v2"]
        sample_data = {col: ["v1", "v2"] for col in columns}
        results = brain.analyze_columns(columns, sample_data, target_schema)
        assert len(results) == 2
        memory_results = [r for r in results if r["from_memory"]]
        gemini_results = [r for r in results if not r["from_memory"]]
        assert len(memory_results) == 1
        assert len(gemini_results) == 1


class TestMockAnalyzer:
    def test_mock_handles_unknown_column(self, brain):
        """Unknown columns get low confidence in mock mode."""
        results = brain._mock_analyze(["totally_unknown_xyz_123"], {})
        assert len(results) == 1
        assert results[0]["confidence"] == "low"
        assert results[0]["target_field"] == "unknown"

    def test_mock_handles_known_column(self, brain):
        """Known columns in mock map correctly."""
        results = brain._mock_analyze(["email_addr"], {})
        assert results[0]["target_field"] == "email"
        assert results[0]["confidence"] == "high"

    def test_mock_handles_mixed_columns(self, brain):
        """Mix of known and unknown columns."""
        results = brain._mock_analyze(["cust_id", "random_col"], {})
        assert len(results) == 2
        cust = next(r for r in results if r["source_column"] == "cust_id")
        rand = next(r for r in results if r["source_column"] == "random_col")
        assert cust["confidence"] == "high"
        assert rand["confidence"] == "low"
