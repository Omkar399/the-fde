"""AGI Inc Browser Automation - The FDE's hands for interacting with web portals.

Uses the AGI Inc API to create browser sessions that can navigate to
client portals, log in, and scrape data. Falls back to local files
when the API is unavailable.
"""

import csv
import io
import time
import requests
from rich.console import Console

from src.config import Config
from server.events import emit_event

console = Console()


class BrowserAgent:
    """AGI Inc browser automation for scraping client portals."""

    def __init__(self):
        self._session_id = None

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

    def _agi_scrape(self, client_name: str, portal_url: str, credentials: dict | None = None) -> dict:
        """Use AGI Inc API to scrape data from a portal."""
        headers = {
            "Authorization": f"Bearer {Config.AGI_API_KEY}",
            "Content-Type": "application/json",
        }

        # Step 1: Create a browser session
        emit_event("browser_navigate", {"url": portal_url, "action": "Creating AGI browser session..."})
        console.print("  [cyan]AGI Browser:[/cyan] Creating session...")
        resp = requests.post(
            f"{Config.AGI_BASE_URL}/sessions",
            headers=headers,
            json={"agent_name": "agi-0"},
            timeout=30,
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

        # Step 2: Send task to navigate and scrape
        cred_user = (credentials or {}).get("username", "admin")
        cred_pass = (credentials or {}).get("password", "admin123")
        task_message = (
            f"Navigate to {portal_url}. "
            f"This is a legacy enterprise portal. Log in with the pre-filled credentials "
            f"(username: {cred_user}, password: {cred_pass}), then navigate to the data dashboard "
            f"and download the customer data CSV file for {client_name}. "
            f"Return the CSV content."
        )
        emit_event("browser_navigate", {"url": portal_url, "action": "Navigating to portal and scraping data..."})
        console.print(f"  [cyan]AGI Browser:[/cyan] Navigating to {portal_url}...")
        requests.post(
            f"{Config.AGI_BASE_URL}/sessions/{self._session_id}/message",
            headers=headers,
            json={"message": task_message},
            timeout=30,
        )

        # Step 3: Poll for results
        csv_content = self._poll_for_result(headers)
        if csv_content:
            return self._parse_csv(csv_content)

        # Fallback: try direct download endpoint
        console.print("  [yellow]AGI Browser: Polling timeout, trying direct download...[/yellow]")
        try:
            download_url = portal_url.rstrip("/") + "/download"
            resp = requests.get(download_url, timeout=10)
            if resp.status_code == 200 and self._looks_like_csv(resp.text):
                console.print("  [cyan]AGI Browser:[/cyan] Direct download succeeded")
                return self._parse_csv(resp.text)
        except Exception:
            pass

        # Fallback to local
        console.print("  [yellow]AGI Browser: No CSV in response, using local file.[/yellow]")
        return self._mock_scrape(client_name)

    def _poll_for_result(self, headers: dict, max_polls: int = 30) -> str | None:
        """Poll AGI session for task completion."""
        after_id = 0
        for _ in range(max_polls):
            time.sleep(2)
            resp = requests.get(
                f"{Config.AGI_BASE_URL}/sessions/{self._session_id}/messages",
                headers=headers,
                params={"after_id": after_id, "sanitize": "true"},
                timeout=10,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            messages = data.get("messages", [])
            for msg in messages:
                after_id = max(after_id, msg.get("id", 0))
                content = msg.get("content", "")
                if self._looks_like_csv(content):
                    return content

            status = data.get("status", "")
            if status in ("finished", "error", "waiting_for_input"):
                break

        return None

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
            "url": f"/portal/{portal_key}/download",
            "action": "Downloading CSV export...",
        })
        console.print("  [cyan]AGI Browser:[/cyan] Downloading CSV...")
        time.sleep(1.0)

        with open(filepath, "r") as f:
            raw_csv = f.read()

        emit_event("browser_navigate", {
            "url": "",
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
                requests.delete(
                    f"{Config.AGI_BASE_URL}/sessions/{self._session_id}",
                    headers={"Authorization": f"Bearer {Config.AGI_API_KEY}"},
                    timeout=5,
                )
            except Exception:
                pass
        self._session_id = None
