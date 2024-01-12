from enum import Enum
from typing import List, Set

from runtoolsio.taro.jobs.instance import LifecycleEvent

from runtoolsio.runcore.criteria import InstanceMetadataCriterion, LifecycleCriterion, TerminationCriterion, \
    EntityRunCriteria
from runtoolsio.runcore.run import Outcome
from runtoolsio.runcore.util import DateTimeFormat


def metadata_match(args, def_id_match_strategy) -> List[InstanceMetadataCriterion]:
    """
    :param args: cli args
    :param def_id_match_strategy: id match strategy used when not overridden by args TODO
    :return: list of ID match criteria or empty when args has no criteria
    """
    if args.instances:
        return [InstanceMetadataCriterion.parse_pattern(i, def_id_match_strategy) for i in args.instances]
    else:
        return []


def id_match(args, def_id_match_strategy) -> EntityRunCriteria:
    return EntityRunCriteria(metadata_criteria=metadata_match(args, def_id_match_strategy))


def interval_criteria_converted_utc(args, interval_event=LifecycleEvent.CREATED):
    criteria = []

    from_ = getattr(args, 'from', None)
    to = getattr(args, 'to', None)
    if from_ or to:
        criteria.append(LifecycleCriterion.to_utc(interval_event, from_, to))

    if getattr(args, 'today', None):
        criteria.append(LifecycleCriterion.today(interval_event, to_utc=True))

    if getattr(args, 'yesterday', None):
        criteria.append(LifecycleCriterion.yesterday(interval_event, to_utc=True))

    if getattr(args, 'week', None):
        criteria.append(LifecycleCriterion.week_back(interval_event, to_utc=True))

    if getattr(args, 'fortnight', None):
        criteria.append(LifecycleCriterion.days_interval(interval_event, -14, to_utc=True))

    if getattr(args, 'month', None):
        criteria.append(LifecycleCriterion.days_interval(interval_event, -31, to_utc=True))

    return criteria


def termination_criteria(args):
    outcomes: Set[Outcome] = set()
    if getattr(args, 'success', False):
        outcomes.add(Outcome.SUCCESS)
    if getattr(args, 'nonsuccess', False):
        outcomes.add(Outcome.NON_SUCCESS)
    if getattr(args, 'aborted', False):
        outcomes.add(Outcome.ABORTED)
    if getattr(args, 'rejected', False):
        outcomes.add(Outcome.REJECTED)
    if getattr(args, 'fault', False):
        outcomes.add(Outcome.FAULT)

    return TerminationCriterion(outcomes)


def run_matching_criteria(args, def_id_match_strategy, interval_event=LifecycleEvent.CREATED) -> \
        EntityRunCriteria:
    return EntityRunCriteria(
        metadata_criteria=metadata_match(args, def_id_match_strategy),
        interval_criteria=interval_criteria_converted_utc(args, interval_event),
        termination_criteria=termination_criteria(args))


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
