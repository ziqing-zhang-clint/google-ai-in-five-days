"""Automated Evaluation Runner for CI/CD Quality Gate."""

import sys
import json
import os
import time
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from nexus_ops.core.orchestrator import orchestrator
from nexus_ops.data.mock_db import db
from nexus_ops.observability.metrics import metrics
from evals.eval_judge import eval_judge, EvaluationScore

console = Console()


def load_dataset() -> List[dict]:
    dataset_path = os.path.join(os.path.dirname(__file__), "eval_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_all_evaluations(pass_threshold_percent: float = 90.0) -> bool:
    console.print(Panel("[bold cyan]NexusOps Enterprise Agent - Automated Evaluation Suite[/bold cyan]\n"
                        "[dim]Dual-Track Verification: Deterministic Assertions & LM Trajectory Scoring[/dim]"))

    dataset = load_dataset()
    scores: List[EvaluationScore] = []
    latencies: List[float] = []

    table = Table(title="Golden Benchmark Evaluation Results", show_header=True, header_style="bold blue")
    table.add_column("Test ID", style="bold", width=10)
    table.add_column("Category", style="cyan", width=22)
    table.add_column("Trajectory", justify="right", width=10)
    table.add_column("Grounded", justify="right", width=10)
    table.add_column("Safety", justify="right", width=10)
    table.add_column("Composite", justify="right", width=10)
    table.add_column("Status", justify="center", width=10)

    for case in dataset:
        # Reset DB state for clean isolation between runs
        db.reset()
        test_id = case["id"]

        start_time = time.time()
        output = orchestrator.process_request(
            user_prompt=case["prompt"],
            user_id=case.get("user_id", "CUST-001"),
            session_id=f"EVAL-SESS-{test_id}"
        )
        elapsed_ms = (time.time() - start_time) * 1000.0
        latencies.append(elapsed_ms)

        score = eval_judge.evaluate_run(case, output)
        scores.append(score)

        status_str = "[bold green]PASS[/bold green]" if score.passed else "[bold red]FAIL[/bold red]"
        table.add_row(
            score.test_id,
            score.category[:20],
            f"{score.trajectory_score:.0f}%",
            f"{score.groundedness_score:.0f}%",
            f"{score.safety_score:.0f}%",
            f"{score.composite_score:.1f}",
            status_str
        )

    console.print(table)

    total_tests = len(scores)
    passed_tests = sum(1 for s in scores if s.passed)
    pass_rate = (passed_tests / total_tests) * 100.0 if total_tests > 0 else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

    summary_panel = Panel(
        f"[bold white]Total Evaluated Cases:[/bold white] {total_tests}\n"
        f"[bold white]Passed Cases:[/bold white] [green]{passed_tests}[/green]\n"
        f"[bold white]Failed Cases:[/bold white] [{'red' if (total_tests - passed_tests) > 0 else 'green'}]{total_tests - passed_tests}[/]\n"
        f"[bold white]Benchmark Pass Rate:[/bold white] [{'green' if pass_rate >= pass_threshold_percent else 'red'}]{pass_rate:.1f}%[/] "
        f"(Target: >={pass_threshold_percent}%)\n"
        f"[bold white]Average Execution Latency:[/bold white] {avg_latency:.1f} ms\n"
        f"[bold white]P95 Execution Latency:[/bold white] {p95_latency:.1f} ms",
        title="[bold green]Evaluation Summary[/bold green]",
        border_style="green" if pass_rate >= pass_threshold_percent else "red"
    )
    console.print(summary_panel)

    if pass_rate >= pass_threshold_percent:
        console.print("[bold green]CI/CD Quality Gate Passed! System meets enterprise SLA criteria.[/bold green]")
        return True
    else:
        console.print("[bold red]CI/CD Quality Gate FAILED! Regression threshold breached.[/bold red]")
        return False


def main():
    success = run_all_evaluations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
