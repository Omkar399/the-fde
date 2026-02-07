"""Phase 6 tests: Composio ToolExecutor -- deploy mapping and data transformation."""
import json
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.tools import ToolExecutor


@pytest.fixture
def target_schema():
    """Load the real target schema."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
    with open(schema_path) as f:
        return json.load(f)


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
        """Result dict always contains success, records_deployed, message, validation keys."""
        result = executor.deploy_mapping("TestCorp", sample_mappings, sample_rows)
        assert "success" in result
        assert "records_deployed" in result
        assert "message" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["records_deployed"], int)
        assert isinstance(result["message"], str)
        assert "validation_warnings" in result
        assert "transformations_applied" in result
        assert isinstance(result["validation_warnings"], int)
        assert isinstance(result["transformations_applied"], int)


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
        # Without schema, no coercion: "Y" stays as string
        assert row["is_active"] == "Y"
        # Verify all 14 target fields present
        assert len(row) == 14


# ---------------------------------------------------------------------------
# TestTypeCoercion
# ---------------------------------------------------------------------------

class TestTypeCoercion:
    """Tests for type coercion when a target_schema is provided."""

    # -- Boolean coercion --

    @pytest.mark.parametrize("input_val,expected", [
        ("Y", True), ("y", True), ("yes", True), ("Yes", True), ("YES", True),
        ("1", True), ("true", True), ("True", True), ("TRUE", True),
        ("active", True), ("Active", True),
        ("N", False), ("n", False), ("no", False), ("No", False), ("NO", False),
        ("0", False), ("false", False), ("False", False), ("FALSE", False),
        ("inactive", False), ("Inactive", False),
    ])
    def test_boolean_coercion(self, executor, target_schema, input_val, expected):
        """Boolean strings are coerced to Python bool."""
        mappings = [{"source_column": "flag", "target_field": "is_active"}]
        rows = [{"flag": input_val}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["is_active"] is expected
        assert len(executor._validation_warnings) == 0

    def test_boolean_invalid_generates_warning(self, executor, target_schema):
        """Non-boolean string keeps original value and generates a warning."""
        mappings = [{"source_column": "flag", "target_field": "is_active"}]
        rows = [{"flag": "maybe"}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["is_active"] == "maybe"
        assert len(executor._validation_warnings) == 1
        assert executor._validation_warnings[0]["expected_type"] == "boolean"

    # -- Date coercion --

    @pytest.mark.parametrize("input_val,expected", [
        ("2023-01-15", "2023-01-15"),
        ("01/15/2023", "2023-01-15"),
        ("Jan 15, 2023", "2023-01-15"),
        ("15-Jan-2023", "2023-01-15"),
    ])
    def test_date_normalization(self, executor, target_schema, input_val, expected):
        """Various date formats are normalized to ISO 8601."""
        mappings = [{"source_column": "dt", "target_field": "signup_date"}]
        rows = [{"dt": input_val}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["signup_date"] == expected
        assert len(executor._validation_warnings) == 0

    def test_date_invalid_generates_warning(self, executor, target_schema):
        """Unparseable date keeps original and generates a warning."""
        mappings = [{"source_column": "dt", "target_field": "signup_date"}]
        rows = [{"dt": "not-a-date"}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["signup_date"] == "not-a-date"
        assert len(executor._validation_warnings) == 1
        assert executor._validation_warnings[0]["expected_type"] == "date"

    # -- Datetime coercion --

    @pytest.mark.parametrize("input_val,expected", [
        ("2024-11-01T09:30:00", "2024-11-01T09:30:00"),
        ("2024-11-01 09:30:00", "2024-11-01T09:30:00"),
    ])
    def test_datetime_normalization(self, executor, target_schema, input_val, expected):
        """Datetime strings are normalized to ISO 8601 with T separator."""
        mappings = [{"source_column": "ts", "target_field": "last_login"}]
        rows = [{"ts": input_val}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["last_login"] == expected
        assert len(executor._validation_warnings) == 0

    def test_datetime_invalid_generates_warning(self, executor, target_schema):
        """Unparseable datetime keeps original and generates a warning."""
        mappings = [{"source_column": "ts", "target_field": "last_login"}]
        rows = [{"ts": "yesterday"}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["last_login"] == "yesterday"
        assert len(executor._validation_warnings) == 1
        assert executor._validation_warnings[0]["expected_type"] == "datetime"

    # -- Number coercion --

    @pytest.mark.parametrize("input_val,expected", [
        ("1500.00", 1500.0),
        ("$1,500.00", 1500.0),
        ("1,500", 1500.0),
        ("750.50", 750.5),
        ("0", 0.0),
    ])
    def test_number_coercion(self, executor, target_schema, input_val, expected):
        """Numeric strings (with $, commas) are coerced to float."""
        mappings = [{"source_column": "bal", "target_field": "account_balance"}]
        rows = [{"bal": input_val}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["account_balance"] == expected
        assert len(executor._validation_warnings) == 0

    def test_number_invalid_generates_warning(self, executor, target_schema):
        """Non-numeric string keeps original and generates a warning."""
        mappings = [{"source_column": "bal", "target_field": "account_balance"}]
        rows = [{"bal": "N/A"}]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0]["account_balance"] == "N/A"
        assert len(executor._validation_warnings) == 1
        assert executor._validation_warnings[0]["expected_type"] == "number"

    # -- Backward compatibility --

    def test_no_schema_skips_coercion(self, executor):
        """Without target_schema, values pass through unchanged."""
        mappings = [
            {"source_column": "flag", "target_field": "is_active"},
            {"source_column": "bal", "target_field": "account_balance"},
        ]
        rows = [{"flag": "Y", "bal": "$1,500.00"}]
        result = executor._transform_data(mappings, rows)
        assert result[0]["is_active"] == "Y"
        assert result[0]["account_balance"] == "$1,500.00"
        assert len(executor._validation_warnings) == 0

    # -- Multi-field, multi-row --

    def test_mixed_coercion_multiple_rows(self, executor, target_schema):
        """Multiple types coerced correctly across multiple rows."""
        mappings = [
            {"source_column": "flag", "target_field": "is_active"},
            {"source_column": "bal", "target_field": "account_balance"},
            {"source_column": "dt", "target_field": "signup_date"},
        ]
        rows = [
            {"flag": "Y", "bal": "$1,500.00", "dt": "01/15/2023"},
            {"flag": "N", "bal": "750.50", "dt": "Jan 15, 2023"},
        ]
        result = executor._transform_data(mappings, rows, target_schema)
        assert result[0] == {"is_active": True, "account_balance": 1500.0, "signup_date": "2023-01-15"}
        assert result[1] == {"is_active": False, "account_balance": 750.5, "signup_date": "2023-01-15"}
        assert len(executor._validation_warnings) == 0

    def test_warnings_track_row_index(self, executor, target_schema):
        """Validation warnings include the correct row index."""
        mappings = [{"source_column": "flag", "target_field": "is_active"}]
        rows = [{"flag": "Y"}, {"flag": "maybe"}, {"flag": "N"}]
        executor._transform_data(mappings, rows, target_schema)
        assert len(executor._validation_warnings) == 1
        assert executor._validation_warnings[0]["row"] == 1
