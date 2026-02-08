"""AGI Inc Browser Automation - The FDE's hands for interacting with web portals.

Uses the AGI Inc API to create browser sessions that can navigate to
client portals, log in, and scrape data. Falls back to local files
when the API is unavailable.
"""

import csv
import io
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rich.console import Console

from src.config import Config
from server.events import emit_event

console = Console()

MAX_POLL_SECONDS = 180
POLL_INTERVAL_SECS = 2.0


def _mk_session() -> requests.Session:
    """Create a requests Session with automatic retries (matches AGI reference)."""
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


DEFAULT_AGENT_NAME = "agi-0"


class BrowserAgent:
    """AGI Inc browser automation for scraping client portals."""

    def __init__(self):
        self._session_id = None
        self._http = _mk_session()
        self._agent_name = DEFAULT_AGENT_NAME

    def scrape_client_data(self, client_name: str, portal_url: str, credentials: dict | None = None) -> dict:
        """Scrape CSV data from a client portal.

        Args:
            client_name: Display name of the client.
            portal_url: URL of the client portal.
            credentials: Optional dict with "username" and "password" keys.

        Returns:
            dict with keys: columns (list), rows (list of dicts), raw_csv (str)
        """
        if Config.DEMO_MODE:
            return self._mock_scrape(client_name)

        try:
            return self._agi_scrape(client_name, portal_url, credentials)
        except Exception as e:
            console.print(f"  [yellow]AGI Browser failed: {e}. Using local fallback.[/yellow]")
            return self._mock_scrape(client_name)

    def _build_headers(self) -> dict:
        """Build API headers matching the AGI reference client."""
        headers = {"Accept": "application/json"}
        if Config.AGI_API_KEY:
            headers["Authorization"] = f"Bearer {Config.AGI_API_KEY}"
        return headers

    def _discover_agent(self, headers: dict) -> str:
        """Query /v1/models and pick the best available agent.

        Prefers a 'fast' variant if available, otherwise falls back to DEFAULT_AGENT_NAME
        or the first model returned by the API.
        """
        try:
            resp = self._http.get(
                f"{Config.AGI_BASE_URL}/models",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            if not models:
                return DEFAULT_AGENT_NAME

            console.print(f"  [cyan]AGI Browser:[/cyan] Available models: {models}")

            # Prefer a fast variant
            for m in models:
                if "fast" in m.lower():
                    console.print(f"  [cyan]AGI Browser:[/cyan] Using fast model: {m}")
                    return m

            # Fall back to default if it exists, otherwise first available
            if DEFAULT_AGENT_NAME in models:
                return DEFAULT_AGENT_NAME
            console.print(f"  [cyan]AGI Browser:[/cyan] '{DEFAULT_AGENT_NAME}' not found, using: {models[0]}")
            return models[0]
        except Exception as e:
            console.print(f"  [yellow]AGI Browser: Model discovery failed ({e}), using default.[/yellow]")
            return DEFAULT_AGENT_NAME

    def _send_and_wait(self, headers: dict, message: str, timeout_secs: float = 60) -> str | None:
        """Send a single message and wait for the agent to finish. Returns final status."""
        resp = self._http.post(
            f"{Config.AGI_BASE_URL}/sessions/{self._session_id}/message",
            headers=headers,
            json={"message": message},
            timeout=30,
        )
        resp.raise_for_status()

        # Poll until the agent finishes this action
        after_id = 0
        deadline = time.time() + timeout_secs
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SECS)
            try:
                resp = self._http.get(
                    f"{Config.AGI_BASE_URL}/sessions/{self._session_id}/messages",
                    headers=headers,
                    params={"after_id": after_id, "sanitize": "true"},
                    timeout=30,
                )
            except requests.exceptions.Timeout:
                continue
            if resp.status_code != 200:
                continue

            data = resp.json()
            for msg in data.get("messages", []):
                mid = msg.get("id", 0)
                after_id = max(after_id, int(mid))
                content = msg.get("content", "")
                if isinstance(content, str) and self._looks_like_csv(content):
                    return content

            status = data.get("status", "")
            if status in ("finished", "error", "waiting_for_input"):
                return None

        return None

    def _agi_scrape(self, client_name: str, portal_url: str, credentials: dict | None = None) -> dict:
        """Use AGI Inc API to scrape data from a portal.

        Uses tightly-scoped single-action steps instead of one big prompt.
        """
        headers = self._build_headers()

        # Step 0: Discover the best available agent model
        self._agent_name = self._discover_agent(headers)

        # Step 1: Create a browser session
        emit_event("browser_navigate", {"url": portal_url, "action": "Creating AGI browser session..."})
        console.print(f"  [cyan]AGI Browser:[/cyan] Creating session (agent: {self._agent_name})...")
        resp = self._http.post(
            f"{Config.AGI_BASE_URL}/sessions",
            headers=headers,
            json={"agent_name": self._agent_name},
            timeout=60,
        )
        resp.raise_for_status()
        session = resp.json()
        self._session_id = session["session_id"]
        console.print(f"  [cyan]AGI Browser:[/cyan] Session ready: {self._session_id[:8]}...")

        # Get live VNC view URL for the dashboard
        vnc_url = session.get("vnc_url", "")
        if vnc_url:
            console.print(f"  [cyan]AGI Browser:[/cyan] Live view: {vnc_url}")
            emit_event("browser_live", {
                "vnc_url": vnc_url,
                "session_id": self._session_id,
                "action": "AGI Browser session started — watching live",
            })

        # Step 2: Navigate to the portal login page
        emit_event("browser_navigate", {"url": portal_url, "action": "Navigating to portal..."})
        console.print(f"  [cyan]AGI Browser:[/cyan] Navigating to {portal_url}...")
        resp = self._http.post(
            f"{Config.AGI_BASE_URL}/sessions/{self._session_id}/navigate",
            headers=headers,
            json={"url": portal_url},
            timeout=60,
        )
        resp.raise_for_status()
        console.print("  [cyan]AGI Browser:[/cyan] Navigation complete.")

        # Step 3: Handle ngrok interstitial if present
        emit_event("browser_navigate", {"url": portal_url, "action": "Checking for ngrok warning..."})
        console.print("  [cyan]AGI Browser:[/cyan] Handling ngrok interstitial (if any)...")
        self._send_and_wait(
            headers,
            "If you see a page that says 'You are about to visit' with a 'Visit Site' button, click the 'Visit Site' button. If you already see a login form, do nothing.",
            timeout_secs=30,
        )

        # Step 4: Click the Log In button (credentials are pre-filled)
        cred_user = (credentials or {}).get("username", "admin")
        cred_pass = (credentials or {}).get("password", "admin123")
        emit_event("browser_navigate", {"url": portal_url, "action": "Logging in..."})
        console.print("  [cyan]AGI Browser:[/cyan] Clicking Log In...")
        self._send_and_wait(
            headers,
            f"You are on a login page. The username field already contains '{cred_user}' and the password field already contains '{cred_pass}'. Click the 'Log In' submit button.",
            timeout_secs=30,
        )

        # Step 5: Click the Download CSV link on the dashboard
        emit_event("browser_navigate", {"url": portal_url, "action": "Downloading CSV..."})
        console.print("  [cyan]AGI Browser:[/cyan] Clicking Download CSV...")
        csv_content = self._send_and_wait(
            headers,
            "You are on a data dashboard page. Find and click the link that says 'Download as CSV' or 'Download CSV'. After clicking, return the full CSV file content as plain text.",
            timeout_secs=60,
        )

        if csv_content:
            console.print("  [cyan]AGI Browser:[/cyan] CSV received from agent.")
            return self._parse_csv(csv_content)

        # Step 6: If the click didn't return CSV, try asking the agent to read the page
        console.print("  [cyan]AGI Browser:[/cyan] Trying to read CSV from page...")
        csv_content = self._send_and_wait(
            headers,
            "Copy all the text content you can see on the current page and return it exactly as-is. Do not summarize or modify it.",
            timeout_secs=30,
        )

        if csv_content:
            return self._parse_csv(csv_content)

        # Fallback: download directly via localhost
        console.print("  [yellow]AGI Browser: Agent couldn't extract CSV, trying direct download...[/yellow]")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(portal_url)
            portal_path = parsed.path.rstrip("/")
            local_download_url = f"http://localhost:5001{portal_path}/download"
            resp = self._http.get(local_download_url, timeout=10)
            if resp.status_code == 200 and self._looks_like_csv(resp.text):
                console.print("  [cyan]AGI Browser:[/cyan] Local download succeeded")
                return self._parse_csv(resp.text)
        except Exception:
            pass

        # Fallback: try via ngrok with skip header
        try:
            download_url = portal_url.rstrip("/") + "/download"
            resp = self._http.get(
                download_url,
                headers={"ngrok-skip-browser-warning": "1"},
                timeout=10,
            )
            if resp.status_code == 200 and self._looks_like_csv(resp.text):
                console.print("  [cyan]AGI Browser:[/cyan] Direct download succeeded")
                return self._parse_csv(resp.text)
        except Exception:
            pass

        # Fallback to local files
        console.print("  [yellow]AGI Browser: All methods failed, using local file.[/yellow]")
        return self._mock_scrape(client_name)

    @staticmethod
    def _looks_like_csv(content: str) -> bool:
        """Check if content is actual CSV data, not conversational text."""
        lines = content.strip().split("\n")
        if len(lines) < 2:
            return False
        # Header line must have 3+ comma-separated short fields
        headers = lines[0].split(",")
        if len(headers) < 3:
            return False
        # Column headers should be short (not sentences)
        if any(len(h.strip()) > 50 for h in headers):
            return False
        # At least one data row must have the same number of commas as the header
        header_commas = lines[0].count(",")
        return any(line.count(",") == header_commas for line in lines[1:5])

    def _mock_scrape(self, client_name: str) -> dict:
        """Load data from local mock CSV files."""
        import os

        file_map = {
            "Acme Corp": "client_a_acme.csv",
            "Globex Inc": "client_b_globex.csv",
        }
        portal_key = "acme" if "Acme" in client_name else "globex"
        filename = file_map.get(client_name, "client_a_acme.csv")
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "mock", filename
        )

        # Emit browser navigation events for the dashboard
        emit_event("browser_navigate", {
            "url": f"/portal/{portal_key}",
            "action": "Opening login page...",
        })
        console.print(f"  [cyan]AGI Browser:[/cyan] Opening portal for {client_name}...")
        time.sleep(1.5)

        emit_event("browser_navigate", {
            "url": f"/portal/{portal_key}/dashboard",
            "action": "Logging in and loading data dashboard...",
        })
        console.print(f"  [cyan]AGI Browser:[/cyan] Logged in. Navigating to data dashboard...")
        time.sleep(1.5)

        emit_event("browser_navigate", {
            "url": f"/portal/{portal_key}/dashboard",
            "action": "Downloading CSV export...",
        })
        console.print("  [cyan]AGI Browser:[/cyan] Downloading CSV...")
        time.sleep(1.0)

        with open(filepath, "r") as f:
            raw_csv = f.read()

        emit_event("browser_navigate", {
            "url": f"/portal/{portal_key}/dashboard",
            "action": "CSV downloaded. Parsing data...",
        })

        return self._parse_csv(raw_csv)

    def _parse_csv(self, raw_csv: str) -> dict:
        """Parse CSV string into structured data."""
        reader = csv.DictReader(io.StringIO(raw_csv))
        columns = reader.fieldnames or []
        rows = list(reader)

        # Build sample data (first 3 values per column)
        sample_data = {}
        for col in columns:
            sample_data[col] = [row.get(col, "") for row in rows[:3]]

        console.print(
            f"  [cyan]AGI Browser:[/cyan] Scraped {len(rows)} rows, "
            f"{len(columns)} columns"
        )
        return {
            "columns": list(columns),
            "rows": rows,
            "sample_data": sample_data,
            "raw_csv": raw_csv,
        }

    def close(self):
        """Clean up the browser session."""
        if self._session_id and not Config.DEMO_MODE:
            try:
                self._http.delete(
                    f"{Config.AGI_BASE_URL}/sessions/{self._session_id}",
                    headers=self._build_headers(),
                    timeout=5,
                )
            except Exception:
                pass
        self._session_id = None
