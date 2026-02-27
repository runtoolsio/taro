"""Persistent dashboard TUI — live-updating overview of active instances and history.

The dashboard is the main entry point for the TUI. Selecting a row pushes the
InstanceScreen detail view; dismissing it pops back to the dashboard. The event
handler continues receiving updates while the detail screen is shown.
"""

from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import InstancePhaseEvent, JobInstance, JobRun
from runtools.runcore.run import Outcome, Stage
from runtools.taro.tui.instance_screen import InstanceScreen
from runtools.taro.tui.selector import (
    LinkedTable, add_columns, build_cells, row_key, update_row,
)
from runtools.taro.theme import Theme
from runtools.taro.view import instance as view_inst

ACTIVE_COLUMNS = [
    view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.PHASES,
    view_inst.EXEC_TIME, view_inst.WARNINGS, view_inst.STATUS,
]
HISTORY_COLUMNS = [
    view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.ENDED,
    view_inst.EXEC_TIME, view_inst.TERM_STATUS, view_inst.WARNINGS, view_inst.RESULT,
]


class DashboardSummary(Static):
    """Single-row summary: active count · completed count · failed count."""

    def __init__(self, live_runs: dict[str, JobRun], history_runs: dict[str, JobRun]) -> None:
        super().__init__(id="summary")
        self._live_runs = live_runs
        self._history_runs = history_runs

    def render(self) -> Text:
        active = len(self._live_runs)
        failed = sum(
            1 for r in self._history_runs.values()
            if r.lifecycle.termination and r.lifecycle.termination.status.outcome == Outcome.FAULT
        )
        completed = len(self._history_runs) - failed

        text = Text()
        text.append(f"{active} active", style=Theme.state_executing if active else "dim")
        text.append("  ·  ", style="dim")
        text.append(f"{completed} completed", style="dim")
        text.append("  ·  ", style="dim")
        text.append(f"{failed} failed", style=Theme.state_failure if failed else "dim")
        return text


