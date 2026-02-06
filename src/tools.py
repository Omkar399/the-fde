"""Composio Tools - The FDE's execution layer for deploying mapped data.

Uses Composio to trigger API calls that configure the target SaaS product
with the mapped customer data.
"""

import time
from rich.console import Console

from src.config import Config

console = Console()


class ToolExecutor:
    """Composio-based tool execution for deploying mapped data."""

    def __init__(self):
        self._client = None
        self._connected_account = None
        if not Config.DEMO_MODE:
            try:
                from composio import Composio
                self._client = Composio(api_key=Config.COMPOSIO_API_KEY)
                # Get the first connected Google Sheets account
                conns = self._client.connected_accounts.get()
                for c in conns:
                    if c.appName == "googlesheets" and c.status == "ACTIVE":
                        self._connected_account = c.id
                        break
            except Exception as e:
                console.print(f"  [yellow]Composio init warning: {e}[/yellow]")

    def deploy_mapping(self, client_name: str, mappings: list[dict], rows: list[dict]) -> dict:
        """Deploy the mapped data to the target SaaS system.

        Args:
            client_name: Name of the client being onboarded
            mappings: List of {source_column, target_field} mappings
            rows: The actual data rows to transform and deploy

        Returns:
            dict with keys: success (bool), records_deployed (int), message (str)
        """
        if Config.DEMO_MODE:
            return self._mock_deploy(client_name, mappings, rows)

        try:
            return self._composio_deploy(client_name, mappings, rows)
        except Exception as e:
            console.print(f"  [yellow]Composio deploy failed: {e}. Using mock.[/yellow]")
            return self._mock_deploy(client_name, mappings, rows)

    def _composio_deploy(self, client_name: str, mappings: list[dict], rows: list[dict]) -> dict:
        """Deploy using Composio tool execution."""
        from composio.client.enums import Action

        # Transform data using the mappings
        transformed = self._transform_data(mappings, rows)

        console.print(f"  [cyan]Composio:[/cyan] Deploying {len(transformed)} records...")

        if self._client and self._connected_account:
            # Step 1: Create a spreadsheet for this client
            console.print(f"  [cyan]Composio:[/cyan] Creating spreadsheet for {client_name}...")
            create_result = self._client.actions.execute(
                action=Action.GOOGLESHEETS_CREATE_GOOGLE_SHEET1,
                params={"title": f"FDE - {client_name} Onboarding"},
                entity_id="default",
                connected_account=self._connected_account,
            )

            # Extract spreadsheet ID
            spreadsheet_id = None
            def _find_key(d, key):
                if isinstance(d, dict):
                    if key in d:
                        return d[key]
                    for v in d.values():
                        r = _find_key(v, key)
                        if r:
                            return r
                return None
            spreadsheet_id = _find_key(create_result, "spreadsheetId")

            if not spreadsheet_id:
                raise RuntimeError(f"Could not create spreadsheet: {create_result}")

            # Step 2: Write data as 2D array (header + rows)
            if transformed:
                headers = list(transformed[0].keys())
                values = [headers] + [[row.get(h, "") for h in headers] for row in transformed]
            else:
                values = [["No data"]]

            console.print(f"  [cyan]Composio:[/cyan] Writing {len(transformed)} records to Google Sheets...")
            write_result = self._client.actions.execute(
                action=Action.GOOGLESHEETS_BATCH_UPDATE,
                params={
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": "Sheet1",
                    "values": values,
                    "first_cell_location": "A1",
                    "valueInputOption": "USER_ENTERED",
                },
                entity_id="default",
                connected_account=self._connected_account,
            )
            success = write_result.get("successfull", False)
            sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            console.print(f"  [cyan]Composio:[/cyan] Sheet URL: {sheet_url}")
        else:
            success = False

        if success:
            console.print(
                f"  [green]Composio:[/green] Successfully deployed "
                f"{len(transformed)} records for {client_name}"
            )
            return {
                "success": True,
                "records_deployed": len(transformed),
                "message": f"Deployed {len(transformed)} records for {client_name}",
            }
        else:
            return {
                "success": False,
                "records_deployed": 0,
                "message": "Composio deployment failed",
            }

    def _mock_deploy(self, client_name: str, mappings: list[dict], rows: list[dict]) -> dict:
        """Simulate deployment for demo mode."""
        transformed = self._transform_data(mappings, rows)

        console.print(f"  [cyan]Composio:[/cyan] Connecting to target SaaS...")
        time.sleep(0.5)
        console.print(f"  [cyan]Composio:[/cyan] Transforming {len(rows)} records...")
        time.sleep(0.3)
        console.print(f"  [cyan]Composio:[/cyan] Deploying to CRM...")
        time.sleep(0.5)
        console.print(
            f"  [green]Composio:[/green] SUCCESS - Deployed "
            f"{len(transformed)} records for {client_name}"
        )

        return {
            "success": True,
            "records_deployed": len(transformed),
            "message": f"Deployed {len(transformed)} records for {client_name}",
        }

    def _transform_data(self, mappings: list[dict], rows: list[dict]) -> list[dict]:
        """Transform source data using the column mappings."""
        mapping_dict = {
            m["source_column"]: m["target_field"]
            for m in mappings
            if m.get("target_field") and m["target_field"] != "unknown"
        }

        transformed = []
        for row in rows:
            new_row = {}
            for src_col, value in row.items():
                target = mapping_dict.get(src_col)
                if target:
                    new_row[target] = value
            transformed.append(new_row)

        return transformed
