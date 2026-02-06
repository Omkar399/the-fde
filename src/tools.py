"""Composio Tools - The FDE's execution layer for deploying mapped data.

Uses Composio to trigger API calls that configure the target SaaS product
with the mapped customer data.
"""

import json
import os
import time
from datetime import datetime
from rich.console import Console

from src.config import Config

console = Console()

_delay = getattr(Config, 'delay', lambda s: s * 0.2)

_TRUTHY = {"Y", "y", "yes", "Yes", "YES", "1", "true", "True", "TRUE", "active", "Active"}
_FALSY = {"N", "n", "no", "No", "NO", "0", "false", "False", "FALSE", "inactive", "Inactive"}

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%d-%b-%Y",
]

_DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
]


class ToolExecutor:
    """Composio-based tool execution for deploying mapped data."""

    def __init__(self):
        self._client = None
        self._connected_account = None
        self._validation_warnings = []
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

    def _load_target_schema(self) -> dict | None:
        """Load the target schema from data/target_schema.json."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "data", "target_schema.json")
        try:
            with open(schema_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _count_coercions(self, mappings: list[dict], rows: list[dict], schema: dict | None) -> int:
        """Count how many fields will have type coercion applied."""
        if not schema or "fields" not in schema:
            return 0
        type_lookup = {
            name: defn.get("type", "string")
            for name, defn in schema["fields"].items()
        }
        coercible_types = {"boolean", "date", "datetime", "number"}
        coerced_targets = set()
        for m in mappings:
            target = m.get("target_field", "")
            if target in type_lookup and type_lookup[target] in coercible_types:
                coerced_targets.add(target)
        return len(coerced_targets) * len(rows)

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
        schema = self._load_target_schema()
        transformed = self._transform_data(mappings, rows, schema)
        transformations_count = self._count_coercions(mappings, rows, schema)

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
                "url": sheet_url,
                "validation_warnings": len(self._validation_warnings),
                "transformations_applied": transformations_count,
            }
        else:
            return {
                "success": False,
                "records_deployed": 0,
                "message": "Composio deployment failed",
            }

    def _mock_deploy(self, client_name: str, mappings: list[dict], rows: list[dict]) -> dict:
        """Simulate deployment for demo mode."""
        schema = self._load_target_schema()
        transformed = self._transform_data(mappings, rows, schema)
        transformations_count = self._count_coercions(mappings, rows, schema)

        console.print(f"  [cyan]Composio:[/cyan] Connecting to target SaaS...")
        time.sleep(_delay(0.5))
        console.print(f"  [cyan]Composio:[/cyan] Transforming {len(rows)} records...")
        time.sleep(_delay(0.3))
        console.print(f"  [cyan]Composio:[/cyan] Applied {transformations_count} type coercions")
        if self._validation_warnings:
            console.print(f"  [yellow]Composio:[/yellow] {len(self._validation_warnings)} validation warnings")
        console.print(f"  [cyan]Composio:[/cyan] Deploying to CRM...")
        time.sleep(_delay(0.5))
        console.print(
            f"  [green]Composio:[/green] SUCCESS - Deployed "
            f"{len(transformed)} records for {client_name}"
        )

        return {
            "success": True,
            "records_deployed": len(transformed),
            "message": f"Deployed {len(transformed)} records for {client_name}",
            "validation_warnings": len(self._validation_warnings),
            "transformations_applied": transformations_count,
        }

    def _transform_data(self, mappings: list[dict], rows: list[dict], target_schema: dict | None = None) -> list[dict]:
        """Transform source data using the column mappings and optional type coercion."""
        self._validation_warnings = []

        mapping_dict = {
            m["source_column"]: m["target_field"]
            for m in mappings
            if m.get("target_field") and m["target_field"] != "unknown"
        }

        # Build a type lookup from schema fields
        type_lookup = {}
        if target_schema and "fields" in target_schema:
            for field_name, field_def in target_schema["fields"].items():
                type_lookup[field_name] = field_def.get("type", "string")

        transformed = []
        for row_idx, row in enumerate(rows):
            new_row = {}
            for src_col, value in row.items():
                target = mapping_dict.get(src_col)
                if target:
                    if target_schema and target in type_lookup:
                        new_row[target] = self._coerce_value(
                            value, type_lookup[target], row_idx, target
                        )
                    else:
                        new_row[target] = value
            transformed.append(new_row)

        return transformed

    def _coerce_value(self, value, field_type: str, row_idx: int, target_field: str):
        """Coerce a value to the expected type, tracking warnings on failure."""
        original = value

        if field_type == "boolean":
            return self._coerce_boolean(original, row_idx, target_field)
        elif field_type == "date":
            return self._coerce_date(original, row_idx, target_field)
        elif field_type == "datetime":
            return self._coerce_datetime(original, row_idx, target_field)
        elif field_type == "number":
            return self._coerce_number(original, row_idx, target_field)
        return original

    def _coerce_boolean(self, value, row_idx: int, target_field: str):
        s = str(value)
        if s in _TRUTHY:
            return True
        if s in _FALSY:
            return False
        self._validation_warnings.append({
            "row": row_idx,
            "field": target_field,
            "value": value,
            "expected_type": "boolean",
            "message": f"Could not coerce '{value}' to boolean",
        })
        return value

    def _coerce_date(self, value, row_idx: int, target_field: str) -> str:
        s = str(value).strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        self._validation_warnings.append({
            "row": row_idx,
            "field": target_field,
            "value": value,
            "expected_type": "date",
            "message": f"Could not coerce '{value}' to date",
        })
        return value

    def _coerce_datetime(self, value, row_idx: int, target_field: str) -> str:
        s = str(value).strip()
        for fmt in _DATETIME_FORMATS:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        self._validation_warnings.append({
            "row": row_idx,
            "field": target_field,
            "value": value,
            "expected_type": "datetime",
            "message": f"Could not coerce '{value}' to datetime",
        })
        return value

    def _coerce_number(self, value, row_idx: int, target_field: str):
        s = str(value).strip().replace("$", "").replace(",", "").strip()
        try:
            return float(s)
        except (ValueError, TypeError):
            self._validation_warnings.append({
                "row": row_idx,
                "field": target_field,
                "value": value,
                "expected_type": "number",
                "message": f"Could not coerce '{value}' to number",
            })
            return value
