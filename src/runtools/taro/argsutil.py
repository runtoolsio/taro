from enum import Enum
from typing import List

from runtools.runcore.criteria import MetadataCriterion, LifecycleCriterion, TerminationCriterion, \
    JobRunCriteria
from runtools.runcore.run import Outcome
from runtools.runcore.util import DateTimeFormat


def instance_criteria(args, id_match_strategy) -> List[MetadataCriterion]:
    """
    :param args: cli args
    :param id_match_strategy: id match strategy used when not overridden by args TODO
    :return: list of ID match criteria or empty when args has no criteria
    """
    if args.instances:
        return [MetadataCriterion.parse_pattern(i, id_match_strategy) for i in args.instances]
    else:
        return []


def lifecycle_criteria(args):
    criteria = []

    from_ = getattr(args, 'from', None)
    to = getattr(args, 'to', None)
    if from_ or to:
        criteria.append(LifecycleCriterion.to_utc(from_, to))

    if getattr(args, 'today', None):
        criteria.append(LifecycleCriterion.today(to_utc=True))

    if getattr(args, 'yesterday', None):
        criteria.append(LifecycleCriterion.yesterday(to_utc=True))

    if getattr(args, 'week', None):
        criteria.append(LifecycleCriterion.week_back(to_utc=True))

    if getattr(args, 'fortnight', None):
        criteria.append(LifecycleCriterion.days_interval(-14, to_utc=True))

    if getattr(args, 'month', None):
        criteria.append(LifecycleCriterion.days_interval(-31, to_utc=True))

    return criteria


def termination_criteria(args):
    criteria = []
    if getattr(args, 'success', False):
        criteria.append(TerminationCriterion(Outcome.SUCCESS))
    if getattr(args, 'nonsuccess', False):
        criteria.append(TerminationCriterion(Outcome.NON_SUCCESS))
    if getattr(args, 'aborted', False):
        criteria.append(TerminationCriterion(Outcome.ABORTED))
    if getattr(args, 'rejected', False):
        criteria.append(TerminationCriterion(Outcome.REJECTED))
    if getattr(args, 'fault', False):
        criteria.append(TerminationCriterion(Outcome.FAULT))

    return criteria


def run_criteria(args, id_match_strategy) -> JobRunCriteria:
    return JobRunCriteria(
        metadata_criteria=instance_criteria(args, id_match_strategy),
        interval_criteria=lifecycle_criteria(args),
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
