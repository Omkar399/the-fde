"""Shared test fixtures for The FDE test suite."""
import os
import pytest

# Ensure demo mode is active for all tests
os.environ["DEMO_MODE"] = "true"
os.environ["DEMO_SPEED"] = "fast"

from src.agent import FDEAgent


@pytest.fixture
def clean_agent():
    """FDEAgent with fully reset memory."""
    agent = FDEAgent()
    agent.reset_memory()
    yield agent
    agent.reset_memory()
