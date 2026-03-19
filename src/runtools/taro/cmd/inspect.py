"""Dev command: print raw history columns for a single job run."""

import json
from typing import List, Optional

import typer
from rich.console import Console
from rich.syntax import Syntax

from runtools.runcore import connector
from runtools.runcore.matching import JobRunCriteria, SortOption
from runtools.runcore.job import JobRun
from runtools.runcore.util import MatchingStrategy
from runtools.runcore.util.dt import format_dt_sql
from runtools.taro import cli
from runtools.taro.tui.selector import select_history_run
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()

SELECTOR_COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT, view_inst.ENDED_COMPACT,
                    view_inst.EXEC_TIME, view_inst.TERM_STATUS]


def _to_db_columns(run: JobRun) -> list[tuple[str, str]]:
    """Reconstruct DB column representations from a JobRun."""
    lifecycle = run.lifecycle

    def fmt_dt(dt):
        return format_dt_sql(dt) if dt else None

    def fmt_json(obj):
        return json.dumps(obj, indent=2, default=str) if obj else None

    return [
        ("job_id", run.job_id),
        ("run_id", run.run_id),
        ("user_params", fmt_json(dict(run.metadata.user_params)) if run.metadata.user_params else None),
        ("created", fmt_dt(lifecycle.created_at)),
        ("started", fmt_dt(lifecycle.started_at)),
        ("ended", fmt_dt(lifecycle.termination.terminated_at) if lifecycle.termination else None),
        ("exec_time", str(round(lifecycle.total_run_time.total_seconds(), 3)) if lifecycle.total_run_time else None),
        ("root_phase", fmt_json(run.root_phase.serialize())),
        ("output_locations", fmt_json([loc.serialize() for loc in run.output_locations]) if run.output_locations else None),
        ("termination_status", str(lifecycle.termination.status.value) if lifecycle.termination else None),
        ("faults", fmt_json([f.serialize() for f in run.faults]) if run.faults else None),
        ("status", fmt_json(run.status.serialize()) if run.status else None),
        ("warnings", str(len(run.status.warnings)) if run.status else None),
    ]


@app.callback()
def inspect(
        env: str = cli.ENV_OPTION_FIELD,
        instance_patterns: Optional[List[str]] = cli.INSTANCE_PATTERNS_OPTIONAL,
):
    """[Dev] Inspect raw history columns for a job run."""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()

    with connector.connect(env) as conn:
        if not conn.persistence_enabled:
            console.print(f"[yellow]⚠[/] Persistence disabled for environment [cyan]{conn.env_id}[/]")
            return

        runs = conn.read_runs(run_match, SortOption.ENDED, asc=False, limit=100)
        if not runs:
            console.print("No matching runs")
            return

        if len(runs) == 1:
            run = runs[0]
        else:
            run = select_history_run(runs, SELECTOR_COLUMNS, title="Select run to inspect")
            if not run:
                return

        _print_columns(run)


def _print_columns(run: JobRun) -> None:
    for name, value in _to_db_columns(run):
        if value is None:
            console.print(f"[bold cyan]{name}[/]: [dim]NULL[/]")
        elif value.startswith(("{", "[")):
            console.print(f"[bold cyan]{name}[/]:")
            console.print(Syntax(value, "json", theme="monokai", padding=(0, 2)))
        else:
            console.print(f"[bold cyan]{name}[/]: {value}")
