from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.matching import criteria, JobRunCriteriaBuilder, SortOption
from runtools.runcore.run import Outcome, Stage
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cliutil, cli
from runtools.taro.tui.selector import show_history
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
                                               help="Sorting criteria (created/ended/time/job_id/run_id)"),

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
        filter_by: Stage = typer.Option(
            Stage.CREATED.value,
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
    run_match = criteria().patterns_or_all(instance_patterns, MatchingStrategy.PARTIAL)
    _apply_outcome_filters(run_match, success, nonsuccess, aborted, rejected, fault)
    run_match.during(
        filter_by, from_date, to_date, today, yesterday, week, fortnight, three_weeks, four_weeks, month, days_back)

    if slowest:
        last = True
        sort_option = SortOption.TIME
        ascending = False

    resolved = cli.select_env(env)
    with connector.connect(resolved) as conn:
        runs_iter = conn.iter_runs(run_match.build(), sort_option, asc=ascending, limit=lines, offset=offset, last=last)

        printer_columns = [view_inst.N, view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.ENDED,
                           view_inst.EXEC_TIME_COMPACT, view_inst.TERM_STATUS_FULL, view_inst.WARNINGS,
                           view_inst.RESULT]
        if no_pager:
            try:
                printer.print_table(runs_iter, printer_columns, show_header=True, pager=False)
            except BrokenPipeError:
                cliutil.handle_broken_pipe(exit_code=1)
        else:
            runs = list(runs_iter)
            if not runs:
                console.print("No matching runs")
                return
            tui_columns = [view_inst.N, view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT,
                           view_inst.ENDED_COMPACT, view_inst.EXEC_TIME, view_inst.TERM_STATUS, view_inst.WARNINGS,
                           view_inst.RESULT]
            show_history(runs, tui_columns, connector=conn)


def _apply_outcome_filters(builder: JobRunCriteriaBuilder, success, nonsuccess, aborted, rejected, fault):
    """Apply outcome filtering options to builder using OR logic on termination outcome."""
    if success:
        builder.success()
    if nonsuccess:
        builder.nonsuccess()
    if aborted:
        builder.termination_outcome(Outcome.ABORTED)
    if rejected:
        builder.termination_outcome(Outcome.REJECTED)
    if fault:
        builder.termination_outcome(Outcome.FAULT)
