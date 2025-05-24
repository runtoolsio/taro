from runtools.runcore import util
from runtools.runcore.run import TerminationStatus, RunState
from runtools.runcore.util import format_dt_local_tz

from runtools.taro.printer import Column
from runtools.taro.style import general_style, job_id_style, instance_style, warn_style, job_state_style, \
    run_term_style

JOB_ID = Column('JOB ID', 30, lambda j: j.job_id, job_id_style)
RUN_ID = Column('RUN ID', 30, lambda j: j.run_id, job_id_style)
INSTANCE_ID = Column('INSTANCE ID', 23, lambda j: j.metadata.instance_id, instance_style)
PARAMETERS = Column('PARAMETERS', 23,
                    lambda j: ', '.join("{}={}".format(k, v) for k, v in j.metadata.user_params.items()), general_style)
CREATED = Column('CREATED', 25, lambda j: format_dt_local_tz(j.lifecycle.created_at, include_ms=False), general_style)
EXECUTED = Column('EXECUTED', 25, lambda j: format_dt_local_tz(j.lifecycle.started_at, include_ms=False, null='N/A'), general_style)
ENDED = Column('ENDED', 25, lambda j: format_dt_local_tz(j.lifecycle.termination.terminated_at, include_ms=False, null='N/A'), general_style)
EXEC_TIME = Column('TIME', 18, lambda j: util.format_timedelta(j.lifecycle.total_run_time, show_ms=False, null='N/A'),
                   general_style)
STATE = Column('RUN STATE', max(len(s.name) for s in RunState) + 2, lambda j: j.lifecycle.run_state.name, job_state_style)
TERM_STATUS = Column('TERM STATUS', max(len(s.name) for s in TerminationStatus) + 2, lambda j: j.lifecycle.termination.status.name, run_term_style)
STATUS = Column('STATUS', 50, lambda j: str(j.status) or '', general_style)
RESULT = Column('RESULT', 50, lambda j: str(j.status) or '', general_style)
WARNINGS = Column('WARN', 40, lambda j: ', '.join(dict.fromkeys((w.message for w in j.status.warnings) if j.status else []).keys()), warn_style)

DEFAULT_COLUMNS = [JOB_ID, RUN_ID, INSTANCE_ID, CREATED, EXEC_TIME, STATE, WARNINGS, STATUS]
