"""The FDE Agent - Main orchestrator for the continual learning pipeline.

Coordinates all components:
1. Browser (AGI Inc) -> scrapes client data
2. Brain (Gemini) + Research (You.com) -> analyzes with confidence
3. Memory (ChromaDB) -> recalls previous learnings
4. Teacher (Plivo) -> asks human when uncertain
5. Tools (Composio) -> deploys mapped data
"""

import json
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.memory import MemoryStore
from src.brain import Brain
from src.research import ResearchEngine
from src.browser import BrowserAgent
from src.teacher import Teacher
from src.tools import ToolExecutor
from server.events import emit_event

console = Console()


class FDEAgent:
    """The Forward Deployed Engineer - a continual learning agent."""

    def __init__(self, target_schema: dict | None = None):
        self.memory = MemoryStore()
        self.research = ResearchEngine()
        self.brain = Brain(self.memory, self.research)
        self.browser = BrowserAgent()
        self.teacher = Teacher()
        self.tools = ToolExecutor()

        if target_schema is not None:
            self.target_schema = target_schema
        else:
            # Load target schema from disk
            schema_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "target_schema.json"
            )
            with open(schema_path) as f:
                self.target_schema = json.load(f)

    def onboard_client(self, client_name: str, portal_url: str, credentials: dict | None = None) -> dict:
        """Run the full onboarding pipeline for a client.

        Args:
            client_name: Display name of the client.
            portal_url: URL of the client portal.
            credentials: Optional dict with "username" and "password" keys.

        Returns a summary of what happened.
        """
        console.print()
        console.print(Panel(
            f"[bold]Onboarding: {client_name}[/bold]\n"
            f"Portal: {portal_url}",
            title="The FDE",
            border_style="blue",
        ))

        summary = {
            "client": client_name,
            "portal_url": portal_url,
            "total_columns": 0,
            "from_memory": 0,
            "auto_mapped": 0,
            "human_confirmed": 0,
            "phone_calls": 0,
            "new_learnings": 0,
            "deployed": False,
            "sheet_url": "",
        }

        # === Step 1: Scrape Data ===
        emit_event("step_start", {"step": "scrape", "message": f"Scraping data from {client_name} portal"})
        console.print("\n[bold cyan]Step 1: Fetching Client Data (AGI Inc Browser)[/bold cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Opening browser and scraping data...", total=None)
            data = self.browser.scrape_client_data(client_name, portal_url, credentials)

        columns = data["columns"]
        sample_data = data["sample_data"]
        rows = data["rows"]
        summary["total_columns"] = len(columns)
        emit_event("step_complete", {"step": "scrape", "message": f"Scraped {len(rows)} rows, {len(columns)} columns"})

        # === Step 2: Analyze Columns ===
        emit_event("step_start", {"step": "analyze", "message": f"Analyzing {len(columns)} columns with Gemini + You.com + Memory"})
        console.print("\n[bold cyan]Step 2: Analyzing Columns (Gemini + You.com + Memory)[/bold cyan]")
        mappings = self.brain.analyze_columns(columns, sample_data, self.target_schema)

        # Categorize results
        confident = []
        uncertain = []
        for m in mappings:
            if m.get("from_memory"):
                confident.append(m)
                summary["from_memory"] += 1
            elif m["confidence"] == "high":
                confident.append(m)
                summary["auto_mapped"] += 1
            elif m["confidence"] == "medium":
                confident.append(m)
                summary["auto_mapped"] += 1
            else:
                uncertain.append(m)

        # Emit individual mapping results for dashboard
        for m in mappings:
            if m.get("from_memory"):
                emit_event("memory_recall", {
                    "source": m["source_column"],
                    "target": m["target_field"],
                })
            emit_event("mapping_result", {
                "source": m["source_column"],
                "target": m["target_field"],
                "confidence": m["confidence"],
                "from_memory": m.get("from_memory", False),
            })
        emit_event("step_complete", {"step": "analyze", "message": f"Mapped {len(mappings)} columns"})

        # Display mapping table
        self._display_mappings(mappings)

        # === Step 3: Handle Uncertain Mappings ===
        # For the first client (Novice phase: no prior memory), always verify at
        # least one field with a phone call so the demo shows the human-in-the-loop.
        is_novice = summary["from_memory"] == 0

        if not uncertain and is_novice and confident:
            # No uncertain fields but this is the first client — demote the
            # least-obvious non-memory mapping to uncertain so we make 1 call.
            # Prefer fields that weren't from memory; pick the last one added.
            demote = None
            for m in reversed(confident):
                if not m.get("from_memory"):
                    demote = m
                    break
            if demote:
                confident.remove(demote)
                summary["auto_mapped"] -= 1
                demote["confidence"] = "low"
                uncertain.append(demote)

        # Only call for the single most uncertain field; auto-accept the rest
        if uncertain:
            call_target = uncertain[0]
            auto_accepted = uncertain[1:]
            for m in auto_accepted:
                m["confidence"] = "medium"
                confident.append(m)
                summary["auto_mapped"] += 1

            emit_event("step_start", {"step": "call", "message": f"Calling human for 1 uncertain column (auto-accepted {len(auto_accepted)} others)"})
            console.print(
                f"\n[bold cyan]Step 3: Asking Human (1 uncertain column) "
                f"(Plivo Voice)[/bold cyan]"
            )
            summary["phone_calls"] += 1
            emit_event("phone_call", {"column": call_target["source_column"], "mapping": call_target["target_field"]})
            human_result = self.teacher.ask_human(
                call_target["source_column"], call_target["target_field"]
            )
            emit_event("phone_response", {
                "column": call_target["source_column"],
                "mapping": call_target["target_field"],
                "confirmed": human_result["confirmed"],
            })
            if human_result["confirmed"]:
                call_target["confidence"] = "high"
                call_target["reasoning"] = f"Human confirmed via {human_result['method']}"
                confident.append(call_target)
                summary["human_confirmed"] += 1
            else:
                console.print(
                    f"  [yellow]Skipping '{call_target['source_column']}' "
                    f"(human rejected mapping)[/yellow]"
                )
            emit_event("step_complete", {"step": "call", "message": f"Human confirmed {summary['human_confirmed']} mappings"})
        else:
            emit_event("step_start", {"step": "call", "message": "No uncertain columns — skipping phone calls"})
            console.print(
                "\n[bold cyan]Step 3: No uncertain columns! "
                "[green]All mapped from memory/AI.[/green][/bold cyan]"
            )
            emit_event("step_complete", {"step": "call", "message": "No phone calls needed!"})

        # === Step 4: Store New Learnings ===
        emit_event("step_start", {"step": "learn", "message": "Storing new mappings in vector memory"})
        console.print("\n[bold cyan]Step 4: Updating Memory (Continual Learning)[/bold cyan]")
        new_learnings = 0
        for m in confident:
            if not m.get("from_memory"):
                self.memory.store_mapping(
                    m["source_column"], m["target_field"], client_name
                )
                new_learnings += 1
                emit_event("memory_store", {
                    "source": m["source_column"],
                    "target": m["target_field"],
                    "client": client_name,
                })
        summary["new_learnings"] = new_learnings
        emit_event("memory_update", {"count": new_learnings, "total": self.memory.count})

        if new_learnings == 0:
            console.print("  [dim]No new learnings needed (all from memory).[/dim]")
        else:
            console.print(
                f"  [green]Stored {new_learnings} new mappings in vector memory.[/green]"
            )
        emit_event("step_complete", {"step": "learn", "message": f"Stored {new_learnings} new mappings"})

        # === Step 5: Deploy ===
        emit_event("step_start", {"step": "deploy", "message": f"Deploying {len(confident)} mappings via Composio"})
        console.print("\n[bold cyan]Step 5: Deploying Mapped Data (Composio)[/bold cyan]")
        deploy_result = self.tools.deploy_mapping(client_name, confident, rows)
        summary["deployed"] = deploy_result["success"]
        summary["sheet_url"] = deploy_result.get("url", "")
        summary["records_deployed"] = deploy_result.get("records_deployed", 0)
        emit_event("deploy_complete", {
            "records": deploy_result.get("records_deployed", 0),
            "target": "Google Sheets",
            "url": deploy_result.get("url", ""),
        })
        emit_event("step_complete", {"step": "deploy", "message": f"Deployed {deploy_result.get('records_deployed', 0)} records"})

        # === Summary ===
        self._display_summary(summary)

        return summary

    def _display_mappings(self, mappings: list[dict]) -> None:
        """Display a rich table of column mappings."""
        table = Table(title="Column Mapping Results", show_lines=True)
        table.add_column("Source Column", style="cyan")
        table.add_column("Target Field", style="green")
        table.add_column("Confidence", justify="center")
        table.add_column("Source", style="dim")

        for m in mappings:
            conf = m["confidence"]
            if conf == "high":
                conf_style = "[bold green]HIGH[/bold green]"
            elif conf == "medium":
                conf_style = "[yellow]MEDIUM[/yellow]"
            else:
                conf_style = "[bold red]LOW[/bold red]"

            source = "Memory" if m.get("from_memory") else "Gemini AI"
            table.add_row(
                m["source_column"],
                m["target_field"],
                conf_style,
                source,
            )

        console.print()
        console.print(table)

    def _display_summary(self, summary: dict) -> None:
        """Display the final onboarding summary."""
        console.print()
        panel_text = (
            f"[bold]Client:[/bold] {summary['client']}\n"
            f"[bold]Total Columns:[/bold] {summary['total_columns']}\n"
            f"[bold]From Memory:[/bold] [green]{summary['from_memory']}[/green]\n"
            f"[bold]Auto-Mapped (AI):[/bold] [blue]{summary['auto_mapped']}[/blue]\n"
            f"[bold]Human Confirmed:[/bold] [magenta]{summary['human_confirmed']}[/magenta]\n"
            f"[bold]New Learnings:[/bold] [cyan]{summary['new_learnings']}[/cyan]\n"
            f"[bold]Deployed:[/bold] {'[green]YES[/green]' if summary['deployed'] else '[red]NO[/red]'}\n"
            f"[bold]Memory Size:[/bold] {self.memory.count} total mappings"
        )
        console.print(Panel(
            panel_text,
            title="Onboarding Complete",
            border_style="green" if summary["deployed"] else "red",
        ))

    def reset_memory(self) -> None:
        """Reset all learned memory (for demo restart)."""
        self.memory.clear()
        console.print("[yellow]Agent memory has been reset.[/yellow]")
