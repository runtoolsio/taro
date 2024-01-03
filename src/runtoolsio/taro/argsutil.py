from enum import Enum
from typing import List, Callable, Set

from runtoolsio.taro.jobs.criteria import IDMatchCriteria, compound_id_filter, IntervalCriteria, StateCriteria, \
    InstanceMatchCriteria
from runtoolsio.taro.jobs.execution import Flag, TerminationStatusFlag
from runtoolsio.taro.jobs.instance import LifecycleEvent
from runtoolsio.taro.util import DateTimeFormat

from runtoolsio.taro import JobInstanceID


def id_matching_criteria(args, def_id_match_strategy) -> List[IDMatchCriteria]:
    """
    :param args: cli args
    :param def_id_match_strategy: id match strategy used when not overridden by args TODO
    :return: list of ID match criteria or empty when args has no criteria
    """
    if args.instances:
        return [IDMatchCriteria.parse_pattern(i, def_id_match_strategy) for i in args.instances]
    else:
        return []


def id_match(args, def_id_match_strategy) -> Callable[[JobInstanceID], bool]:
    return compound_id_filter(id_matching_criteria(args, def_id_match_strategy))


def interval_criteria_converted_utc(args, interval_event=LifecycleEvent.CREATED):
    criteria = []

    from_ = getattr(args, 'from', None)
    to = getattr(args, 'to', None)
    if from_ or to:
        criteria.append(IntervalCriteria.to_utc(interval_event, from_, to))

    if getattr(args, 'today', None):
        criteria.append(IntervalCriteria.today(interval_event, to_utc=True))

    if getattr(args, 'yesterday', None):
        criteria.append(IntervalCriteria.yesterday(interval_event, to_utc=True))

    if getattr(args, 'week', None):
        criteria.append(IntervalCriteria.week_back(interval_event, to_utc=True))

    if getattr(args, 'fortnight', None):
        criteria.append(IntervalCriteria.days_interval(interval_event, -14, to_utc=True))

    if getattr(args, 'month', None):
        criteria.append(IntervalCriteria.days_interval(interval_event, -31, to_utc=True))

    return criteria


def instance_state_criteria(args):
    flag_groups: List[Set[TerminationStatusFlag]] = []
    if getattr(args, 'success', False):
        flag_groups.append({Flag.SUCCESS})
    if getattr(args, 'nonsuccess', False):
        flag_groups.append({Flag.NONSUCCESS})
    if getattr(args, 'aborted', False):
        flag_groups.append({Flag.ABORTED})
    if getattr(args, 'incomplete', False):
        flag_groups.append({Flag.INCOMPLETE})
    if getattr(args, 'discarded', False):
        flag_groups.append({Flag.DISCARDED})
    if getattr(args, 'failed', False):
        flag_groups.append({Flag.FAILURE})
    warning = getattr(args, 'warning', None)

    return StateCriteria(flag_groups=flag_groups, warning=warning)


def instance_matching_criteria(args, def_id_match_strategy, interval_event=LifecycleEvent.CREATED) -> \
        InstanceMatchCriteria:
    return InstanceMatchCriteria(
        id_matching_criteria(args, def_id_match_strategy),
        interval_criteria_converted_utc(args, interval_event),
        instance_state_criteria(args))


class TimestampFormat(Enum):
    DATE_TIME = DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE
    TIME = DateTimeFormat.TIME_MS_LOCAL_ZONE
    NONE = DateTimeFormat.NONE
    UNKNOWN = None

    def __repr__(self) -> str:
        return self.name.lower().replace("_", "-")

    @staticmethod
    def from_str(string: str) -> "TimestampFormat":
        if not string:
            return TimestampFormat.NONE

        string = string.upper().replace("-", "_")
        try:
            return TimestampFormat[string]
        except KeyError:
            return TimestampFormat.UNKNOWN