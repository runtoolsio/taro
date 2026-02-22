"""Live-updating terminal view of active job instances.

Primarily event-driven: phase events provide immediate updates for transitions, and control events
provide immediate updates for stop requests. A slow RPC poll (~10s) serves only as a heartbeat
to detect crashed instances. Recently ended runs are retained briefly (dimmed) before being removed.
"""

import time
from queue import Queue, Empty
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from runtools.runcore import connector
from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria, SortOption
from runtools.runcore.job import InstanceID, InstancePhaseEvent, JobRun
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.tui.widgets import to_rich_style
from runtools.taro.view import instance as view_inst

app = typer.Typer(invoke_without_command=True)
console = Console()

COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.EXEC_TIME, view_inst.TERM_STATUS, view_inst.PHASES,
           view_inst.STATUS]

ENDED_RETENTION_SECONDS = 10
MISSING_GRACE_SECONDS = 5
POLL_INTERVAL_SECONDS = 10

_RIGHT_ALIGNED = {view_inst.EXEC_TIME}
# Column sizing — with expand=True, only columns with ratio set absorb extra space.
# Columns with width are truly fixed; the rest stay content-sized.
_COL_WIDTH = {
    view_inst.JOB_ID: 20,
    view_inst.RUN_ID: 20,
    view_inst.EXEC_TIME: 10,
    view_inst.TERM_STATUS: view_inst.TERM_STATUS.max_width,
}
_COL_RATIO = {
    view_inst.PHASES: 1,
    view_inst.STATUS: 2,
}


class LiveView:
    """Live-updating table display of active job instances."""

    def __init__(self, conn: EnvironmentConnector, env_name: str, run_match: Optional[JobRunCriteria],
                 sort_option: SortOption, descending: bool):
        self._conn: EnvironmentConnector = conn
        self._env_name: str = env_name
        self._run_match: Optional[JobRunCriteria] = run_match
        self._sort_option: SortOption = sort_option
        self._descending: bool = descending
        self._active_runs: dict[InstanceID, JobRun] = {}
        self._ended_runs: dict[InstanceID, tuple[JobRun, float]] = {}
        self._missing_runs: dict[InstanceID, float] = {}  # instance_id -> first_missing_at (monotonic)
        self._event_queue: Queue = Queue()
        self._last_poll: float = 0

    def run(self) -> None:
        """Subscribe to instance events and run event-driven refresh loop with slow RPC heartbeat."""
        handler = lambda e: self._event_queue.put(e)
        self._conn.notifications.add_observer_all_events(handler)
        try:
            self._refresh_active_runs()
            with Live(self._build_table(), console=console, refresh_per_second=10) as live_display:
                try:
                    while True:
                        self._drain_events()
                        self._poll_if_due()
                        self._prune_ended()
                        live_display.update(self._build_table())
                except KeyboardInterrupt:
                    pass
        finally:
            self._conn.notifications.remove_observer_all_events(handler)

    def _poll_if_due(self) -> None:
        """Run RPC poll when the heartbeat interval has elapsed."""
        now = time.monotonic()
        if now - self._last_poll >= POLL_INTERVAL_SECONDS:
            self._refresh_active_runs()

    def _refresh_active_runs(self) -> None:
        """RPC heartbeat to discover new instances and detect crashed ones.

        Instances missing from RPC are given a grace period before removal, allowing END events
        to arrive and handle the transition to ended state properly.
        """
        self._last_poll = time.monotonic()
        polled = {run.instance_id: run for run in self._conn.get_active_runs(self._run_match)}

        # Update snapshots for instances still responding
        for iid, run in polled.items():
            self._active_runs[iid] = run
            self._missing_runs.pop(iid, None)

        # Track instances that disappeared from RPC
        for iid in list(self._active_runs):
            if iid not in polled and iid not in self._missing_runs:
                self._missing_runs[iid] = self._last_poll

        # Remove instances missing beyond grace period (likely crashed)
        for iid, missing_since in list(self._missing_runs.items()):
            if self._last_poll - missing_since >= MISSING_GRACE_SECONDS:
                self._active_runs.pop(iid, None)
                del self._missing_runs[iid]

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

    def _process_event(self, event) -> None:
        """Update active/ended cache from the event's JobRun snapshot."""
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return  # Output events carry only instance metadata, not a full snapshot
        if self._run_match and not self._run_match(job_run):
            return
        if isinstance(event, InstancePhaseEvent) and event.is_root_phase and event.new_stage == Stage.ENDED:
            self._active_runs.pop(job_run.instance_id, None)
            self._missing_runs.pop(job_run.instance_id, None)
            self._ended_runs[job_run.instance_id] = (job_run, time.monotonic())
        elif job_run.instance_id not in self._ended_runs:
            self._active_runs[job_run.instance_id] = job_run
            self._missing_runs.pop(job_run.instance_id, None)

    def _prune_ended(self) -> None:
        """Remove ended run entries older than the retention period."""
        now = time.monotonic()
        self._ended_runs = {
            iid: (run, ts) for iid, (run, ts) in self._ended_runs.items()
            if now - ts < ENDED_RETENTION_SECONDS
        }

    def _sorted_runs(self) -> list[JobRun]:
        """Combine active and retained ended runs, sorted by the configured option."""
        active = list(self._active_runs.values())
        retained = [run for run, _ in self._ended_runs.values()]
        return self._sort_option.sort_runs(active + retained, reverse=self._descending)

    def _build_table(self) -> Table:
        """Build a rich.Table from the current cached runs."""
        runs = self._sorted_runs()
        table = Table(
            title=f" [ {self._env_name} ] ",
            title_style="bold",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            caption="Ctrl+C to exit",
            caption_style="dim",
            padding=(0, 1),
            expand=True,
        )

        for col in COLUMNS:
            justify = "right" if col in _RIGHT_ALIGNED else "left"
            width = _COL_WIDTH.get(col)
            ratio = _COL_RATIO.get(col)
            table.add_column(col.name, no_wrap=True, justify=justify, width=width, ratio=ratio)

        if not runs:
            table.add_row(Text("No active instances", style="dim"), *[""] * (len(COLUMNS) - 1))
            return table

        for run in runs:
            is_ended = run.instance_id in self._ended_runs
            cells = []
            for col in COLUMNS:
                value = col.value_fnc(run)
                style = "dim" if is_ended else to_rich_style(col.colour_fnc(run))
                cells.append(Text(str(value), style=style))
            table.add_row(*cells)

        return table


@app.callback()
def live(
        instance_patterns: list[str] = typer.Argument(
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
