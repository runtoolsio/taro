from typing import List, Tuple

from rich.text import Text

from runtools.runcore import util
from runtools.runcore.job import JobRun
from runtools.runcore.run import TerminationStatus, PhaseVisitor, PhaseRun, PhasePath
from runtools.runcore.util import format_dt_local_tz, format_dt_compact
from runtools.taro.printer import Column
from runtools.taro.style import general_style, job_id_style, run_id_style, run_term_style, warn_count_style, \
    stage_style
from runtools.taro.theme import Theme
from runtools.taro.view.status_render import render_status

JOB_ID = Column('JOB ID', 30, lambda j: j.job_id, job_id_style)
RUN_ID = Column('RUN ID', 14, lambda j: j.run_id, run_id_style)
STAGE = Column('STAGE', 10, lambda j: j.lifecycle.stage.name, stage_style)
INSTANCE_ID = Column('INSTANCE ID', 23, lambda j: j.metadata.instance_id, run_id_style)  # job_id@run_id varies
PARAMETERS = Column('PARAMETERS', 23,
                    lambda j: ', '.join("{}={}".format(k, v) for k, v in j.metadata.user_params.items()), general_style)
CREATED = Column('CREATED', 19, lambda j: format_dt_local_tz(j.lifecycle.created_at, include_ms=False), general_style)
CREATED_COMPACT = Column('CREATED', 12, lambda j: format_dt_compact(j.lifecycle.created_at), general_style)
EXECUTED = Column('EXECUTED', 25, lambda j: format_dt_local_tz(j.lifecycle.started_at, include_ms=False, null='N/A'),
                  general_style)
ENDED = Column('ENDED', 19,
               lambda j: format_dt_local_tz(j.lifecycle.termination.terminated_at, include_ms=False, null='N/A'),
               general_style)
ENDED_COMPACT = Column('ENDED', 12,
                       lambda j: format_dt_compact(j.lifecycle.termination.terminated_at, null='N/A'),
                       general_style)
EXEC_TIME = Column('TIME', 18,
                   lambda j: util.format_timedelta(j.lifecycle.total_run_time or j.lifecycle.elapsed, show_ms=False,
                                                   null='N/A'),
                   general_style)
PHASES = Column('PHASES', 30, lambda j: j.accept_visitor(PhaseExtractor()).text,
                lambda j: j.accept_visitor(PhaseExtractor()).style)
TERM_STATUS = Column('TERM', max(len(s.name) for s in TerminationStatus) + 2,
                     lambda j: j.lifecycle.termination.status.name if j.lifecycle.termination else '',
                     lambda j: run_term_style(j) if j.lifecycle.termination else general_style(j))
STATUS = Column('STATUS', 50, lambda j: str(j.status or ''), general_style, lambda j, w: render_status(j.status, w))
RESULT = Column('RESULT', 50, lambda j: str(j.status or ''), general_style)
WARNINGS = Column('WARN', 6, lambda j: str(len(j.status.warnings)) if j.status else '0', warn_count_style)

DEFAULT_COLUMNS = [JOB_ID, RUN_ID, INSTANCE_ID, CREATED, EXEC_TIME, PHASES, WARNINGS, STATUS]


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
