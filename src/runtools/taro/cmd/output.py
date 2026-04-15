"""Stream or locate a job instance's output."""

import json
import sys
from typing import Optional, List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.matching import JobRunCriteria, SortOption
from runtools.runcore.output import MultiSourceOutputReader, OutputLine, OutputReadError
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.tui.selector import select_history_run
from runtools.taro.view import instance as view_inst
from runtools.taro.view.output_render import format_line_plain, format_line_verbose

app = typer.Typer(name="output", invoke_without_command=True)
_err = Console(stderr=True)

_SELECTOR_COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT, view_inst.ENDED_COMPACT,
                     view_inst.EXEC_TIME, view_inst.TERM_STATUS]

_COLOR_MAP = {"auto": None, "always": True, "never": False}


@app.callback()
def output_cmd(
        instance_patterns: Optional[List[str]] = cli.INSTANCE_PATTERNS_OPTIONAL,
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        path: bool = typer.Option(False, "--path", "-p",
                                  help="Print output location path/URI instead of content"),
        verbose: bool = typer.Option(False, "--verbose", "-v",
                                     help="Verbose format: timestamp, level, logger, message, fields"),
        jsonl: bool = typer.Option(False, "--jsonl",
                                   help="Emit raw JSONL (one serialized OutputLine per line)"),
        errors: bool = typer.Option(False, "--errors",
                                    help="Only emit lines where is_error is true"),
        scheme: Optional[str] = typer.Option(None, "--scheme", "-s",
                                             help="Filter output locations by URI scheme (e.g. 'file')"),
        color: str = typer.Option("auto", "--color", metavar="WHEN",
                                  help="When to emit ANSI colors: auto, always, never"),
):
    """Stream a job instance's output to stdout.

    Default renders content in plain format to stdout — pipe to grep, less, etc.
    When no patterns are given, opens a selector over recent runs; a full
    ``job_id@run_id`` resolves directly.

    Examples:
        taro output                         # selector → stream content
        taro output backup                  # filter + selector if ambiguous
        taro output backup@abc123           # exact resolve
        taro output backup | grep ERROR
        taro output backup -v | less
        taro output backup --jsonl | jq .
        cat "$(taro output backup --path)"
    """
    if verbose and jsonl:
        _err.print("[red]Error:[/] --verbose and --jsonl are mutually exclusive")
        raise typer.Exit(2)
    if color not in _COLOR_MAP:
        _err.print(f"[red]Error:[/] --color must be one of: auto, always, never (got {color!r})")
        raise typer.Exit(2)

    resolved = cli.select_env(env)
    with connector.connect(resolved) as conn:
        run = _resolve_run(conn, instance_patterns)
        if not run:
            return

        locations = list(run.output_locations)
        if scheme:
            locations = [loc for loc in locations if loc.scheme == scheme]

        if not locations:
            _err.print(f"[red]Error:[/] No output locations found for {run.instance_id}")
            raise typer.Exit(1)

        if path:
            _handle_path_mode(locations)
            return

        if len(locations) > 1:
            _err.print(f"[red]Error:[/] multiple output locations matched for {run.instance_id}:")
            for loc in locations:
                _err.print(f"  - {loc.uri}")
            _err.print("Use [cyan]--scheme <name>[/] to pick one, or [cyan]--path[/] to inspect interactively.")
            raise typer.Exit(1)

        _stream_content(conn, run, scheme, verbose, jsonl, errors, color)


# --- Run resolution ---------------------------------------------------------

def _resolve_run(conn, patterns):
    """Resolve a single job run from patterns or an interactive selector."""
    if not patterns:
        runs = conn.read_runs(JobRunCriteria.all(), SortOption.ENDED, asc=False, limit=100)
        if not runs:
            _err.print("[red]Error:[/] No runs found")
            raise typer.Exit(1)
        return select_history_run(runs, _SELECTOR_COLUMNS, title="Select run")

    # Single exact instance ID (job_id@run_id) — fast path
    if len(patterns) == 1 and '@' in patterns[0]:
        try:
            run_match = JobRunCriteria.parse_strict(patterns[0])
        except ValueError as e:
            _err.print(f"[red]Error:[/] Invalid instance ID: {e}")
            raise typer.Exit(1)
        runs = conn.read_runs(run_match)
        if not runs:
            _err.print(f"[red]Error:[/] Instance not found: {patterns[0]}")
            raise typer.Exit(1)
        return runs[0]

    run_match = JobRunCriteria.parse_all(patterns, MatchingStrategy.PARTIAL)
    runs = conn.read_runs(run_match, SortOption.ENDED, asc=False, limit=100)
    if not runs:
        _err.print("[red]Error:[/] No matching runs")
        raise typer.Exit(1)
    if len(runs) == 1:
        return runs[0]
    return select_history_run(runs, _SELECTOR_COLUMNS, title="Select run")


# --- Path mode --------------------------------------------------------------

def _handle_path_mode(locations) -> None:
    if len(locations) == 1:
        _print_location(locations[0])
        return

    import questionary
    from runtools.taro.theme import prompt_style

    choices = [questionary.Choice(title=str(loc.as_path()) if loc.is_file else loc.uri, value=loc)
               for loc in locations]
    selected = questionary.select("Multiple output locations — select one:", choices=choices,
                                  style=prompt_style()).ask()
    if selected:
        _print_location(selected)


def _print_location(loc) -> None:
    """Emit a filesystem path (file scheme) or full URI."""
    print(loc.as_path() if loc.is_file else loc.uri)


# --- Content streaming ------------------------------------------------------

def _stream_content(conn, run, scheme: Optional[str], verbose: bool, jsonl: bool,
                    errors_only: bool, color: str) -> None:
    backends = conn.output_backends
    if scheme:
        backends = [b for b in backends if b.type == scheme]
    if not backends:
        _err.print(f"[red]Error:[/] No output backend available for scheme {scheme!r}")
        raise typer.Exit(1)

    reader = MultiSourceOutputReader(backends)
    try:
        lines = reader.read_output(run.instance_id)
    except OutputReadError as e:
        _err.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    if errors_only:
        lines = [l for l in lines if l.is_error]

    if jsonl:
        _render_jsonl(lines)
    elif verbose:
        _render_rich(lines, format_line_verbose, color)
    else:
        _render_rich(lines, format_line_plain, color)


def _render_jsonl(lines: List[OutputLine]) -> None:
    """Emit raw JSONL. No coloring, no Rich; direct stdout for speed and fidelity."""
    out = sys.stdout
    for line in lines:
        out.write(json.dumps(line.serialize(), ensure_ascii=False))
        out.write("\n")
    out.flush()


def _render_rich(lines: List[OutputLine], formatter, color: str) -> None:
    """Render via Rich with color behavior controlled by --color."""
    console = Console(force_terminal=_COLOR_MAP[color], soft_wrap=True, highlight=False, markup=False)
    for line in lines:
        console.print(formatter(line))
