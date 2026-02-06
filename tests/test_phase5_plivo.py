"""Phase 5 tests: Plivo Teacher in demo mode."""
import os
import threading
import pytest

os.environ["DEMO_MODE"] = "true"

from src.teacher import Teacher, set_human_response, _pending_responses, _response_lock


@pytest.fixture
def teacher():
    return Teacher()


@pytest.fixture(autouse=True)
def clear_pending():
    """Ensure _pending_responses is clean before each test."""
    with _response_lock:
        _pending_responses.clear()
    yield
    with _response_lock:
        _pending_responses.clear()


# ---------------------------------------------------------------------------
# TestTeacherInit -- verify construction
# ---------------------------------------------------------------------------
class TestTeacherInit:
    def test_client_is_none_in_demo(self, teacher):
        """In demo mode, Plivo client is None."""
        assert teacher._client is None

    def test_teacher_creates_without_error(self):
        """Teacher can be instantiated in demo mode without Plivo credentials."""
        t = Teacher()
        assert t is not None


# ---------------------------------------------------------------------------
# TestTeacherAskHuman -- demo-mode behavior
# ---------------------------------------------------------------------------
class TestTeacherAskHuman:
    def test_returns_confirmed_in_demo(self, teacher):
        """Mock ask always confirms in demo mode."""
        result = teacher.ask_human("cust_lvl_v2", "subscription_tier")
        assert result["confirmed"] is True

    def test_returns_correct_target_field(self, teacher):
        """The suggested mapping is echoed back as target_field."""
        result = teacher.ask_human("email_addr", "email")
        assert result["target_field"] == "email"

    def test_method_is_demo_simulated(self, teacher):
        """Demo mode sets method to 'demo_simulated'."""
        result = teacher.ask_human("phone_num", "phone")
        assert result["method"] == "demo_simulated"


# ---------------------------------------------------------------------------
# TestTeacherSharedState -- set_human_response and thread safety
# ---------------------------------------------------------------------------
class TestTeacherSharedState:
    def test_set_and_retrieve_response(self):
        """set_human_response stores value retrievable under the call_id."""
        set_human_response("call-123", "1")
        with _response_lock:
            assert _pending_responses["call-123"] == "1"

    def test_concurrent_writes(self):
        """Multiple threads writing responses do not corrupt shared state."""
        errors = []

        def writer(call_id, value):
            try:
                set_human_response(call_id, value)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"call-{i}", str(i)))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        with _response_lock:
            assert len(_pending_responses) == 20
            for i in range(20):
                assert _pending_responses[f"call-{i}"] == str(i)
