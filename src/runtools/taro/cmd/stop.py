from typing import Optional, List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.client import TargetNotFoundError
from runtools.taro import printer, cli, cliutil
from runtools.taro.cmd.resolve import resolve_instances
from runtools.taro.view.instance import JOB_ID, RUN_ID, CREATED, EXEC_TIME, PHASES, STATUS

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def stop(
        instance_patterns: Optional[List[str]] = cli.INSTANCE_PATTERNS_OPTIONAL,
        env: str = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Skip confirmation prompt and force stop all matching instances"
        ),
):
    """Stop running job instances"""
    with connector.connect(env) as conn:
        instances = resolve_instances(conn, instance_patterns, select_title="Select instance to stop")

        if not instances:
            console.print("[yellow]No instances found[/]")
            raise typer.Exit()

        if not force:
            printer.print_table(
                [i.snap() for i in instances],
                [JOB_ID, RUN_ID, CREATED, EXEC_TIME, PHASES, STATUS],
                show_header=True, pager=False,
            )
            if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                raise typer.Exit()

        total = 0
        for inst in instances:
            try:
                inst.stop()
                total += 1
                console.print(f"  [green]✓[/] Stopped {inst.id}")
            except TargetNotFoundError:
                console.print(f"  [yellow]⚠[/] Instance {inst.id} no longer available")

        console.print(f"\n[{'bold' if total else 'yellow'}]Total stopped: {total}[/]")
