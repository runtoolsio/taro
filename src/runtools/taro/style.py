from typing import List, Tuple

from runtools.runcore.run import Outcome, RunState
from runtools.runcore.util import DateTimeFormat
from runtools.taro.theme import Theme


def job_id_style(job):
    if job.lifecycle.termination and job.lifecycle.termination.status.is_outcome(Outcome.FAULT):
        return Theme.job + " " + Theme.state_failure
    return Theme.job


def job_id_stats_style(job_stats):
    if job_stats.termination_status.is_outcome(Outcome.FAULT):
        return Theme.job + " " + Theme.state_failure
    return Theme.job


def instance_style(job):
    if job.lifecycle.termination and job.lifecycle.termination.status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return Theme.instance


def general_style(job):
    if job.lifecycle.termination and job.lifecycle.termination.status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return ""


def stats_style(stats):
    if stats.termination_status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return ""


def warn_style(_):
    return Theme.warning


def warn_count_style(j):
    """Style function for warning count - grey for 0, orange for >0"""
    count = len(j.status.warnings) if j.status else 0
    if count > 0:
        return Theme.warning
    return Theme.subtle


def stats_warn_count_style(s):
    """Style function for warning count - grey for 0, orange for >0"""
    if s.warning_count > 0:
        return Theme.warning
    return Theme.subtle


def job_state_style(job):
    return state_style(job.lifecycle.run_state)


def term_style(term_status) -> str:
    is_outcome = term_status.is_outcome
    if is_outcome(Outcome.FAULT):
        return Theme.state_failure
    if is_outcome(Outcome.ABORTED):
        return Theme.state_incomplete
    if is_outcome(Outcome.REJECTED):
        return Theme.state_discarded

    return ""


def run_term_style(job_run) -> str:
    return term_style(job_run.lifecycle.termination.status)


def stats_state_style(stats):
    return term_style(stats.termination_status)


def state_style(state):
    if state == RunState.ENDED:
        return ""
    if state == RunState.EXECUTING:
        return Theme.state_executing

    return Theme.state_before_execution


def stats_failed_style(stats):
    if stats.failed_count:
        return Theme.highlight + " " + Theme.state_failure
    return stats_style(stats)


def stats_warn_style(stats):
    if stats.warning_count:
        return Theme.warning
    return stats_style(stats)


def job_instance_styled(job_instance):
    return [
        (job_id_style(job_instance), job_instance.entity_id),
        (Theme.id_separator, "@"),
        (instance_style(job_instance), job_instance.instance_id)
    ]


def job_run_id(metadata) -> List[Tuple[str, str]]:
    return [
        (Theme.job, metadata.entity_id),
        (Theme.id_separator, "@"),
        (Theme.instance, metadata.run_id)
    ]


def run_status_line(job_run, *, ts_prefix_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE) -> List[Tuple[str, str]]:
    if job_run.termination:
        status = (run_term_style(job_run), job_run.termination.status.name)
    else:
        status = (state_style(job_run.lifecycle.run_state), job_run.lifecycle.run_state.name)
    styled_texts = job_run_id(job_run.metadata) + [("", " -> "), status]
    ts = job_run.lifecycle.last_transition_at
    ts_prefix_formatted = ts_prefix_format(ts) if ts else None
    if ts_prefix_formatted:
        return [("", ts_prefix_formatted + " ")] + styled_texts
    else:
        return styled_texts
