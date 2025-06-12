from typing import List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli, cliutil, printer
from runtools.taro.view.instance import JOB_ID, RUN_ID, CREATED, PHASES, STATUS

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def approve(
        instance_patterns: List[str] = cli.INSTANCE_PATTERNS,
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID to approve"),
        env: str = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Skip confirmation prompt and approve all matching instances"
        ),
):
    """Approve jobs waiting in pending state"""
    env_config = get_env_config(env)
    total_approved = 0

    with connector.create(env_config) as conn:
        for pattern in instance_patterns:
            instances = conn.get_instances(JobRunCriteria.parse(pattern, MatchingStrategy.FN_MATCH))

            if not instances:
                console.print(f"\n[yellow]⚠[/] No instances found for pattern: [white]{pattern}[/]")
                continue

            approvable = []
            for inst in instances:
                if inst.find_phase_control_by_id(phase):
                    approvable.append(inst)

            if not approvable:
                console.print(
                    f"\n[dim]Pattern [/][white]{pattern}[/][dim] matches {len(instances)} instance(s), but none have phase '{phase}'[/]")
                continue

            console.print(f"\n[dim]Pattern [/][white]{pattern}[/][dim] matches ({len(approvable)} approvable):[/]")

            if not force:
                printer.print_table(
                    [i.snapshot() for i in approvable],
                    [JOB_ID, RUN_ID, CREATED, PHASES, STATUS],
                    show_header=True, pager=False
                )

                if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                    console.print("[dim]Skipped[/]")
                    continue

            for inst in approvable:
                inst.find_phase_control_by_id(phase).approve()
                console.print(f"  [green]✓[/] Approved {inst.id}")
                total_approved += 1

        style = "bold" if total_approved else "yellow"
        console.print(f"\n[{style}]Total approved: {total_approved}[/]")
