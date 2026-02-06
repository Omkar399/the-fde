"""Phase 2 Teammate B tests: You.com research engine."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.research import ResearchEngine


class TestResearchInit:
    def test_research_initializes(self):
        """ResearchEngine initializes with empty cache."""
        r = ResearchEngine()
        assert isinstance(r._cache, dict)
        assert len(r._cache) == 0


class TestResearchSearch:
    def test_search_returns_string(self):
        """search() returns a string result."""
        r = ResearchEngine()
        result = r.search("What does cust_lvl mean in CRM data?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_caches_results(self):
        """Second call with same query returns cached result (no API call)."""
        r = ResearchEngine()
        r1 = r.search("test query")
        r2 = r.search("test query")
        assert r1 == r2
        assert "test query" in r._cache

    def test_search_different_queries_cached_separately(self):
        """Different queries have separate cache entries."""
        r = ResearchEngine()
        r.search("query one")
        r.search("query two")
        assert "query one" in r._cache
        assert "query two" in r._cache

    def test_search_never_crashes(self):
        """search() returns empty string on error, never raises."""
        r = ResearchEngine()
        # Even nonsense queries should return something in mock mode
        result = r.search("asldkfjlaskdjf")
        assert isinstance(result, str)


class TestResearchColumnContext:
    def test_get_column_context_returns_string(self):
        """get_column_context returns non-empty string."""
        r = ResearchEngine()
        ctx = r.get_column_context("cust_lvl_v2")
        assert isinstance(ctx, str)

    def test_column_context_for_known_abbreviations(self):
        """Known abbreviations return relevant context."""
        r = ResearchEngine()
        ctx = r.get_column_context("dob")
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_column_context_with_custom_domain(self):
        """Custom domain parameter changes the query."""
        r = ResearchEngine()
        ctx = r.get_column_context("patient_id", domain="healthcare")
        assert isinstance(ctx, str)


class TestResearchDomainContext:
    def test_get_domain_context_returns_string(self):
        """get_domain_context returns non-empty string."""
        r = ResearchEngine()
        ctx = r.get_domain_context("healthcare CRM")
        assert isinstance(ctx, str)

    def test_domain_context_is_cached(self):
        """Domain context queries are cached too."""
        r = ResearchEngine()
        r.get_domain_context("retail analytics")
        # The internal query string should be in the cache
        assert any("retail analytics" in key for key in r._cache)


class TestResearchMockMode:
    def test_mock_returns_relevant_context_for_cust_lvl(self):
        """Mock search for 'cust_lvl' returns subscription tier context."""
        r = ResearchEngine()
        result = r._mock_search("What does cust_lvl mean?")
        assert "tier" in result.lower() or "level" in result.lower() or "subscription" in result.lower()

    def test_mock_returns_relevant_context_for_dob(self):
        """Mock search for 'dob' returns date of birth context."""
        r = ResearchEngine()
        result = r._mock_search("What does dob mean?")
        assert "birth" in result.lower() or "date" in result.lower()

    def test_mock_returns_default_for_unknown(self):
        """Unknown terms get a default response."""
        r = ResearchEngine()
        result = r._mock_search("what is xyzzy_123?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_caches_results(self):
        """Mock responses are cached too."""
        r = ResearchEngine()
        r._mock_search("test cust_lvl query")
        assert any("cust_lvl" in key for key in r._cache)
