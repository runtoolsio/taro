from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.db import SortCriteria
from runtools.runcore.env import get_env_config, get_default_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cliutil
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def history(
        instance_patterns: List[str] = typer.Argument(default=None, help="Instance ID patterns to filter results"),
        lines: int = typer.Option(-1, "--lines", "-n", help="Number of history entries to show"),
        offset: int = typer.Option(0, "--offset", "-o", help="Number of history entries to skip"),
        last: bool = typer.Option(False, "--last", "-L", help="Show last execution of each job"),
        slowest: bool = typer.Option(False, "--slowest", help="Show slowest instance from each job"),
        ascending: bool = typer.Option(False, "--asc", "-a", help="Ascending sort"),
        sort: str = typer.Option("ended", "--sort", "-s", help="Sorting criteria (created/ended/time)"),
        show_params: bool = typer.Option(False, "--show-params", help="Show parameters column"),
        no_pager: bool = typer.Option(False, "--no-pager", "-P", help="Do not use pager for output"),
        env: str = typer.Option(None, "--env", "-e", help="Target environment"),
):
    """Show jobs history"""
    run_match = JobRunCriteria.parse_all(instance_patterns, MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()

    if slowest:
        last = True
        sort = "time"
        ascending = False

    sort_criteria = SortCriteria[sort.upper()]

    env_config = get_env_config(env) if env else get_default_env_config()
    with connector.create(env_config) as conn:
        if not conn.persistence_enabled:
            console.print(f"[yellow]⚠[/] Persistence disabled for environment [cyan]{env_config.id}[/]")
            return

        runs_iter = conn.iter_history_runs(run_match, sort_criteria, asc=ascending, limit=lines, offset=offset, last=last)

        columns = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.ENDED, view_inst.EXEC_TIME,
                   view_inst.TERM_STATUS, view_inst.RESULT, view_inst.WARNINGS]
        if show_params:
            columns.insert(2, view_inst.PARAMETERS)
        try:
            printer.print_table(runs_iter, columns, show_header=True, pager=not no_pager)
        except BrokenPipeError:
            cliutil.handle_broken_pipe(exit_code=1)


# Alias for 'hist' command
hist_app = typer.Typer(invoke_without_command=True)
@hist_app.callback()
def hist(
        instance_patterns: List[str] = typer.Argument(default=None),
        lines: int = typer.Option(-1, "--lines", "-n"),
        offset: int = typer.Option(0, "--offset", "-o"),
        last: bool = typer.Option(False, "--last", "-L"),
        slowest: bool = typer.Option(False, "--slowest"),
        ascending: bool = typer.Option(False, "--asc", "-a"),
        sort: str = typer.Option("ended", "--sort", "-s"),
        show_params: bool = typer.Option(False, "--show-params"),
        no_pager: bool = typer.Option(False, "--no-pager", "-P"),
        env: str = typer.Option(None, "--env", "-e"),
):
    """Alias for history command"""
    history(
        instance_patterns=instance_patterns,
        lines=lines,
        offset=offset,
        last=last,
        slowest=slowest,
        ascending=ascending,
        sort=sort,
        show_params=show_params,
        no_pager=no_pager,
        env=env
    )