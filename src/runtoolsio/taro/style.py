from typing import List, Tuple

from runtoolsio.runcore.run import Outcome, RunState
from runtoolsio.runcore.util import DateTimeFormat
from runtoolsio.taro.theme import Theme


def job_id_style(job):
    if job.run.termination and job.run.termination.status.is_outcome(Outcome.FAULT):
        return Theme.job + " " + Theme.state_failure
    return Theme.job


def job_id_stats_style(job_stats):
    if job_stats.termination_status.is_outcome(Outcome.FAULT):
        return Theme.job + " " + Theme.state_failure
    return Theme.job


def instance_style(job):
    if job.run.termination and job.run.termination.status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return Theme.instance


def general_style(job):
    if job.run.termination and job.run.termination.status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return ""


def stats_style(stats):
    if stats.termination_status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return ""


def warn_style(_):
    return Theme.warning


def job_state_style(job):
    return state_style(job.run.lifecycle.run_state)


def term_style(term_status) -> str:
    is_outcome = term_status.is_outcome
    if is_outcome(Outcome.FAULT):
        return Theme.state_failure
    if is_outcome(Outcome.ABORTED):
        return Theme.state_incomplete
    if is_outcome(Outcome.REJECTED):
        return Theme.state_discarded

    return ""


def run_term_style(entity_run) -> str:
    return term_style(entity_run.run.termination.status)


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


def entity_run_id(metadata) -> List[Tuple[str, str]]:
    return [
        (Theme.job, metadata.entity_id),
        (Theme.id_separator, "@"),
        (Theme.instance, metadata.run_id)
    ]


def run_status_line(entity_run, *, ts_prefix_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE) -> List[Tuple[str, str]]:
    if entity_run.run.termination:
        status = (run_term_style(entity_run), entity_run.run.termination.status.name)
    else:
        status = (state_style(entity_run.run.lifecycle.run_state), entity_run.run.lifecycle.run_state.name)
    styled_texts = entity_run_id(entity_run.metadata) + [("", " -> "), status]
    ts = entity_run.run.lifecycle.last_transition_at
    ts_prefix_formatted = ts_prefix_format(ts) if ts else None
    if ts_prefix_formatted:
        return [("", ts_prefix_formatted + " ")] + styled_texts
    else:
        return styled_texts
