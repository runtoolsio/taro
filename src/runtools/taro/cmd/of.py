from typing import Optional, List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import JobRun
from runtools.taro import cli

app = typer.Typer(name="of", invoke_without_command=True)
console = Console()


@app.callback()
def of(
        instance_id: str = typer.Argument(
            ...,
            metavar="INSTANCE_ID",
            help="Full instance ID in format `job_id@run_id`"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """
    Print full path to job instance output file.

    This command locates and prints the full filesystem path to a job instance's
    output file. Requires a full instance ID in the format 'job_id@run_id'.

    Examples:
        cat "$(taro of backup@20240115_123456)"
        tail -f "$(taro of daily_report@run_42)"
        grep ERROR "$(taro of batch_job@abc123def)"
    """
    try:
        run_match = JobRunCriteria.parse_strict(instance_id)
    except ValueError as e:
        console.print(f"[red]Error:[/] Invalid instance ID format: {e}")
        raise typer.Exit(1)
    with connector.connect(env) as conn:
        runs: List[JobRun] = conn.read_history_runs(run_match)
        if not runs:
            console.print(f"[red]Error:[/] Instance not found: {instance_id}")
            raise typer.Exit(1)
        for output_loc in runs[0].output_locations:
            if output_loc.type == 'file':
                print(output_loc.source)
                return

        console.print(f"[red]Error:[/] No output file found for {instance_id}")
        raise typer.Exit(1)
