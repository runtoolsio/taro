"""Live-updating terminal view of active job instances.

Subscribes to lifecycle events via a connector and uses them to trigger table refreshes.
The main loop blocks on the event queue for up to 1 second, then drains any remaining events,
fetches the current active runs, and rebuilds the displayed table.
Recently ended runs are retained for a short period (dimmed) before being removed.
"""

import time
from queue import Queue, Empty
from typing import List, Optional

import typer
from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from runtools.runcore import connector
from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria, SortOption
from runtools.runcore.job import InstanceID, InstanceLifecycleEvent, JobRun
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()

COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.STAGE, view_inst.EXEC_TIME, view_inst.PHASES, view_inst.STATUS]

ENDED_RETENTION_SECONDS = 10

_RIGHT_ALIGNED = {view_inst.EXEC_TIME}


def _to_rich_style(pt_style: str) -> str:
    """Converts prompt_toolkit ANSI style names to rich style names.

    Strips 'ansi' prefix and inserts '_' for bright variants:
    'ansibrightred' -> 'bright_red', 'ansiblue' -> 'blue'.
    """
    if not pt_style:
        return pt_style
    parts = pt_style.split()
    converted = []
    for part in parts:
        if part.startswith("ansi"):
            name = part[4:]  # strip 'ansi'
            if name.startswith("bright"):
                name = "bright_" + name[6:]
            converted.append(name)
        else:
            converted.append(part)
    return " ".join(converted)


class LiveView:
    """Live-updating table display of active job instances."""

    def __init__(self, conn: EnvironmentConnector, env_name: str, run_match: Optional[JobRunCriteria],
                 sort_option: SortOption, descending: bool):
        self._conn: EnvironmentConnector = conn
        self._env_name: str = env_name
        self._run_match: Optional[JobRunCriteria] = run_match
        self._sort_option: SortOption = sort_option
        self._descending: bool = descending
        self._ended_runs: dict[InstanceID, tuple[JobRun, float]] = {}
        self._event_queue: Queue[InstanceLifecycleEvent] = Queue()

    def run(self) -> None:
        """Subscribe to events, fetch initial state, and enter the refresh loop."""
        handler = lambda e: self._event_queue.put(e)
        self._conn.notifications.add_observer_lifecycle(handler)
        try:
            with Live(self._build_table(self._collect_runs()), console=console, refresh_per_second=1) as live_display:
                try:
                    while True:
                        self._drain_events()
                        self._prune_ended()
                        live_display.update(self._build_table(self._collect_runs()))
                except KeyboardInterrupt:
                    pass
        finally:
            self._conn.notifications.remove_observer_lifecycle(handler)

    def _drain_events(self) -> None:
        """Wait up to 1s for the first event, then drain any remaining."""
        first = True
        while True:
            try:
                event = self._event_queue.get(timeout=1 if first else 0)
                self._process_event(event)
                first = False
            except Empty:
                break

    def _process_event(self, event: InstanceLifecycleEvent) -> None:
        """Store ENDED event snapshot if it matches the filter criteria."""
        if event.new_stage == Stage.ENDED and (not self._run_match or self._run_match(event.job_run)):
            self._ended_runs[event.job_run.instance_id] = (event.job_run, time.monotonic())

    def _prune_ended(self) -> None:
        """Remove ended run entries older than the retention period."""
        now = time.monotonic()
        self._ended_runs = {
            iid: (run, ts) for iid, (run, ts) in self._ended_runs.items()
            if now - ts < ENDED_RETENTION_SECONDS
        }

    def _collect_runs(self) -> list[JobRun]:
        """Fetch active runs, merge with retained ended runs, and sort."""
        active = self._conn.get_active_runs(self._run_match)
        active_ids = {r.instance_id for r in active}
        retained = [run for iid, (run, _) in self._ended_runs.items() if iid not in active_ids]
        return self._sort_option.sort_runs(active + retained, reverse=self._descending)

    def _build_table(self, runs: list[JobRun]) -> Table:
        """Build a rich.Table from a list of JobRun objects."""
        table = Table(
            title=f" [ {self._env_name} ] ",
            title_style="bold",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            caption="Ctrl+C to exit",
            caption_style="dim",
            padding=(0, 1),
        )

        for col in COLUMNS:
            justify = "right" if col in _RIGHT_ALIGNED else "left"
            table.add_column(col.name, no_wrap=True, justify=justify)

        if not runs:
            table.add_row(Text("No active instances", style="dim"), *[""] * (len(COLUMNS) - 1))
            return table

        for run in runs:
            is_ended = run.instance_id in self._ended_runs
            cells = []
            for col in COLUMNS:
                value = col.value_fnc(run)
                style = "dim" if is_ended else _to_rich_style(col.colour_fnc(run))
                cells.append(Text(str(value), style=style))
            table.add_row(*cells)

        return table


@app.callback()
def live(
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
    """Live-updating view of active job instances.

    Displays a table that refreshes automatically when jobs start or stop.
    Press Ctrl+C to exit.

    Examples:
        taro live
        taro live "backup*"
        taro live --env production
    """
    run_match = JobRunCriteria.parse_all(instance_patterns, MatchingStrategy.PARTIAL) if instance_patterns else None
    with connector.connect(env) as conn:
        LiveView(conn, conn.env_id, run_match, sort_option, descending).run()
