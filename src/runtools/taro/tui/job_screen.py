"""Job-focused dashboard — two-pane live view for a single job.

Pushed from the JobsScreen when a user selects a job. Shows a ScreenHeader with
the job name and whole-history metrics, an active-instances table, and a recent
history table. Same live-update and drill-down behavior as the main dashboard.
"""

import logging
from typing import Optional

from rich.text import Text
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import DataTable, Footer

from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.job import InstancePhaseEvent, JobInstance, JobRun, JobStats
from runtools.runcore.matching import JobRunCriteria
from runtools.runcore.output import MultiSourceOutputReader
from runtools.runcore.run import Outcome, Stage
from runtools.runcore.util import format_timedelta
from runtools.taro.style import term_style
from runtools.taro.theme import Theme
from runtools.taro.tui.confirm import ConfirmDeleteScreen
from runtools.taro.tui.dashboard import ACTIVE_COLUMNS, HISTORY_COLUMNS
from runtools.taro.tui.instance_screen import InstanceScreen
from runtools.taro.tui.selector import (
    LinkedTable, add_columns, build_cells, last_col_width, reset_auto_widths, row_key,
)
from runtools.taro.tui.widgets import METRIC_SEP, ScreenHeader, Section, build_history_metrics

log = logging.getLogger(__name__)


_OUTCOME_STYLES = {
    Outcome.SUCCESS: Theme.success,
    Outcome.FAULT: Theme.state_failure,
    Outcome.ABORTED: Theme.state_incomplete,
    Outcome.REJECTED: Theme.state_discarded,
    Outcome.IGNORED: Theme.subtle,
}


def build_job_metrics(stats: Optional[JobStats], active_count: int) -> Text:
    """Build a styled metrics bar for a single job.

    Format: N active · since DATE · N runs · {detailed outcome breakdown} · avg DURATION · last: STATUS

    The `since` date anchors the counts to whole-history scope (vs. the 7d history table).
    Only non-zero outcomes are shown to keep the line compact while preserving detail.
    """
    text = Text()
    text.append(f"{active_count} active", style=Theme.state_executing if active_count else "dim")

    if not stats:
        return text

    if stats.first_created:
        text.append(METRIC_SEP, style="dim")
        text.append(f"since {stats.first_created.astimezone().strftime('%Y-%m-%d')}", style="dim")

    text.append(METRIC_SEP, style="dim")
    text.append(f"{stats.count} runs", style="dim")

    outcome_counts = [
        (Outcome.SUCCESS, stats.success_count),
        (Outcome.FAULT, stats.failed_count),
        (Outcome.ABORTED, stats.aborted_count),
        (Outcome.REJECTED, stats.rejected_count),
        (Outcome.IGNORED, stats.ignored_count),
    ]
    for outcome, count in outcome_counts:
        if not count:
            continue
        text.append(METRIC_SEP, style="dim")
        text.append(f"{count} {outcome.name.lower()}", style=_OUTCOME_STYLES[outcome])

    if stats.average_time:
        text.append(METRIC_SEP, style="dim")
        text.append(f"avg {format_timedelta(stats.average_time, show_ms=False)}", style="dim")

    if stats.termination_status:
        status = stats.termination_status
        text.append(METRIC_SEP, style="dim")
        text.append("last: ", style="dim")
        text.append(status.name, style=term_style(status))

    return text


class JobScreen(Screen):
    """Job-focused dashboard with active instances and recent history."""

    CSS_PATH = "job_screen.tcss"

    BINDINGS = [
        Binding("escape", "dismiss", "Back", show=True),
        Binding("q", "dismiss", "Back", show=True),
        Binding("D", "delete_selected", "Delete", show=True),
    ]

    def __init__(self, conn: EnvironmentConnector, job_id: str,
                 instances: list[JobInstance], history_runs: list[JobRun], *,
                 env_name: str = "", history_title: str = "Recent History") -> None:
        super().__init__()
        self._conn = conn
        self._job_id = job_id
        self._env_name = env_name
        self._history_title = history_title
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
        yield ScreenHeader(self._job_id, self._env_name)

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
            section.border_title = self._history_title
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

    # -- Actions ---------------------------------------------------------------

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

    # -- Row selection & detail ------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        self._selected_key = key
        if key in self._instances:
            inst = self._instances[key]
            snap = inst.snap()
            if snap.lifecycle.is_ended:
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
        self._reconcile_instances()
        self._populate_tables(focus_key=self._selected_key)
        self._refresh_header()

    # -- State management ------------------------------------------------------

    def _move_to_history(self, key: str, run: JobRun) -> None:
        self._live_runs.pop(key, None)
        self._instances.pop(key, None)
        self._history_runs[key] = run

    def _reconcile_instances(self) -> bool:
        moved = False
        for key, inst in list(self._instances.items()):
            snap = inst.snap()
            if snap.lifecycle.is_ended:
                self._move_to_history(key, snap)
                moved = True
            else:
                self._live_runs[key] = snap
        return moved

    # -- Header & titles -------------------------------------------------------

    def _active_title(self) -> str:
        count = len(self._live_runs)
        return f"Active ({count})" if count else "Active"

    def _refresh_header(self) -> None:
        # Active section title + empty class
        active_section = self.query_one("#active-section", Section)
        active_section.border_title = self._active_title()
        active_section.set_class(not self._live_runs, "-empty")

        # History section subtitle
        metrics = build_history_metrics(self._history_runs.values(), active_count=len(self._live_runs))
        self.query_one("#history-section", Section).border_subtitle = metrics

        # Re-query whole-history stats for this job so the header stays current
        stats_match = JobRunCriteria.job_match(self._job_id)
        stats_list = self._conn.read_run_stats(stats_match)
        job_stats = stats_list[0] if stats_list else None
        job_metrics = build_job_metrics(job_stats, len(self._live_runs))
        self.query_one(ScreenHeader).update_metrics(job_metrics)

    # -- Event handling --------------------------------------------------------

    def _on_event(self, event) -> None:
        job_run = getattr(event, 'job_run', None)
        if job_run is None:
            return
        # Only handle events for this job
        if job_run.job_id != self._job_id:
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
        elif key not in self._history_runs:
            inst = self._conn.get_instance(iid)
            if inst is not None:
                self._instances[key] = inst
                self._live_runs[key] = job_run
                self._populate_tables()
                self._refresh_header()

    # -- Table population ------------------------------------------------------

    def _active_render_width(self) -> dict[str, int]:
        active_table = self.query_one("#active-table", LinkedTable)
        return {'STATUS': last_col_width(active_table, ACTIVE_COLUMNS)}

    def _populate_tables(self, *, focus_key: str | None = None) -> None:
        active_table = self.query_one("#active-table", LinkedTable)
        history_table = self.query_one("#history-table", LinkedTable)
        tables = (active_table, history_table)

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
        reset_auto_widths(active_table)
        sorted_active = sorted(self._live_runs.items(), key=lambda kv: kv[1].lifecycle.created_at, reverse=True)
        for key, run in sorted_active:
            active_table.add_row(*build_cells(run, ACTIVE_COLUMNS, render_width=rw), key=key)
        history_table.clear()
        reset_auto_widths(history_table)
        sorted_history = sorted(self._history_runs.items(), key=lambda kv: kv[1].lifecycle.created_at, reverse=True)
        for key, run in sorted_history:
            history_table.add_row(*build_cells(run, HISTORY_COLUMNS), key=key)

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
