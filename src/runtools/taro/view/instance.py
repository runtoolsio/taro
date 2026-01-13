from typing import List, Tuple

from runtools.runcore import util
from runtools.runcore.run import TerminationStatus, PhaseVisitor, PhaseDetail, PhasePath
from runtools.runcore.util import format_dt_local_tz
from runtools.taro.theme import Theme
from runtools.taro.printer import Column
from runtools.taro.style import general_style, job_id_style, instance_style, run_term_style, warn_count_style

JOB_ID = Column('JOB ID', 30, lambda j: j.job_id, job_id_style)
RUN_ID = Column('RUN ID', 30, lambda j: j.run_id, job_id_style)
INSTANCE_ID = Column('INSTANCE ID', 23, lambda j: j.metadata.instance_id, instance_style)
PARAMETERS = Column('PARAMETERS', 23,
                    lambda j: ', '.join("{}={}".format(k, v) for k, v in j.metadata.user_params.items()), general_style)
CREATED = Column('CREATED', 25, lambda j: format_dt_local_tz(j.lifecycle.created_at, include_ms=False), general_style)
EXECUTED = Column('EXECUTED', 25, lambda j: format_dt_local_tz(j.lifecycle.started_at, include_ms=False, null='N/A'),
                  general_style)
ENDED = Column('ENDED', 25,
               lambda j: format_dt_local_tz(j.lifecycle.termination.terminated_at, include_ms=False, null='N/A'),
               general_style)
EXEC_TIME = Column('TIME', 18,
                   lambda j: util.format_timedelta(j.lifecycle.total_run_time or j.lifecycle.elapsed, show_ms=False,
                                                   null='N/A'),
                   general_style)
PHASES = Column('PHASES', 30, lambda j: j.accept_visitor(PhaseExtractor()).text,
                lambda j: j.accept_visitor(PhaseExtractor()).style)
TERM_STATUS = Column('TERM STATUS', max(len(s.name) for s in TerminationStatus) + 2,
                     lambda j: j.lifecycle.termination.status.name, run_term_style)
STATUS = Column('STATUS', 50, lambda j: str(j.status or ''), general_style)
RESULT = Column('RESULT', 50, lambda j: str(j.status or ''), general_style)
WARNINGS = Column('WARN', 6, lambda j: str(len(j.status.warnings)) if j.status else '0', warn_count_style)

DEFAULT_COLUMNS = [JOB_ID, RUN_ID, INSTANCE_ID, CREATED, EXEC_TIME, PHASES, WARNINGS, STATUS]


class PhaseExtractor(PhaseVisitor):
    """
    Visitor that collects all root-to-leaf paths for CLI display.
    """

    def __init__(self):
        self.phase_and_style: List[Tuple[PhaseDetail, str]] = []

    def visit_phase(self, phase_detail: PhaseDetail, parent_path: PhasePath) -> None:
        if not phase_detail.lifecycle.is_running or phase_detail.any_child_running:
            return

        if phase_detail.is_idle:
            theme = Theme.idle
        else:
            theme = ""
            for ancestor in parent_path.iter_ancestors(reverse=True):
                if ancestor.phase_type in ("APPROVAL", "MUTEX"):
                    theme = Theme.success
                    break
                if ancestor.phase_type in ("QUEUE",):
                    theme = Theme.managed
                    break

        self.phase_and_style.append((phase_detail, theme))

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
