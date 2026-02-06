#!/usr/bin/env python3
"""The FDE Demo Runner - Demonstrates continual learning in action.

Usage:
    python run_demo.py              # Run full demo
    python run_demo.py --reset      # Reset memory and run fresh
    python run_demo.py --demo-mode  # Force demo mode (no API keys needed)
"""

import os
import sys
import time
import argparse

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

console = Console()


def print_banner():
    banner = Text()
    banner.append("THE FDE", style="bold cyan")
    banner.append(" - The Continual Learning Forward Deployed Engineer\n", style="dim")
    banner.append("An autonomous agent that learns from every client interaction.\n\n", style="italic")
    banner.append("Sponsor Stack: ", style="bold")
    banner.append("Gemini", style="red")
    banner.append(" | ", style="dim")
    banner.append("AGI Inc", style="blue")
    banner.append(" | ", style="dim")
    banner.append("You.com", style="green")
    banner.append(" | ", style="dim")
    banner.append("Plivo", style="magenta")
    banner.append(" | ", style="dim")
    banner.append("Composio", style="yellow")

    console.print(Panel(
        banner,
        border_style="bold blue",
        padding=(1, 2),
    ))


def run_demo(reset: bool = False):
    from src.agent import FDEAgent

    agent = FDEAgent()

    if reset:
        console.print("[yellow]Resetting agent memory for fresh demo...[/yellow]")
        agent.reset_memory()
        time.sleep(0.5)

    # ============================================================
    # PHASE 1: THE NOVICE (Day 1 - Client A)
    # ============================================================
    console.print()
    console.print(Panel(
        "[bold]PHASE 1: THE NOVICE[/bold]\n"
        "Day 1 - The agent has no prior experience.\n"
        "It must reason from scratch and ask humans for help.",
        title="Demo Phase 1",
        border_style="yellow",
    ))
    console.print()
    input("Press Enter to start onboarding Client A (Acme Corp)...")

    summary_a = agent.onboard_client(
        client_name="Acme Corp",
        portal_url="https://portal.acmecorp.com/data",
    )

    # Show what was learned
    console.print()
    console.print("[bold yellow]What the agent learned from Client A:[/bold yellow]")
    all_mappings = agent.memory.get_all_mappings()
    table = Table(title="Vector Memory Contents")
    table.add_column("Source Column", style="cyan")
    table.add_column("Target Field", style="green")
    table.add_column("Learned From", style="dim")
    for m in all_mappings:
        table.add_row(m["source_column"], m["target_field"], m["client_name"])
    console.print(table)

    # ============================================================
    # PHASE 2: THE EXPERT (Day 2 - Client B)
    # ============================================================
    console.print()
    console.print(Panel(
        "[bold]PHASE 2: THE EXPERT[/bold]\n"
        "Day 2 - The agent now has learned mappings in memory.\n"
        "Watch: it will recognize similar columns WITHOUT calling a human!",
        title="Demo Phase 2",
        border_style="green",
    ))
    console.print()
    input("Press Enter to start onboarding Client B (Globex Inc)...")

    summary_b = agent.onboard_client(
        client_name="Globex Inc",
        portal_url="https://portal.globexinc.com/data",
    )

    # ============================================================
    # FINAL COMPARISON
    # ============================================================
    console.print()
    comparison = Table(title="Learning Comparison: Novice vs Expert", show_lines=True)
    comparison.add_column("Metric", style="bold")
    comparison.add_column("Client A (Novice)", justify="center", style="yellow")
    comparison.add_column("Client B (Expert)", justify="center", style="green")

    comparison.add_row("Total Columns", str(summary_a["total_columns"]), str(summary_b["total_columns"]))
    comparison.add_row("From Memory", str(summary_a["from_memory"]), str(summary_b["from_memory"]))
    comparison.add_row("AI Auto-Mapped", str(summary_a["auto_mapped"]), str(summary_b["auto_mapped"]))
    comparison.add_row("Human Calls Needed", str(summary_a["human_confirmed"]), str(summary_b["human_confirmed"]))
    comparison.add_row("New Learnings", str(summary_a["new_learnings"]), str(summary_b["new_learnings"]))
    comparison.add_row(
        "Deployed",
        "[green]Yes[/green]" if summary_a["deployed"] else "[red]No[/red]",
        "[green]Yes[/green]" if summary_b["deployed"] else "[red]No[/red]",
    )

    console.print(comparison)

    # Final message
    console.print()
    console.print(Panel(
        "[bold green]The FDE learned from Client A and applied that knowledge to Client B![/bold green]\n\n"
        f"Memory grew from 0 to [cyan]{agent.memory.count}[/cyan] learned mappings.\n"
        f"Human calls reduced from [yellow]{summary_a['human_confirmed']}[/yellow] "
        f"to [green]{summary_b['human_confirmed']}[/green].\n\n"
        "[bold]This is Continual Learning in action.[/bold]",
        title="Demo Complete",
        border_style="bold green",
    ))

    # Cleanup
    agent.browser.close()


def main():
    parser = argparse.ArgumentParser(description="The FDE Demo")
    parser.add_argument("--reset", action="store_true", help="Reset memory before demo")
    parser.add_argument("--demo-mode", action="store_true", help="Force demo mode (no API keys)")
    args = parser.parse_args()

    if args.demo_mode:
        os.environ["DEMO_MODE"] = "true"

    print_banner()
    run_demo(reset=args.reset)


if __name__ == "__main__":
    main()
