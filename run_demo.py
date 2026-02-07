#!/usr/bin/env python3
"""The FDE Demo Runner - Demonstrates continual learning in action.

Usage:
    python run_demo.py              # Run full demo
    python run_demo.py --reset      # Reset memory and run fresh
    python run_demo.py --demo-mode  # Force demo mode (no API keys needed)
    python run_demo.py --auto       # Auto-pacing mode (no user input needed)
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

from src.config import Config
from server.events import emit_event, reset as reset_events

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


def run_demo(reset: bool = False, auto: bool = False):
    from src.agent import FDEAgent
    agent = FDEAgent()

    if reset:
        console.print("[yellow]Resetting agent memory for fresh demo...[/yellow]")
        agent.reset_memory()
        reset_events()
        emit_event("reset", {})
        time.sleep(0.5)

    def wait_or_auto(message: str):
        """Either wait for user input or auto-advance."""
        if auto:
            console.print(f"[dim]{message} (auto-advancing in 2s...)[/dim]")
            time.sleep(2)
        else:
            input(message)

    portal_base = Config.WEBHOOK_BASE_URL.rstrip("/")

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
    wait_or_auto("Press Enter to start onboarding Client A (Acme Corp)...")

    emit_event("phase_start", {"phase": 1, "client": "Acme Corp"})
    summary_a = agent.onboard_client("Acme Corp", f"{portal_base}/portal/acme")
    emit_event("phase_complete", {"phase": 1, "client": "Acme Corp"})

    # Show memory
    _show_memory(agent)

    # ============================================================
    # PHASE 2: THE INTERMEDIATE (Day 2 - Client B)
    # ============================================================
    console.print()
    console.print(Panel(
        "[bold]PHASE 2: THE INTERMEDIATE[/bold]\n"
        "Day 2 - The agent has learned from Client A.\n"
        "Watch: it will recognize similar columns with fewer human calls!",
        title="Demo Phase 2",
        border_style="cyan",
    ))
    console.print()
    wait_or_auto("Press Enter to start onboarding Client B (Globex Inc)...")

    emit_event("phase_start", {"phase": 2, "client": "Globex Inc"})
    summary_b = agent.onboard_client("Globex Inc", f"{portal_base}/portal/globex")
    emit_event("phase_complete", {"phase": 2, "client": "Globex Inc"})

    _show_memory(agent)

    # ============================================================
    # PHASE 3: THE EXPERT (Day 3 - Client C)
    # ============================================================
    console.print()
    console.print(Panel(
        "[bold]PHASE 3: THE EXPERT[/bold]\n"
        "Day 3 - The agent is now experienced with diverse schemas.\n"
        "Watch: it handles a completely different naming convention autonomously!",
        title="Demo Phase 3",
        border_style="green",
    ))
    console.print()
    wait_or_auto("Press Enter to start onboarding Client C (Initech Ltd)...")

    emit_event("phase_start", {"phase": 3, "client": "Initech Ltd"})
    summary_c = agent.onboard_client("Initech Ltd", f"{portal_base}/portal/initech")
    emit_event("phase_complete", {"phase": 3, "client": "Initech Ltd"})

    # ============================================================
    # FINAL 3-WAY COMPARISON
    # ============================================================
    console.print()
    comparison = Table(title="Learning Curve: Novice \u2192 Intermediate \u2192 Expert", show_lines=True)
    comparison.add_column("Metric", style="bold")
    comparison.add_column("Client A\n(Novice)", justify="center", style="yellow")
    comparison.add_column("Client B\n(Intermediate)", justify="center", style="cyan")
    comparison.add_column("Client C\n(Expert)", justify="center", style="green")

    for label, key in [
        ("Total Columns", "total_columns"),
        ("From Memory", "from_memory"),
        ("AI Auto-Mapped", "auto_mapped"),
        ("Human Calls", "human_confirmed"),
        ("New Learnings", "new_learnings"),
    ]:
        comparison.add_row(
            label,
            str(summary_a[key]),
            str(summary_b[key]),
            str(summary_c[key]),
        )
    comparison.add_row(
        "Deployed",
        "[green]Yes[/green]" if summary_a["deployed"] else "[red]No[/red]",
        "[green]Yes[/green]" if summary_b["deployed"] else "[red]No[/red]",
        "[green]Yes[/green]" if summary_c["deployed"] else "[red]No[/red]",
    )
    console.print(comparison)

    # Final message
    console.print()
    console.print(Panel(
        "[bold green]The FDE demonstrated continual learning across 3 clients![/bold green]\n\n"
        f"Memory grew from 0 \u2192 [cyan]{agent.memory.count}[/cyan] learned mappings.\n"
        f"Human calls: [yellow]{summary_a['human_confirmed']}[/yellow] \u2192 "
        f"[cyan]{summary_b['human_confirmed']}[/cyan] \u2192 "
        f"[green]{summary_c['human_confirmed']}[/green]\n\n"
        "[bold]This is Continual Learning in action.[/bold]",
        title="Demo Complete",
        border_style="bold green",
    ))

    emit_event("demo_complete", {
        "summaries": {"1": summary_a, "2": summary_b, "3": summary_c},
        "memory_size": agent.memory.count,
        "learning_curve": [
            {"client": "Acme Corp", "phase": 1, "human_calls": summary_a["human_confirmed"], "memory_hits": summary_a["from_memory"]},
            {"client": "Globex Inc", "phase": 2, "human_calls": summary_b["human_confirmed"], "memory_hits": summary_b["from_memory"]},
            {"client": "Initech Ltd", "phase": 3, "human_calls": summary_c["human_confirmed"], "memory_hits": summary_c["from_memory"]},
        ],
    })

    agent.browser.close()


def _show_memory(agent):
    """Display current memory contents."""
    console.print()
    console.print("[bold yellow]Current Memory:[/bold yellow]")
    all_mappings = agent.memory.get_all_mappings()
    table = Table(title=f"Vector Memory ({len(all_mappings)} mappings)")
    table.add_column("Source Column", style="cyan")
    table.add_column("Target Field", style="green")
    table.add_column("Learned From", style="dim")
    for m in all_mappings:
        table.add_row(m["source_column"], m["target_field"], m["client_name"])
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="The FDE Demo")
    parser.add_argument("--reset", action="store_true", help="Reset memory before demo")
    parser.add_argument("--demo-mode", action="store_true", help="Force demo mode (no API keys)")
    parser.add_argument("--auto", action="store_true", help="Auto-pacing mode (no user input needed)")
    args = parser.parse_args()

    if args.demo_mode:
        os.environ["DEMO_MODE"] = "true"

    print_banner()
    run_demo(reset=args.reset, auto=args.auto)


if __name__ == "__main__":
    main()
