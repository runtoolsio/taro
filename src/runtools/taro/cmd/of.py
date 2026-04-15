"""Print filesystem path to job instance output file."""

from typing import Optional, List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.matching import JobRunCriteria, SortOption
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.tui.selector import select_history_run
from runtools.taro.view import instance as view_inst

app = typer.Typer(name="of", invoke_without_command=True)
console = Console()

_SELECTOR_COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT, view_inst.ENDED_COMPACT,
                     view_inst.EXEC_TIME, view_inst.TERM_STATUS]


@app.callback()
def of(
        instance_patterns: Optional[List[str]] = cli.INSTANCE_PATTERNS_OPTIONAL,
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        scheme: Optional[str] = typer.Option(None, "--scheme", "-s",
                                             help="Filter output locations by URI scheme (e.g. 'file')"),
):
    """Print path to job instance output location.

    When called without arguments, opens a selector over recent runs.
    When a full instance ID is given (job_id@run_id), resolves directly.
    When multiple output locations remain after filtering, opens a selector.

    Examples:
        taro of
        taro of backup
        taro of "backup@20240115_123456"
        cat "$(taro of backup --scheme file)"
    """
    resolved = cli.select_env(env)
    with connector.connect(resolved) as conn:
        run = _resolve_run(conn, instance_patterns)
        if not run:
            return

        locations = list(run.output_locations)
        if scheme:
            locations = [loc for loc in locations if loc.scheme == scheme]

        if not locations:
            console.print(f"[red]Error:[/] No output locations found for {run.instance_id}")
            raise typer.Exit(1)

        if len(locations) == 1:
            _print_location(locations[0])
        else:
            _select_location(locations)


def _resolve_run(conn, patterns):
    """Resolve a single job run from patterns or an interactive selector."""
    if not patterns:
        runs = conn.read_runs(JobRunCriteria.all(), SortOption.ENDED, asc=False, limit=100)
        if not runs:
            console.print("[red]Error:[/] No runs found")
            raise typer.Exit(1)
        return select_history_run(runs, _SELECTOR_COLUMNS, title="Select run")

    # Single exact instance ID (job_id@run_id) — fast path
    if len(patterns) == 1 and '@' in patterns[0]:
        try:
            run_match = JobRunCriteria.parse_strict(patterns[0])
        except ValueError as e:
            console.print(f"[red]Error:[/] Invalid instance ID: {e}")
            raise typer.Exit(1)
        runs = conn.read_runs(run_match)
        if not runs:
            console.print(f"[red]Error:[/] Instance not found: {patterns[0]}")
            raise typer.Exit(1)
        return runs[0]

    # Pattern matching — filter, then select if multiple
    run_match = JobRunCriteria.parse_all(patterns, MatchingStrategy.PARTIAL)
    runs = conn.read_runs(run_match, SortOption.ENDED, asc=False, limit=100)
    if not runs:
        console.print("[red]Error:[/] No matching runs")
        raise typer.Exit(1)
    if len(runs) == 1:
        return runs[0]
    return select_history_run(runs, _SELECTOR_COLUMNS, title="Select run")


def _print_location(loc) -> None:
    """Print a location as a filesystem path (file scheme) or full URI."""
    print(loc.as_path() if loc.is_file else loc.uri)


def _select_location(locations) -> None:
    """Prompt the user to pick one output location from multiple."""
    import questionary
    from runtools.taro.theme import prompt_style

    choices = [questionary.Choice(title=str(loc.as_path()) if loc.is_file else loc.uri, value=loc)
               for loc in locations]
    selected = questionary.select("Multiple output locations — select one:", choices=choices,
                                  style=prompt_style()).ask()
    if selected:
        _print_location(selected)
