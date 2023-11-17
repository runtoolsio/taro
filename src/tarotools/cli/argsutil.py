from enum import Enum
from typing import List, Callable, Set

from tarotools.taro import JobRunId
from tarotools.taro.execution import Flag
from tarotools.taro.jobs.criteria import JobRunIdCriterion, compound_id_filter, IntervalCriterion, TerminationCriterion, \
    JobRunAggregatedCriteria
from tarotools.taro.jobs.instance import LifecycleEvent
from tarotools.taro.run import Outcome
from tarotools.taro.util import DateTimeFormat


def id_matching_criteria(args, def_id_match_strategy) -> List[JobRunIdCriterion]:
    """
    :param args: cli args
    :param def_id_match_strategy: id match strategy used when not overridden by args TODO
    :return: list of ID match criteria or empty when args has no criteria
    """
    if args.instances:
        return [JobRunIdCriterion.parse_pattern(i, def_id_match_strategy) for i in args.instances]
    else:
        return []


def id_match(args, def_id_match_strategy) -> Callable[[JobRunId], bool]:
    return compound_id_filter(id_matching_criteria(args, def_id_match_strategy))


def interval_criteria_converted_utc(args, interval_event=LifecycleEvent.CREATED):
    criteria = []

    from_ = getattr(args, 'from', None)
    to = getattr(args, 'to', None)
    if from_ or to:
        criteria.append(IntervalCriterion.to_utc(interval_event, from_, to))

    if getattr(args, 'today', None):
        criteria.append(IntervalCriterion.today(interval_event, to_utc=True))

    if getattr(args, 'yesterday', None):
        criteria.append(IntervalCriterion.yesterday(interval_event, to_utc=True))

    if getattr(args, 'week', None):
        criteria.append(IntervalCriterion.week_back(interval_event, to_utc=True))

    if getattr(args, 'fortnight', None):
        criteria.append(IntervalCriterion.days_interval(interval_event, -14, to_utc=True))

    if getattr(args, 'month', None):
        criteria.append(IntervalCriterion.days_interval(interval_event, -31, to_utc=True))

    return criteria


def instance_state_criteria(args):
    flag_groups: List[Set[Outcome]] = []
    if getattr(args, 'success', False):
        flag_groups.append({Flag.SUCCESS})
    if getattr(args, 'nonsuccess', False):
        flag_groups.append({Flag.NONSUCCESS})
    if getattr(args, 'aborted', False):
        flag_groups.append({Flag.ABORT})
    if getattr(args, 'incomplete', False):
        flag_groups.append({Flag.INCOMPLETE})
    if getattr(args, 'discarded', False):
        flag_groups.append({Flag.DISCARDED})
    if getattr(args, 'failed', False):
        flag_groups.append({Flag.FAULT})
    warning = getattr(args, 'warning', None)

    return TerminationCriterion(status_flag_groups=flag_groups, warning=warning)


def instance_matching_criteria(args, def_id_match_strategy, interval_event=LifecycleEvent.CREATED) -> \
        JobRunAggregatedCriteria:
    return JobRunAggregatedCriteria(
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
