"""Shared TUI helpers and instance selector apps.

Provides table-building utilities (LinkedTable, add_columns, build_cells, etc.) used by both
the selector and the dashboard, plus pick-and-exit selector apps for action commands.
"""

from typing import Optional, Sequence

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer

from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import InstanceID, InstancePhaseEvent, JobInstance, JobRun
from runtools.runcore.output import MultiSourceOutputReader
from runtools.runcore.run import Stage
from runtools.taro.tui.confirm import ConfirmDeleteScreen
from runtools.taro.tui.instance_screen import InstanceScreen
from runtools.taro.tui.widgets import APP_CSS, ScreenHeader, Section, build_history_metrics, setup_theme
from runtools.taro.view import instance as view_inst
from runtools.taro.view.instance import render_cell

COLUMNS = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT, view_inst.TERM_STATUS, view_inst.PHASES,
           view_inst.STATUS]


def row_key(iid: InstanceID) -> str:
    return f"{iid.job_id}@{iid.run_id}"


def build_cells(run: JobRun, columns: Sequence = COLUMNS, *,
                render_width: dict[str, int] | None = None) -> list[Text]:
    return [
        render_cell(run, col, width=(render_width.get(col.name) if render_width else None))
        for col in columns
    ]


def add_columns(table: DataTable, columns: Sequence = COLUMNS, *, data: Sequence = ()) -> None:
    for i, col in enumerate(columns):
        is_last = i == len(columns) - 1
        if is_last:
            width = None
        elif data:
            width = max(len(col.name), max((len(col.value_fnc(r)) for r in data), default=0))
        else:
            width = col.max_width
        table.add_column(col.name, key=col.name, width=width)


def last_col_width(table: DataTable, columns: Sequence) -> int:
    """Estimate last column width from table content width minus fixed columns."""
    if table.size.width == 0:
        return columns[-1].max_width
    fixed = sum(col.max_width for col in columns[:-1])
    # DataTable adds 2-char cell padding per column
    padding = len(columns) * 2
    return max(table.size.width - fixed - padding, 20)


def update_row(table: DataTable, key: str, run: JobRun, columns: Sequence = COLUMNS, *,
               render_width: dict[str, int] | None = None) -> None:
    for col, cell in zip(columns, build_cells(run, columns, render_width=render_width)):
        table.update_cell(key, col.name, cell)


class LinkedTable(DataTable):
    """DataTable that jumps cursor to a sibling table at row boundaries."""

    next_table: Optional["LinkedTable"] = None
    prev_table: Optional["LinkedTable"] = None

    def action_cursor_down(self) -> None:
        if self.cursor_coordinate.row >= self.row_count - 1:
            if self.next_table and self.next_table.display and self.next_table.row_count > 0:
                self.next_table.focus()
                self.next_table.move_cursor(row=0)
                return
        super().action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.cursor_coordinate.row <= 0:
            if self.prev_table and self.prev_table.display and self.prev_table.row_count > 0:
                self.prev_table.focus()
                self.prev_table.move_cursor(row=self.prev_table.row_count - 1)
                return
        super().action_cursor_up()


