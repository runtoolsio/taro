"""Persistent dashboard TUI — live-updating overview of active instances and history.

The dashboard is the main entry point for the TUI. Selecting a row pushes the
InstanceScreen detail view; dismissing it pops back to the dashboard. The event
handler continues receiving updates while the detail screen is shown.
"""

import logging
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import InstancePhaseEvent, JobInstance, JobRun
from runtools.runcore.output import MultiSourceOutputReader
from runtools.runcore.run import Stage
from runtools.taro.tui.confirm import ConfirmDeleteScreen
from runtools.taro.tui.instance_screen import InstanceScreen
from runtools.taro.tui.selector import (
    LinkedTable, add_columns, build_cells, last_col_width, row_key,
)
from runtools.taro.tui.widgets import APP_CSS, Section, build_history_metrics, setup_theme
from runtools.taro.view import instance as view_inst

log = logging.getLogger(__name__)

ACTIVE_COLUMNS = [
    view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT, view_inst.EXEC_TIME_COMPACT,
    view_inst.PHASES, view_inst.WARNINGS, view_inst.STATUS,
]
HISTORY_COLUMNS = [
    view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED_COMPACT, view_inst.ENDED_COMPACT,
    view_inst.EXEC_TIME_COMPACT, view_inst.TERM_STATUS, view_inst.WARNINGS, view_inst.RESULT,
]


