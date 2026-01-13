from typing import Optional

from runtools.runcore.criteria import LifecycleCriterion
from runtools.runcore.run import Stage
from runtools.runcore.util import DateTimeRange


def apply_date_filters(run_match, for_stage: Stage, from_date: Optional[str], to_date: Optional[str],
                       today: bool, yesterday: bool, week: bool, fortnight: bool, three_weeks: bool,
                       four_weeks: bool, month: bool, days_back: Optional[int]):
    """
    Apply date filtering options to run_match using OR logic on specified timestamp field.

    Args:
        run_match: JobRunCriteria object to modify
        for_stage: Which timestamp field to filter on
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
        run_match += LifecycleCriterion().set_date_range(date_range, for_stage)
