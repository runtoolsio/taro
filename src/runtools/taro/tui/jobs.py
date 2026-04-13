"""Jobs TUI — interactive overview of all known jobs.

Shows a header with aggregate stats (total jobs, currently running, last-run
success/non-success counts) and a table with one row per job: current running
instance count, last-run details (time, status, duration), average duration,
and whole-history run counts.  Selecting a job pushes JobScreen for drill-down.
"""

import logging
from collections import Counter
from typing import NamedTuple

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.job import JobRun, JobStats
from runtools.runcore.matching import criteria
from runtools.runcore.run import Outcome, Stage
from runtools.runcore.util import MatchingStrategy, format_dt_compact, format_timedelta
from runtools.taro.printer import Column
from runtools.taro.style import job_id_stats_style, stats_state_style
from runtools.taro.theme import Theme
from runtools.taro.tui.selector import add_columns
from runtools.taro.tui.widgets import APP_CSS, METRIC_SEP, ScreenHeader, Section, setup_theme

log = logging.getLogger(__name__)

_DRILL_DOWN_DAYS = 7

class JobRow(NamedTuple):
    """Row data for the jobs table — stats plus current running instance count."""
    stats: JobStats
    running: int


# ---------------------------------------------------------------------------
# Column definitions (operate on JobRow objects)
# ---------------------------------------------------------------------------

_muted = lambda _: Theme.subtle


def _last_status_display(r: JobRow) -> str:
    status = r.stats.termination_status
    return status.name if status else ''


def _format_last_time(r: JobRow) -> str:
    return format_timedelta(r.stats.last_time, show_ms=False) if r.stats.last_time else ''


def _running_display(r: JobRow) -> str:
    return str(r.running) if r.running else ''


def _running_style(r: JobRow) -> str:
    return Theme.state_executing if r.running else Theme.subtle


def _success_style(r: JobRow) -> str:
    return Theme.success if r.stats.success_count else Theme.subtle


def _non_success_count(r: JobRow) -> int:
    return r.stats.count - r.stats.success_count


def _non_success_style(r: JobRow) -> str:
    return Theme.state_failure if _non_success_count(r) else Theme.subtle


def _format_avg(r: JobRow) -> str:
    return format_timedelta(r.stats.average_time, show_ms=False) if r.stats.average_time else ''


JOB = Column('JOB', 30, lambda r: r.stats.job_id, lambda r: job_id_stats_style(r.stats))
RUNNING = Column('RUNNING', 8, _running_display, _running_style)
LAST_RUN = Column('LAST RUN', 14, lambda r: format_dt_compact(r.stats.last_created), _muted)
LAST_STATUS = Column('LAST STATUS', 14, _last_status_display, lambda r: stats_state_style(r.stats))
LAST_TIME = Column('LAST TIME', 12, _format_last_time, lambda _: '')
RUNS = Column('RUNS', 6, lambda r: str(r.stats.count), _muted)
SUCCESS = Column('SUCCESS', 8, lambda r: str(r.stats.success_count), _success_style)
NON_SUCCESS = Column('NON-SUCCESS', 12, lambda r: str(_non_success_count(r)), _non_success_style)
AVG = Column('AVG TIME', 12, _format_avg, _muted)

JOBS_COLUMNS = [JOB, RUNNING, LAST_RUN, LAST_STATUS, LAST_TIME, AVG, RUNS, SUCCESS, NON_SUCCESS]


def build_jobs_metrics(stats_list: list[JobStats], active_runs: list[JobRun]) -> Text:
    """Build a styled header metrics bar from job stats and active runs.

    Uses grouped outcome semantics (success vs non-success) to match the table's
    SUCCESS/NON-SUCCESS columns.  Detailed outcomes live on the per-job drill-down.
    """
    # total_jobs matches the table (historical jobs only).  Active-only jobs
    # are surfaced via the separate "running" count, not added to the catalog.
    total_jobs = len(stats_list)
    running_count = len({r.job_id for r in active_runs})

    success_jobs = 0
    non_success_jobs = 0
    for s in stats_list:
        if s.termination_status is None:
            continue
        if s.termination_status.outcome == Outcome.SUCCESS:
            success_jobs += 1
        else:
            non_success_jobs += 1

    text = Text()
    text.append(f"{total_jobs} jobs", style="bold" if total_jobs else "dim")
    text.append(METRIC_SEP, style="dim")
    text.append(f"{running_count} running", style=Theme.state_executing if running_count else "dim")
    text.append(METRIC_SEP, style="dim")
    text.append("Last runs: ", style="dim")
    text.append(f"{success_jobs} success", style=Theme.success if success_jobs else "dim")
    text.append("  ", style="dim")
    text.append(f"{non_success_jobs} non-success",
                style=Theme.state_failure if non_success_jobs else "dim")
    return text