class DashboardScreen(Screen):
    """Main dashboard view with live-updating active and history tables."""

    CSS_PATH = "dashboard.tcss"

    BINDINGS = [
        Binding("escape", "quit_app", "Quit", show=True),
        Binding("q", "quit_app", "Quit", show=True),
        Binding("d", "delete_selected", "Delete", show=True),
    ]

    def __init__(self, conn: EnvironmentConnector, instances: list[JobInstance], history_runs: list[JobRun], *,
                 env_name: str = "", run_match: Optional[JobRunCriteria] = None) -> None:
        super().__init__()
        self._conn = conn
        self._env_name = env_name
        self._run_match = run_match
        self._instances: dict[str, JobInstance] = {}
        self._live_runs: dict[str, JobRun] = {}
        self._history_runs: dict[str, JobRun] = {}
        self._output_reader = MultiSourceOutputReader(conn.output_backends)
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
        # "renderable" lets Rich Text styles (phase colors, etc.) show through the cursor row
        active_table = LinkedTable(cursor_type="row", id="active-table", cursor_foreground_priority="renderable")
        add_columns(active_table, ACTIVE_COLUMNS)
        history_table = LinkedTable(cursor_type="row", id="history-table", cursor_foreground_priority="renderable")
        add_columns(history_table, HISTORY_COLUMNS, data=self._history_runs.values())
        active_table.next_table = history_table
        history_table.prev_table = active_table

        with Section(id="active-section") as section:
            section.border_title = self._active_title()
            yield active_table
        with Section(id="history-section") as section:
            section.border_title = "History"
            yield history_table
        yield Footer()

    def on_mount(self) -> None:
        self._populate_tables()
        self._refresh_header()
        self._env_handler = lambda e: self.app.call_from_thread(self._on_event, e)
        self._conn.notifications.add_observer_all_events(self._env_handler)
        self.set_interval(0.25, self._refresh_active_rows)
        if not self._live_runs and self._history_runs:
            self.query_one("#history-table", LinkedTable).focus()

    def on_unmount(self) -> None:
        if self._env_handler is not None:
            self._conn.notifications.remove_observer_all_events(self._env_handler)
            self._env_handler = None

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_delete_selected(self) -> None:
        history_table = self.query_one("#history-table", LinkedTable)
        if not history_table.has_focus or not history_table.row_count:
            return
        row_key_val = str(history_table.coordinate_to_cell_key(history_table.cursor_coordinate).row_key.value)
        run = self._history_runs.get(row_key_val)
        if not run:
            return

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self._conn.remove_history_runs(JobRunCriteria.instance_match(run.instance_id))
            except (ValueError, OSError) as e:
                self.app.notify(str(e), severity="error")
                return
            self._history_runs.pop(row_key_val, None)
            history_table.remove_row(row_key=row_key_val)
            self._refresh_header()

        self.app.push_screen(ConfirmDeleteScreen(run.instance_id), callback=_on_confirm)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        self._selected_key = key
        if key in self._instances:
            inst = self._instances[key]
            snap = inst.snap()
            if snap.lifecycle.is_ended:
                # Instance ended between last refresh and selection — treat as history
                self._move_to_history(key, snap)
                self._populate_tables(focus_key=key)
                self._refresh_header()
                self.app.push_screen(
                    InstanceScreen(job_run=snap, output_reader=self._output_reader.read_output),
                    callback=lambda _: self._on_detail_dismissed(),
                )
            else:
                self.app.push_screen(
                    InstanceScreen(instance=inst, output_reader=self._output_reader.read_output),
                    callback=lambda _: self._on_detail_dismissed(),
                )
        elif key in self._history_runs:
            self.app.push_screen(
                InstanceScreen(job_run=self._history_runs[key], output_reader=self._output_reader.read_output),
                callback=lambda _: self._on_detail_dismissed(),
            )

    def _on_detail_dismissed(self) -> None:
        """Re-snap all live instances and reconcile ended → history, then repaint."""
        self._reconcile_instances()
        self._populate_tables(focus_key=self._selected_key)
        self._refresh_header()

    def _move_to_history(self, key: str, run: JobRun) -> None:
        """Move a run from active tracking to history."""
        self._live_runs.pop(key, None)
        self._instances.pop(key, None)
        self._history_runs[key] = run

    def _reconcile_instances(self) -> bool:
        """Re-snap all live instances; move ended ones to history. Returns True if any moved."""
        moved = False
        for key, inst in list(self._instances.items()):
            snap = inst.snap()
            if snap.lifecycle.is_ended:
                self._move_to_history(key, snap)
                moved = True
            else:
                self._live_runs[key] = snap
        return moved

    def _active_title(self) -> str:
        count = len(self._live_runs)
        return f"Active ({count})" if count else "Active"

    def _refresh_header(self) -> None:
        active_section = self.query_one("#active-section", Section)
        active_section.border_title = self._active_title()
        active_section.set_class(not self._live_runs, "-empty")
        metrics = build_history_metrics(self._history_runs.values(), active_count=len(self._live_runs))
        self.query_one("#history-section", Section).border_subtitle = metrics

    def _active_render_width(self) -> dict[str, int]:
        active_table = self.query_one("#active-table", LinkedTable)
        return {'STATUS': last_col_width(active_table, ACTIVE_COLUMNS)}

    def _on_event(self, event) -> None:
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return
        if self._run_match and not self._run_match(job_run):
            return

        try:
            self._handle_event(event, job_run)
        except NoMatches:
            log.debug("DOM query failed during teardown, ignoring event")

    def _handle_event(self, event, job_run: JobRun) -> None:
        iid = job_run.instance_id
        key = row_key(iid)

        if isinstance(event, InstancePhaseEvent) and event.is_root_phase and event.new_stage == Stage.ENDED:
            self._move_to_history(key, job_run)
            self._populate_tables()
            self._refresh_header()
            if not self._live_runs:
                self.query_one("#history-table", LinkedTable).focus()
        elif job_run.lifecycle.is_ended:
            return
        elif key in self._live_runs:
            self._live_runs[key] = job_run
        else:
            inst = self._conn.get_instance(iid)
            if inst is not None:
                self._instances[key] = inst
                self._live_runs[key] = job_run
                self._populate_tables()
                self._refresh_header()

    def _populate_tables(self, *, focus_key: str | None = None) -> None:
        active_table = self.query_one("#active-table", LinkedTable)
        history_table = self.query_one("#history-table", LinkedTable)
        tables = (active_table, history_table)

        # Save cursor position before clearing
        saved: dict[str, tuple[bool, str]] = {}
        if not focus_key:
            for table in tables:
                if table.row_count > 0:
                    saved[table.id] = (
                        table.has_focus,
                        str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value),
                    )

        rw = self._active_render_width()
        active_table.clear()
        sorted_active = sorted(self._live_runs.items(), key=lambda kv: kv[1].lifecycle.created_at, reverse=True)
        for key, run in sorted_active:
            active_table.add_row(*build_cells(run, ACTIVE_COLUMNS, render_width=rw), key=key)
        history_table.clear()
        sorted_history = sorted(self._history_runs.items(), key=lambda kv: kv[1].lifecycle.created_at, reverse=True)
        for key, run in sorted_history:
            history_table.add_row(*build_cells(run, HISTORY_COLUMNS), key=key)

        # Restore cursor position (focus_key resolved after repopulation — row may have moved between tables)
        if focus_key:
            for table in tables:
                if focus_key in table.rows:
                    saved[table.id] = (True, focus_key)
                    break
        for table in tables:
            info = saved.get(table.id)
            if info and info[1] in table.rows:
                table.move_cursor(row=table.get_row_index(info[1]))
                if info[0]:
                    table.focus()

    def _refresh_active_rows(self) -> None:
        if not self._instances:
            return
        moved = self._reconcile_instances()
        self._populate_tables()
        if moved:
            self._refresh_header()
            if not self._live_runs:
                self.query_one("#history-table", LinkedTable).focus()



class DashboardApp(App):
    """Thin wrapper that pushes DashboardScreen and exits when it is dismissed."""

    CSS = APP_CSS

    def __init__(self, conn: EnvironmentConnector, instances: list[JobInstance], history_runs: list[JobRun], *,
                 env_name: str = "", run_match: Optional[JobRunCriteria] = None) -> None:
        super().__init__()
        self._conn = conn
        self._instances = instances
        self._history_runs = history_runs
        self._env_name = env_name
        self._run_match = run_match

    def on_mount(self) -> None:
        setup_theme(self)
        self.push_screen(DashboardScreen(
            self._conn, self._instances, self._history_runs,
            env_name=self._env_name, run_match=self._run_match,
        ))
