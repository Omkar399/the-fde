"""You.com Research Module - Context loading for improved data mapping.

Queries You.com Search API to find domain-specific context that helps
the agent make better guesses about ambiguous column names.
"""

import requests
from rich.console import Console

from src.config import Config

console = Console()


class ResearchEngine:
    """Searches You.com for domain context to improve mapping accuracy."""

    def __init__(self):
        self._cache: dict[str, str] = {}

    def search(self, query: str) -> str:
        """Search You.com for context. Returns concatenated snippet text."""
        if query in self._cache:
            console.print(f"  [dim]Research cache hit: {query[:50]}...[/dim]")
            return self._cache[query]

        if Config.DEMO_MODE:
            return self._mock_search(query)

        try:
            response = requests.get(
                Config.YOU_SEARCH_URL,
                headers={"X-API-Key": Config.YOU_API_KEY, "Accept": "application/json"},
                params={"query": query, "language": "EN"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            snippets = []
            for result in data.get("results", {}).get("web", []):
                snippets.extend(result.get("snippets", []))

            context = "\n".join(snippets[:5])  # Top 5 snippets
            self._cache[query] = context
            console.print(f"  [blue]You.com:[/blue] Found {len(snippets)} context snippets")
            return context

        except Exception as e:
            console.print(f"  [yellow]You.com search failed: {e}[/yellow]")
            return ""

    def get_column_context(self, column_name: str, domain: str = "CRM") -> str:
        """Get context for a specific column name mapping."""
        query = f"What does the column '{column_name}' typically mean in {domain} data? Standard field name mapping."
        return self.search(query)

    def get_domain_context(self, domain_description: str) -> str:
        """Get general domain context for better mapping."""
        query = f"Standard data schema and field names for {domain_description}"
        return self.search(query)

    def _mock_search(self, query: str) -> str:
        """Return mock search results for demo mode."""
        mock_responses = {
            "cust_lvl": "Customer level typically refers to the subscription tier or membership grade in CRM systems. Common mappings: tier, level, grade, plan.",
            "signup": "Signup date refers to when a customer first registered. Standard field: signup_date, registration_date, created_at.",
            "dob": "DOB is a common abbreviation for Date of Birth. Standard field: date_of_birth, birth_date.",
            "acct_bal": "Account balance represents the current monetary balance. Standard field: account_balance, balance.",
            "flg": "FLG or flag typically represents a boolean indicator. Common: is_active, active_flag, status.",
        }
        for key, response in mock_responses.items():
            if key in query.lower():
                self._cache[query] = response
                return response
        default = "This column name follows common CRM data conventions."
        self._cache[query] = default
        return default