def _build_row_cells(row: JobRow, columns=JOBS_COLUMNS) -> list[Text]:
    """Render a row of cells for a JobRow."""
    return [Text(str(col.value_fnc(row)), style=col.colour_fnc(row)) for col in columns]


class JobsScreen(Screen):
    """Interactive jobs overview — last-run state of every known job."""

    CSS_PATH = "jobs.tcss"

    BINDINGS = [
        Binding("escape", "quit_app", "Quit", show=True),
        Binding("q", "quit_app", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, conn: EnvironmentConnector, stats_list: list[JobStats], active_runs: list[JobRun], *,
                 env_name: str = "") -> None:
        super().__init__()
        self._conn = conn
        self._env_name = env_name
        self._stats_list = stats_list
        self._active_runs = active_runs

    def compose(self) -> ComposeResult:
        yield ScreenHeader("Jobs", self._env_name)
        table = DataTable(cursor_type="row", id="jobs-table", cursor_foreground_priority="renderable")
        add_columns(table, JOBS_COLUMNS, data=self._build_rows())
        with Section(id="jobs-section") as section:
            section.border_title = "All Jobs"
            yield table
        yield Footer()

    def on_mount(self) -> None:
        self._populate_table()
        self._refresh_header()
        self.set_interval(10.0, self._periodic_refresh)

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_refresh(self) -> None:
        self._do_refresh()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        job_id = str(event.row_key.value)
        self._drill_down(job_id)

    def _drill_down(self, job_id: str) -> None:
        """Push JobScreen for a single job."""
        from runtools.taro.tui.job_screen import JobScreen

        active_match = criteria().job(job_id, MatchingStrategy.EXACT).build()
        history_match = (criteria()
                         .job(job_id, MatchingStrategy.EXACT)
                         .during(Stage.CREATED, days_back=_DRILL_DOWN_DAYS)
                         .build())

        instances = list(self._conn.get_instances(active_match))
        history_runs = self._conn.read_runs(history_match, asc=False, limit=200)

        screen = JobScreen(
            self._conn, job_id, instances, history_runs,
            env_name=self._env_name, history_title=f"Last {_DRILL_DOWN_DAYS} days",
        )
        self.app.push_screen(screen, callback=lambda _: self._on_dashboard_dismissed())

    def _on_dashboard_dismissed(self) -> None:
        self._do_refresh()

    def _periodic_refresh(self) -> None:
        try:
            self._do_refresh()
        except Exception:
            log.debug("Periodic refresh failed", exc_info=True)

    def _do_refresh(self) -> None:
        """Re-query stats and active runs, then repaint."""
        self._stats_list = self._conn.read_run_stats()
        self._active_runs = self._conn.get_active_runs()
        self._populate_table()
        self._refresh_header()

    def _build_rows(self) -> list[JobRow]:
        """Combine stats with active-instance counts, sorted by job_id."""
        running_by_job = Counter(r.job_id for r in self._active_runs)
        rows = [JobRow(stats=s, running=running_by_job.get(s.job_id, 0)) for s in self._stats_list]
        return sorted(rows, key=lambda r: r.stats.job_id)

    def _populate_table(self) -> None:
        table = self.query_one("#jobs-table", DataTable)

        # Save cursor position
        saved_key = None
        if table.row_count > 0:
            saved_key = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)

        table.clear()
        for row in self._build_rows():
            table.add_row(*_build_row_cells(row), key=row.stats.job_id)

        # Restore cursor
        if saved_key and saved_key in table.rows:
            table.move_cursor(row=table.get_row_index(saved_key))

    def _refresh_header(self) -> None:
        metrics = build_jobs_metrics(self._stats_list, self._active_runs)
        self.query_one(ScreenHeader).update_metrics(metrics)


class JobsApp(App):
    """Thin wrapper that pushes JobsScreen and exits when it is dismissed."""

    CSS = APP_CSS

    def __init__(self, conn: EnvironmentConnector, stats_list: list[JobStats], active_runs: list[JobRun], *,
                 env_name: str = "") -> None:
        super().__init__()
        self._conn = conn
        self._stats_list = stats_list
        self._active_runs = active_runs
        self._env_name = env_name

    def on_mount(self) -> None:
        setup_theme(self)
        self.push_screen(JobsScreen(
            self._conn, self._stats_list, self._active_runs,
            env_name=self._env_name,
        ))
