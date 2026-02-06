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

from src.config import Config
from src.memory import MemoryStore
from src.brain import Brain
from src.research import ResearchEngine
from src.browser import BrowserAgent
from src.teacher import Teacher
from src.tools import ToolExecutor

console = Console()


class FDEAgent:
    """The Forward Deployed Engineer - a continual learning agent."""

    def __init__(self):
        self.memory = MemoryStore()
        self.research = ResearchEngine()
        self.brain = Brain(self.memory, self.research)
        self.browser = BrowserAgent()
        self.teacher = Teacher()
        self.tools = ToolExecutor()

        # Load target schema
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "target_schema.json"
        )
        with open(schema_path) as f:
            self.target_schema = json.load(f)

    def onboard_client(self, client_name: str, portal_url: str) -> dict:
        """Run the full onboarding pipeline for a client.

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
            "total_columns": 0,
            "from_memory": 0,
            "auto_mapped": 0,
            "human_confirmed": 0,
            "new_learnings": 0,
            "deployed": False,
        }

        # === Step 1: Scrape Data ===
        console.print("\n[bold cyan]Step 1: Fetching Client Data (AGI Inc Browser)[/bold cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Opening browser and scraping data...", total=None)
            data = self.browser.scrape_client_data(client_name, portal_url)

        columns = data["columns"]
        sample_data = data["sample_data"]
        rows = data["rows"]
        summary["total_columns"] = len(columns)

        # === Step 2: Analyze Columns ===
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

        # Display mapping table
        self._display_mappings(mappings)

        # === Step 3: Handle Uncertain Mappings ===
        if uncertain:
            console.print(
                f"\n[bold cyan]Step 3: Asking Human ({len(uncertain)} uncertain columns) "
                f"(Plivo Voice)[/bold cyan]"
            )
            for m in uncertain:
                human_result = self.teacher.ask_human(
                    m["source_column"], m["target_field"]
                )
                if human_result["confirmed"]:
                    m["confidence"] = "high"
                    m["reasoning"] = f"Human confirmed via {human_result['method']}"
                    confident.append(m)
                    summary["human_confirmed"] += 1
                else:
                    console.print(
                        f"  [yellow]Skipping '{m['source_column']}' "
                        f"(human rejected mapping)[/yellow]"
                    )
        else:
            console.print(
                "\n[bold cyan]Step 3: No uncertain columns! "
                "[green]All mapped from memory/AI.[/green][/bold cyan]"
            )

        # === Step 4: Store New Learnings ===
        console.print("\n[bold cyan]Step 4: Updating Memory (Continual Learning)[/bold cyan]")
        new_learnings = 0
        for m in confident:
            if not m.get("from_memory"):
                self.memory.store_mapping(
                    m["source_column"], m["target_field"], client_name
                )
                new_learnings += 1
        summary["new_learnings"] = new_learnings

        if new_learnings == 0:
            console.print("  [dim]No new learnings needed (all from memory).[/dim]")
        else:
            console.print(
                f"  [green]Stored {new_learnings} new mappings in vector memory.[/green]"
            )

        # === Step 5: Deploy ===
        console.print("\n[bold cyan]Step 5: Deploying Mapped Data (Composio)[/bold cyan]")
        deploy_result = self.tools.deploy_mapping(client_name, confident, rows)
        summary["deployed"] = deploy_result["success"]

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
