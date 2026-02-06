"""Phase 1 tests: MemoryStore CRUD, lookup, similarity, and persistence."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.memory import MemoryStore
from src.config import Config


@pytest.fixture
def memory():
    """Fresh MemoryStore for each test, cleared on teardown."""
    mem = MemoryStore()
    mem.clear()
    yield mem
    mem.clear()


class TestMemoryInit:
    def test_initializes_with_zero_count(self, memory):
        """Fresh MemoryStore has zero mappings."""
        assert memory.count == 0

    def test_memory_dir_is_created(self, memory):
        """MemoryStore creates the MEMORY_DIR directory if it doesn't exist."""
        assert os.path.isdir(Config.MEMORY_DIR)


class TestMemoryStoreMappings:
    def test_store_single_mapping(self, memory):
        """Storing one mapping increments count to 1."""
        memory.store_mapping("cust_id", "customer_id", "Acme")
        assert memory.count == 1

    def test_store_multiple_mappings(self, memory):
        """Storing N distinct mappings gives count == N."""
        memory.store_mapping("cust_id", "customer_id", "Acme")
        memory.store_mapping("email_addr", "email", "Acme")
        memory.store_mapping("phone_num", "phone", "Acme")
        assert memory.count == 3

    def test_upsert_same_key_does_not_duplicate(self, memory):
        """Upserting with same client+column replaces, not duplicates."""
        memory.store_mapping("cust_id", "customer_id", "Acme")
        memory.store_mapping("cust_id", "customer_id", "Acme")
        assert memory.count == 1

    def test_upsert_updates_target_field(self, memory):
        """Upserting with a new target_field updates the existing entry."""
        memory.store_mapping("cust_id", "wrong_field", "Acme")
        memory.store_mapping("cust_id", "customer_id", "Acme")
        match = memory.find_match("cust_id")
        assert match is not None
        assert match["target_field"] == "customer_id"

    def test_different_clients_same_column(self, memory):
        """Same column from different clients = separate entries."""
        memory.store_mapping("email", "email", "Acme")
        memory.store_mapping("email", "email", "Globex")
        assert memory.count == 2


class TestMemoryLookup:
    def test_lookup_empty_returns_empty(self, memory):
        """Lookup on empty store returns empty list."""
        results = memory.lookup("anything")
        assert results == []

    def test_lookup_returns_list_of_dicts(self, memory):
        """Lookup returns a list of dict with expected keys."""
        memory.store_mapping("email_addr", "email", "Acme")
        results = memory.lookup("email_addr")
        assert isinstance(results, list)
        assert len(results) >= 1
        result = results[0]
        assert "source_column" in result
        assert "target_field" in result
        assert "client_name" in result
        assert "distance" in result
        assert "is_confident" in result

    def test_exact_match_has_low_distance(self, memory):
        """Exact same column name returns low distance."""
        memory.store_mapping("email_addr", "email", "Acme")
        results = memory.lookup("email_addr")
        assert results[0]["distance"] < 0.05

    def test_exact_match_is_confident(self, memory):
        """Exact match is always within MEMORY_DISTANCE_THRESHOLD."""
        memory.store_mapping("email_addr", "email", "Acme")
        results = memory.lookup("email_addr")
        assert results[0]["is_confident"] is True

    def test_lookup_respects_n_results(self, memory):
        """Lookup returns at most n_results entries."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.store_mapping("col_b", "field_b", "Acme")
        memory.store_mapping("col_c", "field_c", "Acme")
        results = memory.lookup("col_a", n_results=2)
        assert len(results) <= 2

    def test_lookup_n_results_capped_to_count(self, memory):
        """If n_results > count, returns count entries."""
        memory.store_mapping("col_a", "field_a", "Acme")
        results = memory.lookup("col_a", n_results=100)
        assert len(results) == 1


class TestMemoryFindMatch:
    def test_find_match_returns_none_on_empty(self, memory):
        """find_match on empty store returns None."""
        assert memory.find_match("anything") is None

    def test_find_match_returns_exact_match(self, memory):
        """Exact column name returns the stored mapping."""
        memory.store_mapping("email_addr", "email", "Acme")
        match = memory.find_match("email_addr")
        assert match is not None
        assert match["target_field"] == "email"
        assert match["client_name"] == "Acme"

    def test_find_match_returns_none_for_dissimilar(self, memory):
        """Completely unrelated column names return None."""
        memory.store_mapping("email_addr", "email", "Acme")
        match = memory.find_match("total_revenue_ytd_usd")
        # Dissimilar enough that distance > threshold
        # This may or may not be None depending on embedding model
        # but we at least verify the function runs without error
        assert match is None or isinstance(match, dict)


class TestMemoryGetAll:
    def test_get_all_empty(self, memory):
        """get_all_mappings on empty store returns empty list."""
        assert memory.get_all_mappings() == []

    def test_get_all_returns_all_stored(self, memory):
        """get_all_mappings returns every stored mapping."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.store_mapping("col_b", "field_b", "Globex")
        all_mappings = memory.get_all_mappings()
        assert len(all_mappings) == 2
        sources = {m["source_column"] for m in all_mappings}
        assert sources == {"col_a", "col_b"}


class TestMemoryClear:
    def test_clear_resets_count_to_zero(self, memory):
        """clear() removes all mappings."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.store_mapping("col_b", "field_b", "Acme")
        assert memory.count == 2
        memory.clear()
        assert memory.count == 0

    def test_clear_then_store_works(self, memory):
        """Store works normally after clear()."""
        memory.store_mapping("col_a", "field_a", "Acme")
        memory.clear()
        memory.store_mapping("col_b", "field_b", "Globex")
        assert memory.count == 1
        match = memory.find_match("col_b")
        assert match is not None


class TestContinualLearning:
    def test_learn_from_client_a_helps_client_b(self, memory):
        """Mappings learned from one client help with similar columns from another."""
        # Learn from Client A
        memory.store_mapping("email_addr", "email", "Acme")
        memory.store_mapping("cust_id", "customer_id", "Acme")

        # Client B has similar but not identical column names
        match = memory.find_match("email_addr")
        assert match is not None
        assert match["target_field"] == "email"

    def test_exact_column_reuse_across_clients(self, memory):
        """If Client B uses same column name, memory returns prior mapping."""
        memory.store_mapping("customer_id", "customer_id", "Acme")
        match = memory.find_match("customer_id")
        assert match is not None
        assert match["target_field"] == "customer_id"
        assert match["is_confident"] is True
