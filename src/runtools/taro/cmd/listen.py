from queue import Queue, Empty
from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import InstanceLifecycleEvent
from runtools.runcore.util import MatchingStrategy, format_dt_local_tz
from runtools.taro import cli, printer
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()


def print_event(event: InstanceLifecycleEvent):
    """Print a lifecycle event."""
    timestamp = format_dt_local_tz(event.timestamp, include_ms=False)
    stage_style = _stage_style(event.new_stage.name)
    console.print(
        f"[dim]{timestamp}[/]  [bold]{event.job_run.instance_id}[/]  [{stage_style}]{event.new_stage.name}[/]"
    )


def _stage_style(stage_name: str) -> str:
    """Get rich style for a stage."""
    styles = {"CREATED": "cyan", "RUNNING": "green", "ENDED": "blue"}
    return styles.get(stage_name, "")


@app.callback()
def listen(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance ID patterns to filter results"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """
    Listen for job lifecycle events in real-time.

    Shows current active instances, then streams lifecycle events
    (CREATED, RUNNING, ENDED) as they happen.

    Examples:
        taro listen
        taro listen "backup*"
        taro listen --env production
    """
    run_match = JobRunCriteria.parse_all(instance_patterns, MatchingStrategy.PARTIAL) if instance_patterns else None
    event_queue = Queue()
    with connector.connect(env) as conn:
        conn.notifications.add_observer_lifecycle(lambda e: event_queue.put(e))  # 1. Register observer first (no events missed)

        runs = conn.get_active_runs(run_match)  # 2. Get and display current active instances
        if runs:
            console.print(f"[dim]Active instances in [/][ {conn.env_id} ]")
            columns = [
                view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED,
                view_inst.EXEC_TIME, view_inst.PHASES, view_inst.WARNINGS,
                view_inst.STATUS
            ]
            printer.print_table(runs, columns, show_header=True, pager=False)
            console.print()

        console.print("[dim]Listening for events... (Ctrl+C to stop)[/]\n")

        while True:  # 3. Process queue
            try:
                event = event_queue.get(timeout=0.5)
                if not run_match or run_match(event.job_run):
                    print_event(event)
            except Empty:
                continue
