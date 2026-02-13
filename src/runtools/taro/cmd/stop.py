from typing import List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.client import TargetNotFoundError
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cli, cliutil
from runtools.taro.view.instance import JOB_ID, RUN_ID, EXEC_TIME, CREATED, PHASES, STATUS

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def stop(
        instance_patterns: List[str] = typer.Argument(
            metavar="PATTERN",
            help="Instance ID patterns to match for stopping"
        ),
        env: str = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Skip confirmation prompt and force stop all matching instances"
        ),
):
    """Stop running job instances"""
    total_stopped = 0

    with connector.connect(env) as conn:
        for pattern in instance_patterns:
            instances = conn.get_instances(JobRunCriteria.parse(pattern, MatchingStrategy.FN_MATCH))

            if not instances:
                console.print(f"\n[yellow]⚠[/] No instances found for pattern: [white]{pattern}[/]")
                continue

            console.print(f"\n[dim]Pattern [/][white]{pattern}[/][dim] matches:[/]")

            if not force:
                printer.print_table(
                    [i.to_run() for i in instances],
                    [JOB_ID, RUN_ID, CREATED, EXEC_TIME, PHASES, STATUS],
                    show_header=True, pager=False
                )

                if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                    console.print("[dim]Skipped[/]")
                    continue

            for instance in instances:
                try:
                    instance.stop()
                    total_stopped += 1
                    console.print(f"  [green]✓[/] Stopped {instance.id}")
                except TargetNotFoundError:
                    console.print(f"  [yellow]⚠[/] Instance {instance.id} no longer available (job may have already stopped)")

        style = "bold" if total_stopped else "yellow"
        console.print(f"\n[{style}]Total stopped: {total_stopped}[/]")