class _LiveSelectorApp(App[Optional[JobInstance]]):
    """Live-updating pick-and-exit selector for active instances.

    Subscribes to environment-level events via the connector — handles updates to existing
    instances, discovery of new ones, and removal of ended ones.
    """

    CSS = APP_CSS
    CSS_PATH = "selector.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("q", "cancel", "Cancel", show=True),
    ]

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
            key = row_key(snap.instance_id)
            self._instances[key] = inst
            self._runs[key] = snap

    def compose(self) -> ComposeResult:
        yield ScreenHeader(self._selector_title, self._conn.env_id)
        table = DataTable(cursor_type="row", cursor_foreground_priority="renderable")
        add_columns(table)
        with Section(id="table-section") as section:
            section.border_title = "Instances"
            yield table
        yield Footer()

    def on_mount(self) -> None:
        setup_theme(self)
        table = self.query_one(DataTable)
        for key, run in self._runs.items():
            table.add_row(*build_cells(run), key=key)
        self._env_handler = lambda e: self.call_from_thread(self._on_event, e)
        self._conn.notifications.add_observer_all_events(self._env_handler)

    def on_unmount(self) -> None:
        if self._env_handler is not None:
            self._conn.notifications.remove_observer_all_events(self._env_handler)
            self._env_handler = None

    def action_cancel(self) -> None:
        self.exit(None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.exit(self._instances.get(str(event.row_key.value)))

    def _on_event(self, event) -> None:
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return
        if self._run_match and not self._run_match(job_run):
            return

        iid = job_run.instance_id
        key = row_key(iid)
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
            update_row(table, key, job_run)
        else:
            inst = self._conn.get_instance(iid)
            if inst is not None:
                self._instances[key] = inst
                self._runs[key] = job_run
                table.add_row(*build_cells(job_run), key=key)


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


class _HistoryApp(App):
    """Static read-only table for browsing historical job runs."""

    CSS = APP_CSS
    CSS_PATH = "selector.tcss"

    BINDINGS = [
        Binding("escape", "quit", "Quit", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("d", "delete_selected", "Delete", show=True),
    ]

    def __init__(self, runs: Sequence[JobRun], columns: Sequence, *,
                 connector: Optional[EnvironmentConnector] = None, title: str = "History") -> None:
        super().__init__()
        self._runs = {row_key(r.instance_id): r for r in runs}
        self._columns = columns
        self._connector = connector
        self._output_reader = (
            MultiSourceOutputReader(connector.output_backends).read_output if connector else None
        )
        self._title = title
        self._env_name = connector.env_id if connector else ""

    def compose(self) -> ComposeResult:
        yield ScreenHeader(self._title, self._env_name)
        with Section(id="table-section") as section:
            section.border_title = "History"
            yield DataTable(cursor_type="row", cursor_foreground_priority="renderable")
        yield Footer()

    def on_mount(self) -> None:
        setup_theme(self)
        table = self.query_one(DataTable)
        add_columns(table, self._columns, data=self._runs.values())
        for key, run in self._runs.items():
            table.add_row(*build_cells(run, self._columns), key=key)
        self._refresh_metrics()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        run = self._runs.get(key)
        if run:
            self.push_screen(InstanceScreen(job_run=run, output_reader=self._output_reader))

    def action_delete_selected(self) -> None:
        if not self._connector:
            return
        table = self.query_one(DataTable)
        if not table.row_count:
            return
        row_key_val = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        run = self._runs.get(row_key_val)
        if not run:
            return

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self._connector.remove_history_runs(JobRunCriteria.instance_match(run.instance_id))
            except (ValueError, OSError) as e:
                self.notify(str(e), severity="error")
                return
            self._runs.pop(row_key_val, None)
            table.remove_row(row_key=row_key_val)
            self._refresh_metrics()

        self.push_screen(ConfirmDeleteScreen(run.instance_id), callback=_on_confirm)

    def _refresh_metrics(self) -> None:
        self.query_one(ScreenHeader).update_metrics(build_history_metrics(self._runs.values()))


def show_history(runs: Sequence[JobRun], columns: Sequence, *,
                 connector: Optional[EnvironmentConnector] = None, title: str = "History") -> None:
    """Show a static DataTable of historical job runs with a summary bar.

    Args:
        runs: Job runs to display.
        columns: Column definitions for the table.
        connector: Open connector for output reading and delete operations.
        title: Title displayed in the header.
    """
    _HistoryApp(runs, columns, connector=connector, title=title).run()


class _HistoryPickerApp(App[Optional[JobRun]]):
    """Pick-and-exit selector for historical job runs."""

    CSS = APP_CSS
    CSS_PATH = "selector.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("q", "cancel", "Cancel", show=True),
    ]

    def __init__(self, runs: Sequence[JobRun], columns: Sequence, *, title: str = "Select run") -> None:
        super().__init__()
        self._runs = {row_key(r.instance_id): r for r in runs}
        self._columns = columns
        self._title = title

    def compose(self) -> ComposeResult:
        yield ScreenHeader(self._title, "")
        with Section(id="table-section") as section:
            section.border_title = "History"
            yield DataTable(cursor_type="row", cursor_foreground_priority="renderable")
        yield Footer()

    def on_mount(self) -> None:
        setup_theme(self)
        table = self.query_one(DataTable)
        add_columns(table, self._columns, data=self._runs.values())
        for key, run in self._runs.items():
            table.add_row(*build_cells(run, self._columns), key=key)

    def action_cancel(self) -> None:
        self.exit(None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.exit(self._runs.get(str(event.row_key.value)))


def select_history_run(runs: Sequence[JobRun], columns: Sequence, *,
                       title: str = "Select run") -> Optional[JobRun]:
    """Show a pick-and-exit selector over historical job runs.

    Args:
        runs: Job runs to display.
        columns: Column definitions for the table.
        title: Title displayed in the header.

    Returns:
        Selected JobRun or None on cancel.
    """
    return _HistoryPickerApp(runs, columns, title=title).run()
