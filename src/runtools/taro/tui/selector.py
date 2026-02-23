"""Instance/run selector — full-screen Textual DataTable for picking a single item.

For active instances the table updates live via environment-level events: new instances appear
automatically, phase/status changes refresh immediately, and ended instances are removed.
Historical runs are displayed statically.
"""

from typing import Optional, Sequence, Union

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header

from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import InstanceID, InstancePhaseEvent, JobInstance, JobRun
from runtools.runcore.run import Stage
from runtools.taro.view import instance as view_inst

COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.TERM_STATUS, view_inst.PHASES,
           view_inst.STATUS]

_SEP_PREFIX = "__sep_"


def _row_key(iid: InstanceID) -> str:
    return f"{iid.job_id}@{iid.run_id}"


def _build_cells(run: JobRun) -> list[Text]:
    return [Text(str(col.value_fnc(run)), style=col.colour_fnc(run)) for col in COLUMNS]


def _separator_cells(label: str) -> list[Text]:
    return [Text(f"── {label} ──", style="bold dim")] + [Text("") for _ in COLUMNS[1:]]


def _update_row(table: DataTable, key: str, run: JobRun) -> None:
    for col, cell in zip(COLUMNS, _build_cells(run)):
        table.update_cell(key, col.name, cell)


class _SelectorApp[T](App[T]):
    """Base selector app — shared layout and key bindings for live and static selectors."""

    CSS_PATH = "selector.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("q", "cancel", "Cancel", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        table = DataTable(cursor_type="row")
        for col in COLUMNS:
            table.add_column(col.name, key=col.name)
        yield table
        yield Footer()

    def action_cancel(self) -> None:
        self.exit(None)


class _LiveSelectorApp(_SelectorApp[Optional[JobInstance]]):
    """Live-updating selector for active instances.

    Subscribes to environment-level events via the connector — handles updates to existing
    instances, discovery of new ones, and removal of ended ones.
    """

    def __init__(self, conn: EnvironmentConnector, instances: list[JobInstance], *,
                 run_match: Optional[JobRunCriteria] = None, title: str = "Select instance") -> None:
        super().__init__()
        self._conn = conn
        self._run_match = run_match
        self._selector_title = title
        self._instances: dict[str, JobInstance] = {}
        self._runs: dict[str, JobRun] = {}
        self._env_handler = None

        for inst in instances:
            snap = inst.snap()
            key = _row_key(snap.instance_id)
            self._instances[key] = inst
            self._runs[key] = snap

    def on_mount(self) -> None:
        self.title = self._selector_title
        table = self.query_one(DataTable)
        for key, run in self._runs.items():
            table.add_row(*_build_cells(run), key=key)
        self._env_handler = lambda e: self.call_from_thread(self._on_event, e)
        self._conn.notifications.add_observer_all_events(self._env_handler)

    def on_unmount(self) -> None:
        if self._env_handler is not None:
            self._conn.notifications.remove_observer_all_events(self._env_handler)
            self._env_handler = None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        self.exit(self._instances.get(key))

    def _on_event(self, event) -> None:
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return
        if self._run_match and not self._run_match(job_run):
            return

        iid = job_run.instance_id
        key = _row_key(iid)
        table = self.query_one(DataTable)

        if isinstance(event, InstancePhaseEvent) and event.is_root_phase and event.new_stage == Stage.ENDED:
            self._runs.pop(key, None)
            self._instances.pop(key, None)
            if key in table.rows:
                table.remove_row(row_key=key)
        elif job_run.lifecycle.is_ended:
            return
        elif key in self._runs:
            self._runs[key] = job_run
            _update_row(table, key, job_run)
        else:
            # New instance — RPC fetch for the live proxy (fast for local sockets)
            inst = self._conn.get_instance(iid)
            if inst is not None:
                self._instances[key] = inst
                self._runs[key] = job_run
                table.add_row(*_build_cells(job_run), key=key)