class DashboardScreen(Screen):
    """Main dashboard view with live-updating active and history tables."""

    CSS_PATH = "dashboard.tcss"

    BINDINGS = [
        Binding("escape", "quit_app", "Quit", show=True),
        Binding("q", "quit_app", "Quit", show=True),
    ]

    def __init__(self, conn: EnvironmentConnector, instances: list[JobInstance], history_runs: list[JobRun], *,
                 run_match: Optional[JobRunCriteria] = None) -> None:
        super().__init__()
        self._conn = conn
        self._run_match = run_match
        self._instances: dict[str, JobInstance] = {}
        self._live_runs: dict[str, JobRun] = {}
        self._history_runs: dict[str, JobRun] = {}
        self._env_handler = None
        self._selected_key: str | None = None

        active_ids = set()
        for inst in instances:
            snap = inst.snap()
            key = row_key(snap.instance_id)
            self._instances[key] = inst
            self._live_runs[key] = snap
            active_ids.add(snap.instance_id)

        for run in history_runs:
            if run.instance_id not in active_ids:
                key = row_key(run.instance_id)
                self._history_runs[key] = run

    def compose(self) -> ComposeResult:
        yield Header()
        yield DashboardSummary(self._live_runs, self._history_runs)

        active_table = LinkedTable(cursor_type="row", id="active-table")
        add_columns(active_table, ACTIVE_COLUMNS)
        history_table = LinkedTable(cursor_type="row", id="history-table")
        add_columns(history_table, HISTORY_COLUMNS)
        active_table.next_table = history_table
        history_table.prev_table = active_table

        yield Static("[bold dim]── Active ──[/]", id="active-label")
        yield active_table
        yield Static("[bold dim]── History ──[/]", id="history-label")
        yield history_table
        yield Footer()

    def on_mount(self) -> None:
        self.app.title = "Dashboard"
        self._populate_tables()
        self._env_handler = lambda e: self.app.call_from_thread(self._on_event, e)
        self._conn.notifications.add_observer_all_events(self._env_handler)

    def on_unmount(self) -> None:
        if self._env_handler is not None:
            self._conn.notifications.remove_observer_all_events(self._env_handler)
            self._env_handler = None

    def action_quit_app(self) -> None:
        self.app.exit()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        self._selected_key = key
        if key in self._instances:
            self.app.push_screen(
                InstanceScreen(instance=self._instances[key]),
                callback=lambda _: self._on_detail_dismissed(),
            )
        elif key in self._history_runs:
            self.app.push_screen(
                InstanceScreen(job_run=self._history_runs[key]),
                callback=lambda _: self._on_detail_dismissed(),
            )

    def _on_detail_dismissed(self) -> None:
        """Re-snap all live instances and reconcile ended → history, then repaint."""
        for key, inst in list(self._instances.items()):
            snap = inst.snap()
            if snap.lifecycle.is_ended:
                self._live_runs.pop(key, None)
                self._instances.pop(key)
                self._history_runs[key] = snap
            else:
                self._live_runs[key] = snap

        self._populate_tables()
        self._restore_cursor(self._selected_key)
        self.query_one(DashboardSummary).refresh()

    def _on_event(self, event) -> None:
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return
        if self._run_match and not self._run_match(job_run):
            return

        iid = job_run.instance_id
        key = row_key(iid)

        if isinstance(event, InstancePhaseEvent) and event.is_root_phase and event.new_stage == Stage.ENDED:
            self._live_runs.pop(key, None)
            self._instances.pop(key, None)
            self._history_runs[key] = job_run
            self._populate_tables()
            self.query_one(DashboardSummary).refresh()
        elif job_run.lifecycle.is_ended:
            return
        elif key in self._live_runs:
            self._live_runs[key] = job_run
            active_table = self.query_one("#active-table", LinkedTable)
            update_row(active_table, key, job_run, ACTIVE_COLUMNS)
        else:
            inst = self._conn.get_instance(iid)
            if inst is not None:
                self._instances[key] = inst
                self._live_runs[key] = job_run
                active_table = self.query_one("#active-table", LinkedTable)
                active_table.add_row(*build_cells(job_run, ACTIVE_COLUMNS), key=key)
                self.query_one(DashboardSummary).refresh()

    def _populate_tables(self) -> None:
        active_table = self.query_one("#active-table", LinkedTable)
        history_table = self.query_one("#history-table", LinkedTable)
        active_table.clear()
        sorted_active = sorted(self._live_runs.items(), key=lambda kv: kv[1].lifecycle.created_at, reverse=True)
        for key, run in sorted_active:
            active_table.add_row(*build_cells(run, ACTIVE_COLUMNS), key=key)
        history_table.clear()
        sorted_history = sorted(self._history_runs.items(), key=lambda kv: kv[1].lifecycle.created_at, reverse=True)
        for key, run in sorted_history:
            history_table.add_row(*build_cells(run, HISTORY_COLUMNS), key=key)

    def _restore_cursor(self, key: str | None) -> None:
        """Move cursor back to the row identified by key, searching both tables."""
        if key is None:
            return
        for table in (self.query_one("#active-table", LinkedTable), self.query_one("#history-table", LinkedTable)):
            if key in table.rows:
                table.focus()
                table.move_cursor(row=table.get_row_index(key))
                return


class DashboardApp(App):
    """Thin wrapper that pushes DashboardScreen and exits when it is dismissed."""

    def __init__(self, conn: EnvironmentConnector, instances: list[JobInstance], history_runs: list[JobRun], *,
                 run_match: Optional[JobRunCriteria] = None) -> None:
        super().__init__()
        self._conn = conn
        self._instances = instances
        self._history_runs = history_runs
        self._run_match = run_match

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen(
            self._conn, self._instances, self._history_runs, run_match=self._run_match,
        ))
