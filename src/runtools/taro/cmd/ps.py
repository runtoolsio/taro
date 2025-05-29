from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, SortOption
from runtools.runcore.env import get_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cli, cliutil
from runtools.taro.view import instance as view_inst

app = typer.Typer(name="ps", invoke_without_command=True)
console = Console()


@app.callback()
def ps(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance ID patterns to filter results"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        sort_option: SortOption = typer.Option(SortOption.CREATED, "--sort", "-s",
                                               help="Sorting criteria (created/ended/time/job_id/run_id)"),
        descending: bool = typer.Option(False, "--descending", "-d", help="Sort in descending order"),
):
    """Show active/running job instances"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()
    env_config = get_env_config(env)
    with connector.create(env_config) as conn:
        runs = conn.get_active_runs(run_match)

    if not runs:
        console.print(f"No active instances found in [cyan]{env_config.id}[/]")
        return

    columns = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.EXEC_TIME, view_inst.WARNINGS,
               view_inst.STATUS]
    runs_sorted = sort_option.sort_runs(runs, reverse=descending)
    try:
        printer.print_table(runs_sorted, columns, show_header=True, pager=False)
    except BrokenPipeError:
        cliutil.handle_broken_pipe(exit_code=1)
