"""Interactive Terminal CLI for NexusOps Enterprise Agent."""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from nexus_ops.core.orchestrator import orchestrator
from nexus_ops.observability.metrics import metrics
from nexus_ops.data.mock_db import db

console = Console()


def print_banner():
    banner_text = r"""[bold cyan]
 _   _                       ____             
| \ | | _____  ___   _ ___  / __ \ _ __  ___ 
|  \| |/ _ \ \/ / | | / __|/ / _` | '_ \/ __|
| |\  |  __/>  <| |_| \__ \ | (_| | |_) \__ \
|_| \_|\___/_/\_\\__,_|___/\ \__,_| .__/|___/
                            \____/|_|        
[/bold cyan]
[dim]Enterprise Operations & Dispute Intelligence Multi-Agent System (Google ADK)[/dim]
"""
    console.print(banner_text)
    console.print("[green]Ready to triage customer issues. Type 'exit' to quit, 'metrics' for dashboard.[/green]\n")


def display_result(result: dict):
    status_color = "green" if result["status"] == "COMPLETED" else "yellow" if "HITL" in result["status"] else "red"
    console.print(Panel(
        f"[bold {status_color}]Status: {result['status']}[/bold {status_color}]\n\n"
        f"[bold white]Resolution Response:[/bold white]\n{result['final_response']}",
        title=f"Run {result['run_id']} | Session: {result['session_id']}",
        border_style=status_color
    ))

    if result.get("actions_taken"):
        table = Table(title="Autonomous Actions & Specialist Trajectory", show_header=True, header_style="bold magenta")
        table.add_column("Step", style="dim", width=6)
        table.add_column("Action", style="cyan")
        table.add_column("Result Summary", style="white")

        for idx, act in enumerate(result["actions_taken"], 1):
            act_name = act.get("action", "unknown")
            res = act.get("result", act.get("reason", ""))
            summary = str(res)[:100] + "..." if len(str(res)) > 100 else str(res)
            table.add_row(str(idx), act_name, summary)

        console.print(table)


def main():
    print_banner()
    session_id = "CLI-SESSION-001"
    user_id = "CUST-001"

    while True:
        try:
            prompt = Prompt.ask(f"[bold blue]{user_id} @ {session_id}[/bold blue]")
            if not prompt or not prompt.strip():
                continue

            cmd = prompt.strip().lower()
            if cmd in {"exit", "quit", "q"}:
                console.print("[dim]Exiting NexusOps CLI. Goodbye![/dim]")
                break
            elif cmd == "metrics":
                summary = metrics.get_summary()
                console.print(Panel(str(summary), title="Runtime Operational Metrics", border_style="cyan"))
                continue
            elif cmd == "reset":
                db.reset()
                metrics.reset()
                console.print("[yellow]Database and metrics reset to initial state.[/yellow]")
                continue

            with console.status("[bold green]TriageCoordinator evaluating and dispatching specialists...[/bold green]"):
                res = orchestrator.process_request(
                    user_prompt=prompt,
                    session_id=session_id,
                    user_id=user_id
                )

            display_result(res)

        except KeyboardInterrupt:
            console.print("\n[dim]Session terminated.[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
