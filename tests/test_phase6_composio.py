"""Phase 6 tests: Composio ToolExecutor -- deploy mapping and data transformation."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.tools import ToolExecutor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def executor():
    """Create a ToolExecutor in demo mode."""
    return ToolExecutor()


@pytest.fixture
def sample_mappings():
    """Standard set of column mappings."""
    return [
        {"source_column": "cust_id", "target_field": "customer_id"},
        {"source_column": "cust_nm", "target_field": "full_name"},
        {"source_column": "email_addr", "target_field": "email"},
    ]


@pytest.fixture
def sample_rows():
    """Sample data rows matching Client A CSV."""
    return [
        {"cust_id": "1001", "cust_nm": "John Smith", "email_addr": "john@acme.com"},
        {"cust_id": "1002", "cust_nm": "Jane Doe", "email_addr": "jane@acme.com"},
    ]


# ---------------------------------------------------------------------------
# TestToolExecutorInit
# ---------------------------------------------------------------------------

class TestToolExecutorInit:
    def test_demo_mode_toolset_is_none(self, executor):
        """In demo mode, _toolset is None (no Composio import attempted)."""
        assert executor._client is None


# ---------------------------------------------------------------------------
# TestToolExecutorDeploy
# ---------------------------------------------------------------------------

class TestToolExecutorDeploy:
    def test_deploy_success(self, executor, sample_mappings, sample_rows):
        """deploy_mapping returns success=True with correct record count."""
        result = executor.deploy_mapping("Acme Corp", sample_mappings, sample_rows)
        assert result["success"] is True
        assert result["records_deployed"] == 2
        assert "Acme Corp" in result["message"]

    def test_deploy_empty_data(self, executor, sample_mappings):
        """Deploying with zero rows succeeds with records_deployed=0."""
        result = executor.deploy_mapping("EmptyClient", sample_mappings, [])
        assert result["success"] is True
        assert result["records_deployed"] == 0

    def test_deploy_result_has_required_keys(self, executor, sample_mappings, sample_rows):
        """Result dict always contains success, records_deployed, message."""
        result = executor.deploy_mapping("TestCorp", sample_mappings, sample_rows)
        assert "success" in result
        assert "records_deployed" in result
        assert "message" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["records_deployed"], int)
        assert isinstance(result["message"], str)


# ---------------------------------------------------------------------------
# TestToolExecutorTransform
# ---------------------------------------------------------------------------

class TestToolExecutorTransform:
    def test_renames_columns(self, executor):
        """Source columns are renamed to target fields."""
        mappings = [{"source_column": "cust_id", "target_field": "customer_id"}]
        rows = [{"cust_id": "1001"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]

    def test_skips_unknown_target(self, executor):
        """Mappings with target_field='unknown' are excluded from output."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "weird_col", "target_field": "unknown"},
        ]
        rows = [{"cust_id": "1001", "weird_col": "garbage"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]
        assert "unknown" not in result[0]

    def test_multiple_rows(self, executor):
        """Transform works correctly across multiple rows."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "email_addr", "target_field": "email"},
        ]
        rows = [
            {"cust_id": "1001", "email_addr": "a@b.com"},
            {"cust_id": "1002", "email_addr": "c@d.com"},
            {"cust_id": "1003", "email_addr": "e@f.com"},
        ]
        result = executor._transform_data(mappings, rows)
        assert len(result) == 3
        assert result[0] == {"customer_id": "1001", "email": "a@b.com"}
        assert result[2] == {"customer_id": "1003", "email": "e@f.com"}

    def test_ignores_unmapped_source_columns(self, executor):
        """Source columns without a mapping entry are dropped from output."""
        mappings = [{"source_column": "cust_id", "target_field": "customer_id"}]
        rows = [{"cust_id": "1001", "extra_col": "should_vanish"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]
        assert "extra_col" not in result[0]

    def test_empty_mappings(self, executor):
        """Empty mappings list produces rows of empty dicts."""
        rows = [{"cust_id": "1001"}, {"cust_id": "1002"}]
        result = executor._transform_data([], rows)
        assert len(result) == 2
        assert result[0] == {}
        assert result[1] == {}

    def test_skips_mapping_without_target_field(self, executor):
        """Mappings missing the target_field key are skipped."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm"},  # No target_field key
        ]
        rows = [{"cust_id": "1001", "cust_nm": "John"}]
        result = executor._transform_data(mappings, rows)
        assert result == [{"customer_id": "1001"}]

    def test_real_client_data_transform(self, executor):
        """Transform with realistic Client A data and full mappings."""
        mappings = [
            {"source_column": "cust_id", "target_field": "customer_id"},
            {"source_column": "cust_nm", "target_field": "full_name"},
            {"source_column": "cust_lvl_v2", "target_field": "subscription_tier"},
            {"source_column": "signup_dt", "target_field": "signup_date"},
            {"source_column": "email_addr", "target_field": "email"},
            {"source_column": "phone_num", "target_field": "phone"},
            {"source_column": "addr_line1", "target_field": "address"},
            {"source_column": "city_nm", "target_field": "city"},
            {"source_column": "st_cd", "target_field": "state"},
            {"source_column": "zip_cd", "target_field": "zip_code"},
            {"source_column": "dob", "target_field": "date_of_birth"},
            {"source_column": "acct_bal", "target_field": "account_balance"},
            {"source_column": "last_login_ts", "target_field": "last_login"},
            {"source_column": "is_active_flg", "target_field": "is_active"},
        ]
        rows = [
            {
                "cust_id": "1001", "cust_nm": "John Smith",
                "cust_lvl_v2": "Gold", "signup_dt": "2023-01-15",
                "email_addr": "john.smith@acme.com", "phone_num": "555-0101",
                "addr_line1": "123 Main St", "city_nm": "Springfield",
                "st_cd": "IL", "zip_cd": "62701",
                "dob": "1985-03-22", "acct_bal": "1500.00",
                "last_login_ts": "2024-11-01 09:30:00", "is_active_flg": "Y",
            },
        ]
        result = executor._transform_data(mappings, rows)
        assert len(result) == 1
        row = result[0]
        assert row["customer_id"] == "1001"
        assert row["full_name"] == "John Smith"
        assert row["subscription_tier"] == "Gold"
        assert row["email"] == "john.smith@acme.com"
        assert row["state"] == "IL"
        assert row["is_active"] == "Y"
        # Verify all 14 target fields present
        assert len(row) == 14
