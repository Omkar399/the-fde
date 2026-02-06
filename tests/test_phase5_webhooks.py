"""Phase 5 tests: Flask webhook endpoints for Plivo callbacks."""
import os
import pytest

os.environ["DEMO_MODE"] = "true"

from server.webhooks import app
from src.teacher import _pending_responses, _response_lock


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clear_pending():
    """Ensure _pending_responses is clean before each test."""
    with _response_lock:
        _pending_responses.clear()
    yield
    with _response_lock:
        _pending_responses.clear()


# ---------------------------------------------------------------------------
# TestWebhookHealth -- basic health check
# ---------------------------------------------------------------------------
class TestWebhookHealth:
    def test_health_returns_ok(self, client):
        """GET /health returns status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "fde-webhooks"


# ---------------------------------------------------------------------------
# TestWebhookAnswer -- Plivo answer callback
# ---------------------------------------------------------------------------
class TestWebhookAnswer:
    def test_returns_xml_content_type(self, client):
        """POST /plivo/answer returns text/xml."""
        resp = client.post("/plivo/answer?column=email&mapping=email")
        assert "text/xml" in resp.content_type

    def test_contains_speak_text(self, client):
        """Response XML contains the column name in spoken text."""
        resp = client.post("/plivo/answer?column=cust_lvl_v2&mapping=subscription_tier")
        xml = resp.data.decode()
        assert "cust_lvl_v2" in xml
        assert "subscription_tier" in xml

    def test_contains_get_input(self, client):
        """Response XML contains a GetInput element for DTMF collection."""
        resp = client.post("/plivo/answer?column=test_col&mapping=test_field")
        xml = resp.data.decode()
        assert "GetInput" in xml or "getInput" in xml.lower()

    def test_fallback_speak_on_no_input(self, client):
        """Response XML has a fallback speak for no-input scenario."""
        resp = client.post("/plivo/answer?column=col&mapping=field")
        xml = resp.data.decode()
        assert "didn" in xml.lower() or "no input" in xml.lower()


# ---------------------------------------------------------------------------
# TestWebhookInput -- DTMF digit handling
# ---------------------------------------------------------------------------
class TestWebhookInput:
    def test_digit_1_confirms(self, client):
        """Pressing 1 stores '1' in pending responses."""
        resp = client.post(
            "/plivo/input?column=email&mapping=email",
            data={"Digits": "1", "CallUUID": "uuid-abc"},
        )
        assert resp.status_code == 200
        with _response_lock:
            assert _pending_responses.get("uuid-abc") == "1"

    def test_digit_2_rejects(self, client):
        """Pressing 2 stores '2' in pending responses."""
        resp = client.post(
            "/plivo/input?column=col&mapping=field",
            data={"Digits": "2", "CallUUID": "uuid-def"},
        )
        assert resp.status_code == 200
        with _response_lock:
            assert _pending_responses.get("uuid-def") == "2"

    def test_invalid_digit(self, client):
        """Any digit other than 1 or 2 stores 'invalid'."""
        resp = client.post(
            "/plivo/input?column=col&mapping=field",
            data={"Digits": "5", "CallUUID": "uuid-ghi"},
        )
        assert resp.status_code == 200
        with _response_lock:
            assert _pending_responses.get("uuid-ghi") == "invalid"

    def test_response_is_xml(self, client):
        """Input handler returns XML response."""
        resp = client.post(
            "/plivo/input?column=col&mapping=field",
            data={"Digits": "1", "CallUUID": "uuid-xml"},
        )
        assert "text/xml" in resp.content_type
