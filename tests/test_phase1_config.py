"""Phase 1 tests: Config loading and data file validation."""
import os
import csv
import json
import pytest

os.environ["DEMO_MODE"] = "true"

from src.config import Config


class TestConfigValues:
    def test_gemini_model_is_set(self):
        """GEMINI_MODEL has a default value."""
        assert Config.GEMINI_MODEL == "gemini-3-flash-preview"

    def test_demo_mode_is_bool(self):
        """DEMO_MODE is parsed as a boolean."""
        assert isinstance(Config.DEMO_MODE, bool)

    def test_confidence_threshold_is_float(self):
        """CONFIDENCE_THRESHOLD is a float between 0 and 1."""
        assert isinstance(Config.CONFIDENCE_THRESHOLD, float)
        assert 0 < Config.CONFIDENCE_THRESHOLD < 1

    def test_memory_distance_threshold_is_float(self):
        """MEMORY_DISTANCE_THRESHOLD is a float between 0 and 1."""
        assert isinstance(Config.MEMORY_DISTANCE_THRESHOLD, float)
        assert 0 < Config.MEMORY_DISTANCE_THRESHOLD < 1

    def test_memory_dir_is_absolute_path(self):
        """MEMORY_DIR is an absolute path ending with data/memory."""
        assert os.path.isabs(Config.MEMORY_DIR)
        assert Config.MEMORY_DIR.endswith(os.path.join("data", "memory"))

    def test_you_search_url_is_valid(self):
        """YOU_SEARCH_URL points to the You.com API."""
        assert Config.YOU_SEARCH_URL == "https://ydc-index.io/v1/search"

    def test_agi_base_url_is_valid(self):
        """AGI_BASE_URL points to the AGI API."""
        assert Config.AGI_BASE_URL == "https://api.agi.tech/v1"

    def test_webhook_base_url_default(self):
        """WEBHOOK_BASE_URL is a valid HTTP(S) URL (defaults to localhost:5001)."""
        assert Config.WEBHOOK_BASE_URL.startswith("http")
        assert "://" in Config.WEBHOOK_BASE_URL

    def test_api_keys_are_strings(self):
        """All API keys are strings (possibly empty)."""
        assert isinstance(Config.GEMINI_API_KEY, str)
        assert isinstance(Config.AGI_API_KEY, str)
        assert isinstance(Config.COMPOSIO_API_KEY, str)
        assert isinstance(Config.YOU_API_KEY, str)

    def test_demo_speed_default(self):
        """DEMO_SPEED defaults to 'fast'."""
        assert Config.DEMO_SPEED in ("fast", "normal")

    def test_delay_returns_float(self):
        """Config.delay() returns a float."""
        result = Config.delay(1.0)
        assert isinstance(result, float)
        if Config.DEMO_SPEED == "fast":
            assert result == pytest.approx(0.2)
        else:
            assert result == pytest.approx(1.0)

    def test_plivo_fields_are_strings(self):
        """All Plivo fields are strings (possibly empty)."""
        assert isinstance(Config.PLIVO_AUTH_ID, str)
        assert isinstance(Config.PLIVO_AUTH_TOKEN, str)
        assert isinstance(Config.PLIVO_PHONE_NUMBER, str)
        assert isinstance(Config.ENGINEER_PHONE_NUMBER, str)


class TestEnvExample:
    def test_env_example_exists(self):
        """The .env.example file exists at the project root."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        assert os.path.exists(env_path), ".env.example not found"

    def test_env_example_has_all_keys(self):
        """The .env.example documents all required env vars."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        with open(env_path) as f:
            content = f.read()
        required_keys = [
            "GEMINI_API_KEY", "AGI_API_KEY", "COMPOSIO_API_KEY",
            "PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "PLIVO_PHONE_NUMBER",
            "ENGINEER_PHONE_NUMBER", "YOU_API_KEY", "DEMO_MODE",
            "WEBHOOK_BASE_URL",
        ]
        for key in required_keys:
            assert key in content, f"{key} missing from .env.example"


