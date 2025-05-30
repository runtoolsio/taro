from enum import Enum
from typing import List, Optional

from runtools.runcore.criteria import MetadataCriterion, LifecycleCriterion, TerminationCriterion, \
    JobRunCriteria, TemporalField
from runtools.runcore.run import Outcome
from runtools.runcore.util import DateTimeFormat, DateTimeRange


def apply_date_filters(run_match, filter_by: TemporalField, from_date: Optional[str], to_date: Optional[str],
                       today: bool, yesterday: bool, week: bool, fortnight: bool, three_weeks: bool,
                       four_weeks: bool, month: bool, days_back: Optional[int]):
    """
    Apply date filtering options to run_match using OR logic on specified timestamp field.

    Args:
        run_match: JobRunCriteria object to modify
        filter_by: Which timestamp field to filter on
        from_date: Start date string
        to_date: End date string
        today: Filter for today
        yesterday: Filter for yesterday
        week: Filter for last week
        fortnight: Filter for last 2 weeks
        three_weeks: Filter for last 3 weeks
        four_weeks: Filter for last 4 weeks
        month: Filter for last month
        days_back: Filter for N days back
    """
    date_ranges = []

    if from_date or to_date:
        date_ranges.append(DateTimeRange.parse_to_utc(from_date, to_date))
    if today:
        date_ranges.append(DateTimeRange.today(to_utc=True))
    if yesterday:
        date_ranges.append(DateTimeRange.yesterday(to_utc=True))
    if week:
        date_ranges.append(DateTimeRange.week_back(to_utc=True))
    if fortnight:
        date_ranges.append(DateTimeRange.days_range(-14, to_utc=True))
    if three_weeks:
        date_ranges.append(DateTimeRange.days_range(-21, to_utc=True))
    if four_weeks:
        date_ranges.append(DateTimeRange.days_range(-28, to_utc=True))
    if month:
        date_ranges.append(DateTimeRange.days_range(-31, to_utc=True))
    if days_back is not None:
        date_ranges.append(DateTimeRange.days_range(-days_back, to_utc=True))

    for date_range in date_ranges:
        run_match += LifecycleCriterion().set_date_range(date_range, filter_by)


def instance_criteria(args, id_match_strategy) -> List[MetadataCriterion]:
    """
    :param args: cli args
    :param id_match_strategy: id match strategy used when not overridden by args TODO
    :return: list of ID match criteria or empty when args has no criteria
    """
    if args.instances:
        return [MetadataCriterion.parse(i, id_match_strategy) for i in args.instances]
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
