"""Centralized configuration for The FDE."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.0-flash"

    # AGI Inc Browser
    AGI_API_KEY = os.getenv("AGI_API_KEY", "")
    AGI_BASE_URL = "https://api.agi.tech/v1"

    # Composio
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")

    # Plivo
    PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID", "")
    PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN", "")
    PLIVO_PHONE_NUMBER = os.getenv("PLIVO_PHONE_NUMBER", "")
    ENGINEER_PHONE_NUMBER = os.getenv("ENGINEER_PHONE_NUMBER", "")

    # You.com
    YOU_API_KEY = os.getenv("YOU_API_KEY", "")
    YOU_SEARCH_URL = "https://api.ydc-index.io/v1/search"

    # Webhook server
    WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "http://localhost:5000")

    # Demo mode
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

    # Memory
    MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory")
    CONFIDENCE_THRESHOLD = 0.75  # Below this, ask the human
    MEMORY_DISTANCE_THRESHOLD = 0.3  # Max vector distance for auto-match
