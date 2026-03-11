from typing import List, Tuple

from rich.text import Text

from runtools.runcore import util
from runtools.runcore.job import JobRun
from runtools.runcore.run import Outcome, TerminationStatus, PhaseVisitor, PhaseRun, PhasePath
from runtools.runcore.util import format_dt_local_tz, format_dt_compact
from runtools.taro.printer import Column
from runtools.taro.style import general_style, job_id_style, run_id_style, run_term_style, warn_count_style
from runtools.taro.theme import Theme
from runtools.taro.view.status_render import render_result, render_status

_CELL_PADDING = 2


def end_ellipsis(text: str, width: int) -> str:
    """Truncate with end ellipsis: ``stream-expiration-event`` → ``stream-expiration-ev…``."""
    if len(text) <= width:
        return text
    return text[:width - 1] + "…" if width >= 2 else text[:width]


def mid_ellipsis(text: str, width: int) -> str:
    """Truncate with middle ellipsis: ``2026-03-07T02-2`` → ``2026-…T02-2``."""
    if len(text) <= width:
        return text
    if width < 3:
        return text[:width]
    tail = (width - 1) // 2
    head = width - 1 - tail
    return text[:head] + "…" + text[-tail:]


JOB_ID = Column('JOB ID', 25, lambda j: end_ellipsis(j.job_id, 25), job_id_style)
RUN_ID = Column('RUN ID', 14, lambda j: mid_ellipsis(j.run_id, 14), run_id_style)
_muted_style = lambda _: Theme.subtle
CREATED = Column('CREATED', 21, lambda j: format_dt_local_tz(j.lifecycle.created_at, include_ms=False), _muted_style)
CREATED_COMPACT = Column('CREATED', 12, lambda j: format_dt_compact(j.lifecycle.created_at), _muted_style)
ENDED = Column('ENDED', 21,
               lambda j: format_dt_local_tz(j.lifecycle.termination.terminated_at, include_ms=False, null='N/A'),
               _muted_style)
ENDED_COMPACT = Column('ENDED', 12,
                       lambda j: format_dt_compact(j.lifecycle.termination.terminated_at, null='N/A'),
                       _muted_style)
def _format_elapsed_compact(td) -> str:
    """Format as H:MM:SS — collapses days into hours."""
    if not td:
        return 'N/A'
    total_secs = int(td.total_seconds())
    hours, remainder = divmod(total_secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def _format_elapsed_days(td) -> str:
    """Format as HH:MM:SS or Nd HH:MM:SS for multi-day durations."""
    if not td:
        return 'N/A'
    total_secs = int(td.total_seconds())
    hours, remainder = divmod(total_secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


EXEC_TIME = Column('TIME', 14,
                   lambda j: _format_elapsed_days(j.lifecycle.total_run_time or j.lifecycle.elapsed),
                   general_style)
EXEC_TIME_COMPACT = Column('TIME', 11,
                           lambda j: _format_elapsed_compact(j.lifecycle.total_run_time or j.lifecycle.elapsed),
                           general_style)
PHASES = Column('PHASES', 25, lambda j: j.accept_visitor(PhaseExtractor()).text,
                lambda j: j.accept_visitor(PhaseExtractor()).style)
def _term_display(j: JobRun) -> str:
    if not j.lifecycle.termination:
        return ''
    status = j.lifecycle.termination.status
    if status == TerminationStatus.COMPLETED:
        return '✓'
    return status.name


_term_style = lambda j: run_term_style(j) if j.lifecycle.termination else general_style(j)
TERM_STATUS = Column('TERM', max(len(s.name) for s in TerminationStatus) + 2,
                     _term_display, _term_style)
TERM_STATUS_FULL = Column('TERM', max(len(s.name) for s in TerminationStatus) + 2,
                          lambda j: j.lifecycle.termination.status.name if j.lifecycle.termination else '',
                          _term_style)
STATUS = Column('STATUS', 50, lambda j: str(j.status or ''), general_style,
                lambda j, w: render_status(j.status, w, j.lifecycle.is_ended))
RESULT = Column('RESULT', 50,
                lambda j: j.status.result.message if j.status and j.status.result
                else j.status.finished_ops_summary if j.status else '',
                general_style, lambda j, w: render_result(j.status, w))
WARNINGS = Column('WARN', 6, lambda j: str(len(j.status.warnings)) if j.status else '0', warn_count_style)


def render_cell(run: JobRun, col: Column, *, width: int | None = None, style_override: str = "") -> Text:
    """Render a single column cell for a job run.

    Args:
        run: Job run snapshot.
        col: Column definition.
        width: Optional render width hint for columns with rich_fnc.
            If omitted, ``col.max_width`` is used.
        style_override: If set, used instead of col.colour_fnc (e.g. "dim" for ended runs).
    """
    if col.rich_fnc:
        rich_width = width if width is not None else col.max_width
        value = col.rich_fnc(run, rich_width)
    else:
        value = col.value_fnc(run)
    style = style_override or col.colour_fnc(run)
    if isinstance(value, Text):
        if style:
            value = value.copy()
            value.stylize(style)
        return value
    return Text(str(value), style=style)


class PhaseExtractor(PhaseVisitor):
    """
    Visitor that collects all root-to-leaf paths for CLI display.
    """

    def __init__(self):
        self.phase_and_style: List[Tuple[PhaseRun, str]] = []

    def visit_phase(self, phase_run: PhaseRun, parent_path: PhasePath) -> None:
        if not phase_run.lifecycle.is_running or phase_run.any_child_running:
            return

        if phase_run.stop_requested:
            theme = Theme.state_incomplete
        elif phase_run.is_idle:
            theme = Theme.idle
        else:
            theme = Theme.state_executing
            for ancestor in parent_path.iter_ancestors(reverse=True):
                if ancestor.phase_type in ("APPROVAL", "MUTEX", "CHECKPOINT"):
                    theme = Theme.success
                    break
                if ancestor.phase_type in ("QUEUE",):
                    theme = Theme.managed
                    break

        self.phase_and_style.append((phase_run, theme))

    @property
    def text(self) -> str:
        if not self.phase_and_style:
            return ""
        if len(self.phase_and_style) > 1:
            return "<multiple>"

        return self.phase_and_style[0][0].phase_id

    @property
    def style(self):
        if not self.phase_and_style or len(self.phase_and_style) > 1:
            return ""
        return self.phase_and_style[0][1]
