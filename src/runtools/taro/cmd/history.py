from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, LifecycleCriterion
from runtools.runcore.db import SortOption
from runtools.runcore.env import get_env_config, get_default_env_config
from runtools.runcore.util import MatchingStrategy, DateTimeRange
from runtools.taro import printer, cliutil
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def history(
        env: str = typer.Option(None, "--env", "-e", metavar="ENV_ID", help="Target environment"),
        instance_patterns: List[str] = typer.Argument(default=None, metavar="PATTERN", help="Instance ID patterns to filter results"),
        # Pagination
        no_pager: bool = typer.Option(False, "--no-pager", "-p", help="Do not use pager for output"),
        lines: int = typer.Option(-1, "--lines", "-n", metavar="NUM", help="Number of history runs to show"),
        offset: int = typer.Option(0, "--offset", "-o", metavar="NUM", help="Number of history runs to skip"),
        # Sort options
        ascending: bool = typer.Option(False, "--asc", "-a", help="Ascending sort"),
        sort_option: SortOption = typer.Option(SortOption.ENDED, "--sort", "-s", help="Sorting criteria (created/ended/time)"),
        # Filter options
        last: bool = typer.Option(False, "--last", "-L", help="Show last execution of each job"),
        slowest: bool = typer.Option(False, "--slowest", "-S", help="Show slowest run from each job"),
        # - Date filtering
        from_date: Optional[str] = typer.Option(
            None,
            "--from",
            "-f",
            metavar="DATETIME",
            help="Start date/time. Formats: YYYY-MM-DD or YYYY-MM-DD[ |T]HH:MM[:SS][.ms][Z|+HHMM]",
        ),
        to_date: Optional[str] = typer.Option(
            None,
            "--to",
            "-t",
            metavar="DATETIME",
            help="End date/time. Formats: YYYY-MM-DD or YYYY-MM-DD[ |T]HH:MM[:SS][.ms][Z|+HHMM]",
        ),
        today: bool = typer.Option(False, "--today", "-T"),
        yesterday: bool = typer.Option(False, "--yesterday", "-Y"),
        week: bool = typer.Option(False, "--week", "-1", "-W"),
        fortnight: bool = typer.Option(False, "--fortnight", "-2"),
        month: bool = typer.Option(False, "--month", "-3", "-M"),
):
    """Show jobs history"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()
    _apply_date_filters(run_match, from_date, to_date, today, yesterday, week, fortnight, month)

    if slowest:
        last = True
        sort = "time"
        ascending = False

    env_config = get_env_config(env) if env else get_default_env_config()
    with connector.create(env_config) as conn:
        if not conn.persistence_enabled:
            console.print(f"[yellow]⚠[/] Persistence disabled for environment [cyan]{env_config.id}[/]")
            return

        runs_iter = conn.iter_history_runs(run_match, sort_option, asc=ascending, limit=lines, offset=offset, last=last)

        columns = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.ENDED, view_inst.EXEC_TIME,
                   view_inst.TERM_STATUS, view_inst.WARNINGS, view_inst.RESULT]
        try:
            printer.print_table(runs_iter, columns, show_header=True, pager=not no_pager)
        except BrokenPipeError:
            cliutil.handle_broken_pipe(exit_code=1)


def _apply_date_filters(run_match, from_date, to_date, today, yesterday, week, fortnight, month):
    """Apply date filtering options to run_match using OR logic on created timestamp."""
    date_ranges = []

    if from_date or to_date:
        date_ranges.append(DateTimeRange.parse_to_utc(from_date, to_date))
    if today:
        date_ranges.append(DateTimeRange.today(to_utc=True))
    if yesterday:
        date_ranges.append(DateTimeRange.yesterday(to_utc=True))
    if week:
        date_ranges.append(DateTimeRange.week_back(to_utc=True))
    if fortnight:
        date_ranges.append(DateTimeRange.days_range(-14, to_utc=True))
    if month:
        date_ranges.append(DateTimeRange.days_range(-31, to_utc=True))

    for date_range in date_ranges:
        run_match += LifecycleCriterion(created=date_range)


# Alias for 'hist' command
hist_app = typer.Typer(invoke_without_command=True)


@hist_app.callback()
def hist(
        instance_patterns: List[str] = typer.Argument(default=None),
        lines: int = typer.Option(-1, "--lines", "-n"),
        offset: int = typer.Option(0, "--offset", "-o"),
        last: bool = typer.Option(False, "--last", "-L"),
        slowest: bool = typer.Option(False, "--slowest", "-S"),
        ascending: bool = typer.Option(False, "--asc", "-a"),
        sort: str = typer.Option("ended", "--sort", "-s"),
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
        no_pager=no_pager,
        env=env
    )
