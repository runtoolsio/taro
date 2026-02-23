from typing import Optional, List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import PhaseCriterion, LifecycleCriterion
from runtools.runcore.run import Stage
from runtools.taro import cli, cliutil, printer
from runtools.taro.cmd.resolve import resolve_instances
from runtools.taro.view.instance import JOB_ID, RUN_ID, CREATED, PHASES, STATUS

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def approve(
        instance_patterns: Optional[List[str]] = cli.INSTANCE_PATTERNS_OPTIONAL,
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
    with connector.connect(env) as conn:
        instances = resolve_instances(
            conn, instance_patterns,
            update_criteria=lambda c: (
                c.add(PhaseCriterion(phase_id=phase, lifecycle=LifecycleCriterion(stage=Stage.CREATED))),
                c.add(PhaseCriterion(phase_id=phase, idle=True)),
            ),
            instance_filter=lambda i: i.find_phase_control_by_id(phase),
            select_title="Select instance to approve",
        )

        if not instances:
            console.print("[yellow]No approvable instances found[/]")
            raise typer.Exit()

        if not force:
            printer.print_table(
                [i.snap() for i in instances],
                [JOB_ID, RUN_ID, CREATED, PHASES, STATUS],
                show_header=True, pager=False,
            )
            if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                raise typer.Exit()

        total = 0
        for inst in instances:
            inst.find_phase_control_by_id(phase).approve()
            total += 1
            console.print(f"  [green]✓[/] Approved {inst.id}")

        console.print(f"\n[{'bold' if total else 'yellow'}]Total approved: {total}[/]")