class TestTargetSchema:
    @pytest.fixture
    def schema(self):
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        with open(schema_path) as f:
            return json.load(f)

    def test_schema_has_14_fields(self, schema):
        """Target schema defines exactly 14 CRM fields."""
        assert len(schema["fields"]) == 14

    def test_schema_has_required_fields(self, schema):
        """Schema includes all expected canonical field names."""
        expected = [
            "customer_id", "full_name", "subscription_tier", "signup_date",
            "email", "phone", "address", "city", "state", "zip_code",
            "date_of_birth", "account_balance", "last_login", "is_active",
        ]
        for field in expected:
            assert field in schema["fields"], f"Missing schema field: {field}"

    def test_each_field_has_type_and_description(self, schema):
        """Every field has type and description keys."""
        for name, defn in schema["fields"].items():
            assert "type" in defn, f"{name} missing type"
            assert "description" in defn, f"{name} missing description"


class TestMockCSVs:
    def _load_csv(self, filename):
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock", filename)
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            return list(reader.fieldnames), list(reader)

    def test_client_a_has_14_columns(self):
        """Client A CSV has exactly 14 columns."""
        cols, _ = self._load_csv("client_a_acme.csv")
        assert len(cols) == 14

    def test_client_a_has_5_rows(self):
        """Client A CSV has 5 data rows."""
        _, rows = self._load_csv("client_a_acme.csv")
        assert len(rows) == 5

    def test_client_b_has_14_columns(self):
        """Client B CSV has exactly 14 columns."""
        cols, _ = self._load_csv("client_b_globex.csv")
        assert len(cols) == 14

    def test_client_b_has_5_rows(self):
        """Client B CSV has 5 data rows."""
        _, rows = self._load_csv("client_b_globex.csv")
        assert len(rows) == 5

    def test_client_a_columns_are_abbreviated(self):
        """Client A uses abbreviated column names (cust_id, cust_nm, etc.)."""
        cols, _ = self._load_csv("client_a_acme.csv")
        assert "cust_id" in cols
        assert "cust_nm" in cols
        assert "cust_lvl_v2" in cols

    def test_client_b_columns_are_cleaner(self):
        """Client B uses cleaner column names (customer_id, full_name, etc.)."""
        cols, _ = self._load_csv("client_b_globex.csv")
        assert "customer_id" in cols
        assert "full_name" in cols

    def test_no_empty_values_in_client_a(self):
        """Client A has no empty cells."""
        _, rows = self._load_csv("client_a_acme.csv")
        for row in rows:
            for key, val in row.items():
                assert val.strip() != "", f"Empty value in Client A: row {row}, col {key}"

    def test_no_empty_values_in_client_b(self):
        """Client B has no empty cells."""
        _, rows = self._load_csv("client_b_globex.csv")
        for row in rows:
            for key, val in row.items():
                assert val.strip() != "", f"Empty value in Client B: row {row}, col {key}"

    def test_client_c_has_14_columns(self):
        """Client C CSV has exactly 14 columns."""
        cols, _ = self._load_csv("client_c_initech.csv")
        assert len(cols) == 14

    def test_client_c_has_5_rows(self):
        """Client C CSV has 5 data rows."""
        _, rows = self._load_csv("client_c_initech.csv")
        assert len(rows) == 5

    def test_client_c_columns_are_different(self):
        """Client C uses yet another naming convention (client_ref, display_name, etc.)."""
        cols, _ = self._load_csv("client_c_initech.csv")
        assert "client_ref" in cols
        assert "display_name" in cols
        assert "tier_level" in cols

    def test_no_empty_values_in_client_c(self):
        """Client C has no empty cells."""
        _, rows = self._load_csv("client_c_initech.csv")
        for row in rows:
            for key, val in row.items():
                assert val.strip() != "", f"Empty value in Client C: row {row}, col {key}"
