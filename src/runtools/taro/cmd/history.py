from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, LifecycleCriterion, TemporalField, TerminationCriterion
from runtools.runcore.db import SortOption
from runtools.runcore.env import get_env_config
from runtools.runcore.run import Outcome
from runtools.runcore.util import MatchingStrategy, DateTimeRange
from runtools.taro import printer, cliutil, cli
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def history(
        env: str = cli.ENV_OPTION_FIELD,
        instance_patterns: List[str] = typer.Argument(default=None, metavar="PATTERN",
                                                      help="Instance ID patterns to filter results"),

        # Pagination
        no_pager: bool = typer.Option(False, "--no-pager", "-p", help="Do not use pager for output"),
        lines: int = typer.Option(-1, "--lines", "-n", metavar="NUM", help="Number of history runs to show"),
        offset: int = typer.Option(0, "--offset", "-o", metavar="NUM", help="Number of history runs to skip"),

        # Sort options
        ascending: bool = typer.Option(False, "--asc", "-a", help="Ascending sort"),
        sort_option: SortOption = typer.Option(SortOption.ENDED, "--sort", "-s",
                                               help="Sorting criteria (created/ended/time)"),

        # - Outcome based filtering
        success: bool = typer.Option(False, "--success", "-S", help="Show only successfully completed jobs"),
        nonsuccess: bool = typer.Option(False, "--nonsuccess", "-X",
                                        help="Show only jobs without successful completion"),
        aborted: bool = typer.Option(False, "--aborted", "-A", help="Show only jobs which were aborted by user"),
        rejected: bool = typer.Option(False, "--rejected", "-R", help="Show only jobs rejected at some phase"),
        fault: bool = typer.Option(False, "--fault", "-E", help="Show only failed jobs"),

        # Filter options
        last: bool = typer.Option(False, "--last", "-L", help="Show last execution of each job"),
        slowest: bool = typer.Option(False, "--slowest", "-O", help="Show slowest run from each job"),

        # - Temporal filtering
        filter_by: TemporalField = typer.Option(
            TemporalField.CREATED,
            "--filter-by",
            "-F",
            help="Which timestamp field to use for datetime filtering (options below)"
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
    """Show job runs history"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()
    _apply_outcome_filters(run_match, success, nonsuccess, aborted, rejected, fault)
    _apply_date_filters(run_match, filter_by, from_date, to_date, today, yesterday, week, fortnight, three_weeks,
                        four_weeks, month, days_back)

    if slowest:
        last = True
        sort_option = SortOption.TIME
        ascending = False

    env_config = get_env_config(env)
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


def _apply_outcome_filters(run_match, success, nonsuccess, aborted, rejected, fault):
    """Apply outcome filtering options to run_match using OR logic on termination outcome."""
    outcome_criteria = []

    if success:
        outcome_criteria.append(TerminationCriterion(outcome=Outcome.SUCCESS))
    if nonsuccess:
        outcome_criteria.append(TerminationCriterion(outcome=Outcome.NON_SUCCESS))
    if aborted:
        outcome_criteria.append(TerminationCriterion(outcome=Outcome.ABORTED))
    if rejected:
        outcome_criteria.append(TerminationCriterion(outcome=Outcome.REJECTED))
    if fault:
        outcome_criteria.append(TerminationCriterion(outcome=Outcome.FAULT))

    for criterion in outcome_criteria:
        run_match += LifecycleCriterion(termination=criterion)


def _apply_date_filters(run_match, filter_by, from_date, to_date, today, yesterday, week, fortnight, three_weeks,
                        four_weeks, month, days_back):
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
    if three_weeks:
        date_ranges.append(DateTimeRange.days_range(-21, to_utc=True))
    if four_weeks:
        date_ranges.append(DateTimeRange.days_range(-28, to_utc=True))
    if month:
        date_ranges.append(DateTimeRange.days_range(-31, to_utc=True))
    if days_back is not None:
        date_ranges.append(DateTimeRange.days_range(-days_back, to_utc=True))

    for date_range in date_ranges:
        run_match += LifecycleCriterion().set_date_range(date_range, filter_by)


# Alias for 'hist' command
hist_app = typer.Typer(invoke_without_command=True)


@hist_app.callback()
def h(
        env: str = typer.Option(None, "--env", "-e", metavar="ENV_ID", help="Target environment"),
        instance_patterns: List[str] = typer.Argument(default=None, metavar="PATTERN",
                                                        help="Instance ID patterns to filter results"),

        # Pagination
        no_pager: bool = typer.Option(False, "--no-pager", "-p", help="Do not use pager for output"),
        lines: int = typer.Option(-1, "--lines", "-n", metavar="NUM", help="Number of history runs to show"),
        offset: int = typer.Option(0, "--offset", "-o", metavar="NUM", help="Number of history runs to skip"),

        # Sort options
        ascending: bool = typer.Option(False, "--asc", "-a", help="Ascending sort"),
        sort_option: SortOption = typer.Option(SortOption.ENDED, "--sort", "-s",
                                                help="Sorting criteria (created/ended/time)"),

        # - Outcome based filtering
        success: bool = typer.Option(False, "--success", "-S", help="Show only successfully completed jobs"),
        nonsuccess: bool = typer.Option(False, "--nonsuccess", "-X",
                                        help="Show only jobs without successful completion"),
        aborted: bool = typer.Option(False, "--aborted", "-A", help="Show only jobs which were aborted by user"),
        rejected: bool = typer.Option(False, "--rejected", "-R", help="Show only jobs rejected at some phase"),
        fault: bool = typer.Option(False, "--fault", "-E", help="Show only failed jobs"),

        # Filter options
        last: bool = typer.Option(False, "--last", "-L", help="Show last execution of each job"),
        slowest: bool = typer.Option(False, "--slowest", "-O", help="Show slowest run from each job"),

        # - Temporal filtering
        filter_by: TemporalField = typer.Option(
            TemporalField.CREATED,
            "--filter-by",
            "-F",
            help="Which timestamp field to use for datetime filtering (options below)"
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
    """Alias for history command"""
    history(
        env=env,
        instance_patterns=instance_patterns,
        no_pager=no_pager,
        lines=lines,
        offset=offset,
        ascending=ascending,
        sort_option=sort_option,
        success=success,
        nonsuccess=nonsuccess,
        aborted=aborted,
        rejected=rejected,
        fault=fault,
        last=last,
        slowest=slowest,
        filter_by=filter_by,
        from_date=from_date,
        to_date=to_date,
        today=today,
        yesterday=yesterday,
        week=week,
        fortnight=fortnight,
        three_weeks=three_weeks,
        four_weeks=four_weeks,
        month=month,
        days_back=days_back,
    )