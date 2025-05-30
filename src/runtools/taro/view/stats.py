from runtools.runcore import util
from runtools.runcore.run import TerminationStatus
from runtools.runcore.util import format_dt_local_tz

from runtools.taro.printer import Column
from runtools.taro.style import stats_style, job_id_stats_style, stats_state_style, stats_failed_style, \
    stats_warn_count_style

JOB_ID = Column('JOB ID', 30, lambda s: s.job_id, job_id_stats_style)
RUNS = Column('RUNS', 10, lambda s: str(s.count), stats_style)
FIRST_CREATED = Column('FIRST RUN', 25, lambda s: format_dt_local_tz(s.first_created, include_ms=False), stats_style)
LAST_CREATED = Column('LAST RUN', 25, lambda s: format_dt_local_tz(s.last_created, include_ms=False), stats_style)
AVERAGE = Column('AVERAGE', 18, lambda s: util.format_timedelta(s.average_time, show_ms=False), stats_style)
SLOWEST = Column('SLOWEST', 18, lambda s: util.format_timedelta(s.slowest_time, show_ms=False), stats_style)
LAST_TIME = Column('LAST', 18, lambda s: util.format_timedelta(s.last_time, show_ms=False), stats_style)
STATE = Column('LAST STATUS', max(len(s.name) for s in TerminationStatus) + 2, lambda s: s.termination_status.name, stats_state_style)
FAULTS = Column('FAULTS', 10, lambda s: str(s.failed_count), stats_failed_style)
WARN = Column('WARNINGS', 10, lambda s: str(s.warning_count or '0'), stats_warn_count_style)

DEFAULT_COLUMNS = \
    [JOB_ID, RUNS, FIRST_CREATED, LAST_CREATED, AVERAGE, SLOWEST, LAST_TIME, STATE, FAULTS, WARN]
