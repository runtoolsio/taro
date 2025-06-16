from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.job import StatsSortOption
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cli
from runtools.taro.argsutil import apply_date_filters
from runtools.taro.view import stats

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def stats_cmd(
        env: str = cli.ENV_OPTION_FIELD,
        instance_patterns: List[str] = typer.Argument(default=None, metavar="PATTERN",
                                                      help="Instance ID patterns to filter results"),

        # Sort options
        descending: bool = typer.Option(False, "--descending", "-d", help="Sort in descending order"),
        sort_option: StatsSortOption = typer.Option(StatsSortOption.JOB_ID, "--sort", "-s",
                                                    help="Sorting criteria"),

        # Temporal filtering
        filter_by: Stage = typer.Option(
            Stage.CREATED.value,
            "--filter-by",
            "-F",
            help="Which timestamp field to use for datetime filtering"
        ),
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
        three_weeks: bool = typer.Option(False, "--three-weeks", "-3",
                                         help="Show only jobs created from now 3 weeks back"),
        four_weeks: bool = typer.Option(False, "--four-weeks", "-4",
                                        help="Show only jobs created from now 4 weeks back"),
        month: bool = typer.Option(False, "--month", "-M"),
        days_back: Optional[int] = typer.Option(None, "--days-back", "-D", metavar="DAYS",
                                                help="Show only jobs created from now N days back"),
):
    """Show job statistics"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()

    apply_date_filters(run_match, filter_by, from_date, to_date, today, yesterday, week, fortnight, three_weeks,
                       four_weeks, month, days_back)

    env_config = get_env_config(env)
    with connector.create(env_config) as conn:
        if not conn.persistence_enabled:
            console.print(f"[yellow]⚠[/] Persistence disabled for environment [cyan]{env_config.id}[/]")
            return

        job_stats_list = conn.read_history_stats(run_match)

    sorted_stats = sort_option.sort_stats(job_stats_list, reverse=descending)
    printer.print_table(sorted_stats, stats.DEFAULT_COLUMNS, show_header=True, pager=True)
