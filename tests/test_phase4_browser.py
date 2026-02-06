"""Phase 4 tests: AGI Inc BrowserAgent in demo mode."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from src.browser import BrowserAgent


@pytest.fixture
def browser():
    b = BrowserAgent()
    yield b
    b.close()


# ---------------------------------------------------------------------------
# TestBrowserInit -- verify construction and teardown
# ---------------------------------------------------------------------------
class TestBrowserInit:
    def test_init_session_is_none(self):
        """BrowserAgent starts with no active session."""
        b = BrowserAgent()
        assert b._session_id is None

    def test_close_on_fresh_instance(self):
        """Calling close() on a fresh instance does not raise."""
        b = BrowserAgent()
        b.close()  # should be a no-op
        assert b._session_id is None


# ---------------------------------------------------------------------------
# TestBrowserScrapeClientA -- Acme Corp mock data
# ---------------------------------------------------------------------------
class TestBrowserScrapeClientA:
    def test_returns_valid_structure(self, browser):
        """scrape_client_data returns dict with required keys."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert isinstance(result, dict)
        assert "columns" in result
        assert "rows" in result
        assert "sample_data" in result
        assert "raw_csv" in result

    def test_columns_match_acme_csv(self, browser):
        """Columns match the header row in client_a_acme.csv."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        expected = [
            "cust_id", "cust_nm", "cust_lvl_v2", "signup_dt", "email_addr",
            "phone_num", "addr_line1", "city_nm", "st_cd", "zip_cd",
            "dob", "acct_bal", "last_login_ts", "is_active_flg",
        ]
        assert result["columns"] == expected

    def test_rows_count(self, browser):
        """Acme CSV has 5 data rows."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        assert len(result["rows"]) == 5

    def test_sample_data_has_three_values(self, browser):
        """sample_data contains at most 3 values per column."""
        result = browser.scrape_client_data("Acme Corp", "https://portal.acme.com")
        for col, values in result["sample_data"].items():
            assert len(values) <= 3
            assert col in result["columns"]


# ---------------------------------------------------------------------------
# TestBrowserScrapeClientB -- Globex Inc mock data
# ---------------------------------------------------------------------------
class TestBrowserScrapeClientB:
    def test_columns_match_globex_csv(self, browser):
        """Columns match the header row in client_b_globex.csv."""
        result = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        expected = [
            "customer_id", "full_name", "customer_level_ver2",
            "registration_date", "contact_email", "mobile",
            "street_address", "city", "state_code", "postal_code",
            "date_of_birth", "balance_usd", "last_activity", "status",
        ]
        assert result["columns"] == expected

    def test_rows_count(self, browser):
        """Globex CSV has 5 data rows."""
        result = browser.scrape_client_data("Globex Inc", "https://portal.globex.com")
        assert len(result["rows"]) == 5


# ---------------------------------------------------------------------------
# TestBrowserFallback -- unknown client name
# ---------------------------------------------------------------------------
class TestBrowserFallback:
    def test_unknown_client_falls_back_to_acme(self, browser):
        """An unrecognized client name loads the default (Acme Corp) CSV."""
        result = browser.scrape_client_data("Unknown Co", "https://example.com")
        assert result["columns"][0] == "cust_id"
        assert len(result["rows"]) == 5


# ---------------------------------------------------------------------------
# TestBrowserCSVParser -- _parse_csv unit tests
# ---------------------------------------------------------------------------
class TestBrowserCSVParser:
    def test_simple_parse(self):
        """_parse_csv correctly splits a two-row CSV."""
        b = BrowserAgent()
        raw = "name,age\nAlice,30\nBob,25\n"
        result = b._parse_csv(raw)
        assert result["columns"] == ["name", "age"]
        assert len(result["rows"]) == 2
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][1]["age"] == "25"

    def test_sample_data_limited_to_three(self):
        """sample_data includes at most 3 values even with more rows."""
        b = BrowserAgent()
        raw = "x\n1\n2\n3\n4\n5\n"
        result = b._parse_csv(raw)
        assert len(result["sample_data"]["x"]) == 3
        assert result["sample_data"]["x"] == ["1", "2", "3"]

    def test_preserves_raw_csv(self):
        """raw_csv key contains the original CSV string unmodified."""
        b = BrowserAgent()
        raw = "col_a,col_b\nfoo,bar\n"
        result = b._parse_csv(raw)
        assert result["raw_csv"] == raw