class _CombinedSelectorApp(_SelectorApp[Optional[Union[JobInstance, JobRun]]]):
    """Selector showing both active instances (live-updating) and historical runs (static)."""

    def __init__(self, conn: EnvironmentConnector, instances: list[JobInstance], history_runs: list[JobRun], *,
                 run_match: Optional[JobRunCriteria] = None, title: str = "Select instance") -> None:
        super().__init__()
        self._conn = conn
        self._run_match = run_match
        self._selector_title = title
        self._instances: dict[str, JobInstance] = {}
        self._live_runs: dict[str, JobRun] = {}
        self._history_runs: dict[str, JobRun] = {}
        self._env_handler = None

        active_ids = set()
        for inst in instances:
            snap = inst.snap()
            key = _row_key(snap.instance_id)
            self._instances[key] = inst
            self._live_runs[key] = snap
            active_ids.add(snap.instance_id)

        for run in history_runs:
            if run.instance_id not in active_ids:
                key = _row_key(run.instance_id)
                self._history_runs[key] = run

    def on_mount(self) -> None:
        self.title = self._selector_title
        self._rebuild_table(self.query_one(DataTable))
        self._env_handler = lambda e: self.call_from_thread(self._on_event, e)
        self._conn.notifications.add_observer_all_events(self._env_handler)

    def on_unmount(self) -> None:
        if self._env_handler is not None:
            self._conn.notifications.remove_observer_all_events(self._env_handler)
            self._env_handler = None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        if key.startswith(_SEP_PREFIX):
            return
        if key in self._instances:
            self.exit(self._instances[key])
        elif key in self._history_runs:
            self.exit(self._history_runs[key])

    def _on_event(self, event) -> None:
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return
        if self._run_match and not self._run_match(job_run):
            return

        iid = job_run.instance_id
        key = _row_key(iid)
        table = self.query_one(DataTable)

        if isinstance(event, InstancePhaseEvent) and event.is_root_phase and event.new_stage == Stage.ENDED:
            self._live_runs.pop(key, None)
            self._instances.pop(key, None)
            if key in table.rows:
                table.remove_row(row_key=key)
            if not self._live_runs and f"{_SEP_PREFIX}active" in table.rows:
                table.remove_row(row_key=f"{_SEP_PREFIX}active")
        elif job_run.lifecycle.is_ended:
            return
        elif key in self._live_runs:
            self._live_runs[key] = job_run
            _update_row(table, key, job_run)
        else:
            inst = self._conn.get_instance(iid)
            if inst is not None:
                self._instances[key] = inst
                self._live_runs[key] = job_run
                self._rebuild_table(table)

    def _rebuild_table(self, table: DataTable) -> None:
        """Clear and re-populate table maintaining Active-then-History order."""
        table.clear()
        if self._live_runs:
            table.add_row(*_separator_cells("Active"), key=f"{_SEP_PREFIX}active")
            for key, run in self._live_runs.items():
                table.add_row(*_build_cells(run), key=key)
        if self._history_runs:
            table.add_row(*_separator_cells("History"), key=f"{_SEP_PREFIX}history")
            for key, run in self._history_runs.items():
                table.add_row(*_build_cells(run), key=key)


class _StaticSelectorApp(_SelectorApp[Optional[int]]):
    """Static selector for historical runs — no live updates."""

    def __init__(self, runs: list[JobRun], title: str) -> None:
        super().__init__()
        self._runs = list(runs)
        self._selector_title = title

    def on_mount(self) -> None:
        self.title = self._selector_title
        table = self.query_one(DataTable)
        for i, run in enumerate(self._runs):
            table.add_row(*_build_cells(run), key=str(i))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.exit(int(event.row_key.value))


def select_instance(conn: EnvironmentConnector, instances: Sequence[JobInstance], *,
                    run_match: Optional[JobRunCriteria] = None,
                    title: str = "Select instance") -> Optional[JobInstance]:
    """Show a live-updating DataTable selector over active instances.

    Subscribes to environment events so new instances appear automatically and ended ones
    are removed. Returns the selected JobInstance or None on cancel.

    Args:
        conn: Open environment connector for event subscription and instance discovery.
        instances: Initial instances to display.
        run_match: Optional criteria to filter new instances discovered via events.
        title: Title displayed in the header.
    """
    sorted_instances = sorted(instances, key=lambda i: i.snap().lifecycle.created_at, reverse=True)
    return _LiveSelectorApp(conn, sorted_instances, run_match=run_match, title=title).run()


def select_instance_or_run(
        conn: EnvironmentConnector,
        instances: Sequence[JobInstance],
        history_runs: Sequence[JobRun],
        *,
        run_match: Optional[JobRunCriteria] = None,
        title: str = "Select instance",
) -> Optional[Union[JobInstance, JobRun]]:
    """Show a combined selector with active instances and historical runs.

    Active instances are shown first with live updates, followed by historical runs.
    Returns the selected JobInstance (live) or JobRun (historical), or None on cancel.
    """
    sorted_instances = sorted(instances, key=lambda i: i.snap().lifecycle.created_at, reverse=True)
    sorted_history = sorted(history_runs, key=lambda r: r.lifecycle.created_at, reverse=True)
    return _CombinedSelectorApp(conn, sorted_instances, sorted_history, run_match=run_match, title=title).run()


def select_run(runs: Sequence[JobRun], *, title: str = "Select run") -> Optional[JobRun]:
    """Show a static DataTable selector over historical runs.

    Args:
        runs: Non-empty sequence of runs to choose from.
        title: Title displayed in the header.

    Returns:
        The selected JobRun, or None if the user cancelled.
    """
    indexed = sorted(enumerate(runs), key=lambda pair: pair[1].lifecycle.created_at, reverse=True)
    ordered_runs = [run for _, run in indexed]
    index_map = [orig_idx for orig_idx, _ in indexed]

    selected = _StaticSelectorApp(ordered_runs, title).run()
    if selected is None:
        return None
    return runs[index_map[selected]]
